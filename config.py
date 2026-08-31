import os

from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHANNEL_USERNAME = os.getenv("CHANNEL_USERNAME", "@zangorafilm")

# Reklama tugmasi bosilganda foydalanuvchi shu admin bilan yozishmaga o'tadi
ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "auwsn")

# Admin telegram ID lari (vergul bilan ajratilgan), masalan: ADMIN_IDS=123456789,987654321
ADMIN_IDS = [int(x) for x in os.getenv("ADMIN_IDS", "").split(",") if x.strip().isdigit()]

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN topilmadi! .env faylida BOT_TOKEN ni belgilang.")
