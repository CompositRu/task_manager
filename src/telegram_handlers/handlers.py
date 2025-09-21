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


class TaskBotHandlers:
    def __init__(self, db: DatabaseManager):
        self.db = db
        self.gemini = GeminiProcessor()
        self.voice_processor = VoiceProcessor()  # Заглушка для совместимости
        self.category_manager = CategoryManager(db)

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
            await update.message.reply_text(
                "🎤 Обработка голосовых сообщений недоступна.\n"
                "Необходимо настроить GEMINI_API_KEY."
            )
            return

        user_id = update.effective_user.id

        await update.message.reply_text("🎤 Обрабатываю голосовое сообщение...")

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
                    await update.message.reply_text("😔 Не удалось распознать речь. Попробуйте отправить текстом.")
                    return

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

        await update.message.reply_text(message, parse_mode='Markdown')

    async def show_all(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Показать все активные задачи"""
        user_id = update.effective_user.id
        tasks = self.db.get_all_active_tasks(user_id)

        if not tasks:
            await update.message.reply_text("📭 Нет активных задач")
            return

        message = "📋 *Все активные задачи:*\n"
        message += self.category_manager.format_tasks_by_category(tasks)

        await update.message.reply_text(message, parse_mode='Markdown')

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
        voice_status = "✅ Доступна (Gemini Audio)" if self.gemini.is_voice_processing_available() else "❌ Недоступна"

        await update.message.reply_text(
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
            "/myid - мой ID\n"
            "/reset_db - удаление базы данных (только админ)"
        )

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
        """Планирование напоминаний для задачи"""
        # Если указано конкретное время напоминания
        if structured.get('reminder_needed') and structured.get('reminder_time'):
            try:
                reminder_time_str = structured['reminder_time']
                hour, minute = map(int, reminder_time_str.split(':'))

                # Планируем на сегодня или завтра
                reminder_date = date.today()
                if datetime.now().time() > datetime.time(hour, minute):
                    reminder_date = reminder_date + timedelta(days=1)

                reminder_datetime = datetime.combine(reminder_date, datetime.time(hour, minute))

                # Здесь нужно будет добавить планировщик
                # self.reminder_scheduler.schedule_task_reminder(task_id, user_id, reminder_datetime)

            except Exception as e:
                print(f"Ошибка планирования напоминания: {e}")

        # Напоминание о дедлайне
        if structured.get('due_date'):
            try:
                due_date = datetime.strptime(structured['due_date'], '%Y-%m-%d')
                # self.reminder_scheduler.schedule_deadline_reminder(task_id, user_id, due_date)
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

        await update.message.reply_text(
            f"✅ {voice_emoji}Задача #{task_id} сохранена!\n\n"
            f"📝 *{structured['title']}*\n"
            f"{priority_emoji} Приоритет: {structured.get('priority', 'medium')}"
            f"{date_text}"
            f"{category_text}"
            f"{tags_text}"
            f"{conditions_text}",
            parse_mode='Markdown'
        )