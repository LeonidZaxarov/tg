import telebot
from telebot import types
import logging
import os
from dotenv import load_dotenv
import sqlite3
from datetime import datetime

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Загрузка токена
load_dotenv()
BOT_TOKEN = os.getenv('BOT_TOKEN')

if not BOT_TOKEN:
    logger.error("❌ BOT_TOKEN не найден! Проверьте файл .env")
    exit(1)

# Создаем бота
bot = telebot.TeleBot(BOT_TOKEN)
logger.info("✅ Бот создан")

# ========== БАЗА ДАННЫХ ==========

def init_database():
    """Инициализация базы данных"""
    conn = sqlite3.connect('events_bot.db')
    cursor = conn.cursor()
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            first_name TEXT,
            step TEXT DEFAULT 'start',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS applications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            event_info TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (user_id)
        )
    ''')
    
    conn.commit()
    conn.close()
    logger.info("✅ База данных инициализирована")

def get_user_step(user_id):
    """Получить шаг пользователя"""
    conn = sqlite3.connect('events_bot.db')
    cursor = conn.cursor()
    cursor.execute('SELECT step FROM users WHERE user_id = ?', (user_id,))
    result = cursor.fetchone()
    conn.close()
    
    if result:
        logger.info(f"🔍 Получен шаг пользователя {user_id}: {result[0]}")
        return result[0]
    else:
        logger.info(f"🔍 Пользователь {user_id} не найден в БД, возвращаем 'start'")
        return 'start'

def update_user_step(user_id, step, username=None, first_name=None):
    """Обновить шаг пользователя"""
    conn = sqlite3.connect('events_bot.db')
    cursor = conn.cursor()
    
    # Проверяем, существует ли пользователь
    cursor.execute('SELECT 1 FROM users WHERE user_id = ?', (user_id,))
    user_exists = cursor.fetchone()
    
    if user_exists:
        # Обновляем существующего пользователя
        cursor.execute('UPDATE users SET step = ? WHERE user_id = ?', (step, user_id))
        logger.info(f"🔄 Шаг пользователя {user_id} обновлен на: {step}")
    else:
        # Создаем нового пользователя
        cursor.execute(
            'INSERT INTO users (user_id, username, first_name, step) VALUES (?, ?, ?, ?)',
            (user_id, username, first_name, step)
        )
        logger.info(f"👤 Создан новый пользователь {user_id} с шагом: {step}")
    
    conn.commit()
    conn.close()

def save_application(user_id, event_info):
    """Сохранить заявку"""
    conn = sqlite3.connect('events_bot.db')
    cursor = conn.cursor()
    cursor.execute(
        'INSERT INTO applications (user_id, event_info) VALUES (?, ?)',
        (user_id, event_info)
    )
    conn.commit()
    conn.close()
    logger.info(f"✅ Заявка сохранена для пользователя {user_id}")

# Инициализируем БД
init_database()

# ========== ОБРАБОТЧИКИ ==========

@bot.message_handler(commands=['start'])
def handle_start(message):
    """Обработчик команды /start"""
    user_id = message.from_user.id
    username = message.from_user.username
    first_name = message.from_user.first_name
    
    logger.info(f"👤 Пользователь {user_id} запустил бота")
    
    # Устанавливаем шаг 'awaiting_info' для пользователя
    update_user_step(user_id, 'awaiting_info', username, first_name)
    
    # Приветственное сообщение
    welcome_text = (
        f"🎉 Здравствуйте, {first_name}!\n\n"
        "Спасибо, что обратились в Event Agency 'CONCEPT'. Чтобы наши менеджеры смогли дать наиболее точный ответ, поделитесь, пожалуйста, следующей информацией:\n\n"
        "• Тип события (день рождения, свадьба и т.д.)\n"
        "• Дата проведения мероприятия\n"
        "• Место проведения\n"
        "• Примерное количество гостей\n"
        "• Контактный номер телефона\n\n"
        "📝 Вы можете отправить информацию одним сообщением!\n\n"
        "Ждем ваших ответов! 🎊\n"
        "Свяжемся с Вами в ближайшее время!"
    )
    
    bot.send_message(message.chat.id, welcome_text)
    logger.info(f"✅ Приветствие отправлено пользователю {user_id}")

@bot.message_handler(commands=['help'])
def handle_help(message):
    """Обработчик команды /help"""
    help_text = (
        "📋 Доступные команды:\n"
        "/start - начать общение с ботом\n"
        "/help - показать эту справку\n\n"
        "После команды /start просто отправьте информацию о вашем мероприятии!"
    )
    bot.send_message(message.chat.id, help_text)

@bot.message_handler(commands=['status'])
def handle_status(message):
    """Обработчик команды /status"""
    user_id = message.from_user.id
    step = get_user_step(user_id)
    
    if step == 'info_received':
        status_text = "✅ Вы уже предоставили информацию. Наш менеджер свяжется с вами в ближайшее время!"
    elif step == 'awaiting_info':
        status_text = "⏳ Мы ждем информацию о вашем мероприятии. Пожалуйста, отправьте данные."
    else:
        status_text = "💡 Используйте /start чтобы начать общение с ботом."
    
    bot.send_message(message.chat.id, status_text)

# ГЛАВНЫЙ ОБРАБОТЧИК ВСЕХ СООБЩЕНИЙ
@bot.message_handler(func=lambda message: True)
def handle_all_messages(message):
    """Обработчик всех сообщений"""
    user_id = message.from_user.id
    user_text = message.text if message.text else ""
    
    # Логируем полученное сообщение
    logger.info(f"📩 Получено сообщение от {user_id}: '{user_text}' (длина: {len(user_text)})")
    
    # Получаем текущий шаг пользователя
    current_step = get_user_step(user_id)
    logger.info(f"🔍 Текущий шаг пользователя {user_id}: {current_step}")
    
    # Если это команда - пропускаем (она обработается другими обработчиками)
    if user_text.startswith('/'):
        logger.info(f"⚡ Пропускаем команду: {user_text}")
        return
    
    # Если пользователь в состоянии ожидания информации
    if current_step == 'awaiting_info':
        logger.info(f"📝 Пользователь {user_id} предоставил информацию")
        
        # Сохраняем информацию о мероприятии (даже если это один символ)
        save_application(user_id, user_text)
        
        # Обновляем шаг пользователя
        update_user_step(user_id, 'info_received')
        
        # Отправляем благодарственное сообщение
        gratitude_text = (
            "✅ Спасибо за предоставленную информацию!\n\n"
            "В ближайшее время к работе с Вами подключится наш менеджер. "
            "Мы ценим сотрудничество с Вами и готовы ответить на любые вопросы."
        )
        
        bot.send_message(message.chat.id, gratitude_text)
        logger.info(f"✅ Благодарность отправлена пользователю {user_id}")
        
    else:
        # Стандартный ответ для пользователей не в состоянии ожидания информации
        response_text = (
            f"🔊 Вы написали: '{user_text}'\n\n"
            "💡 Для оформления заявки на мероприятие используйте команду /start"
        )
        bot.send_message(message.chat.id, response_text)
        logger.info(f"📤 Стандартный ответ отправлен пользователю {user_id}")

# ========== ЗАПУСК БОТА ==========

if __name__ == '__main__':
    logger.info("🚀 Запуск бота...")
    logger.info("📱 Найдите бота в Telegram и отправьте /start")
    logger.info("⏹️  Для остановки нажмите Ctrl+C")
    
    try:
        bot.polling(none_stop=True, interval=0, timeout=60)
    except Exception as e:
        logger.error(f"❌ Ошибка при работе бота: {e}")
    finally:
        logger.info("🛑 Бот остановлен")