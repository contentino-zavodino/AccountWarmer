"""Конфигурация скрипта прогрева аккаунтов (Dolphin{anty} / BitBrowser) с защитой от детекта."""

from __future__ import annotations
import os
from typing import List, Dict, Any

class Config:
    # Тип используемого антидетект-браузера: "bitbrowser" или "dolphin"
    BROWSER_TYPE: str = "bitbrowser"

    # --- Настройки Dolphin{anty} ---
    # Порт по умолчанию: 3001 (используем 127.0.0.1 для стабильности на Mac)
    DOLPHIN_API_URL: str = "http://127.0.0.1:3001"
    # Опционально: токен API из Dolphin{anty} (Настройки -> API)
    DOLPHIN_API_TOKEN: str = os.getenv("DOLPHIN_API_TOKEN", "")
    # Пауза (в секундах) между запуском профиля и подключением CDP для полной инжекции отпечатков Dolphin
    DOLPHIN_STARTUP_DELAY: float = 4.0

    # --- Настройки мобильных прокси ---
    # Ссылка для ротации мобильного прокси (Change IP URL).
    # Если заполнена, скрипт перед стартом профиля отправляет GET-запрос и ждет PROXY_ROTATION_DELAY секунд.
    PROXY_ROTATION_URL: str = ""
    PROXY_ROTATION_DELAY: int = 8  # Пауза в секундах для смены IP мобильным оператором

    # --- Настройки нагуливания куков (Cookie Warmup) ---
    # Если True, перед переходом в TikTok/YouTube профиль посетит 1–2 нейтральных сайта для сбора куки
    COOKIE_WARMUP: bool = False
    COOKIE_WARMUP_SITES: List[str] = [
        "https://www.google.com",
        "https://en.wikipedia.org",
        "https://www.yahoo.com",
        "https://news.ycombinator.com",
        "https://weather.com"
    ]

    # --- Настройки BitBrowser ---
    BITBROWSER_API_URL: str = "http://127.0.0.1:54345"

    # Список ID профилей браузера (Dolphin или BitBrowser).
    # Оставлен пустым [] для авто-определения: под YouTube выберет YouTube-профили, под TikTok — TikTok-профили.
    PROFILE_IDS: List[str] = []

    # Режим работы по умолчанию: "tiktok", "youtube" или "combined"
    DEFAULT_PLATFORM_MODE: str = "tiktok"

    # Максимальное количество одновременно работающих профилей (3-5)
    MAX_CONCURRENT_PROFILES: int = 3

    # Количество просматриваемых видео на один аккаунт за сессию
    VIDEOS_PER_SESSION_MIN: int = 35
    VIDEOS_PER_SESSION_MAX: int = 70

    # Распределение времени просмотра:
    WATCH_PROFILES = [
        {"type": "quick_swipe",  "range": (2.0, 5.0),   "weight": 0.70},  # Быстрый пропуск 2-5 сек (70%)
        {"type": "medium_watch", "range": (6.0, 11.0),  "weight": 0.22},  # Заинтересовало 6-11 сек (22%)
        {"type": "long_watch",   "range": (12.0, 19.0), "weight": 0.08},  # Досмотрел интересное 12-19 сек (8%)
    ]

    # --- Настройки TikTok ---
    TIKTOK_START_URL: str = "https://www.tiktok.com/foryou"
    TIKTOK_LIKE_PROBABILITY: float = 0.10          # ~10% видео
    TIKTOK_FAVORITE_PROBABILITY: float = 0.03      # ~3% видео
    TIKTOK_READ_COMMENTS_PROBABILITY: float = 0.05  # ~5% видео чтение комментариев

    # --- Настройки YouTube Shorts ---
    YOUTUBE_START_URL: str = "https://www.youtube.com/shorts"
    YOUTUBE_LIKE_PROBABILITY: float = 0.10         # ~10% видео
    YOUTUBE_SUBSCRIBE_PROBABILITY: float = 0.03    # ~3% подписка на канал
    YOUTUBE_READ_COMMENTS_PROBABILITY: float = 0.06 # ~6% видео чтение комментариев

    # Размеры окон для отображения на экране
    WINDOW_WIDTH: int = 430
    WINDOW_HEIGHT: int = 800

    # Таймауты (в секундах)
    PAGE_LOAD_TIMEOUT: int = 45
