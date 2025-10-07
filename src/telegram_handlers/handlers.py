import os
import json
import tempfile
from datetime import datetime, date, timedelta
from telegram import Update
from telegram.ext import ContextTypes

from src.database.models import DatabaseManager
from src.ai.gemini_processor import GeminiProcessor
from src.voice.whisper_processor import VoiceProcessor
from src.categories.manager import CategoryManager
from src.reminders.scheduler import ReminderScheduler
from src.config.manager import ConfigManager
from src.telegram_ui.keyboards import KeyboardBuilder


class TaskBotHandlers:
    def __init__(self, db: DatabaseManager, reminder_scheduler: ReminderScheduler = None):
        self.db = db
        self.gemini = GeminiProcessor()
        self.voice_processor = VoiceProcessor()  # Заглушка для совместимости
        self.category_manager = CategoryManager(db)
        self.reminder_scheduler = reminder_scheduler
        self.config = ConfigManager()
        self.keyboards = KeyboardBuilder()

    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработка текстовых сообщений"""
        user_id = update.effective_user.id
        message_text = update.message.text

        await self.process_task_from_text(update, context, message_text, user_id, is_voice=False)

    async def process_task_from_text(self, update: Update, context: ContextTypes.DEFAULT_TYPE,
                                   text: str, user_id: int, is_voice: bool = False):
        """Общая функция обработки задачи из текста"""

        await update.message.chat.send_action(action="typing")

        # Обработка через Gemini
        structured = self.gemini.process_task_text(text)

        # Обработка категории
        if structured.get('category'):
            structured['category'] = self.category_manager.get_or_create_category(
                user_id, structured['category']
            )

        # Сохранение
        task_id = self.db.save_task(user_id, text, structured)

        # Планирование напоминаний
        await self._schedule_reminders(task_id, user_id, structured)

        # Формирование ответа
        await self._send_task_confirmation(update, task_id, structured, is_voice)

    async def handle_voice_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработка голосовых сообщений через Gemini Audio API"""
        if not self.gemini.is_voice_processing_available():
            status = self.gemini.get_voice_status_message()
            await update.message.reply_text(
                f"🎤 Обработка голосовых сообщений недоступна.\n"
                f"Статус: {status}"
            )
            return

        user_id = update.effective_user.id

        processing_msg = await update.message.reply_text("🎤 Обрабатываю голосовое сообщение...")

        try:
            # Скачиваем голосовое сообщение
            voice_file = await context.bot.get_file(update.message.voice.file_id)

            # Создаем временный файл
            with tempfile.NamedTemporaryFile(suffix=".ogg", delete=False) as tmp_ogg:
                await voice_file.download_to_drive(tmp_ogg.name)
                ogg_path = tmp_ogg.name

            try:
                # Транскрибируем через Gemini
                transcribed_text = await self.gemini.process_voice_message(ogg_path)

                if not transcribed_text:
                    await processing_msg.edit_text("😔 Не удалось распознать речь. Попробуйте отправить текстом.")
                    return

                # Удаляем сообщение о обработке
                await processing_msg.delete()

                # Показываем распознанный текст
                await update.message.reply_text(f"📝 Распознано: _{transcribed_text}_", parse_mode='Markdown')

                # Обрабатываем как обычную задачу
                await self.process_task_from_text(update, context, transcribed_text, user_id, is_voice=True)

            finally:
                # Удаляем временный файл
                if os.path.exists(ogg_path):
                    os.unlink(ogg_path)

        except Exception as e:
            print(f"Error processing voice: {e}")
            try:
                await processing_msg.edit_text(
                    "❌ Ошибка обработки голоса. Попробуйте отправить текстом."
                )
            except:
                await update.message.reply_text(
                    "❌ Ошибка обработки голоса. Попробуйте отправить текстом."
                )

    async def show_today(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Показать задачи на сегодня"""
        user_id = update.effective_user.id
        today = date.today().strftime('%Y-%m-%d')

        tasks = self.db.get_tasks_by_date(user_id, today)

        if not tasks:
            await update.message.reply_text("📭 На сегодня задач нет")
            return

        message = f"📋 *Задачи на сегодня ({datetime.now().strftime('%d.%m.%Y')}):*\n"
        message += self.category_manager.format_tasks_by_category(tasks)

        # Добавляем inline кнопки для задач
        keyboard = self.keyboards.get_task_list_keyboard(tasks[:10])
        await update.message.reply_text(message, parse_mode='Markdown', reply_markup=keyboard)

    async def show_all(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Показать все активные задачи"""
        user_id = update.effective_user.id
        tasks = self.db.get_all_active_tasks(user_id)

        if not tasks:
            await update.message.reply_text("📭 Нет активных задач")
            return

        message = "📋 *Все активные задачи:*\n"
        message += self.category_manager.format_tasks_by_category(tasks)

        # Добавляем inline кнопки
        keyboard = self.keyboards.get_task_list_keyboard(tasks[:10])
        await update.message.reply_text(message, parse_mode='Markdown', reply_markup=keyboard)

    async def show_week(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Показать задачи на неделю"""
        user_id = update.effective_user.id
        today = date.today()
        week_end = today + timedelta(days=7)

        # Нужно добавить метод в DatabaseManager для получения задач по диапазону дат
        # tasks = self.db.get_tasks_by_date_range(user_id, today.strftime('%Y-%m-%d'), week_end.strftime('%Y-%m-%d'))

        await update.message.reply_text("📅 Функция просмотра задач на неделю в разработке")

    async def show_categories(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Показать категории пользователя"""
        user_id = update.effective_user.id
        categories_text = self.category_manager.get_categories_list(user_id)
        await update.message.reply_text(categories_text, parse_mode='Markdown')

    async def show_category_tasks(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Показать задачи по категории"""
        if not context.args:
            await update.message.reply_text(
                "Укажите категорию: /category работа\n"
                "Доступные категории: /categories"
            )
            return

        user_id = update.effective_user.id
        category_name = " ".join(context.args).lower()

        tasks = self.db.get_tasks_by_category(user_id, category_name)

        if not tasks:
            await update.message.reply_text(f"📭 В категории '{category_name}' нет задач")
            return

        category_display = self.category_manager.get_category_display_name(user_id, category_name)
        message = f"📋 *Задачи в категории {category_display}:*\n\n"

        for task_id, title, priority, conditions, due_date, category, tags in tasks:
            priority_emoji = {'high': '🔴', 'medium': '🟡', 'low': '🟢'}.get(priority, '🟡')
            date_text = ""
            if due_date:
                date_obj = datetime.strptime(due_date, '%Y-%m-%d')
                date_text = f" ({date_obj.strftime('%d.%m')})"

            message += f"{priority_emoji} #{task_id} {title}{date_text}\n"

        await update.message.reply_text(message, parse_mode='Markdown')

    async def mark_done(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Отметить задачу выполненной"""
        if not context.args:
            await update.message.reply_text("Укажите ID задачи: /done 123")
            return

        try:
            task_id = int(context.args[0])
            user_id = update.effective_user.id

            if self.db.mark_task_done(task_id, user_id):
                await update.message.reply_text(f"✅ Задача #{task_id} выполнена!")
            else:
                await update.message.reply_text(f"Задача #{task_id} не найдена")

        except ValueError:
            await update.message.reply_text("Неверный формат. Используйте: /done 123")

    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда /start"""
        voice_status = self.gemini.get_voice_status_message()
        user_id = update.effective_user.id
        admin_id = os.getenv('ADMIN_TELEGRAM_ID')

        keyboard = self.keyboards.get_main_menu_keyboard()

        help_text = (
            "👋 Привет! Я помогу организовать твои задачи.\n\n"
            "📝 Просто отправь мне задачу текстом или голосовым сообщением.\n\n"
            "🎤 Голосовые сообщения: " + voice_status + "\n\n"
            "Команды:\n"
            "/today - задачи на сегодня\n"
            "/week - задачи на неделю\n"
            "/all - все активные задачи\n"
            "/categories - мои категории\n"
            "/category [название] - задачи по категории\n"
            "/done [id] - отметить выполненной\n"
            "/settings - настройки\n"
            "/myid - мой ID"
        )

        # Добавляем команду reset_db только для админа
        if admin_id and str(user_id) == admin_id:
            help_text += "\n/reset_db - удаление базы данных (только админ)"

        await update.message.reply_text(help_text, reply_markup=keyboard)

    async def get_my_id(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Показать ID пользователя"""
        user_id = update.effective_user.id
        await update.message.reply_text(f"Ваш Telegram ID: `{user_id}`", parse_mode='Markdown')

    async def reset_database(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Сброс базы данных (только для админа)"""
        user_id = update.effective_user.id
        admin_id = os.getenv('ADMIN_TELEGRAM_ID')

        if not admin_id:
            await update.message.reply_text("❌ Админ не настроен")
            return

        if str(user_id) != admin_id:
            await update.message.reply_text("❌ У вас нет прав для этой команды")
            return

        if not context.args or context.args[0] != 'confirm':
            await update.message.reply_text(
                "⚠️ Это удалит ВСЕ задачи!\n"
                "Для подтверждения используйте:\n"
                "`/reset_db confirm`",
                parse_mode='Markdown'
            )
            return

        try:
            self.db.reset_database()
            await update.message.reply_text("✅ База данных успешно сброшена!")
        except Exception as e:
            await update.message.reply_text(f"❌ Ошибка: {e}")

    async def _schedule_reminders(self, task_id: int, user_id: int, structured: dict):
        """Планирование напоминаний для задачи на основе конфигурации"""
        if not self.reminder_scheduler:
            return

        # Если указано конкретное время напоминания
        if structured.get('reminder_needed') and structured.get('reminder_time'):
            try:
                reminder_time_str = structured['reminder_time']
                hour, minute = map(int, reminder_time_str.split(':'))

                # Планируем на сегодня или завтра
                reminder_date = date.today()
                from datetime import time as dt_time
                if datetime.now().time() > dt_time(hour, minute):
                    reminder_date = reminder_date + timedelta(days=1)

                reminder_datetime = datetime.combine(reminder_date, dt_time(hour, minute))

                self.reminder_scheduler.schedule_task_reminder(task_id, user_id, reminder_datetime)

            except Exception as e:
                print(f"Ошибка планирования напоминания: {e}")

        # Напоминания о дедлайне (из конфигурации)
        if structured.get('due_date'):
            try:
                due_date = datetime.strptime(structured['due_date'], '%Y-%m-%d')
                from datetime import time as dt_time

                # Если есть точное время события - используем его
                if structured.get('has_specific_time') and structured.get('due_time'):
                    try:
                        # Создаем полный datetime события
                        event_hour, event_minute = map(int, structured['due_time'].split(':'))
                        event_datetime = datetime.combine(due_date.date(), dt_time(event_hour, event_minute))

                        # Проверяем, включены ли напоминания по времени
                        if self.config.is_time_based_reminders_enabled():
                            # Напоминания за N часов
                            hours_before = self.config.get_time_based_hours_before()
                            for hours in hours_before:
                                reminder_datetime = event_datetime - timedelta(hours=hours)
                                if reminder_datetime > datetime.now():
                                    self.reminder_scheduler.schedule_task_reminder(
                                        task_id, user_id, reminder_datetime, 'time_based'
                                    )
                                    print(f"Запланировано напоминание на {reminder_datetime} (за {hours} ч. до {structured['due_time']})")

                            # Напоминания за N минут (если настроены)
                            minutes_before = self.config.get_time_based_minutes_before()
                            for minutes in minutes_before:
                                reminder_datetime = event_datetime - timedelta(minutes=minutes)
                                if reminder_datetime > datetime.now():
                                    self.reminder_scheduler.schedule_task_reminder(
                                        task_id, user_id, reminder_datetime, 'time_based'
                                    )
                                    print(f"Запланировано напоминание на {reminder_datetime} (за {minutes} мин. до {structured['due_time']})")

                    except Exception as e:
                        print(f"Ошибка планирования напоминаний по времени: {e}")

                # Стандартные напоминания о дедлайне (по дням)
                deadline_reminders = self.config.get_deadline_reminders()

                for reminder_config in deadline_reminders:
                    days_before = reminder_config.get('days_before', 0)
                    time_str = reminder_config.get('time', '09:00')

                    # Парсим время
                    try:
                        hour, minute = map(int, time_str.split(':'))
                        reminder_time = dt_time(hour, minute)
                    except:
                        print(f"Неверный формат времени в конфиге: {time_str}")
                        continue

                    # Вычисляем дату напоминания
                    reminder_date = due_date.date() - timedelta(days=days_before)
                    reminder_datetime = datetime.combine(reminder_date, reminder_time)

                    # Создаем напоминание только если оно в будущем
                    if reminder_datetime > datetime.now():
                        self.reminder_scheduler.schedule_task_reminder(
                            task_id, user_id, reminder_datetime, 'deadline'
                        )
                        print(f"Запланировано напоминание на {reminder_datetime} (за {days_before} дней)")

            except Exception as e:
                print(f"Ошибка планирования напоминания о дедлайне: {e}")

    async def _send_task_confirmation(self, update: Update, task_id: int, structured: dict, is_voice: bool = False):
        """Отправка подтверждения создания задачи"""
        # Условия
        conditions_text = ""
        if structured.get('conditions'):
            conditions_text = "\n📌 Условия: " + ", ".join(structured['conditions'])

        # Дата
        date_text = ""
        if structured.get('due_date'):
            date_obj = datetime.strptime(structured['due_date'], '%Y-%m-%d')
            date_text = f"\n📅 Дата: {date_obj.strftime('%d.%m.%Y')}"

        # Категория
        category_text = ""
        if structured.get('category'):
            category_display = self.category_manager.get_category_display_name(
                update.effective_user.id, structured['category']
            )
            category_text = f"\n📂 Категория: {category_display}"

        # Теги
        tags_text = ""
        if structured.get('tags'):
            tags_text = f"\n🏷️ Теги: {', '.join(structured['tags'])}"

        # Приоритет
        priority_emoji = {
            'high': '🔴',
            'medium': '🟡',
            'low': '🟢'
        }.get(structured.get('priority', 'medium'), '🟡')

        # Иконка голосового сообщения
        voice_emoji = "🎤 " if is_voice else ""

        # Добавляем кнопки действий
        keyboard = self.keyboards.get_task_actions_keyboard(task_id)

        await update.message.reply_text(
            f"✅ {voice_emoji}Задача #{task_id} сохранена!\n\n"
            f"📝 *{structured['title']}*\n"
            f"{priority_emoji} Приоритет: {structured.get('priority', 'medium')}"
            f"{date_text}"
            f"{category_text}"
            f"{tags_text}"
            f"{conditions_text}",
            parse_mode='Markdown',
            reply_markup=keyboard
        )

    async def handle_reply_button(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработка нажатий на Reply кнопки"""
        text = update.message.text

        if text == '📋 Сегодня':
            await self.show_today(update, context)
        elif text == '📅 Неделя':
            await self.show_week(update, context)
        elif text == '✅ Все задачи':
            await self.show_all(update, context)
        elif text == '📂 Категории':
            await self.show_categories(update, context)
        elif text == '⚙️ Настройки':
            await self.show_settings(update, context)
        elif text == '❓ Помощь':
            await self.start(update, context)
        else:
            # Это обычное сообщение - создаем задачу
            await self.handle_message(update, context)

    async def show_settings(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Показать настройки"""
        keyboard = self.keyboards.get_settings_keyboard()
        await update.message.reply_text(
            "⚙️ *Настройки*\n\n"
            "Выберите раздел:",
            parse_mode='Markdown',
            reply_markup=keyboard
        )