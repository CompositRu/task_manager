"""
Интеграционный тест: полный жизненный цикл напоминания
"""
import pytest
from datetime import datetime, timedelta
from src.reminders.smart_scheduler import Reminder


@pytest.mark.asyncio
async def test_reminder_full_lifecycle(smart_scheduler, temp_db, sample_user_id, sample_task_data, mock_send_reminder):
    """
    Полный жизненный цикл напоминания:
    1. Создание задачи
    2. Добавление напоминания в БД
    3. Загрузка в очередь (0-72ч окно)
    4. Обработка при наступлении времени
    5. Отметка как отправленное
    6. Очистка через 7 дней
    """

    # 1. Создаём задачу
    task_id = temp_db.save_task(sample_user_id, "Важная встреча", sample_task_data)
    assert task_id > 0

    # 2. Добавляем напоминание на через 30 минут
    reminder_time = datetime.now() + timedelta(minutes=30)
    temp_db.add_reminder(task_id, sample_user_id, reminder_time, 'deadline')

    # 3. Загружаем напоминания в очередь
    await smart_scheduler.load_initial_reminders()

    assert len(smart_scheduler.reminder_queue) == 1
    assert smart_scheduler.reminder_queue[0].task_id == task_id

    # 4. Имитируем наступление времени (переносим напоминание в прошлое)
    smart_scheduler.reminder_queue[0].time = datetime.now() - timedelta(seconds=1)

    # Обрабатываем
    await smart_scheduler.process_due_reminders()

    # Очередь должна быть пуста
    assert len(smart_scheduler.reminder_queue) == 0

    # 5. Проверяем, что напоминание отмечено как отправленное
    cursor = temp_db.conn.cursor()
    cursor.execute("SELECT is_sent FROM reminders WHERE task_id = ?", (task_id,))
    is_sent = cursor.fetchone()[0]
    assert is_sent == 1  # True

    # 6. Проверяем очистку старых напоминаний
    # Переносим время напоминания в прошлое (10 дней назад)
    cursor.execute(
        "UPDATE reminders SET reminder_time = ? WHERE task_id = ?",
        (datetime.now() - timedelta(days=10), task_id)
    )
    temp_db.conn.commit()

    deleted = temp_db.delete_old_reminders(days_old=7)
    assert deleted == 1


@pytest.mark.asyncio
async def test_72h_window_loading(smart_scheduler, temp_db, sample_user_id, sample_task_data):
    """
    Тест загрузки напоминаний в 72-часовое окно
    """
    task_id = temp_db.save_task(sample_user_id, "Задача", sample_task_data)

    now = datetime.now()

    # Создаём напоминания в разное время
    temp_db.add_reminder(task_id, sample_user_id, now + timedelta(hours=10), 'deadline')   # Внутри окна
    temp_db.add_reminder(task_id, sample_user_id, now + timedelta(hours=50), 'deadline')   # Внутри окна
    temp_db.add_reminder(task_id, sample_user_id, now + timedelta(hours=71), 'deadline')   # Внутри окна
    temp_db.add_reminder(task_id, sample_user_id, now + timedelta(hours=100), 'deadline')  # Вне окна

    # Загружаем 72-часовое окно
    await smart_scheduler.load_initial_reminders()

    # Должно быть 3 напоминания (не 100ч)
    assert len(smart_scheduler.reminder_queue) == 3


@pytest.mark.asyncio
async def test_daily_reload_48_72h(smart_scheduler, temp_db, sample_user_id, sample_task_data):
    """
    Тест ежедневной догрузки окна 48-72ч
    """
    task_id = temp_db.save_task(sample_user_id, "Задача", sample_task_data)

    now = datetime.now()

    # Создаём напоминания в окне 48-72ч
    temp_db.add_reminder(task_id, sample_user_id, now + timedelta(hours=50), 'deadline')
    temp_db.add_reminder(task_id, sample_user_id, now + timedelta(hours=60), 'deadline')
    temp_db.add_reminder(task_id, sample_user_id, now + timedelta(hours=70), 'deadline')

    # Догружаем окно 48-72ч
    await smart_scheduler.reload_next_day_reminders()

    # Все 3 должны быть в очереди
    assert len(smart_scheduler.reminder_queue) == 3


@pytest.mark.asyncio
async def test_new_task_within_72h_added_to_queue(smart_scheduler, temp_db, sample_user_id, sample_task_data):
    """
    Тест: новая задача с напоминанием < 72ч сразу добавляется в очередь
    """
    task_id = temp_db.save_task(sample_user_id, "Срочная задача", sample_task_data)

    reminder_time = datetime.now() + timedelta(hours=10)

    # Планируем через scheduler (как в реальном сценарии)
    smart_scheduler.schedule_task_reminder(task_id, sample_user_id, reminder_time, 'deadline')

    # Должно быть в очереди
    assert len(smart_scheduler.reminder_queue) > 0
    assert any(r.task_id == task_id for r in smart_scheduler.reminder_queue)


@pytest.mark.asyncio
async def test_new_task_beyond_72h_only_in_db(smart_scheduler, temp_db, sample_user_id, sample_task_data):
    """
    Тест: новая задача с напоминанием > 72ч только в БД, не в очереди
    """
    task_id = temp_db.save_task(sample_user_id, "Задача в будущем", sample_task_data)

    reminder_time = datetime.now() + timedelta(hours=100)

    # Планируем
    smart_scheduler.schedule_task_reminder(task_id, sample_user_id, reminder_time, 'deadline')

    # НЕ должно быть в очереди
    assert not any(r.task_id == task_id for r in smart_scheduler.reminder_queue)

    # Должно быть в БД
    reminders = temp_db.get_future_reminders(hours=200)
    assert len(reminders) > 0
    assert any(r[1] == task_id for r in reminders)


@pytest.mark.asyncio
async def test_multiple_reminders_sorted_correctly(smart_scheduler, temp_db, sample_user_id, sample_task_data):
    """
    Тест: несколько напоминаний сортируются правильно
    """
    # Создаём 3 задачи с разным временем
    now = datetime.now()

    task1_id = temp_db.save_task(sample_user_id, "Задача 1", sample_task_data)
    task2_id = temp_db.save_task(sample_user_id, "Задача 2", sample_task_data)
    task3_id = temp_db.save_task(sample_user_id, "Задача 3", sample_task_data)

    temp_db.add_reminder(task1_id, sample_user_id, now + timedelta(hours=30), 'deadline')
    temp_db.add_reminder(task2_id, sample_user_id, now + timedelta(hours=10), 'deadline')
    temp_db.add_reminder(task3_id, sample_user_id, now + timedelta(hours=20), 'deadline')

    await smart_scheduler.load_initial_reminders()

    # Очередь должна быть отсортирована по времени
    assert len(smart_scheduler.reminder_queue) == 3
    assert smart_scheduler.reminder_queue[0].task_id == task2_id  # 10ч - ближайшее
    assert smart_scheduler.reminder_queue[1].task_id == task3_id  # 20ч
    assert smart_scheduler.reminder_queue[2].task_id == task1_id  # 30ч
