"""
Unit тесты для CategoryManager
"""
import pytest
from datetime import datetime
from src.categories.manager import CategoryManager


@pytest.fixture
def category_manager(temp_db):
    """Фикстура для CategoryManager с временной БД"""
    return CategoryManager(temp_db)


@pytest.fixture
def sample_user_id():
    """Тестовый user_id"""
    return 12345


def test_get_or_create_category_new(category_manager, sample_user_id):
    """Тест создания новой категории"""
    category_name = category_manager.get_or_create_category(sample_user_id, "работа")

    assert category_name == "работа"

    # Проверяем, что категория создана в БД
    categories = category_manager.db.get_user_categories(sample_user_id)
    assert len(categories) == 1
    assert categories[0][1] == "работа"


def test_get_or_create_category_existing(category_manager, sample_user_id):
    """Тест получения существующей категории"""
    # Создаём категорию
    category_manager.get_or_create_category(sample_user_id, "работа")

    # Пытаемся создать снова
    category_name = category_manager.get_or_create_category(sample_user_id, "работа")

    assert category_name == "работа"

    # Проверяем, что не создалась дубликат
    categories = category_manager.db.get_user_categories(sample_user_id)
    assert len(categories) == 1


def test_get_or_create_category_case_insensitive(category_manager, sample_user_id):
    """Тест case-insensitive обработки"""
    category_manager.get_or_create_category(sample_user_id, "Работа")
    category_name = category_manager.get_or_create_category(sample_user_id, "РАБОТА")

    assert category_name == "работа"

    # Проверяем, что создана только одна категория
    categories = category_manager.db.get_user_categories(sample_user_id)
    assert len(categories) == 1


def test_get_or_create_category_empty(category_manager, sample_user_id):
    """Тест с пустым названием категории"""
    result = category_manager.get_or_create_category(sample_user_id, "")

    assert result is None


def test_get_or_create_category_with_spaces(category_manager, sample_user_id):
    """Тест обрезания пробелов"""
    category_name = category_manager.get_or_create_category(sample_user_id, "  работа  ")

    assert category_name == "работа"


def test_get_category_display_name_default(category_manager, sample_user_id):
    """Тест отображаемого имени для дефолтной категории"""
    category_manager.get_or_create_category(sample_user_id, "работа")

    display_name = category_manager.get_category_display_name(sample_user_id, "работа")

    assert "🔷" in display_name
    assert "Работа" in display_name


def test_get_category_display_name_custom(category_manager, sample_user_id):
    """Тест отображаемого имени для пользовательской категории"""
    category_manager.create_user_category(sample_user_id, "проект", "🚀")

    display_name = category_manager.get_category_display_name(sample_user_id, "проект")

    assert "🚀" in display_name
    assert "Проект" in display_name


def test_get_category_display_name_empty(category_manager, sample_user_id):
    """Тест отображаемого имени для пустой категории"""
    display_name = category_manager.get_category_display_name(sample_user_id, "")

    assert display_name == ""


def test_get_category_display_name_nonexistent(category_manager, sample_user_id):
    """Тест отображаемого имени для несуществующей категории"""
    display_name = category_manager.get_category_display_name(sample_user_id, "несуществующая")

    # Должна использоваться дефолтная иконка
    assert "📁" in display_name
    assert "Несуществующая" in display_name


def test_format_tasks_by_category_empty(category_manager):
    """Тест форматирования пустого списка задач"""
    message = category_manager.format_tasks_by_category([])

    assert message == "📭 Задач нет"


def test_format_tasks_by_category_with_categories(category_manager, sample_user_id):
    """Тест форматирования задач с категориями"""
    # Создаём категории
    category_manager.get_or_create_category(sample_user_id, "работа")
    category_manager.get_or_create_category(sample_user_id, "дом")

    # Создаём задачи
    tasks = [
        (1, "Задача работа 1", "high", None, "2025-10-10", "работа", None),
        (2, "Задача дом 1", "medium", None, "2025-10-11", "дом", None),
        (3, "Задача работа 2", "low", None, None, "работа", None),
    ]

    message = category_manager.format_tasks_by_category(tasks)

    # Проверяем структуру
    assert "🔷 Работа" in message or "работа" in message.lower()
    assert "🏠 Дом" in message or "дом" in message.lower()
    assert "#1" in message
    assert "#2" in message
    assert "#3" in message


def test_format_tasks_by_category_uncategorized(category_manager):
    """Тест форматирования задач без категории"""
    tasks = [
        (1, "Задача без категории", "medium", None, None, None, None),
        (2, "Ещё задача без категории", "high", None, "2025-10-10", None, None),
    ]

    message = category_manager.format_tasks_by_category(tasks)

    assert "📁 Без категории" in message
    assert "#1" in message
    assert "#2" in message


def test_format_tasks_by_category_priority_emoji(category_manager):
    """Тест отображения эмодзи приоритетов"""
    tasks = [
        (1, "Задача high", "high", None, None, "работа", None),
        (2, "Задача medium", "medium", None, None, "работа", None),
        (3, "Задача low", "low", None, None, "работа", None),
    ]

    message = category_manager.format_tasks_by_category(tasks)

    assert "🔴" in message  # high priority
    assert "🟡" in message  # medium priority
    assert "🟢" in message  # low priority


def test_format_tasks_by_category_with_dates(category_manager):
    """Тест форматирования задач с датами"""
    tasks = [
        (1, "Задача с датой", "medium", None, "2025-10-25", "работа", None),
    ]

    message = category_manager.format_tasks_by_category(tasks)

    # Проверяем формат даты (25.10)
    assert "25.10" in message


def test_get_categories_list_empty(category_manager, sample_user_id):
    """Тест получения списка категорий когда их нет"""
    message = category_manager.get_categories_list(sample_user_id)

    assert "У вас пока нет категорий" in message


def test_get_categories_list(category_manager, sample_user_id):
    """Тест получения списка категорий"""
    # Создаём категории
    category_manager.get_or_create_category(sample_user_id, "работа")
    category_manager.get_or_create_category(sample_user_id, "дом")

    message = category_manager.get_categories_list(sample_user_id)

    assert "Ваши категории" in message
    assert "Работа" in message
    assert "Дом" in message
    assert "🔷" in message  # работа
    assert "🏠" in message  # дом


def test_create_user_category_success(category_manager, sample_user_id):
    """Тест успешного создания пользовательской категории"""
    result = category_manager.create_user_category(sample_user_id, "мой проект", "🎯")

    assert result is True

    categories = category_manager.db.get_user_categories(sample_user_id)
    assert len(categories) == 1
    assert categories[0][1] == "мой проект"
    assert categories[0][2] == "🎯"


def test_create_user_category_duplicate(category_manager, sample_user_id):
    """Тест создания дублирующейся категории"""
    category_manager.create_user_category(sample_user_id, "работа")
    result = category_manager.create_user_category(sample_user_id, "работа")

    assert result is False


def test_create_user_category_default_color(category_manager, sample_user_id):
    """Тест создания категории с дефолтным цветом"""
    result = category_manager.create_user_category(sample_user_id, "покупки")

    assert result is True

    categories = category_manager.db.get_user_categories(sample_user_id)
    # Должна использоваться иконка из default_categories
    assert categories[0][2] == "🛒"


def test_create_user_category_unknown_default_color(category_manager, sample_user_id):
    """Тест создания категории с неизвестным дефолтным цветом"""
    result = category_manager.create_user_category(sample_user_id, "новая_категория")

    assert result is True

    categories = category_manager.db.get_user_categories(sample_user_id)
    # Должна использоваться дефолтная иконка
    assert categories[0][2] == "📁"


def test_get_priority_emoji(category_manager):
    """Тест получения эмодзи приоритета"""
    assert category_manager._get_priority_emoji("high") == "🔴"
    assert category_manager._get_priority_emoji("medium") == "🟡"
    assert category_manager._get_priority_emoji("low") == "🟢"
    assert category_manager._get_priority_emoji("unknown") == "🟡"  # default


def test_default_categories_exist(category_manager):
    """Тест наличия дефолтных категорий"""
    assert "работа" in category_manager.default_categories
    assert "дом" in category_manager.default_categories
    assert "личное" in category_manager.default_categories
    assert "учеба" in category_manager.default_categories

    # Проверяем иконки
    assert category_manager.default_categories["работа"] == "🔷"
    assert category_manager.default_categories["дом"] == "🏠"
    assert category_manager.default_categories["здоровье"] == "🏥"


def test_user_isolation_categories(category_manager):
    """Тест изоляции категорий по пользователям"""
    user1_id = 111
    user2_id = 222

    # Создаём категории для разных пользователей
    category_manager.get_or_create_category(user1_id, "работа")
    category_manager.get_or_create_category(user2_id, "дом")

    # Проверяем изоляцию
    user1_categories = category_manager.db.get_user_categories(user1_id)
    user2_categories = category_manager.db.get_user_categories(user2_id)

    assert len(user1_categories) == 1
    assert len(user2_categories) == 1
    assert user1_categories[0][1] == "работа"
    assert user2_categories[0][1] == "дом"


def test_format_tasks_mixed_categories(category_manager, sample_user_id):
    """Тест форматирования смешанного списка задач"""
    category_manager.get_or_create_category(sample_user_id, "работа")

    tasks = [
        (1, "С категорией", "high", None, "2025-10-10", "работа", None),
        (2, "Без категории", "medium", None, None, None, None),
        (3, "С категорией 2", "low", None, None, "работа", None),
    ]

    message = category_manager.format_tasks_by_category(tasks)

    # Проверяем наличие обеих секций
    assert "Работа" in message or "работа" in message.lower()
    assert "Без категории" in message
    assert "#1" in message
    assert "#2" in message
    assert "#3" in message
