import os

from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")

# ID пользователей Telegram, которым доступны команды разработчика.
# В Railway/локальном .env указываются через запятую: ADMIN_IDS=111111111,222222222
ADMIN_IDS = [int(x) for x in os.getenv("ADMIN_IDS", "").split(",") if x.strip().isdigit()]

# Путь к файлу базы данных SQLite.
# На Railway обязательно подключите Volume и укажите путь внутри него
# (например /data/bot.db), иначе база будет стираться при каждом деплое.
DB_PATH = os.getenv("DB_PATH", "bot.db")

if not BOT_TOKEN:
    raise RuntimeError(
        "BOT_TOKEN не задан. Добавьте его в переменные окружения (.env локально "
        "или Variables в Railway)."
    )

if not ADMIN_IDS:
    print(
        "⚠️  ADMIN_IDS не задан — команды /addcode, /delcode, /stats, /addch, "
        "/delch, /ch будут недоступны никому."
    )
