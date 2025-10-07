import asyncio
import logging
from datetime import datetime, timedelta, time
from typing import List, Callable, Awaitable
from src.database.models import DatabaseManager
from src.config.manager import ConfigManager


class ReminderScheduler:
    def __init__(self, db: DatabaseManager, send_reminder_callback: Callable[[int, str, str], Awaitable[None]]):
        self.db = db
        self.send_reminder_callback = send_reminder_callback
        self.is_running = False
        self.config = ConfigManager()

        # Загружаем время утренних напоминаний из конфига
        morning_time_str = self.config.get_morning_reminder_time()
        try:
            hour, minute = map(int, morning_time_str.split(':'))
            self.morning_reminder_time = time(hour, minute)
        except:
            self.morning_reminder_time = time(9, 0)  # Fallback на 9:00

    def set_morning_reminder_time(self, hour: int, minute: int = 0):
        """Установить время утренних напоминаний"""
        self.morning_reminder_time = time(hour, minute)

    async def start_scheduler(self):
        """Запуск планировщика напоминаний"""
        self.is_running = True

        # Получаем интервал проверки из конфигурации
        check_interval = self.config.get_check_interval()
        logging.info(f"Планировщик напоминаний запущен (интервал проверки: {check_interval} сек)")

        while self.is_running:
            try:
                await self._check_and_send_reminders()
                await self._check_condition_reminders()
                await asyncio.sleep(check_interval)
            except Exception as e:
                logging.error(f"Ошибка в планировщике напоминаний: {e}")
                await asyncio.sleep(check_interval)

    def stop_scheduler(self):
        """Остановка планировщика"""
        self.is_running = False
        logging.info("Планировщик напоминаний остановлен")

    async def _check_and_send_reminders(self):
        """Проверка и отправка напоминаний"""
        pending_reminders = self.db.get_pending_reminders()

        for reminder_id, task_id, user_id, task_title, reminder_type in pending_reminders:
            try:
                message = self._format_reminder_message(task_title, reminder_type)
                await self.send_reminder_callback(user_id, message, reminder_type)
                self.db.mark_reminder_sent(reminder_id)
                logging.info(f"Отправлено напоминание {reminder_id} для задачи {task_id}")
            except Exception as e:
                logging.error(f"Ошибка отправки напоминания {reminder_id}: {e}")

    async def _check_condition_reminders(self):
        """Проверка задач с условиями"""
        tasks_for_check = self.db.get_tasks_for_condition_check()

        for task_id, user_id, title, conditions_json, last_check, interval in tasks_for_check:
            try:
                from src.ai.gemini_processor import GeminiProcessor
                import json

                conditions = json.loads(conditions_json) if conditions_json else []
                if not conditions:
                    continue

                gemini = GeminiProcessor()
                question = gemini.process_condition_check(title, conditions)

                message = f"🔔 Проверка условий для задачи:\n\n📝 *{title}*\n\n❓ {question}"

                await self.send_reminder_callback(user_id, message, 'condition_check')
                self.db.update_last_condition_check(task_id)

                logging.info(f"Отправлен запрос проверки условий для задачи {task_id}")

            except Exception as e:
                logging.error(f"Ошибка проверки условий задачи {task_id}: {e}")

    def _format_reminder_message(self, task_title: str, reminder_type: str) -> str:
        """Форматирование сообщения напоминания"""
        if reminder_type == 'morning':
            return f"🌅 *Доброе утро!*\n\n📋 У вас есть активная задача:\n📝 {task_title}"
        elif reminder_type == 'specific_time':
            return f"⏰ *Напоминание*\n\n📝 {task_title}"
        elif reminder_type == 'deadline':
            return f"🚨 *Приближается дедлайн!*\n\n📝 {task_title}"
        else:
            return f"🔔 *Напоминание*\n\n📝 {task_title}"

    def create_morning_reminders(self):
        """Создание утренних напоминаний для активных задач"""
        try:
            # Получаем все активные задачи с датами на сегодня и завтра
            from datetime import date
            today = date.today()
            tomorrow = today + timedelta(days=1)

            # Получаем задачи (нужно будет добавить метод в DatabaseManager)
            # tasks_today = self.db.get_tasks_by_date_range(today.strftime('%Y-%m-%d'))

            # Создаем напоминания на завтра утром
            tomorrow_morning = datetime.combine(tomorrow, self.morning_reminder_time)

            # Здесь должна быть логика создания напоминаний для релевантных задач

        except Exception as e:
            logging.error(f"Ошибка создания утренних напоминаний: {e}")

    def schedule_task_reminder(self, task_id: int, user_id: int, reminder_time: datetime, reminder_type: str = 'specific_time'):
        """Запланировать напоминание для задачи"""
        try:
            self.db.add_reminder(task_id, user_id, reminder_time, reminder_type)
            logging.info(f"Запланировано напоминание для задачи {task_id} на {reminder_time}")
        except Exception as e:
            logging.error(f"Ошибка планирования напоминания: {e}")

    def schedule_deadline_reminder(self, task_id: int, user_id: int, due_date: datetime):
        """Запланировать напоминание о дедлайне"""
        try:
            # Напоминание за день до дедлайна
            reminder_time = due_date - timedelta(days=1)
            reminder_time = reminder_time.replace(hour=self.morning_reminder_time.hour,
                                                minute=self.morning_reminder_time.minute)

            if reminder_time > datetime.now():
                self.schedule_task_reminder(task_id, user_id, reminder_time, 'deadline')

        except Exception as e:
            logging.error(f"Ошибка планирования напоминания о дедлайне: {e}")