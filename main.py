import os
import warnings
import logging
import asyncio
from threading import Thread

# Отключаем предупреждения Google
os.environ['GRPC_VERBOSITY'] = 'ERROR'
os.environ['GLOG_minloglevel'] = '2'
warnings.filterwarnings('ignore')
logging.getLogger('absl').setLevel(logging.ERROR)

from dotenv import load_dotenv
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

from src.database.models import DatabaseManager
from src.telegram_handlers.handlers import TaskBotHandlers
from src.reminders.scheduler import ReminderScheduler

load_dotenv()

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# Отключение HTTP логов
logging.getLogger('httpx').setLevel(logging.WARNING)
logging.getLogger('telegram').setLevel(logging.WARNING)

logger = logging.getLogger(__name__)


class ModularTaskBot:
    def __init__(self):
        # Инициализация компонентов
        self.telegram_token = os.getenv('TELEGRAM_TOKEN')
        self.db = DatabaseManager()
        self.handlers = TaskBotHandlers(self.db)

        # Инициализация планировщика напоминаний
        self.reminder_scheduler = ReminderScheduler(
            db=self.db,
            send_reminder_callback=self.send_reminder
        )

        # Telegram Application
        self.app = None

    async def send_reminder(self, user_id: int, message: str, reminder_type: str):
        """Колбэк для отправки напоминаний"""
        try:
            if self.app:
                await self.app.bot.send_message(
                    chat_id=user_id,
                    text=message,
                    parse_mode='Markdown'
                )
                logger.info(f"Отправлено напоминание пользователю {user_id}: {reminder_type}")
        except Exception as e:
            logger.error(f"Ошибка отправки напоминания пользователю {user_id}: {e}")

    def setup_handlers(self):
        """Настройка обработчиков команд"""
        # Команды
        self.app.add_handler(CommandHandler("start", self.handlers.start))
        self.app.add_handler(CommandHandler("today", self.handlers.show_today))
        self.app.add_handler(CommandHandler("week", self.handlers.show_week))
        self.app.add_handler(CommandHandler("all", self.handlers.show_all))
        self.app.add_handler(CommandHandler("categories", self.handlers.show_categories))
        self.app.add_handler(CommandHandler("category", self.handlers.show_category_tasks))
        self.app.add_handler(CommandHandler("done", self.handlers.mark_done))
        self.app.add_handler(CommandHandler("myid", self.handlers.get_my_id))
        self.app.add_handler(CommandHandler("reset_db", self.handlers.reset_database))

        # Обработка сообщений
        self.app.add_handler(MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            self.handlers.handle_message
        ))

        # Обработка голосовых сообщений
        self.app.add_handler(MessageHandler(
            filters.VOICE,
            self.handlers.handle_voice_message
        ))

        logger.info("Обработчики команд настроены")

    def start_reminder_scheduler(self):
        """Запуск планировщика напоминаний в отдельном потоке"""
        def run_scheduler():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(self.reminder_scheduler.start_scheduler())

        scheduler_thread = Thread(target=run_scheduler, daemon=True)
        scheduler_thread.start()
        logger.info("Планировщик напоминаний запущен в отдельном потоке")

    async def setup_bot(self):
        """Асинхронная настройка бота"""
        self.app = Application.builder().token(self.telegram_token).build()
        self.setup_handlers()

    def run(self):
        """Запуск бота"""
        try:
            # Создаем event loop для основного потока
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

            # Асинхронная настройка
            loop.run_until_complete(self.setup_bot())

            # Запуск планировщика напоминаний
            self.start_reminder_scheduler()

            logger.info("🤖 Модульный бот запущен! Нажмите Ctrl+C для остановки.")

            # Запуск polling
            self.app.run_polling()

        except KeyboardInterrupt:
            logger.info("Получен сигнал остановки")
        except Exception as e:
            logger.error(f"Критическая ошибка: {e}")
        finally:
            # Остановка планировщика
            self.reminder_scheduler.stop_scheduler()
            logger.info("Бот остановлен")


if __name__ == "__main__":
    bot = ModularTaskBot()
    bot.run()