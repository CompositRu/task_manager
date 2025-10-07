import os
import yaml
from typing import Dict, Any, List
from pathlib import Path


class ConfigManager:
    """Менеджер конфигурации для Task Manager Bot"""

    def __init__(self, config_path: str = None):
        if config_path is None:
            # Путь к config.yaml в корне проекта
            config_path = Path(__file__).parent.parent.parent / "config.yaml"

        self.config_path = config_path
        self.config = self._load_config()

    def _load_config(self) -> Dict[str, Any]:
        """Загрузка конфигурации из YAML файла"""
        try:
            if not os.path.exists(self.config_path):
                print(f"Warning: Config file not found at {self.config_path}, using defaults")
                return self._get_default_config()

            with open(self.config_path, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
                return config if config else self._get_default_config()

        except Exception as e:
            print(f"Error loading config: {e}, using defaults")
            return self._get_default_config()

    def _get_default_config(self) -> Dict[str, Any]:
        """Конфигурация по умолчанию"""
        return {
            'reminders': {
                'scheduler': {
                    'type': 'smart',
                    'initial_lookahead_hours': 72,
                    'daily_reload_window': [48, 72],
                    'cleanup_time': '23:55',
                    'config_reload_time': '03:00',
                    'old_reminders_retention_days': 7
                },
                'check_interval': 3600,  # Для обратной совместимости
                'deadline_reminders': [
                    {'days_before': 2, 'time': '09:00'},
                    {'days_before': 1, 'time': '18:00'},
                    {'days_before': 0, 'time': '10:00'},
                    {'days_before': 0, 'time': '16:00'}
                ],
                'time_based_reminders': {
                    'enabled': True,
                    'hours_before': [3, 1],
                    'minutes_before': []
                },
                'condition_checks': {
                    'default_interval': 86400,
                    'default_time': '10:00'
                },
                'morning_reminders': {
                    'enabled': True,
                    'time': '09:00'
                }
            },
            'general': {
                'timezone': 'Europe/Moscow',
                'min_reminder_interval': 60
            }
        }

    def get_check_interval(self) -> int:
        """Получить интервал проверки планировщика (в секундах)"""
        return self.config.get('reminders', {}).get('check_interval', 3600)

    def get_deadline_reminders(self) -> List[Dict[str, Any]]:
        """Получить список настроек напоминаний о дедлайнах"""
        return self.config.get('reminders', {}).get('deadline_reminders', [])

    def get_condition_check_interval(self) -> int:
        """Получить интервал проверки условий (в секундах)"""
        return self.config.get('reminders', {}).get('condition_checks', {}).get('default_interval', 86400)

    def get_condition_check_time(self) -> str:
        """Получить время проверки условий"""
        return self.config.get('reminders', {}).get('condition_checks', {}).get('default_time', '10:00')

    def get_morning_reminder_time(self) -> str:
        """Получить время утренних напоминаний"""
        return self.config.get('reminders', {}).get('morning_reminders', {}).get('time', '09:00')

    def is_morning_reminders_enabled(self) -> bool:
        """Проверить, включены ли утренние напоминания"""
        return self.config.get('reminders', {}).get('morning_reminders', {}).get('enabled', True)

    def get_timezone(self) -> str:
        """Получить временную зону"""
        return self.config.get('general', {}).get('timezone', 'Europe/Moscow')

    def get_min_reminder_interval(self) -> int:
        """Получить минимальный интервал между напоминаниями (в минутах)"""
        return self.config.get('general', {}).get('min_reminder_interval', 60)

    def get_time_based_reminders_config(self) -> Dict[str, Any]:
        """Получить конфигурацию напоминаний для задач с точным временем"""
        return self.config.get('reminders', {}).get('time_based_reminders', {
            'enabled': True,
            'hours_before': [3, 1],
            'minutes_before': []
        })

    def is_time_based_reminders_enabled(self) -> bool:
        """Проверить, включены ли напоминания для задач с точным временем"""
        return self.get_time_based_reminders_config().get('enabled', True)

    def get_time_based_hours_before(self) -> List[int]:
        """Получить список интервалов (в часах) для напоминаний с точным временем"""
        return self.get_time_based_reminders_config().get('hours_before', [3, 1])

    def get_time_based_minutes_before(self) -> List[int]:
        """Получить список интервалов (в минутах) для напоминаний с точным временем"""
        return self.get_time_based_reminders_config().get('minutes_before', [])

    def get_scheduler_type(self) -> str:
        """Получить тип планировщика (smart или polling)"""
        return self.config.get('reminders', {}).get('scheduler', {}).get('type', 'smart')

    def get_scheduler_config(self) -> Dict[str, Any]:
        """Получить полную конфигурацию планировщика"""
        return self.config.get('reminders', {}).get('scheduler', {
            'type': 'smart',
            'initial_lookahead_hours': 72,
            'daily_reload_window': [48, 72],
            'cleanup_time': '23:55',
            'config_reload_time': '03:00',
            'old_reminders_retention_days': 7
        })

    def reload_config(self):
        """Перезагрузить конфигурацию из файла"""
        self.config = self._load_config()
        print("Configuration reloaded successfully")
