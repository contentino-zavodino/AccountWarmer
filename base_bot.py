"""Базовый абстрактный класс бота для платформ видеоконтента."""

from __future__ import annotations
import asyncio
import logging
import random
from typing import Tuple, List, Dict, Any, Optional

try:
    from playwright.async_api import Page
except ImportError:
    Page = Any  # type: ignore
from config import Config
from gestures import natural_move

logger = logging.getLogger("base_bot")

class BasePlatformBot:
    """Базовый класс, определяющий жизненный цикл взаимодействия с лентой коротких видео."""

    def __init__(self, page: Page, profile_id: str, profile_tag: str = "", platform_name: str = "Base"):
        self.page = page
        self.profile_id = profile_id
        self.tag = profile_tag or profile_id[:8]
        self.platform_name = platform_name

    def log(self, message: str):
        """Информационный вывод с меткой профиля и платформы."""
        prefix = f"[{self.tag} | {self.platform_name}]"
        try:
            print(f"{prefix} {message}")
        except Exception:
            safe_msg = message.encode("ascii", errors="replace").decode("ascii")
            print(f"{prefix} {safe_msg}")

    def calculate_watch_time(self, video_idx: int) -> Tuple[float, str]:
        """Определяет время просмотра видео на основе распределения в Config."""
        if video_idx == 1:
            return random.uniform(3.0, 5.0), "Стартовый просмотр"

        profile = random.choices(
            Config.WATCH_PROFILES,
            weights=[p["weight"] for p in Config.WATCH_PROFILES]
        )[0]

        min_t, max_t = profile["range"]
        watch_time = random.uniform(min_t, max_t)

        type_names = {
            "quick_swipe": "Быстрый пропуск",
            "medium_watch": "Обычный просмотр",
            "long_watch": "Внимательный просмотр",
        }
        return watch_time, type_names.get(profile["type"], profile["type"])

    async def watch_video(self, video_idx: int, total_videos: int):
        """Эмулирует просмотр текущего ролика с естественным поведением."""
        watch_time, type_name = self.calculate_watch_time(video_idx)
        self.log(f"[{video_idx}/{total_videos}] {type_name}: {watch_time:.1f} сек...")

        # Если видео смотрится дольше 5 секунд, имитируем легкое микродвижение курсора
        if watch_time > 5.0:
            part1 = watch_time * random.uniform(0.35, 0.55)
            await asyncio.sleep(part1)

            if random.random() < 0.4:
                viewport = self.page.viewport_size or {"width": 430, "height": 800}
                rx = viewport["width"] * random.uniform(0.3, 0.7)
                ry = viewport["height"] * random.uniform(0.35, 0.65)
                await natural_move(self.page, rx, ry)

            await asyncio.sleep(watch_time - part1)
        else:
            await asyncio.sleep(watch_time)

    async def init_session(self):
        """Инициализация сессии на платформе."""
        raise NotImplementedError

    async def maybe_like(self) -> bool:
        """Постановка лайка с заданной вероятностью."""
        raise NotImplementedError

    async def maybe_secondary_action(self) -> bool:
        """Вторичное действие (избранное в TikTok, подписка в YouTube)."""
        raise NotImplementedError

    async def maybe_explore_comments(self) -> bool:
        """Просмотр и чтение комментариев."""
        raise NotImplementedError

    async def is_ad_video(self) -> bool:
        """Проверяет, является ли текущее видео рекламным (Sponsored)."""
        return False

    async def next_video(self) -> bool:
        """Переход к следующему видео."""
        raise NotImplementedError
