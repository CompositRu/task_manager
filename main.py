import os
import warnings
import logging

# Отключаем предупреждения Google
os.environ['GRPC_VERBOSITY'] = 'ERROR'
os.environ['GLOG_minloglevel'] = '2'
warnings.filterwarnings('ignore')
logging.getLogger('absl').setLevel(logging.ERROR)

import json
import sqlite3
from datetime import datetime, timedelta, date
# from dateutil import parser
# from dateutil.relativedelta import relativedelta
import re
from dotenv import load_dotenv
import google.generativeai as genai
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

load_dotenv()

class TaskBot:
    def __init__(self):
        # Настройка API
        self.telegram_token = os.getenv('TELEGRAM_TOKEN')
        genai.configure(api_key=os.getenv('GEMINI_API_KEY'))
        self.model = genai.GenerativeModel('gemini-1.5-flash')
        
        # База данных
        self.setup_database()
        
    def setup_database(self):
        self.conn = sqlite3.connect('tasks.db', check_same_thread=False)
        cursor = self.conn.cursor()
        
        # Обновленная схема БД с полем due_date
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
                status TEXT DEFAULT 'active',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        self.conn.commit()
    
    def process_with_gemini(self, text):
        """Обработка текста через Gemini с извлечением дат"""
        current_date = datetime.now().strftime("%Y-%m-%d")
        current_day = datetime.now().strftime("%A")
        
        prompt = f"""
        Сегодня {current_date} ({current_day}).
        
        Проанализируй текст и создай структурированную задачу.
        Ответь ТОЛЬКО валидным JSON без markdown разметки:
        {{
            "title": "короткое название задачи",
            "description": "подробное описание",
            "conditions": ["условие 1", "условие 2"],
            "priority": "high/medium/low",
            "context": ["дом", "работа", "дорога"],
            "due_date": "YYYY-MM-DD или null",
            "has_specific_date": true/false
        }}
        
        Правила извлечения даты:
        - Если упоминается конкретная дата (3 октября, 15.11, etc) - укажи её в формате YYYY-MM-DD
        - Если упоминается день недели (вторник, в пятницу) - вычисли ближайшую дату
        - Если упоминается "завтра", "послезавтра" - вычисли дату
        - Если даты нет - установи null
        - has_specific_date = true если в тексте есть указание на время
        
        Текст: {text}
        """
        
        try:
            response = self.model.generate_content(prompt)
            json_text = response.text.strip()
            if json_text.startswith('```'):
                json_text = json_text.split('```')[1]
                if json_text.startswith('json'):
                    json_text = json_text[4:]
            
            result = json.loads(json_text.strip())
            
            # Дополнительная обработка дат на стороне Python
            if result.get('due_date'):
                try:
                    # Проверяем валидность даты
                    parsed_date = datetime.strptime(result['due_date'], '%Y-%m-%d')
                    result['due_date'] = parsed_date.strftime('%Y-%m-%d')
                except:
                    result['due_date'] = None
                    
            return result
            
        except Exception as e:
            print(f"Ошибка Gemini: {e}")
            return {
                "title": text[:50],
                "description": text,
                "conditions": [],
                "priority": "medium",
                "context": [],
                "due_date": None,
                "has_specific_date": False
            }
    
    def save_task(self, user_id, raw_text, structured):
        """Сохранение задачи в БД"""
        cursor = self.conn.cursor()
        cursor.execute('''
            INSERT INTO tasks (user_id, raw_text, title, description, conditions, priority, due_date)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (
            user_id,
            raw_text,
            structured['title'],
            structured.get('description', ''),
            json.dumps(structured.get('conditions', []), ensure_ascii=False),
            structured.get('priority', 'medium'),
            structured.get('due_date')
        ))
        self.conn.commit()
        return cursor.lastrowid
    
    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработка новой задачи"""
        user_id = update.effective_user.id
        message_text = update.message.text
        
        await update.message.chat.send_action(action="typing")
        
        # Обработка через Gemini
        structured = self.process_with_gemini(message_text)
        
        # Сохранение
        task_id = self.save_task(user_id, message_text, structured)
        
        # Формирование ответа
        conditions_text = ""
        if structured.get('conditions'):
            conditions_text = "\n📌 Условия: " + ", ".join(structured['conditions'])
        
        date_text = ""
        if structured.get('due_date'):
            date_obj = datetime.strptime(structured['due_date'], '%Y-%m-%d')
            date_text = f"\n📅 Дата: {date_obj.strftime('%d.%m.%Y')}"
        
        priority_emoji = {
            'high': '🔴',
            'medium': '🟡', 
            'low': '🟢'
        }.get(structured.get('priority', 'medium'), '🟡')
        
        await update.message.reply_text(
            f"✅ Задача #{task_id} сохранена!\n\n"
            f"📝 *{structured['title']}*\n"
            f"{priority_emoji} Приоритет: {structured.get('priority', 'medium')}"
            f"{date_text}"
            f"{conditions_text}",
            parse_mode='Markdown'
        )
    
    async def show_today(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Показать задачи на сегодня"""
        user_id = update.effective_user.id
        today = date.today().strftime('%Y-%m-%d')
        
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT id, title, priority, conditions, due_date 
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
        ''', (user_id, today))
        
        tasks = cursor.fetchall()
        
        if not tasks:
            await update.message.reply_text("📭 На сегодня задач нет")
            return
        
        message = f"📋 *Задачи на сегодня ({datetime.now().strftime('%d.%m.%Y')}):*\n\n"
        
        # Сначала задачи с датой на сегодня
        tasks_with_date = [t for t in tasks if t[4] is not None]
        tasks_without_date = [t for t in tasks if t[4] is None]
        
        if tasks_with_date:
            message += "*🎯 Запланировано на сегодня:*\n"
            for task_id, title, priority, conditions, due_date in tasks_with_date:
                priority_emoji = {'high': '🔴', 'medium': '🟡', 'low': '🟢'}.get(priority, '🟡')
                message += f"{priority_emoji} #{task_id} {title}\n"
        
        if tasks_without_date:
            message += "\n*📝 Задачи без конкретной даты:*\n"
            for task_id, title, priority, conditions, due_date in tasks_without_date:
                priority_emoji = {'high': '🔴', 'medium': '🟡', 'low': '🟢'}.get(priority, '🟡')
                message += f"{priority_emoji} #{task_id} {title}\n"
        
        await update.message.reply_text(message, parse_mode='Markdown')
    
    async def show_all(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Показать все активные задачи"""
        user_id = update.effective_user.id
        
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT id, title, priority, conditions, due_date 
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
        
        tasks = cursor.fetchall()
        
        if not tasks:
            await update.message.reply_text("📭 Нет активных задач")
            return
        
        message = "📋 *Все активные задачи:*\n\n"
        
        # Группировка по датам
        tasks_by_date = {}
        tasks_no_date = []
        
        for task_id, title, priority, conditions, due_date in tasks:
            if due_date:
                if due_date not in tasks_by_date:
                    tasks_by_date[due_date] = []
                tasks_by_date[due_date].append((task_id, title, priority))
            else:
                tasks_no_date.append((task_id, title, priority))
        
        # Вывод задач с датами
        for task_date in sorted(tasks_by_date.keys()):
            date_obj = datetime.strptime(task_date, '%Y-%m-%d')
            message += f"*📅 {date_obj.strftime('%d.%m.%Y')}:*\n"
            
            for task_id, title, priority in tasks_by_date[task_date]:
                priority_emoji = {'high': '🔴', 'medium': '🟡', 'low': '🟢'}.get(priority, '🟡')
                message += f"{priority_emoji} #{task_id} {title}\n"
            message += "\n"
        
        # Задачи без даты
        if tasks_no_date:
            message += "*📝 Без конкретной даты:*\n"
            for task_id, title, priority in tasks_no_date:
                priority_emoji = {'high': '🔴', 'medium': '🟡', 'low': '🟢'}.get(priority, '🟡')
                message += f"{priority_emoji} #{task_id} {title}\n"
        
        await update.message.reply_text(message, parse_mode='Markdown')
    
    async def show_week(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Показать задачи на неделю"""
        user_id = update.effective_user.id
        today = date.today()
        week_end = today + timedelta(days=7)
        
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT id, title, priority, due_date 
            FROM tasks 
            WHERE user_id = ? 
                AND status = 'active'
                AND due_date >= ? 
                AND due_date <= ?
            ORDER BY due_date, priority
        ''', (user_id, today.strftime('%Y-%m-%d'), week_end.strftime('%Y-%m-%d')))
        
        tasks = cursor.fetchall()
        
        if not tasks:
            await update.message.reply_text("📭 На ближайшую неделю задач нет")
            return
        
        message = "📅 *Задачи на неделю:*\n\n"
        
        for task_id, title, priority, due_date in tasks:
            date_obj = datetime.strptime(due_date, '%Y-%m-%d')
            priority_emoji = {'high': '🔴', 'medium': '🟡', 'low': '🟢'}.get(priority, '🟡')
            message += f"{date_obj.strftime('%d.%m')} {priority_emoji} #{task_id} {title}\n"
        
        await update.message.reply_text(message, parse_mode='Markdown')
    
    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда /start"""
        await update.message.reply_text(
            "👋 Привет! Я помогу организовать твои задачи.\n\n"
            "Просто отправь мне задачу текстом.\n\n"
            "Команды:\n"
            "/today - задачи на сегодня\n"
            "/week - задачи на неделю\n"
            "/all - все активные задачи\n"
            "/done [id] - отметить выполненной"
            "/reset_db - удаление базы данных (только админ)"
        )
    
    async def mark_done(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Отметить задачу выполненной"""
        if not context.args:
            await update.message.reply_text("Укажите ID задачи: /done 123")
            return
        
        try:
            task_id = int(context.args[0])
            user_id = update.effective_user.id
            
            cursor = self.conn.cursor()
            cursor.execute('''
                UPDATE tasks 
                SET status = 'done' 
                WHERE id = ? AND user_id = ?
            ''', (task_id, user_id))
            self.conn.commit()
            
            if cursor.rowcount > 0:
                await update.message.reply_text(f"✅ Задача #{task_id} выполнена!")
            else:
                await update.message.reply_text(f"Задача #{task_id} не найдена")
        except ValueError:
            await update.message.reply_text("Неверный формат. Используйте: /done 123")
    
    async def get_my_id(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Показать ID пользователя"""
        user_id = update.effective_user.id
        await update.message.reply_text(f"Ваш Telegram ID: `{user_id}`", parse_mode='Markdown')


    async def reset_database(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Сброс базы данных (только для админа)"""
        user_id = update.effective_user.id
        
        # Получаем ID админа из переменных окружения
        admin_id = os.getenv('ADMIN_TELEGRAM_ID')
        
        # Если не задан админ, команда недоступна
        if not admin_id:
            await update.message.reply_text("❌ Админ не настроен")
            return
        
        # Проверяем права
        if str(user_id) != admin_id:
            await update.message.reply_text("❌ У вас нет прав для этой команды")
            return
        
        # Подтверждение
        if not context.args or context.args[0] != 'confirm':
            await update.message.reply_text(
                "⚠️ Это удалит ВСЕ задачи!\n"
                "Для подтверждения используйте:\n"
                "`/reset_db confirm`",
                parse_mode='Markdown'
            )
            return
        
        try:
            cursor = self.conn.cursor()
            cursor.execute("DROP TABLE IF EXISTS tasks")
            self.conn.commit()
            self.setup_database()  # Создаём таблицу заново
            await update.message.reply_text("✅ База данных успешно сброшена!")
        except Exception as e:
            await update.message.reply_text(f"❌ Ошибка: {e}")

    def run(self):
        """Запуск бота"""
        app = Application.builder().token(self.telegram_token).build()
        
        # Регистрация обработчиков
        app.add_handler(CommandHandler("start", self.start))
        app.add_handler(CommandHandler("today", self.show_today))
        app.add_handler(CommandHandler("week", self.show_week))
        app.add_handler(CommandHandler("all", self.show_all))
        app.add_handler(CommandHandler("done", self.mark_done))
        app.add_handler(CommandHandler("myid", self.get_my_id))
        app.add_handler(CommandHandler("reset_db", self.reset_database))
        app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message))
        
        print("🤖 Бот запущен! Нажмите Ctrl+C для остановки.")
        app.run_polling()

if __name__ == "__main__":
    bot = TaskBot()
    bot.run()