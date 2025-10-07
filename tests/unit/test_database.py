"""
Unit тесты для DatabaseManager
"""
import pytest
from datetime import datetime, timedelta


def test_database_initialization(temp_db):
    """Тест инициализации базы данных"""
    assert temp_db.conn is not None

    # Проверяем, что таблицы созданы
    cursor = temp_db.conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = {row[0] for row in cursor.fetchall()}

    assert 'tasks' in tables
    assert 'reminders' in tables
    assert 'categories' in tables


def test_save_and_get_task(temp_db, sample_user_id, sample_task_data):
    """Тест сохранения и получения задачи"""
    # Сохраняем задачу
    task_id = temp_db.save_task(sample_user_id, "Тестовая задача завтра в 15:00", sample_task_data)

    assert task_id > 0

    # Получаем задачу
    task = temp_db.get_task_by_id(task_id)

    assert task is not None
    assert task[0] == task_id  # id
    assert task[1] == sample_user_id  # user_id
    assert task[2] == sample_task_data['title']  # title


def test_get_tasks_by_date(temp_db, sample_user_id, sample_task_data):
    """Тест получения задач по дате"""
    # Создаём несколько задач
    task_data_1 = sample_task_data.copy()
    task_data_1['due_date'] = '2025-10-10'

    task_data_2 = sample_task_data.copy()
    task_data_2['due_date'] = '2025-10-11'

    temp_db.save_task(sample_user_id, "Задача 1", task_data_1)
    temp_db.save_task(sample_user_id, "Задача 2", task_data_2)

    # Получаем задачи на 10 октября
    tasks = temp_db.get_tasks_by_date(sample_user_id, '2025-10-10')

    assert len(tasks) == 1
    assert tasks[0][1] == task_data_1['title']  # Index 1 is title


def test_mark_task_done(temp_db, sample_user_id, sample_task_data):
    """Тест отметки задачи как выполненной"""
    task_id = temp_db.save_task(sample_user_id, "Задача", sample_task_data)

    # Отмечаем как выполненную
    result = temp_db.mark_task_done(task_id, sample_user_id)
    assert result is True

    # Проверяем статус
    cursor = temp_db.conn.cursor()
    cursor.execute("SELECT status FROM tasks WHERE id = ?", (task_id,))
    status = cursor.fetchone()[0]

    assert status == 'done'


def test_add_reminder(temp_db, sample_user_id, sample_task_data):
    """Тест добавления напоминания"""
    task_id = temp_db.save_task(sample_user_id, "Задача", sample_task_data)

    reminder_time = datetime.now() + timedelta(hours=1)
    temp_db.add_reminder(task_id, sample_user_id, reminder_time, 'deadline')

    # Проверяем, что напоминание создано
    cursor = temp_db.conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM reminders WHERE task_id = ?", (task_id,))
    count = cursor.fetchone()[0]

    assert count == 1


def test_get_future_reminders(temp_db, sample_user_id, sample_task_data):
    """Тест получения будущих напоминаний"""
    # Создаём задачу
    task_id = temp_db.save_task(sample_user_id, "Задача", sample_task_data)

    # Добавляем напоминания в разное время
    now = datetime.now()
    temp_db.add_reminder(task_id, sample_user_id, now + timedelta(hours=1), 'deadline')
    temp_db.add_reminder(task_id, sample_user_id, now + timedelta(hours=50), 'deadline')
    temp_db.add_reminder(task_id, sample_user_id, now + timedelta(hours=100), 'deadline')

    # Получаем напоминания на 72 часа
    reminders = temp_db.get_future_reminders(hours=72)

    # Должно быть 2 напоминания (1ч и 50ч, но не 100ч)
    assert len(reminders) == 2


def test_get_future_reminders_with_window(temp_db, sample_user_id, sample_task_data):
    """Тест получения напоминаний в окне времени"""
    task_id = temp_db.save_task(sample_user_id, "Задача", sample_task_data)

    now = datetime.now()
    temp_db.add_reminder(task_id, sample_user_id, now + timedelta(hours=10), 'deadline')
    temp_db.add_reminder(task_id, sample_user_id, now + timedelta(hours=50), 'deadline')
    temp_db.add_reminder(task_id, sample_user_id, now + timedelta(hours=60), 'deadline')

    # Получаем напоминания в окне 48-72 часа
    reminders = temp_db.get_future_reminders(hours=72, from_hours=48)

    # Должно быть 2 напоминания (50ч и 60ч)
    assert len(reminders) == 2


def test_delete_old_reminders(temp_db, sample_user_id, sample_task_data):
    """Тест удаления старых напоминаний"""
    task_id = temp_db.save_task(sample_user_id, "Задача", sample_task_data)

    # Создаём старое отправленное напоминание
    old_time = datetime.now() - timedelta(days=10)
    temp_db.add_reminder(task_id, sample_user_id, old_time, 'deadline')

    # Получаем ID напоминания
    cursor = temp_db.conn.cursor()
    cursor.execute("SELECT id FROM reminders WHERE task_id = ?", (task_id,))
    reminder_id = cursor.fetchone()[0]

    # Отмечаем как отправленное
    temp_db.mark_reminder_sent(reminder_id)

    # Удаляем старые напоминания (старше 7 дней)
    deleted = temp_db.delete_old_reminders(days_old=7)

    assert deleted == 1


def test_create_and_get_category(temp_db, sample_user_id):
    """Тест создания и получения категории"""
    category_id = temp_db.create_category(sample_user_id, "работа", "#FF0000")

    assert category_id > 0

    # Получаем категории пользователя
    categories = temp_db.get_user_categories(sample_user_id)

    assert len(categories) > 0
    assert any(cat[1] == "работа" for cat in categories)


def test_user_isolation(temp_db, sample_task_data):
    """Тест изоляции данных пользователей"""
    user1_id = 111
    user2_id = 222

    # Создаём задачи для разных пользователей
    task1_id = temp_db.save_task(user1_id, "Задача пользователя 1", sample_task_data)
    task2_id = temp_db.save_task(user2_id, "Задача пользователя 2", sample_task_data)

    # Получаем задачи пользователя 1
    user1_tasks = temp_db.get_all_active_tasks(user1_id)

    # Должна быть только одна задача
    assert len(user1_tasks) == 1
    assert user1_tasks[0][0] == task1_id

    # Получаем задачи пользователя 2
    user2_tasks = temp_db.get_all_active_tasks(user2_id)

    assert len(user2_tasks) == 1
    assert user2_tasks[0][0] == task2_id


def test_get_all_active_tasks(temp_db, sample_user_id, sample_task_data):
    """Тест получения всех активных задач"""
    # Создаём несколько активных задач с разными датами
    task_data_1 = sample_task_data.copy()
    task_data_1['due_date'] = '2025-10-10'
    task_data_1['priority'] = 'high'

    task_data_2 = sample_task_data.copy()
    task_data_2['due_date'] = '2025-10-15'
    task_data_2['priority'] = 'medium'

    task_data_3 = sample_task_data.copy()
    task_data_3['due_date'] = None
    task_data_3['priority'] = 'low'

    task1_id = temp_db.save_task(sample_user_id, "Задача 1", task_data_1)
    task2_id = temp_db.save_task(sample_user_id, "Задача 2", task_data_2)
    task3_id = temp_db.save_task(sample_user_id, "Задача 3", task_data_3)

    # Получаем все активные задачи
    tasks = temp_db.get_all_active_tasks(sample_user_id)

    # Должно быть 3 задачи
    assert len(tasks) == 3

    # Проверяем, что все задачи присутствуют
    task_ids = [task[0] for task in tasks]
    assert task1_id in task_ids
    assert task2_id in task_ids
    assert task3_id in task_ids

    # Проверяем сортировку: задачи с датами должны быть первыми
    # task1 и task2 должны быть раньше task3 (у которого нет даты)
    tasks_with_dates = [t for t in tasks if t[4] is not None]  # Index 4 is due_date
    tasks_without_dates = [t for t in tasks if t[4] is None]

    assert len(tasks_with_dates) == 2
    assert len(tasks_without_dates) == 1

    # Проверяем, что задачи с датами идут первыми
    for i, task in enumerate(tasks):
        if task[4] is None:  # Если нашли задачу без даты
            # Все предыдущие должны иметь дату
            for prev_task in tasks[:i]:
                assert prev_task[4] is not None


def test_get_all_active_tasks_excludes_completed(temp_db, sample_user_id, sample_task_data):
    """Тест что get_all_active_tasks исключает выполненные задачи"""
    # Создаём активную задачу
    task1_id = temp_db.save_task(sample_user_id, "Активная задача", sample_task_data)

    # Создаём задачу и отмечаем её как выполненную
    task2_id = temp_db.save_task(sample_user_id, "Выполненная задача", sample_task_data)
    temp_db.mark_task_done(task2_id, sample_user_id)

    # Получаем все активные задачи
    tasks = temp_db.get_all_active_tasks(sample_user_id)

    # Должна быть только одна активная задача
    assert len(tasks) == 1
    assert tasks[0][0] == task1_id


def test_get_all_active_tasks_empty(temp_db, sample_user_id):
    """Тест получения задач когда их нет"""
    tasks = temp_db.get_all_active_tasks(sample_user_id)
    assert len(tasks) == 0
