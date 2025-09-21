from typing import List, Tuple, Optional
from src.database.models import DatabaseManager


class CategoryManager:
    def __init__(self, db: DatabaseManager):
        self.db = db
        self.default_categories = {
            'работа': '🔷',
            'дом': '🏠',
            'личное': '👤',
            'учеба': '📚',
            'здоровье': '🏥',
            'покупки': '🛒',
            'спорт': '⚽',
            'проекты': '🚀'
        }

    def get_or_create_category(self, user_id: int, category_name: str) -> Optional[str]:
        """Получить или создать категорию"""
        if not category_name:
            return None

        category_name = category_name.lower().strip()

        # Проверяем существующие категории пользователя
        user_categories = self.db.get_user_categories(user_id)
        existing_names = [cat[1].lower() for cat in user_categories]

        if category_name in existing_names:
            return category_name

        # Создаем новую категорию
        color = self.default_categories.get(category_name, '📁')
        self.db.create_category(user_id, category_name, color)
        return category_name

    def get_category_display_name(self, user_id: int, category_name: str) -> str:
        """Получить отображаемое имя категории с иконкой"""
        if not category_name:
            return ""

        user_categories = self.db.get_user_categories(user_id)
        for cat_id, name, color in user_categories:
            if name.lower() == category_name.lower():
                return f"{color} {name.title()}"

        # Если категория не найдена, используем дефолтную иконку
        color = self.default_categories.get(category_name.lower(), '📁')
        return f"{color} {category_name.title()}"

    def format_tasks_by_category(self, tasks: List[tuple]) -> str:
        """Форматировать задачи по категориям"""
        if not tasks:
            return "📭 Задач нет"

        # Группируем задачи по категориям
        categorized_tasks = {}
        uncategorized_tasks = []

        for task in tasks:
            task_id, title, priority, conditions, due_date, category, tags = task
            if category:
                if category not in categorized_tasks:
                    categorized_tasks[category] = []
                categorized_tasks[category].append((task_id, title, priority, due_date))
            else:
                uncategorized_tasks.append((task_id, title, priority, due_date))

        message = ""

        # Выводим задачи по категориям
        for category, category_tasks in sorted(categorized_tasks.items()):
            category_display = self.get_category_display_name(0, category)  # user_id нужно передавать
            message += f"\n*{category_display}:*\n"

            for task_id, title, priority, due_date in category_tasks:
                priority_emoji = self._get_priority_emoji(priority)
                date_text = ""
                if due_date:
                    from datetime import datetime
                    date_obj = datetime.strptime(due_date, '%Y-%m-%d')
                    date_text = f" ({date_obj.strftime('%d.%m')})"

                message += f"{priority_emoji} #{task_id} {title}{date_text}\n"

        # Задачи без категории
        if uncategorized_tasks:
            message += "\n*📁 Без категории:*\n"
            for task_id, title, priority, due_date in uncategorized_tasks:
                priority_emoji = self._get_priority_emoji(priority)
                date_text = ""
                if due_date:
                    from datetime import datetime
                    date_obj = datetime.strptime(due_date, '%Y-%m-%d')
                    date_text = f" ({date_obj.strftime('%d.%m')})"

                message += f"{priority_emoji} #{task_id} {title}{date_text}\n"

        return message.strip()

    def get_categories_list(self, user_id: int) -> str:
        """Получить список категорий пользователя"""
        categories = self.db.get_user_categories(user_id)

        if not categories:
            return "📁 У вас пока нет категорий"

        message = "📂 *Ваши категории:*\n\n"
        for cat_id, name, color in categories:
            emoji = color or '📁'
            message += f"{emoji} {name.title()}\n"

        return message

    def _get_priority_emoji(self, priority: str) -> str:
        """Получить эмодзи для приоритета"""
        return {
            'high': '🔴',
            'medium': '🟡',
            'low': '🟢'
        }.get(priority, '🟡')

    def create_user_category(self, user_id: int, category_name: str, color: str = None) -> bool:
        """Создать пользовательскую категорию"""
        try:
            category_name = category_name.lower().strip()

            # Проверяем, что категория не существует
            user_categories = self.db.get_user_categories(user_id)
            existing_names = [cat[1].lower() for cat in user_categories]

            if category_name in existing_names:
                return False

            if not color:
                color = self.default_categories.get(category_name, '📁')

            self.db.create_category(user_id, category_name, color)
            return True

        except Exception as e:
            print(f"Ошибка создания категории: {e}")
            return False