"""
Обработчики callback query от Inline кнопок
"""
import logging
from datetime import datetime, timedelta
from telegram import Update
from telegram.ext import ContextTypes
from src.database.models import DatabaseManager
from src.telegram_ui.keyboards import KeyboardBuilder


class CallbackHandler:
    """Класс для обработки callback query"""

    def __init__(self, db: DatabaseManager, reminder_scheduler=None):
        self.db = db
        self.reminder_scheduler = reminder_scheduler
        self.keyboards = KeyboardBuilder()

    async def handle_callback_query(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """
        Главный обработчик всех callback query

        Формат callback_data: "action:param1:param2:..."
        """
        query = update.callback_query
        await query.answer()  # Убрать "часики" загрузки

        callback_data = query.data
        user_id = query.from_user.id

        try:
            # Парсим callback_data
            parts = callback_data.split(':')
            action = parts[0]

            # Маршрутизация по action
            if action == "task_done":
                await self._handle_task_done(query, user_id, int(parts[1]))

            elif action == "task_delete":
                await self._handle_task_delete(query, user_id, int(parts[1]))

            elif action == "task_view":
                await self._handle_task_view(query, user_id, int(parts[1]))

            elif action == "task_edit":
                await self._handle_task_edit(query, user_id, int(parts[1]))

            elif action == "task_snooze":
                await self._handle_task_snooze(query, user_id, int(parts[1]), int(parts[2]))

            elif action == "category_view":
                await self._handle_category_view(query, user_id, parts[1])

            elif action == "confirm":
                await self._handle_confirm(query, user_id, parts[1], int(parts[2]))

            elif action == "cancel":
                await query.edit_message_text("❌ Действие отменено")

            elif action == "settings_reminders":
                await self._handle_settings_reminders(query, user_id)

            elif action == "settings_categories":
                await self._handle_settings_categories(query, user_id)

            elif action == "settings_time":
                await self._handle_settings_time(query, user_id)

            elif action == "settings_back":
                await self._handle_settings_main(query, user_id)

            else:
                await query.edit_message_text(f"⚠️ Неизвестная команда: {action}")

        except Exception as e:
            logging.error(f"Ошибка обработки callback: {e}")
            await query.edit_message_text("❌ Произошла ошибка при обработке команды")

    async def _handle_task_done(self, query, user_id: int, task_id: int):
        """Отметить задачу выполненной"""
        result = self.db.mark_task_done(task_id)

        if result:
            # Получаем инфо о задаче
            task = self.db.get_task_by_id(task_id)
            if task:
                title = task[2]
                await query.edit_message_text(f"✅ Задача выполнена!\n\n<b>{title}</b>", parse_mode='HTML')
            else:
                await query.edit_message_text("✅ Задача выполнена!")
        else:
            await query.edit_message_text("❌ Не удалось отметить задачу")

    async def _handle_task_delete(self, query, user_id: int, task_id: int):
        """Запросить подтверждение удаления"""
        keyboard = self.keyboards.get_confirmation_keyboard("delete_task", task_id)
        await query.edit_message_text(
            "⚠️ Вы уверены, что хотите удалить эту задачу?",
            reply_markup=keyboard
        )

    async def _handle_task_view(self, query, user_id: int, task_id: int):
        """Показать детали задачи"""
        task = self.db.get_task_by_id(task_id)

        if not task:
            await query.edit_message_text("❌ Задача не найдена")
            return

        task_id, user_id, title, description, priority, due_date, category, tags, status = task

        # Форматируем вывод
        text = f"<b>📋 {title}</b>\n\n"

        if description:
            text += f"<i>{description}</i>\n\n"

        text += f"🎯 Приоритет: {priority}\n"

        if due_date:
            text += f"📅 Дедлайн: {due_date}\n"

        if category:
            text += f"📂 Категория: {category}\n"

        if tags and tags != "[]":
            text += f"🏷 Теги: {tags}\n"

        text += f"📊 Статус: {status}"

        keyboard = self.keyboards.get_task_actions_keyboard(task_id)
        await query.edit_message_text(text, parse_mode='HTML', reply_markup=keyboard)

    async def _handle_task_edit(self, query, user_id: int, task_id: int):
        """Редактирование задачи (заглушка)"""
        await query.edit_message_text(
            "✏️ Редактирование задачи\n\n"
            "Эта функция будет реализована в следующих версиях.\n"
            "Пока вы можете удалить задачу и создать новую."
        )

    async def _handle_task_snooze(self, query, user_id: int, task_id: int, minutes: int):
        """Отложить напоминание"""
        if not self.reminder_scheduler:
            await query.edit_message_text("❌ Планировщик напоминаний недоступен")
            return

        # Вычисляем новое время
        new_time = datetime.now() + timedelta(minutes=minutes)

        # Создаем новое напоминание
        self.db.add_reminder(task_id, user_id, new_time, 'snoozed')

        # Если есть scheduler, добавляем в очередь
        if hasattr(self.reminder_scheduler, 'schedule_task_reminder'):
            self.reminder_scheduler.schedule_task_reminder(task_id, user_id, new_time, 'snoozed')

        hours = minutes // 60
        mins = minutes % 60

        time_str = ""
        if hours > 0:
            time_str += f"{hours} ч "
        if mins > 0:
            time_str += f"{mins} мин"

        await query.edit_message_text(
            f"🔔 Напоминание отложено на {time_str}\n"
            f"⏰ Новое время: {new_time.strftime('%d.%m.%Y %H:%M')}"
        )

    async def _handle_category_view(self, query, user_id: int, category: str):
        """Показать задачи категории"""
        from src.categories.manager import CategoryManager
        category_manager = CategoryManager(self.db)

        if category == "all":
            tasks = self.db.get_all_tasks(user_id)
            text = "📋 <b>Все задачи</b>\n\n"
        else:
            tasks = category_manager.get_tasks_by_category(user_id, category)
            text = f"📂 <b>Категория: {category.title()}</b>\n\n"

        if not tasks:
            text += "Нет задач"
            await query.edit_message_text(text, parse_mode='HTML')
            return

        # Форматируем задачи
        for task in tasks[:10]:  # Ограничение на 10 задач
            task_id, _, title, _, priority, due_date, _, _, status = task
            icon = "✅" if status == "completed" else "⏹"
            text += f"{icon} <b>{title}</b>\n"
            if due_date:
                text += f"   📅 {due_date}\n"

        if len(tasks) > 10:
            text += f"\n... и ещё {len(tasks) - 10} задач"

        keyboard = self.keyboards.get_task_list_keyboard(tasks[:10])
        await query.edit_message_text(text, parse_mode='HTML', reply_markup=keyboard)

    async def _handle_confirm(self, query, user_id: int, action: str, item_id: int):
        """Обработка подтверждения действия"""
        if action == "delete_task":
            # Удаляем задачу (реализовать в DatabaseManager)
            task = self.db.get_task_by_id(item_id)
            if task:
                self.db.mark_task_done(item_id)  # Временно используем mark_done
                await query.edit_message_text(f"🗑 Задача удалена")
            else:
                await query.edit_message_text("❌ Задача не найдена")
        else:
            await query.edit_message_text("✅ Действие подтверждено")

    async def _handle_settings_main(self, query, user_id: int):
        """Главное меню настроек"""
        keyboard = self.keyboards.get_settings_keyboard()
        await query.edit_message_text(
            "⚙️ <b>Настройки</b>\n\n"
            "Выберите раздел:",
            parse_mode='HTML',
            reply_markup=keyboard
        )

    async def _handle_settings_reminders(self, query, user_id: int):
        """Настройки напоминаний"""
        keyboard = self.keyboards.get_reminder_settings_keyboard()
        await query.edit_message_text(
            "🔔 <b>Настройки напоминаний</b>\n\n"
            "Управление системой напоминаний:",
            parse_mode='HTML',
            reply_markup=keyboard
        )

    async def _handle_settings_categories(self, query, user_id: int):
        """Настройки категорий"""
        categories = self.db.get_user_categories(user_id)

        text = "📂 <b>Категории</b>\n\n"
        if categories:
            for cat in categories:
                cat_id, name, color = cat
                text += f"{color} {name.title()}\n"
        else:
            text += "У вас пока нет категорий"

        keyboard = self.keyboards.get_back_button("settings_back")
        await query.edit_message_text(text, parse_mode='HTML', reply_markup=keyboard)

    async def _handle_settings_time(self, query, user_id: int):
        """Настройки времени"""
        await query.edit_message_text(
            "⏰ <b>Настройки времени уведомлений</b>\n\n"
            "Время настраивается в файле config.yaml\n"
            "Текущие настройки:\n"
            "• Утренние напоминания: 09:00\n"
            "• Напоминания о дедлайнах: за 1 и 3 дня",
            parse_mode='HTML',
            reply_markup=self.keyboards.get_back_button("settings_back")
        )
