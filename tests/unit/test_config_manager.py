"""
Unit тесты для ConfigManager
"""
import pytest
import yaml
from pathlib import Path
from src.config.manager import ConfigManager


@pytest.fixture
def test_config_data():
    """Тестовые данные конфигурации"""
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
            'check_interval': 1800,
            'deadline_reminders': [
                {'days_before': 2, 'time': '09:00'},
                {'days_before': 1, 'time': '18:00'}
            ],
            'time_based_reminders': {
                'enabled': True,
                'hours_before': [2, 1],
                'minutes_before': [30, 15]
            },
            'condition_checks': {
                'default_interval': 43200,
                'default_time': '12:00'
            },
            'morning_reminders': {
                'enabled': True,
                'time': '08:00'
            }
        },
        'general': {
            'timezone': 'Europe/London',
            'min_reminder_interval': 30
        }
    }


@pytest.fixture
def test_config_file(tmp_path, test_config_data):
    """Создать временный файл конфигурации"""
    config_file = tmp_path / "test_config.yaml"
    with open(config_file, 'w', encoding='utf-8') as f:
        yaml.dump(test_config_data, f)
    return config_file


def test_load_config_from_file(test_config_file):
    """Тест загрузки конфигурации из файла"""
    config_manager = ConfigManager(config_path=test_config_file)

    assert config_manager.config is not None
    assert 'reminders' in config_manager.config
    assert 'general' in config_manager.config


def test_load_config_nonexistent_file(tmp_path):
    """Тест загрузки конфигурации из несуществующего файла"""
    nonexistent_file = tmp_path / "nonexistent.yaml"

    config_manager = ConfigManager(config_path=nonexistent_file)

    # Должна загрузиться конфигурация по умолчанию
    assert config_manager.config is not None
    assert config_manager.get_scheduler_type() == 'smart'


def test_get_check_interval(test_config_file):
    """Тест получения интервала проверки"""
    config_manager = ConfigManager(config_path=test_config_file)

    assert config_manager.get_check_interval() == 1800


def test_get_check_interval_default():
    """Тест получения интервала проверки по умолчанию"""
    config_manager = ConfigManager(config_path="/nonexistent/path")

    assert config_manager.get_check_interval() == 3600


def test_get_deadline_reminders(test_config_file):
    """Тест получения настроек напоминаний о дедлайнах"""
    config_manager = ConfigManager(config_path=test_config_file)

    deadline_reminders = config_manager.get_deadline_reminders()

    assert len(deadline_reminders) == 2
    assert deadline_reminders[0]['days_before'] == 2
    assert deadline_reminders[0]['time'] == '09:00'
    assert deadline_reminders[1]['days_before'] == 1
    assert deadline_reminders[1]['time'] == '18:00'


def test_get_condition_check_interval(test_config_file):
    """Тест получения интервала проверки условий"""
    config_manager = ConfigManager(config_path=test_config_file)

    assert config_manager.get_condition_check_interval() == 43200


def test_get_condition_check_time(test_config_file):
    """Тест получения времени проверки условий"""
    config_manager = ConfigManager(config_path=test_config_file)

    assert config_manager.get_condition_check_time() == '12:00'


def test_get_morning_reminder_time(test_config_file):
    """Тест получения времени утренних напоминаний"""
    config_manager = ConfigManager(config_path=test_config_file)

    assert config_manager.get_morning_reminder_time() == '08:00'


def test_is_morning_reminders_enabled(test_config_file):
    """Тест проверки включения утренних напоминаний"""
    config_manager = ConfigManager(config_path=test_config_file)

    assert config_manager.is_morning_reminders_enabled() is True


def test_get_timezone(test_config_file):
    """Тест получения временной зоны"""
    config_manager = ConfigManager(config_path=test_config_file)

    assert config_manager.get_timezone() == 'Europe/London'


def test_get_min_reminder_interval(test_config_file):
    """Тест получения минимального интервала напоминаний"""
    config_manager = ConfigManager(config_path=test_config_file)

    assert config_manager.get_min_reminder_interval() == 30


def test_get_time_based_reminders_config(test_config_file):
    """Тест получения конфигурации напоминаний с точным временем"""
    config_manager = ConfigManager(config_path=test_config_file)

    config = config_manager.get_time_based_reminders_config()

    assert config['enabled'] is True
    assert config['hours_before'] == [2, 1]
    assert config['minutes_before'] == [30, 15]


def test_is_time_based_reminders_enabled(test_config_file):
    """Тест проверки включения напоминаний с точным временем"""
    config_manager = ConfigManager(config_path=test_config_file)

    assert config_manager.is_time_based_reminders_enabled() is True


def test_get_time_based_hours_before(test_config_file):
    """Тест получения интервалов в часах для напоминаний"""
    config_manager = ConfigManager(config_path=test_config_file)

    hours_before = config_manager.get_time_based_hours_before()

    assert hours_before == [2, 1]


def test_get_time_based_minutes_before(test_config_file):
    """Тест получения интервалов в минутах для напоминаний"""
    config_manager = ConfigManager(config_path=test_config_file)

    minutes_before = config_manager.get_time_based_minutes_before()

    assert minutes_before == [30, 15]


def test_get_scheduler_type(test_config_file):
    """Тест получения типа планировщика"""
    config_manager = ConfigManager(config_path=test_config_file)

    assert config_manager.get_scheduler_type() == 'smart'


def test_get_scheduler_config(test_config_file):
    """Тест получения полной конфигурации планировщика"""
    config_manager = ConfigManager(config_path=test_config_file)

    scheduler_config = config_manager.get_scheduler_config()

    assert scheduler_config['type'] == 'smart'
    assert scheduler_config['initial_lookahead_hours'] == 72
    assert scheduler_config['daily_reload_window'] == [48, 72]
    assert scheduler_config['cleanup_time'] == '23:55'
    assert scheduler_config['config_reload_time'] == '03:00'
    assert scheduler_config['old_reminders_retention_days'] == 7


def test_reload_config(test_config_file, test_config_data):
    """Тест перезагрузки конфигурации"""
    config_manager = ConfigManager(config_path=test_config_file)

    # Исходный интервал
    assert config_manager.get_check_interval() == 1800

    # Изменяем файл конфигурации
    test_config_data['reminders']['check_interval'] = 2400
    with open(test_config_file, 'w', encoding='utf-8') as f:
        yaml.dump(test_config_data, f)

    # Перезагружаем конфигурацию
    config_manager.reload_config()

    # Проверяем новое значение
    assert config_manager.get_check_interval() == 2400


def test_invalid_yaml_file(tmp_path):
    """Тест загрузки невалидного YAML файла"""
    invalid_config = tmp_path / "invalid.yaml"
    with open(invalid_config, 'w') as f:
        f.write("{ invalid yaml content : [ unclosed")

    config_manager = ConfigManager(config_path=invalid_config)

    # Должна загрузиться конфигурация по умолчанию
    assert config_manager.config is not None
    assert config_manager.get_scheduler_type() == 'smart'


def test_empty_yaml_file(tmp_path):
    """Тест загрузки пустого YAML файла"""
    empty_config = tmp_path / "empty.yaml"
    empty_config.write_text("")

    config_manager = ConfigManager(config_path=empty_config)

    # Должна загрузиться конфигурация по умолчанию
    assert config_manager.config is not None
    assert config_manager.get_check_interval() == 3600


def test_partial_config(tmp_path):
    """Тест частичной конфигурации (отсутствующие секции)"""
    partial_config = tmp_path / "partial.yaml"
    partial_data = {
        'reminders': {
            'check_interval': 5000
        }
    }

    with open(partial_config, 'w', encoding='utf-8') as f:
        yaml.dump(partial_data, f)

    config_manager = ConfigManager(config_path=partial_config)

    # Существующее значение
    assert config_manager.get_check_interval() == 5000

    # Значения по умолчанию для отсутствующих секций
    assert config_manager.get_timezone() == 'Europe/Moscow'
    assert config_manager.get_scheduler_type() == 'smart'


def test_default_config_structure():
    """Тест структуры конфигурации по умолчанию"""
    config_manager = ConfigManager(config_path="/nonexistent/path")

    default_config = config_manager._get_default_config()

    # Проверяем наличие всех основных секций
    assert 'reminders' in default_config
    assert 'general' in default_config

    # Проверяем структуру reminders
    assert 'scheduler' in default_config['reminders']
    assert 'check_interval' in default_config['reminders']
    assert 'deadline_reminders' in default_config['reminders']
    assert 'time_based_reminders' in default_config['reminders']
    assert 'condition_checks' in default_config['reminders']
    assert 'morning_reminders' in default_config['reminders']

    # Проверяем структуру scheduler
    scheduler = default_config['reminders']['scheduler']
    assert 'type' in scheduler
    assert 'initial_lookahead_hours' in scheduler
    assert 'daily_reload_window' in scheduler

    # Проверяем значения по умолчанию
    assert scheduler['type'] == 'smart'
    assert scheduler['initial_lookahead_hours'] == 72
    assert default_config['general']['timezone'] == 'Europe/Moscow'


def test_missing_nested_keys():
    """Тест получения значений при отсутствующих вложенных ключах"""
    config_manager = ConfigManager(config_path="/nonexistent/path")

    # Удаляем некоторые вложенные ключи
    config_manager.config = {'reminders': {}}

    # Должны вернуться значения по умолчанию
    assert config_manager.get_check_interval() == 3600
    assert config_manager.get_deadline_reminders() == []
    assert config_manager.is_morning_reminders_enabled() is True
