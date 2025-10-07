"""
Модуль клавиатур для Telegram бота
"""
from telegram import ReplyKeyboardMarkup, InlineKeyboardButton, InlineKeyboardMarkup
from typing import List, Optional


class KeyboardBuilder:
    """Класс для создания клавиатур"""

    @staticmethod
    def get_main_menu_keyboard() -> ReplyKeyboardMarkup:
        """
        Главная Reply клавиатура (постоянная панель)
        """
        keyboard = [
            ['📋 Сегодня', '📅 Неделя'],
            ['✅ Все задачи', '📂 Категории'],
            ['⚙️ Настройки', '❓ Помощь']
        ]
        return ReplyKeyboardMarkup(
            keyboard,
            resize_keyboard=True,
            one_time_keyboard=False
        )

    @staticmethod
    def get_task_actions_keyboard(task_id: int) -> InlineKeyboardMarkup:
        """
        Inline клавиатура для действий с задачей

        Args:
            task_id: ID задачи
        """
        keyboard = [
            [
                InlineKeyboardButton("✅ Выполнено", callback_data=f"task_done:{task_id}"),
                InlineKeyboardButton("✏️ Изменить", callback_data=f"task_edit:{task_id}")
            ],
            [
                InlineKeyboardButton("🔔 Отложить 15м", callback_data=f"task_snooze:{task_id}:15"),
                InlineKeyboardButton("🔔 Отложить 1ч", callback_data=f"task_snooze:{task_id}:60")
            ],
            [
                InlineKeyboardButton("🗑 Удалить", callback_data=f"task_delete:{task_id}")
            ]
        ]
        return InlineKeyboardMarkup(keyboard)

    @staticmethod
    def get_task_list_keyboard(tasks: List[tuple]) -> InlineKeyboardMarkup:
        """
        Inline клавиатура со списком задач

        Args:
            tasks: Список задач из БД (tuples)
        """
        keyboard = []
        for task in tasks:
            task_id = task[0]
            title = task[2][:40]  # Ограничиваем длину

            keyboard.append([
                InlineKeyboardButton(f"✅ {title}", callback_data=f"task_done:{task_id}"),
                InlineKeyboardButton("👁", callback_data=f"task_view:{task_id}")
            ])

        return InlineKeyboardMarkup(keyboard)

    @staticmethod
    def get_categories_keyboard(categories: List[tuple]) -> InlineKeyboardMarkup:
        """
        Inline клавиатура с категориями

        Args:
            categories: Список категорий из БД (id, name, color)
        """
        keyboard = []
        row = []

        for i, cat in enumerate(categories):
            cat_id, name, color = cat
            row.append(InlineKeyboardButton(
                f"{color} {name.title()}",
                callback_data=f"category_view:{name}"
            ))

            # По 2 кнопки в ряду
            if len(row) == 2:
                keyboard.append(row)
                row = []

        # Добавить остаток
        if row:
            keyboard.append(row)

        # Кнопка "Все задачи"
        keyboard.append([
            InlineKeyboardButton("📋 Все задачи", callback_data="category_view:all")
        ])

        return InlineKeyboardMarkup(keyboard)

    @staticmethod
    def get_priority_keyboard() -> InlineKeyboardMarkup:
        """
        Клавиатура выбора приоритета
        """
        keyboard = [
            [
                InlineKeyboardButton("🔴 Высокий", callback_data="priority:high"),
                InlineKeyboardButton("🟡 Средний", callback_data="priority:medium"),
                InlineKeyboardButton("🟢 Низкий", callback_data="priority:low")
            ]
        ]
        return InlineKeyboardMarkup(keyboard)

    @staticmethod
    def get_snooze_keyboard(task_id: int) -> InlineKeyboardMarkup:
        """
        Клавиатура для отложения напоминания

        Args:
            task_id: ID задачи
        """
        keyboard = [
            [
                InlineKeyboardButton("15 минут", callback_data=f"task_snooze:{task_id}:15"),
                InlineKeyboardButton("30 минут", callback_data=f"task_snooze:{task_id}:30")
            ],
            [
                InlineKeyboardButton("1 час", callback_data=f"task_snooze:{task_id}:60"),
                InlineKeyboardButton("3 часа", callback_data=f"task_snooze:{task_id}:180")
            ],
            [
                InlineKeyboardButton("Завтра", callback_data=f"task_snooze:{task_id}:1440")
            ]
        ]
        return InlineKeyboardMarkup(keyboard)

    @staticmethod
    def get_confirmation_keyboard(action: str, item_id: int) -> InlineKeyboardMarkup:
        """
        Клавиатура подтверждения действия

        Args:
            action: Тип действия (delete, reset, etc.)
            item_id: ID элемента
        """
        keyboard = [
            [
                InlineKeyboardButton("✅ Да", callback_data=f"confirm:{action}:{item_id}"),
                InlineKeyboardButton("❌ Нет", callback_data=f"cancel:{action}")
            ]
        ]
        return InlineKeyboardMarkup(keyboard)

    @staticmethod
    def get_settings_keyboard() -> InlineKeyboardMarkup:
        """
        Клавиатура настроек
        """
        keyboard = [
            [
                InlineKeyboardButton("🔔 Напоминания", callback_data="settings_reminders")
            ],
            [
                InlineKeyboardButton("📂 Категории", callback_data="settings_categories")
            ],
            [
                InlineKeyboardButton("⏰ Время уведомлений", callback_data="settings_time")
            ],
            [
                InlineKeyboardButton("« Назад", callback_data="settings_back")
            ]
        ]
        return InlineKeyboardMarkup(keyboard)

    @staticmethod
    def get_reminder_settings_keyboard() -> InlineKeyboardMarkup:
        """
        Клавиатура настроек напоминаний
        """
        keyboard = [
            [
                InlineKeyboardButton("🌅 Утренние напоминания", callback_data="reminder_morning")
            ],
            [
                InlineKeyboardButton("📅 Напоминания о дедлайнах", callback_data="reminder_deadline")
            ],
            [
                InlineKeyboardButton("⏱ Временные напоминания", callback_data="reminder_timed")
            ],
            [
                InlineKeyboardButton("« Назад", callback_data="settings_back")
            ]
        ]
        return InlineKeyboardMarkup(keyboard)

    @staticmethod
    def get_back_button(callback_data: str = "back") -> InlineKeyboardMarkup:
        """
        Простая кнопка "Назад"

        Args:
            callback_data: Callback данные для кнопки
        """
        keyboard = [[InlineKeyboardButton("« Назад", callback_data=callback_data)]]
        return InlineKeyboardMarkup(keyboard)

    @staticmethod
    def remove_keyboard() -> dict:
        """
        Убрать клавиатуру (для ReplyKeyboard)
        """
        from telegram import ReplyKeyboardRemove
        return {"reply_markup": ReplyKeyboardRemove()}
