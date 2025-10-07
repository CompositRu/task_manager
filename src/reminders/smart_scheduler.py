import asyncio
import logging
from datetime import datetime, timedelta
from typing import List, Callable, Awaitable, Optional
from dataclasses import dataclass

from src.database.models import DatabaseManager
from src.config.manager import ConfigManager


@dataclass
class Reminder:
    """Класс для представления напоминания в очереди"""
    id: int
    task_id: int
    user_id: int
    time: datetime
    type: str
    title: str

    def __lt__(self, other):
        """Для сортировки по времени"""
        return self.time < other.time


class SmartReminderScheduler:
    """
    Event-driven планировщик напоминаний с динамическим пробуждением.

    Особенности:
    - Спит до ближайшего события вместо polling
    - Загружает напоминания на 72 часа вперёд
    - Догружает новые напоминания раз в сутки (48-72ч окно)
    - Очищает старые напоминания в конце дня
    - Перезагружает конфиг раз в день
    """

    def __init__(self, db: DatabaseManager, send_reminder_callback: Callable[[int, str, str], Awaitable[None]]):
        self.db = db
        self.send_reminder_callback = send_reminder_callback
        self.config = ConfigManager()

        # Очередь напоминаний (отсортирована по времени)
        self.reminder_queue: List[Reminder] = []

        # Состояние
        self.is_running = False
        self.wake_event = asyncio.Event()  # Для прерывания сна

        # Метки времени последних операций
        self.last_daily_reload: Optional[datetime] = None
        self.last_cleanup: Optional[datetime] = None
        self.last_config_reload: Optional[datetime] = None

    async def start_scheduler(self):
        """Главный цикл планировщика"""
        self.is_running = True
        logging.info("🚀 SmartReminderScheduler запущен (event-driven режим)")

        # Первоначальная загрузка на 72 часа
        await self.load_initial_reminders()

        while self.is_running:
            try:
                # 1. Проверяем и выполняем ежедневные задачи
                await self.check_daily_tasks()

                # 2. Вычисляем время до следующего события
                next_wake_time = self.get_next_wake_time()

                # 3. Спим до события (или до прерывания)
                await self.sleep_until(next_wake_time)

                # 4. Обрабатываем все просроченные напоминания
                await self.process_due_reminders()

            except Exception as e:
                logging.error(f"Ошибка в главном цикле планировщика: {e}")
                await asyncio.sleep(60)  # Пауза перед retry

    def stop_scheduler(self):
        """Остановка планировщика"""
        self.is_running = False
        self.wake_event.set()  # Прерываем сон
        logging.info("SmartReminderScheduler остановлен")

    async def load_initial_reminders(self):
        """Загрузка напоминаний на 72 часа при старте"""
        try:
            future_reminders = self.db.get_future_reminders(hours=72)

            self.reminder_queue = [
                Reminder(
                    id=r[0],
                    task_id=r[1],
                    user_id=r[2],
                    title=r[3],
                    type=r[4],
                    time=datetime.fromisoformat(r[5]) if isinstance(r[5], str) else r[5]
                )
                for r in future_reminders
            ]

            self.reminder_queue.sort()
            self.last_daily_reload = datetime.now()

            logging.info(f"📥 Загружено {len(self.reminder_queue)} напоминаний на 72 часа")
            if self.reminder_queue:
                logging.info(f"   Первое напоминание: {self.reminder_queue[0].time.strftime('%Y-%m-%d %H:%M')}")
                logging.info(f"   Последнее напоминание: {self.reminder_queue[-1].time.strftime('%Y-%m-%d %H:%M')}")

        except Exception as e:
            logging.error(f"Ошибка загрузки напоминаний: {e}")

    async def check_daily_tasks(self):
        """Проверка и выполнение ежедневных задач"""
        now = datetime.now()

        # 1. Догрузка новых напоминаний (раз в сутки)
        if self.should_reload_db(now):
            await self.reload_next_day_reminders()
            self.last_daily_reload = now

        # 2. Очистка старых напоминаний (в конце дня)
        if self.should_cleanup_db(now):
            await self.cleanup_old_reminders()
            self.last_cleanup = now

        # 3. Перезагрузка конфига (в 03:00)
        if self.should_reload_config(now):
            self.config.reload_config()
            self.last_config_reload = now
            logging.info("🔄 Конфигурация перезагружена")

    async def reload_next_day_reminders(self):
        """Догружаем напоминания с 48 до 72 часов"""
        try:
            new_reminders = self.db.get_future_reminders(hours=72, from_hours=48)

            new_reminder_objects = [
                Reminder(
                    id=r[0],
                    task_id=r[1],
                    user_id=r[2],
                    title=r[3],
                    type=r[4],
                    time=datetime.fromisoformat(r[5]) if isinstance(r[5], str) else r[5]
                )
                for r in new_reminders
            ]

            # Добавляем в очередь и пересортировываем
            self.reminder_queue.extend(new_reminder_objects)
            self.reminder_queue.sort()

            logging.info(f"📥 Догружено {len(new_reminder_objects)} напоминаний (окно 48-72ч)")

        except Exception as e:
            logging.error(f"Ошибка догрузки напоминаний: {e}")

    async def cleanup_old_reminders(self):
        """Очистка просроченных напоминаний из БД"""
        try:
            deleted_count = self.db.delete_old_reminders(days_old=7)
            logging.info(f"🗑️  Очищено {deleted_count} старых напоминаний из БД")
        except Exception as e:
            logging.error(f"Ошибка очистки БД: {e}")

    def should_reload_db(self, now: datetime) -> bool:
        """Нужно ли догрузить новые напоминания"""
        if not self.last_daily_reload:
            return False  # Только что загрузили при старте

        # Раз в сутки
        hours_since_reload = (now - self.last_daily_reload).total_seconds() / 3600
        return hours_since_reload >= 24

    def should_cleanup_db(self, now: datetime) -> bool:
        """Нужно ли очистить старые напоминания (в конце дня)"""
        if not self.last_cleanup:
            self.last_cleanup = now.replace(hour=0, minute=0, second=0)

        # В 23:55 раз в сутки
        return now.hour == 23 and now.minute >= 55 and \
               (now.date() > self.last_cleanup.date())

    def should_reload_config(self, now: datetime) -> bool:
        """Нужно ли перезагрузить конфиг (в 03:00)"""
        if not self.last_config_reload:
            self.last_config_reload = now.replace(hour=0, minute=0, second=0)

        # В 03:00 раз в сутки
        return now.hour == 3 and now.minute < 5 and \
               (now.date() > self.last_config_reload.date())

    def add_reminder_to_queue(self, reminder: Reminder):
        """
        Добавление нового напоминания в очередь.
        Вызывается когда создаётся новая задача с напоминанием < 72 часов.
        """
        # Добавляем в очередь и пересортировываем
        self.reminder_queue.append(reminder)
        self.reminder_queue.sort()

        logging.info(f"➕ Напоминание добавлено в очередь: {reminder.time.strftime('%Y-%m-%d %H:%M')} ({reminder.title})")

        # Прерываем сон, если новое напоминание стало первым
        if self.reminder_queue[0] == reminder:
            self.wake_event.set()
            logging.info("⏰ Прерывание сна - новое ближайшее напоминание")

    def get_next_wake_time(self) -> datetime:
        """Вычисляет время следующего пробуждения"""
        now = datetime.now()
        candidates = []

        # 1. Ближайшее напоминание
        if self.reminder_queue:
            candidates.append(self.reminder_queue[0].time)

        # 2. Ежедневная перезагрузка БД (через 24 часа от последней)
        if self.last_daily_reload:
            next_reload = self.last_daily_reload + timedelta(hours=24)
            candidates.append(next_reload)
        else:
            candidates.append(now + timedelta(hours=24))

        # 3. Очистка БД (23:55)
        next_cleanup = now.replace(hour=23, minute=55, second=0, microsecond=0)
        if next_cleanup <= now:
            next_cleanup += timedelta(days=1)
        candidates.append(next_cleanup)

        # 4. Перезагрузка конфига (03:00)
        next_config_reload = now.replace(hour=3, minute=0, second=0, microsecond=0)
        if next_config_reload <= now:
            next_config_reload += timedelta(days=1)
        candidates.append(next_config_reload)

        # Выбираем самое раннее будущее событие
        future_times = [t for t in candidates if t > now]

        if future_times:
            next_time = min(future_times)
            return next_time
        else:
            # Fallback: спим 1 час
            return now + timedelta(hours=1)

    async def sleep_until(self, wake_time: datetime):
        """Спит до указанного времени или до прерывания"""
        now = datetime.now()
        seconds = (wake_time - now).total_seconds()

        if seconds <= 0:
            return

        hours = seconds / 3600
        logging.info(f"😴 Сон до {wake_time.strftime('%Y-%m-%d %H:%M:%S')} ({hours:.1f}ч)")

        try:
            await asyncio.wait_for(self.wake_event.wait(), timeout=seconds)
            # Прерван событием
            self.wake_event.clear()
            logging.info("⏰ Пробуждение по событию (новая задача)")
        except asyncio.TimeoutError:
            # Проснулись по таймеру
            logging.info("⏰ Пробуждение по расписанию")

    async def process_due_reminders(self):
        """Обрабатывает все просроченные напоминания"""
        now = datetime.now()
        processed = 0

        while self.reminder_queue and self.reminder_queue[0].time <= now:
            reminder = self.reminder_queue.pop(0)

            try:
                # Форматируем сообщение
                message = self._format_reminder_message(reminder.title, reminder.type)

                # Отправляем напоминание
                await self.send_reminder_callback(
                    reminder.user_id,
                    message,
                    reminder.type
                )

                # Отмечаем в БД как отправленное
                self.db.mark_reminder_sent(reminder.id)
                processed += 1

                logging.info(f"✅ Отправлено напоминание #{reminder.id}: {reminder.title}")

            except Exception as e:
                logging.error(f"❌ Ошибка отправки напоминания #{reminder.id}: {e}")

        if processed > 0:
            logging.info(f"📤 Обработано {processed} напоминаний")

    def _format_reminder_message(self, task_title: str, reminder_type: str) -> str:
        """Форматирование сообщения напоминания"""
        if reminder_type == 'morning':
            return f"🌅 *Доброе утро!*\n\n📋 У вас есть активная задача:\n📝 {task_title}"
        elif reminder_type == 'specific_time':
            return f"⏰ *Напоминание*\n\n📝 {task_title}"
        elif reminder_type == 'deadline':
            return f"🚨 *Приближается дедлайн!*\n\n📝 {task_title}"
        elif reminder_type == 'time_based':
            return f"⏱️ *Скоро событие*\n\n📝 {task_title}"
        else:
            return f"🔔 *Напоминание*\n\n📝 {task_title}"

    # Методы для обратной совместимости со старым API
    def schedule_task_reminder(self, task_id: int, user_id: int, reminder_time: datetime, reminder_type: str = 'specific_time'):
        """Создать напоминание (для совместимости с handlers)"""
        try:
            # Добавляем в БД
            self.db.add_reminder(task_id, user_id, reminder_time, reminder_type)

            # Если напоминание в пределах 72 часов - добавляем в очередь
            hours_until = (reminder_time - datetime.now()).total_seconds() / 3600
            if hours_until <= 72:
                # Получаем title задачи для Reminder объекта
                task = self.db.get_task_by_id(task_id)
                if task:
                    reminder = Reminder(
                        id=self.db.get_last_reminder_id(),  # Получаем ID только что созданного напоминания
                        task_id=task_id,
                        user_id=user_id,
                        time=reminder_time,
                        type=reminder_type,
                        title=task[2] if len(task) > 2 else "Задача"  # task[2] - это title
                    )
                    self.add_reminder_to_queue(reminder)

            logging.info(f"Запланировано напоминание для задачи {task_id} на {reminder_time}")

        except Exception as e:
            logging.error(f"Ошибка планирования напоминания: {e}")

    def schedule_deadline_reminder(self, task_id: int, user_id: int, due_date: datetime):
        """Запланировать напоминание о дедлайне (для совместимости)"""
        try:
            # Напоминание за день до дедлайна в 9:00
            morning_time_str = self.config.get_morning_reminder_time()
            hour, minute = map(int, morning_time_str.split(':'))

            reminder_time = due_date - timedelta(days=1)
            reminder_time = reminder_time.replace(hour=hour, minute=minute)

            if reminder_time > datetime.now():
                self.schedule_task_reminder(task_id, user_id, reminder_time, 'deadline')

        except Exception as e:
            logging.error(f"Ошибка планирования напоминания о дедлайне: {e}")
