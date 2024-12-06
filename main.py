import asyncio
from datetime import datetime
import sqlite3
import logging
from telethon import TelegramClient, events
from telethon.tl.types import User
from config import API_ID, API_HASH, BOT_TOKEN

# Настройка логирования
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Инициализация базы данных
def init_db():
    conn = sqlite3.connect("user_status.db")
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS status_logs
                 (user_id INTEGER, username TEXT, status TEXT, timestamp DATETIME)''')
    c.execute('''CREATE TABLE IF NOT EXISTS tracked_users
                 (username TEXT UNIQUE)''')  # Таблица для отслеживаемых пользователей
    conn.commit()
    conn.close()

# Инициализация клиента
client = TelegramClient("bot_session", API_ID, API_HASH).start(bot_token=BOT_TOKEN)

# Добавление пользователя для отслеживания
@client.on(events.NewMessage(pattern="/track"))
async def add_user_to_track(event):
    command_args = event.message.text.split()
    if len(command_args) != 2:
        await event.respond("Usage: /track username")
        return
    
    username = command_args[1].replace("@", "")
    conn = sqlite3.connect("user_status.db")
    c = conn.cursor()
    try:
        c.execute("INSERT INTO tracked_users (username) VALUES (?)", (username,))
        conn.commit()
        await event.respond(f"Started tracking @{username}")
    except sqlite3.IntegrityError:
        await event.respond(f"@{username} is already being tracked.")
    finally:
        conn.close()

# Удаление пользователя из отслеживания
@client.on(events.NewMessage(pattern="/untrack"))
async def remove_user_from_track(event):
    command_args = event.message.text.split()
    if len(command_args) != 2:
        await event.respond("Usage: /untrack username")
        return
    
    username = command_args[1].replace("@", "")
    conn = sqlite3.connect("user_status.db")
    c = conn.cursor()
    c.execute("DELETE FROM tracked_users WHERE username = ?", (username,))
    conn.commit()
    conn.close()
    await event.respond(f"Stopped tracking @{username}")

# Отслеживание статуса пользователей
@client.on(events.UserUpdate)
async def handle_user_update(event):
    user: User = await event.get_user()
    if user and not user.bot:
        conn = sqlite3.connect("user_status.db")
        c = conn.cursor()
        c.execute("SELECT 1 FROM tracked_users WHERE username = ?", (user.username,))
        if c.fetchone():  # Проверяем, отслеживается ли пользователь
            status = "online" if event.online else "offline"
            timestamp = datetime.now()

            # Сохранение в базу данных
            c.execute('''INSERT INTO status_logs (user_id, username, status, timestamp)
                         VALUES (?, ?, ?, ?)''',
                      (user.id, user.username, status, timestamp))
            conn.commit()
            logger.info(f"User {user.username} ({user.id}) is now {status} at {timestamp}")
        conn.close()

# Команда для получения отчёта
@client.on(events.NewMessage(pattern="/report"))
async def command_report(event):
    command_args = event.message.text.split()
    if len(command_args) != 2:
        await event.respond("Usage: /report username")
        return

    target_username = command_args[1].replace("@", "")
    conn = sqlite3.connect("user_status.db")
    c = conn.cursor()
    c.execute('''SELECT status, timestamp FROM status_logs 
                 WHERE username = ? ORDER BY timestamp DESC LIMIT 10''', (target_username,))
    records = c.fetchall()
    conn.close()

    if not records:
        await event.respond(f"No records found for user @{target_username}")
        return

    report = f"Status report for @{target_username}:\n\n"
    for status, timestamp in records:
        report += f"• {status} at {timestamp}\n"

    await event.respond(report)

# Запуск бота
def main():
    init_db()
    logger.info("Bot started...")
    client.run_until_disconnected()

if __name__ == "__main__":
    main()
