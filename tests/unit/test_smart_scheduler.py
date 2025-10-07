"""
Unit тесты для SmartReminderScheduler
"""
import pytest
from datetime import datetime, timedelta
from src.reminders.smart_scheduler import Reminder


def test_reminder_sorting():
    """Тест сортировки напоминаний по времени"""
    now = datetime.now()

    r1 = Reminder(1, 1, 123, now + timedelta(hours=3), 'deadline', 'Задача 1')
    r2 = Reminder(2, 2, 123, now + timedelta(hours=1), 'deadline', 'Задача 2')
    r3 = Reminder(3, 3, 123, now + timedelta(hours=2), 'deadline', 'Задача 3')

    reminders = [r1, r2, r3]
    reminders.sort()

    assert reminders[0].id == 2  # Ближайшее через 1 час
    assert reminders[1].id == 3  # Через 2 часа
    assert reminders[2].id == 1  # Через 3 часа


@pytest.mark.asyncio
async def test_load_initial_reminders(smart_scheduler, temp_db, sample_user_id, sample_task_data):
    """Тест загрузки начальных напоминаний"""
    # Создаём задачу с напоминаниями
    task_id = temp_db.save_task(sample_user_id, "Задача", sample_task_data)

    now = datetime.now()
    temp_db.add_reminder(task_id, sample_user_id, now + timedelta(hours=10), 'deadline')
    temp_db.add_reminder(task_id, sample_user_id, now + timedelta(hours=20), 'deadline')

    # Загружаем напоминания
    await smart_scheduler.load_initial_reminders()

    assert len(smart_scheduler.reminder_queue) == 2
    assert smart_scheduler.last_daily_reload is not None


def test_should_reload_db(smart_scheduler):
    """Тест проверки необходимости перезагрузки БД"""
    # Сразу после старта - не нужно
    assert smart_scheduler.should_reload_db(datetime.now()) is False

    # Через 25 часов - нужно
    smart_scheduler.last_daily_reload = datetime.now() - timedelta(hours=25)
    assert smart_scheduler.should_reload_db(datetime.now()) is True


def test_should_cleanup_db(smart_scheduler):
    """Тест проверки необходимости очистки БД"""
    now = datetime.now()

    # В 23:56 сегодня - нужно (last_cleanup был вчера)
    cleanup_time = now.replace(hour=23, minute=56, second=0)
    smart_scheduler.last_cleanup = (now - timedelta(days=1)).replace(hour=0, minute=0)
    assert smart_scheduler.should_cleanup_db(cleanup_time) is True

    # В 10:00 - не нужно
    morning_time = now.replace(hour=10, minute=0, second=0)
    smart_scheduler.last_cleanup = now.replace(hour=0, minute=0)  # Reset to today
    assert smart_scheduler.should_cleanup_db(morning_time) is False


def test_should_reload_config(smart_scheduler):
    """Тест проверки необходимости перезагрузки конфига"""
    now = datetime.now()

    # В 03:02 сегодня - нужно (если не было сегодня)
    config_time = now.replace(hour=3, minute=2, second=0)
    smart_scheduler.last_config_reload = (now - timedelta(days=1)).replace(hour=0, minute=0)
    assert smart_scheduler.should_reload_config(config_time) is True

    # В 10:00 - не нужно
    morning_time = now.replace(hour=10, minute=0, second=0)
    smart_scheduler.last_config_reload = now.replace(hour=3, minute=0)
    assert smart_scheduler.should_reload_config(morning_time) is False


def test_add_reminder_to_queue(smart_scheduler):
    """Тест добавления напоминания в очередь"""
    now = datetime.now()

    r1 = Reminder(1, 1, 123, now + timedelta(hours=5), 'deadline', 'Задача 1')
    r2 = Reminder(2, 2, 123, now + timedelta(hours=2), 'deadline', 'Задача 2')

    smart_scheduler.add_reminder_to_queue(r1)
    assert len(smart_scheduler.reminder_queue) == 1

    smart_scheduler.add_reminder_to_queue(r2)
    assert len(smart_scheduler.reminder_queue) == 2

    # Проверяем, что очередь отсортирована
    assert smart_scheduler.reminder_queue[0].id == 2  # Ближайшее


def test_get_next_wake_time(smart_scheduler):
    """Тест вычисления времени следующего пробуждения"""
    now = datetime.now()

    # Добавляем напоминание через 2 часа
    r = Reminder(1, 1, 123, now + timedelta(hours=2), 'deadline', 'Задача')
    smart_scheduler.add_reminder_to_queue(r)

    # Время пробуждения должно быть через 2 часа (или раньше если есть системное событие)
    wake_time = smart_scheduler.get_next_wake_time()

    # Должно быть в будущем
    assert wake_time > now

    # Должно быть не позже чем через 2 часа
    assert wake_time <= now + timedelta(hours=2, minutes=1)


def test_format_reminder_message(smart_scheduler):
    """Тест форматирования сообщений"""
    message = smart_scheduler._format_reminder_message("Тестовая задача", "deadline")
    assert "Тестовая задача" in message
    assert "дедлайн" in message.lower()

    message = smart_scheduler._format_reminder_message("Задача", "morning")
    assert "утро" in message.lower()

    message = smart_scheduler._format_reminder_message("Задача", "time_based")
    assert "событие" in message.lower()


@pytest.mark.asyncio
async def test_process_due_reminders(smart_scheduler, mock_send_reminder, temp_db, sample_user_id, sample_task_data):
    """Тест обработки просроченных напоминаний"""
    # Создаём задачу
    task_id = temp_db.save_task(sample_user_id, "Задача", sample_task_data)

    # Создаём напоминание в прошлом
    past_time = datetime.now() - timedelta(minutes=5)
    temp_db.add_reminder(task_id, sample_user_id, past_time, 'deadline')

    # Загружаем (хотя оно в прошлом, но для теста добавим вручную)
    r = Reminder(1, task_id, sample_user_id, past_time, 'deadline', 'Задача')
    smart_scheduler.reminder_queue.append(r)

    # Обрабатываем
    await smart_scheduler.process_due_reminders()

    # Очередь должна быть пуста
    assert len(smart_scheduler.reminder_queue) == 0

    # Callback должен был быть вызван
    mock_send_reminder.assert_called_once()


def test_schedule_task_reminder_within_72h(smart_scheduler, temp_db, sample_user_id, sample_task_data):
    """Тест планирования напоминания в пределах 72 часов"""
    task_id = temp_db.save_task(sample_user_id, "Задача", sample_task_data)

    reminder_time = datetime.now() + timedelta(hours=10)

    # Планируем напоминание
    smart_scheduler.schedule_task_reminder(task_id, sample_user_id, reminder_time, 'deadline')

    # Должно появиться в очереди
    assert len(smart_scheduler.reminder_queue) > 0


def test_schedule_task_reminder_beyond_72h(smart_scheduler, temp_db, sample_user_id, sample_task_data):
    """Тест планирования напоминания за пределами 72 часов"""
    task_id = temp_db.save_task(sample_user_id, "Задача", sample_task_data)

    reminder_time = datetime.now() + timedelta(hours=100)

    # Планируем напоминание
    smart_scheduler.schedule_task_reminder(task_id, sample_user_id, reminder_time, 'deadline')

    # НЕ должно появиться в очереди (только в БД)
    # Проверяем БД
    reminders = temp_db.get_future_reminders(hours=200)
    assert len(reminders) > 0
