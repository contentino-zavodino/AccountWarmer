"""Модуль органического взаимодействия со страницей YouTube Shorts (просмотр, лайки, подписки, чтение комментариев)."""

from __future__ import annotations
import asyncio
import logging
import random
from typing import Optional, Any

try:
    from playwright.async_api import Page
except ImportError:
    Page = Any  # type: ignore

from base_bot import BasePlatformBot
from config import Config
from gestures import human_next_video, natural_click, natural_move, natural_scroll_comments, get_viewport_dimensions

logger = logging.getLogger("youtube_bot")

class YouTubeBot(BasePlatformBot):
    """Управляет действиями аккаунта в веб-версии YouTube Shorts с максимальной имитацией человека."""

    def __init__(self, page: Page, profile_id: str, profile_tag: str = ""):
        super().__init__(page=page, profile_id=profile_id, profile_tag=profile_tag, platform_name="YouTube")

    async def init_session(self):
        """Открывает ленту YouTube Shorts и готовит плеер к просмотру."""
        current_url = self.page.url
        if "youtube.com/shorts" not in current_url:
            self.log("Переход в ленту YouTube Shorts...")
            try:
                await self.page.goto(
                    Config.YOUTUBE_START_URL,
                    wait_until="domcontentloaded",
                    timeout=Config.PAGE_LOAD_TIMEOUT * 1000
                )
            except Exception as e:
                self.log(f"Предупреждение при переходе: {e}")
        else:
            self.log("Страница YouTube Shorts уже открыта, подключаемся...")

        try:
            await self.page.bring_to_front()
        except Exception:
            pass

        await asyncio.sleep(2.0)
        await self._dismiss_popups()
        await self._unmute_if_needed()

        # Фокусируем видео для готовности плеера к клавиатурному управлению
        vw, vh = await get_viewport_dimensions(self.page)
        cx = vw * 0.5 + random.uniform(-15, 15)
        cy = vh * 0.45 + random.uniform(-15, 15)
        try:
            await natural_click(self.page, cx, cy)
            self.log("Плеер YouTube Shorts сфокусирован и готов.")
        except Exception:
            pass

    async def _dismiss_popups(self):
        """Закрывает окна согласия Google (Consent dialogs), промо YouTube Premium и баннеры."""
        popup_selectors = [
            'button:has-text("Accept all")',
            'button:has-text("Принять все")',
            'button:has-text("I agree")',
            'button:has-text("Согласиться")',
            'button:has-text("Reject all")',
            'button:has-text("Отклонить все")',
            'tp-yt-paper-dialog button:has-text("No thanks")',
            'tp-yt-paper-dialog button:has-text("Не сейчас")',
            'yt-button-renderer:has-text("Не сейчас")',
            'ytd-button-renderer:has-text("No thanks")',
            'button[aria-label="Dismiss"]',
            'button[aria-label="Закрыть"]',
        ]
        for sel in popup_selectors:
            try:
                el = await self.page.query_selector(sel)
                if el and await el.is_visible():
                    box = await el.bounding_box()
                    if box:
                        await natural_click(self.page, box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
                        await asyncio.sleep(0.6)
            except Exception:
                pass

    async def _unmute_if_needed(self):
        """Включает звук, если видео загрузилось без звука."""
        try:
            unmute_selectors = [
                'ytd-reel-video-renderer[is-active] button[aria-label*="Unmute"]',
                'ytd-reel-video-renderer[is-active] button[aria-label*="Включить звук"]',
                'button[aria-label*="Unmute"]',
                'button[aria-label*="Включить звук"]',
            ]
            for sel in unmute_selectors:
                btn = await self.page.query_selector(sel)
                if btn and await btn.is_visible():
                    box = await btn.bounding_box()
                    if box:
                        await natural_click(self.page, box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
                        self.log("[Звук] Включен звук в плеере.")
                        await asyncio.sleep(0.4)
                        break
        except Exception:
            pass

    async def is_ad_video(self) -> bool:
        """Проверяет, является ли активный YouTube Short рекламным (Sponsored)."""
        try:
            is_ad = await self.page.evaluate('''() => {
                const activeReel = document.querySelector('ytd-reel-video-renderer[is-active]');
                if (!activeReel) return false;

                // 1. Проверяем рекламные контейнеры внутри активного ролика
                if (activeReel.querySelector('ytd-ad-slot-renderer, [class*="badge-style-type-ad"], #ad-badge, [class*="ytd-ad-"], [class*="ad-container"]')) {
                    return true;
                }

                // 2. Проверяем текстовые бейджи рекламы
                const badges = activeReel.querySelectorAll('.ytd-badge-supported-renderer, span, div, p');
                for (const b of badges) {
                    const text = (b.innerText || '').trim().toLowerCase();
                    if (['sponsored', 'реклама', 'promoted'].includes(text)) {
                        return true;
                    }
                }
                return false;
            }''')
            return bool(is_ad)
        except Exception:
            return False

    async def watch_video(self, video_idx: int, total_videos: int):
        """Просмотр ролика Shorts с пропуском рекламы."""
        if await self.is_ad_video():
            self.log(f"[{video_idx}/{total_videos}] [Реклама] Обнаружен рекламный Short (Sponsored). Быстрый пропуск...")
            await asyncio.sleep(random.uniform(1.8, 3.2))
            return
        await super().watch_video(video_idx, total_videos)

    async def maybe_like(self) -> bool:
        """Ставит лайк текущему Short через клик по кнопке с пальцем вверх (пропуская рекламу)."""
        if await self.is_ad_video():
            return False

        if random.random() > Config.YOUTUBE_LIKE_PROBABILITY:
            return False

        try:
            # Ищем кнопку лайка в активном видео
            like_selectors = [
                'ytd-reel-video-renderer[is-active] #like-button button',
                'ytd-reel-video-renderer[is-active] #like-button yt-button-shape button',
                '#like-button button[aria-pressed="false"]',
                '#like-button button',
            ]
            for sel in like_selectors:
                btn = await self.page.query_selector(sel)
                if btn and await btn.is_visible():
                    pressed = await btn.get_attribute("aria-pressed")
                    if pressed == "true":
                        # Уже лайкнуто
                        return False

                    box = await btn.bounding_box()
                    if box:
                        cx = box["x"] + box["width"] / 2 + random.uniform(-2, 2)
                        cy = box["y"] + box["height"] / 2 + random.uniform(-2, 2)
                        await natural_click(self.page, cx, cy)
                        self.log("[Лайк] Поставлен лайк текущему Short.")
                        await asyncio.sleep(random.uniform(0.5, 0.9))
                        return True
        except Exception as e:
            self.log(f"Предупреждение при постановке лайка в YouTube: {e}")
        return False

    async def maybe_secondary_action(self) -> bool:
        """
        Выполняет редкую органическую подписку на канал автора Shorts (~2-4%).
        Очень сильный сигнал доверия алгоритмов YouTube (на рекламу не подписывается).
        """
        if await self.is_ad_video():
            return False

        if random.random() > Config.YOUTUBE_SUBSCRIBE_PROBABILITY:
            return False

        try:
            sub_selectors = [
                'ytd-reel-video-renderer[is-active] #subscribe-button button',
                'ytd-reel-video-renderer[is-active] yt-subscribe-button-view-model button',
                'ytd-reel-video-renderer[is-active] ytd-subscribe-button-renderer button',
            ]
            for sel in sub_selectors:
                btn = await self.page.query_selector(sel)
                if btn and await btn.is_visible():
                    text = (await btn.inner_text()).lower()
                    # Проверяем, что еще не подписаны
                    if any(w in text for w in ["subscribed", "подписаны", "вы подписаны"]):
                        return False

                    box = await btn.bounding_box()
                    if box:
                        cx = box["x"] + box["width"] / 2 + random.uniform(-3, 3)
                        cy = box["y"] + box["height"] / 2 + random.uniform(-2, 2)
                        await natural_click(self.page, cx, cy)
                        self.log("[Подписка] Оформлена подписка на автора Shorts!")
                        await asyncio.sleep(random.uniform(0.6, 1.2))
                        return True
        except Exception as e:
            self.log(f"Предупреждение при оформлении подписки: {e}")
        return False

    async def maybe_explore_comments(self) -> bool:
        """
        Имитирует чтение комментариев в Shorts:
        1. Нажимает кнопку комментариев.
        2. Дожидается открытия боковой/нижней панели.
        3. Скроллит и читает 2-4 комментария.
        4. Закрывает панель комментариев.
        """
        if await self.is_ad_video():
            return False

        if random.random() > Config.YOUTUBE_READ_COMMENTS_PROBABILITY:
            return False

        try:
            comment_selectors = [
                'ytd-reel-video-renderer[is-active] #comments-button button',
                'ytd-reel-video-renderer[is-active] #comments-button yt-button-shape button',
                '#comments-button button',
            ]
            for sel in comment_selectors:
                btn = await self.page.query_selector(sel)
                if btn and await btn.is_visible():
                    box = await btn.bounding_box()
                    if box:
                        self.log("[Комментарии] Открываем блок комментариев Shorts для чтения...")
                        await natural_click(self.page, box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
                        await asyncio.sleep(random.uniform(1.2, 2.0))

                        # Находим контейнер комментариев
                        panel = await self.page.query_selector(
                            'ytd-engagement-panel-section-list-renderer[target-id="engagement-panel-comments-section"], #contents.ytd-item-section-renderer'
                        )
                        panel_box = await panel.bounding_box() if panel else None

                        # Скроллим и читаем комментарии
                        await natural_scroll_comments(self.page, panel_box)

                        # Закрываем панель комментариев
                        close_selectors = [
                            'ytd-engagement-panel-section-list-renderer[target-id="engagement-panel-comments-section"] #visibility-button button',
                            '#visibility-button button',
                            'button[aria-label*="Close"]',
                            'button[aria-label*="Закрыть"]',
                        ]
                        closed = False
                        for csel in close_selectors:
                            cbtn = await self.page.query_selector(csel)
                            if cbtn and await cbtn.is_visible():
                                cbox = await cbtn.bounding_box()
                                if cbox:
                                    await natural_click(self.page, cbox["x"] + cbox["width"] / 2, cbox["y"] + cbox["height"] / 2)
                                    closed = True
                                    break
                        if not closed:
                            await self.page.keyboard.press("Escape")

                        self.log("[Комментарии] Просмотр комментариев YouTube завершен.")
                        await asyncio.sleep(random.uniform(0.5, 0.8))
                        return True
        except Exception as e:
            self.log(f"Предупреждение при просмотре комментариев YouTube: {e}")
            try:
                await self.page.keyboard.press("Escape")
            except Exception:
                pass
        return False

    async def next_video(self) -> bool:
        """Переход к следующему видео в ленте YouTube Shorts."""
        return await human_next_video(self.page, platform="youtube")
