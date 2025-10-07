"""
Pytest configuration and shared fixtures
"""
import pytest
import sqlite3
import tempfile
import os
from datetime import datetime, timedelta
from unittest.mock import Mock, AsyncMock, MagicMock

import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.database.models import DatabaseManager
from src.reminders.smart_scheduler import SmartReminderScheduler, Reminder
from src.config.manager import ConfigManager


@pytest.fixture
def temp_db():
    """Temporary in-memory database for testing"""
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
        db_path = f.name

    db = DatabaseManager(db_path)
    yield db

    # Cleanup
    db.conn.close()
    if os.path.exists(db_path):
        os.unlink(db_path)


@pytest.fixture
def sample_user_id():
    """Sample user ID for tests"""
    return 123456789


@pytest.fixture
def sample_task_data():
    """Sample task data"""
    return {
        'title': 'Тестовая задача',
        'description': 'Описание тестовой задачи',
        'priority': 'high',
        'due_date': '2025-10-10',
        'due_time': '15:00',
        'has_specific_time': True,
        'category': 'работа',
        'tags': ['важное', 'срочное'],
        'conditions': [],
        'reminder_needed': False,
        'reminder_time': None
    }


@pytest.fixture
def mock_telegram_bot():
    """Mock Telegram Bot"""
    bot = AsyncMock()
    bot.send_message = AsyncMock()
    return bot


@pytest.fixture
def mock_gemini_api(monkeypatch):
    """Mock Gemini API responses"""
    mock_response = Mock()
    mock_response.text = '''{
        "title": "Тестовая задача",
        "description": "Описание",
        "conditions": [],
        "priority": "medium",
        "context": [],
        "due_date": "2025-10-10",
        "due_time": "15:00",
        "has_specific_date": true,
        "has_specific_time": true,
        "category": "работа",
        "tags": ["тест"],
        "reminder_needed": false,
        "reminder_time": null
    }'''

    mock_model = Mock()
    mock_model.generate_content = Mock(return_value=mock_response)

    def mock_GenerativeModel(*args, **kwargs):
        return mock_model

    import src.ai.gemini_processor as gp
    monkeypatch.setattr(gp.genai, 'GenerativeModel', mock_GenerativeModel)

    return mock_model


@pytest.fixture
async def mock_send_reminder():
    """Mock callback for sending reminders"""
    async def send_reminder(user_id: int, message: str, reminder_type: str):
        pass
    return AsyncMock(side_effect=send_reminder)


@pytest.fixture
async def smart_scheduler(temp_db, mock_send_reminder):
    """SmartReminderScheduler with test database"""
    scheduler = SmartReminderScheduler(temp_db, mock_send_reminder)
    yield scheduler
    scheduler.stop_scheduler()


@pytest.fixture
def test_config():
    """Test configuration"""
    config_data = {
        'reminders': {
            'scheduler': {
                'type': 'smart',
                'initial_lookahead_hours': 72,
                'daily_reload_window': [48, 72],
                'cleanup_time': '23:55',
                'config_reload_time': '03:00',
                'old_reminders_retention_days': 7
            },
            'deadline_reminders': [
                {'days_before': 1, 'time': '09:00'}
            ],
            'time_based_reminders': {
                'enabled': True,
                'hours_before': [3, 1],
                'minutes_before': []
            }
        }
    }
    return config_data


@pytest.fixture
def freeze_time(monkeypatch):
    """Helper to freeze datetime.now() for tests"""
    def _freeze(frozen_time: datetime):
        class FrozenDatetime:
            @staticmethod
            def now():
                return frozen_time

            @staticmethod
            def today():
                return frozen_time.date()

        from datetime import datetime as dt
        monkeypatch.setattr('datetime.datetime', FrozenDatetime)

    return _freeze
