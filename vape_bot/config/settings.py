"""Конфігурація бота. Завантаження .env, константи, категорії."""

import os
from pathlib import Path

from dotenv import load_dotenv

# Завантаження .env з кореня проєкту
env_path = Path(__file__).resolve().parent.parent.parent / ".env"
load_dotenv(env_path)

# === Telegram ===
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
NOTIFICATION_CHANNEL_ID = os.getenv("NOTIFICATION_CHANNEL_ID", "")

# === Poster CRM ===
POSTER_ACCOUNT = os.getenv("POSTER_ACCOUNT", "")
POSTER_TOKEN = os.getenv("POSTER_TOKEN", "")
POSTER_API_URL = f"https://{POSTER_ACCOUNT}.joinposter.com/api"

# === Supabase ===
SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "")

# === Bot settings ===
MANAGER_USERNAME = os.getenv("MANAGER_USERNAME", "")
CACHE_TTL_MINUTES = int(os.getenv("CACHE_TTL_MINUTES", "10"))
PRODUCTS_PER_PAGE = 10
STORAGE_ID = int(os.getenv("STORAGE_ID", "1"))

# === Категорії (захардкоджені з Poster API, дата: 2026-04-08) ===
# Структура: кореневі → підкатегорії (бренди)
# Повний список товарів: output/poster_api_data.md

ROOT_CATEGORIES = {
    4: "Pod-системи",
    7: "Комплектуючі",
    23: "Набори",
    37: "SHISHA",
}

SUBCATEGORIES = {
    # Pod-системи (id:4)
    4: {
        15: "ElfBar",
        16: "GeekVape",
        17: "LostVape",
        18: "OXVA",
        19: "SMOK",
        20: "Vaporesso",
        21: "VooPoo",
        35: "ZQ",
    },
    # Комплектуючі (id:7)
    7: {
        8: "Картриджі Vaporesso",
        9: "Картриджі Elf Bar",
        10: "Картриджі GeekVape",
        11: "Картриджі LostVape",
        12: "Картриджі OXVA",
        13: "Картриджі SMOK",
        14: "Картриджі VooPoo",
        34: "Випарник Voopoo",
        36: "Картриджі ZQ",
    },
    # Набори / рідини (id:23)
    23: {
        5: "Cheser",
        6: "Гліцерини",
        22: "Alchemist",
        24: "InBottle",
        25: "Lucky",
        26: "FL350",
        27: "Fluffy Puff Organic",
        28: "Octobar",
        29: "Infinity Max",
        30: "Refrost",
        31: "SteamPuff",
        32: "Wick&Wire",
        33: "Бустер",
        43: "Troublemaker",
    },
    # SHISHA (id:37)
    37: {
        38: "Вугілля",
        39: "Кальяни",
    },
}

# Підкатегорії третього рівня (Кальяни → ...)
SUBCATEGORIES_L3 = {
    39: {
        40: "Аксесуари",
        41: "Колби",
        42: "Чаші",
    },
}
