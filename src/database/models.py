import sqlite3
import json
from datetime import datetime
from typing import List, Optional, Dict, Any


class DatabaseManager:
    def __init__(self, db_path: str = 'tasks.db'):
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.setup_database()

    def setup_database(self):
        cursor = self.conn.cursor()

        # Обновленная схема БД с новыми полями
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                raw_text TEXT,
                title TEXT,
                description TEXT,
                conditions TEXT,
                priority TEXT,
                due_date DATE,
                reminder_time DATETIME,
                category TEXT,
                tags TEXT,
                status TEXT DEFAULT 'active',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_condition_check TIMESTAMP,
                condition_check_interval INTEGER DEFAULT 86400
            )
        ''')

        # Таблица для напоминаний
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS reminders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                task_id INTEGER,
                user_id INTEGER,
                reminder_time DATETIME,
                reminder_type TEXT,
                is_sent BOOLEAN DEFAULT FALSE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (task_id) REFERENCES tasks (id)
            )
        ''')

        # Таблица для категорий
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS categories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                name TEXT,
                color TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        self.conn.commit()

    def save_task(self, user_id: int, raw_text: str, structured: Dict[str, Any]) -> int:
        """Сохранение задачи в БД"""
        cursor = self.conn.cursor()
        cursor.execute('''
            INSERT INTO tasks (
                user_id, raw_text, title, description, conditions,
                priority, due_date, category, tags
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            user_id,
            raw_text,
            structured['title'],
            structured.get('description', ''),
            json.dumps(structured.get('conditions', []), ensure_ascii=False),
            structured.get('priority', 'medium'),
            structured.get('due_date'),
            structured.get('category'),
            json.dumps(structured.get('tags', []), ensure_ascii=False)
        ))
        self.conn.commit()
        return cursor.lastrowid

    def get_tasks_by_date(self, user_id: int, date: str) -> List[tuple]:
        """Получить задачи по дате"""
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT id, title, priority, conditions, due_date, category, tags
            FROM tasks
            WHERE user_id = ?
                AND status = 'active'
                AND (due_date = ? OR due_date IS NULL)
            ORDER BY
                CASE
                    WHEN due_date IS NOT NULL THEN 0
                    ELSE 1
                END,
                CASE priority
                    WHEN 'high' THEN 1
                    WHEN 'medium' THEN 2
                    ELSE 3
                END
        ''', (user_id, date))
        return cursor.fetchall()

    def get_all_active_tasks(self, user_id: int) -> List[tuple]:
        """Получить все активные задачи"""
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT id, title, priority, conditions, due_date, category, tags
            FROM tasks
            WHERE user_id = ? AND status = 'active'
            ORDER BY
                CASE
                    WHEN due_date IS NOT NULL THEN 0
                    ELSE 1
                END,
                due_date,
                CASE priority
                    WHEN 'high' THEN 1
                    WHEN 'medium' THEN 2
                    ELSE 3
                END
        ''', (user_id,))
        return cursor.fetchall()

    def get_tasks_by_category(self, user_id: int, category: str) -> List[tuple]:
        """Получить задачи по категории"""
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT id, title, priority, conditions, due_date, category, tags
            FROM tasks
            WHERE user_id = ? AND status = 'active' AND category = ?
            ORDER BY due_date, priority
        ''', (user_id, category))
        return cursor.fetchall()

    def mark_task_done(self, task_id: int, user_id: int) -> bool:
        """Отметить задачу выполненной"""
        cursor = self.conn.cursor()
        cursor.execute('''
            UPDATE tasks
            SET status = 'done'
            WHERE id = ? AND user_id = ?
        ''', (task_id, user_id))
        self.conn.commit()
        return cursor.rowcount > 0

    def get_tasks_for_condition_check(self) -> List[tuple]:
        """Получить задачи для проверки условий"""
        cursor = self.conn.cursor()
        current_time = datetime.now()
        cursor.execute('''
            SELECT id, user_id, title, conditions, last_condition_check, condition_check_interval
            FROM tasks
            WHERE status = 'active'
                AND conditions IS NOT NULL
                AND conditions != '[]'
                AND (
                    last_condition_check IS NULL
                    OR datetime(last_condition_check, '+' || condition_check_interval || ' seconds') <= ?
                )
        ''', (current_time,))
        return cursor.fetchall()

    def update_last_condition_check(self, task_id: int):
        """Обновить время последней проверки условий"""
        cursor = self.conn.cursor()
        cursor.execute('''
            UPDATE tasks
            SET last_condition_check = CURRENT_TIMESTAMP
            WHERE id = ?
        ''', (task_id,))
        self.conn.commit()

    def add_reminder(self, task_id: int, user_id: int, reminder_time: datetime, reminder_type: str):
        """Добавить напоминание"""
        cursor = self.conn.cursor()
        cursor.execute('''
            INSERT INTO reminders (task_id, user_id, reminder_time, reminder_type)
            VALUES (?, ?, ?, ?)
        ''', (task_id, user_id, reminder_time, reminder_type))
        self.conn.commit()

    def get_pending_reminders(self) -> List[tuple]:
        """Получить неотправленные напоминания"""
        cursor = self.conn.cursor()
        current_time = datetime.now()
        cursor.execute('''
            SELECT r.id, r.task_id, r.user_id, t.title, r.reminder_type
            FROM reminders r
            JOIN tasks t ON r.task_id = t.id
            WHERE r.is_sent = FALSE
                AND r.reminder_time <= ?
                AND t.status = 'active'
        ''', (current_time,))
        return cursor.fetchall()

    def mark_reminder_sent(self, reminder_id: int):
        """Отметить напоминание как отправленное"""
        cursor = self.conn.cursor()
        cursor.execute('''
            UPDATE reminders
            SET is_sent = TRUE
            WHERE id = ?
        ''', (reminder_id,))
        self.conn.commit()

    def create_category(self, user_id: int, name: str, color: str = None) -> int:
        """Создать категорию"""
        cursor = self.conn.cursor()
        cursor.execute('''
            INSERT INTO categories (user_id, name, color)
            VALUES (?, ?, ?)
        ''', (user_id, name, color))
        self.conn.commit()
        return cursor.lastrowid

    def get_user_categories(self, user_id: int) -> List[tuple]:
        """Получить категории пользователя"""
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT id, name, color
            FROM categories
            WHERE user_id = ?
            ORDER BY name
        ''', (user_id,))
        return cursor.fetchall()

    def reset_database(self):
        """Сброс базы данных"""
        cursor = self.conn.cursor()
        cursor.execute("DROP TABLE IF EXISTS tasks")
        cursor.execute("DROP TABLE IF EXISTS reminders")
        cursor.execute("DROP TABLE IF EXISTS categories")
        self.conn.commit()
        self.setup_database()