"""Модуль органического взаимодействия со страницей TikTok (просмотр, нативные клики, чтение комментариев)."""

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
from gestures import human_next_video, natural_click, natural_double_click, natural_move, natural_scroll_comments, get_viewport_dimensions

logger = logging.getLogger("tiktok_bot")

class TikTokBot(BasePlatformBot):
    """Управляет действиями аккаунта в веб-версии TikTok с максимальной имитацией человека."""

    def __init__(self, page: Page, profile_id: str, profile_tag: str = ""):
        super().__init__(page=page, profile_id=profile_id, profile_tag=profile_tag, platform_name="TikTok")

    async def init_session(self):
        """Открывает TikTok For You и активирует ленту."""
        current_url = self.page.url
        if "tiktok.com/foryou" not in current_url:
            self.log("Переход в ленту рекомендаций TikTok For You...")
            try:
                await self.page.goto(Config.TIKTOK_START_URL, wait_until="domcontentloaded", timeout=Config.PAGE_LOAD_TIMEOUT * 1000)
            except Exception as e:
                self.log(f"Предупреждение при переходе: {e}")
        else:
            self.log("Лента TikTok For You уже открыта, подключаемся...")

        try:
            await self.page.bring_to_front()
        except Exception:
            pass

        await asyncio.sleep(2.0)
        await self._dismiss_popups()

        # Фокусируем видео для готовности плеера
        vw, vh = await get_viewport_dimensions(self.page)
        cx = vw * 0.5 + random.uniform(-20, 20)
        cy = vh * 0.5 + random.uniform(-20, 20)
        try:
            await natural_click(self.page, cx, cy)
            self.log("Лента активирована, плеер готов к просмотру.")
        except Exception:
            pass

    async def _dismiss_popups(self):
        """Закрывает мешающие модальные окна и куки-баннеры."""
        popup_selectors = [
            'button:has-text("Accept all")',
            'button:has-text("Принять все")',
            'button:has-text("Continue as guest")',
            'button:has-text("Продолжить как гость")',
            '[data-e2e="modal-close-inner-button"]',
            'div[aria-label="Close"]',
            'button[aria-label="Close"]',
            'button[aria-label="Закрыть"]',
        ]
        for sel in popup_selectors:
            try:
                el = await self.page.query_selector(sel)
                if el and await el.is_visible():
                    box = await el.bounding_box()
                    if box:
                        await natural_click(self.page, box["x"] + box["width"]/2, box["y"] + box["height"]/2)
                        await asyncio.sleep(0.5)
            except Exception:
                pass

    async def check_captcha(self) -> bool:
        """Проверяет наличие капчи."""
        captcha_indicators = [
            'div[class*="captcha"]',
            '#captcha-verify-image',
            '[data-e2e="sec-sdk-iframe"]',
            'iframe[src*="captcha"]'
        ]
        for sel in captcha_indicators:
            try:
                el = await self.page.query_selector(sel)
                if el and await el.is_visible():
                    self.log("[!] ОБНАРУЖЕНА КАПЧА! Решите её в окне браузера (ожидание до 2 минут)...")
                    for _ in range(24):
                        await asyncio.sleep(5)
                        if not await el.is_visible():
                            self.log("[+] Капча пройдена! Продолжаем сессию.")
                            return True
                    return False
            except Exception:
                pass
        return True

    async def is_ad_video(self) -> bool:
        """Проверяет, является ли текущее видео в ленте TikTok рекламным (Sponsored)."""
        try:
            is_ad = await self.page.evaluate('''() => {
                // 1. Селекторы рекламных контейнеров и CTA-кнопок
                const adSelectors = [
                    '[data-e2e="feed-ad-icon"]',
                    '[data-e2e="ad-icon"]',
                    '[data-e2e="ad-action-button"]',
                    '[data-e2e="ad-cta"]',
                    '[class*="AdBadge"]',
                    '[class*="ad-badge"]',
                    '[class*="DivAdBadge"]',
                    'a[href*="tiktok.com/business"]'
                ];
                for (const sel of adSelectors) {
                    const elements = document.querySelectorAll(sel);
                    for (const el of elements) {
                        const r = el.getBoundingClientRect();
                        if (r.top >= 0 && r.bottom <= window.innerHeight && r.width > 0 && r.height > 0) {
                            return true;
                        }
                    }
                }

                // 2. Текстовые бейджи рекламы
                const badges = document.querySelectorAll('span, div, p, strong, button');
                for (const b of badges) {
                    const text = (b.innerText || '').trim().toLowerCase();
                    if (['sponsored', 'реклама', 'promoted', 'learn more', 'shop now', 'узнать больше', 'в магазин'].includes(text)) {
                        const r = b.getBoundingClientRect();
                        if (r.top >= 0 && r.bottom <= window.innerHeight && r.width > 0 && r.height > 0) {
                            return true;
                        }
                    }
                }
                return false;
            }''')
            return bool(is_ad)
        except Exception:
            return False

    async def watch_video(self, video_idx: int, total_videos: int):
        """Просмотр ролика с проверкой капчи и пропуском рекламы."""
        await self.check_captcha()
        if await self.is_ad_video():
            self.log(f"[{video_idx}/{total_videos}] [Реклама] Обнаружен рекламный ролик (Sponsored). Быстрый пропуск...")
            await asyncio.sleep(random.uniform(1.8, 3.2))
            return
        await super().watch_video(video_idx, total_videos)

    async def maybe_like(self) -> bool:
        """
        Ставит лайк через физический клик по активной кнопке сердечка.
        Ищет контейнер, видимый на экране, и кликает по внутренней кнопке.
        Рекламные видео гарантированно пропускаются.
        """
        if await self.is_ad_video():
            return False

        if random.random() > Config.TIKTOK_LIKE_PROBABILITY:
            return False

        try:
            btn_info = await self.page.evaluate('''() => {
                const selectors = ['[data-e2e="like-icon"]', '[data-e2e="feed-like-icon"]', '[data-e2e="browse-like-icon"]'];
                for (const sel of selectors) {
                    const containers = Array.from(document.querySelectorAll(sel));
                    for (const c of containers) {
                        const r = c.getBoundingClientRect();
                        if (r.top >= 0 && r.bottom <= window.innerHeight && r.width > 0 && r.height > 0) {
                            const isLiked = c.getAttribute('aria-pressed') === 'true' ||
                                            c.innerHTML.includes('#FE2C55') ||
                                            c.innerHTML.includes('rgb(254, 44, 85)');
                            const btn = c.querySelector('button') || c;
                            const br = btn.getBoundingClientRect();
                            return {
                                x: br.x + br.width / 2,
                                y: br.y + br.height / 2,
                                isLiked: isLiked
                            };
                        }
                    }
                }
                return null;
            }''')

            if not btn_info:
                return False

            if btn_info.get("isLiked"):
                # Ролик уже отмечен лайком ранее
                return False

            cx = btn_info["x"] + random.uniform(-2, 2)
            cy = btn_info["y"] + random.uniform(-2, 2)
            await natural_click(self.page, cx, cy)
            self.log("[Лайк] Поставлен лайк кликом по сердечку.")
            await asyncio.sleep(random.uniform(0.5, 0.9))
            return True

        except Exception as e:
            self.log(f"Предупреждение при постановке лайка: {e}")
            return False

    async def maybe_secondary_action(self) -> bool:
        """Добавляет видео в избранное/закладки."""
        if await self.is_ad_video():
            return False

        if random.random() > Config.TIKTOK_FAVORITE_PROBABILITY:
            return False

        try:
            btn_info = await self.page.evaluate('''() => {
                const selectors = ['[data-e2e="favorite-icon"]', '[data-e2e="feed-favorite-icon"]', '[data-e2e="favorites-icon"]'];
                for (const sel of selectors) {
                    const containers = Array.from(document.querySelectorAll(sel));
                    for (const c of containers) {
                        const r = c.getBoundingClientRect();
                        if (r.top >= 0 && r.bottom <= window.innerHeight && r.width > 0 && r.height > 0) {
                            const isFav = c.getAttribute('aria-pressed') === 'true' ||
                                          c.innerHTML.includes('#FACE15') ||
                                          c.innerHTML.includes('rgb(250, 206, 21)');
                            const btn = c.querySelector('button') || c;
                            const br = btn.getBoundingClientRect();
                            return {
                                x: br.x + br.width / 2,
                                y: br.y + br.height / 2,
                                isFav: isFav
                            };
                        }
                    }
                }
                return null;
            }''')

            if not btn_info or btn_info.get("isFav"):
                return False

            cx = btn_info["x"] + random.uniform(-2, 2)
            cy = btn_info["y"] + random.uniform(-2, 2)
            await natural_click(self.page, cx, cy)
            self.log("[Избранное] Ролик добавлен в закладки.")
            await asyncio.sleep(random.uniform(0.5, 0.9))
            return True
        except Exception as e:
            self.log(f"Предупреждение при добавлении в избранное: {e}")
        return False

    async def maybe_explore_comments(self) -> bool:
        """
        Имитирует чтение комментариев человеком (без опасных спам-эмодзи):
        1. Открывает панель комментариев.
        2. Плавно прокручивает список, делая паузы на чтение.
        3. Закрывает панель комментариев.
        """
        if await self.is_ad_video():
            return False

        if random.random() > Config.TIKTOK_READ_COMMENTS_PROBABILITY:
            return False

        try:
            btn_info = await self.page.evaluate('''() => {
                const selectors = ['[data-e2e="comment-icon"]', '[data-e2e="feed-comment-icon"]'];
                for (const sel of selectors) {
                    const containers = Array.from(document.querySelectorAll(sel));
                    for (const c of containers) {
                        const r = c.getBoundingClientRect();
                        if (r.top >= 0 && r.bottom <= window.innerHeight && r.width > 0 && r.height > 0) {
                            const btn = c.querySelector('button') || c;
                            const br = btn.getBoundingClientRect();
                            return { x: br.x + br.width / 2, y: br.y + br.height / 2 };
                        }
                    }
                }
                return null;
            }''')

            if not btn_info:
                return False

            self.log("[Комментарии] Открываем блок комментариев для чтения...")
            await natural_click(self.page, btn_info["x"], btn_info["y"])
            await asyncio.sleep(random.uniform(1.5, 2.3))

            # Ищем контейнер сайдбара комментариев для скролла
            panel_box = await self.page.evaluate('''() => {
                const p = document.querySelector('[class*="CommentSidebar"], [class*="BaseCommentContainerStyles"], [class*="DivCommentListContainer"]');
                if (p) {
                    const r = p.getBoundingClientRect();
                    return { x: r.x, y: r.y, width: r.width, height: r.height };
                }
                return null;
            }''')

            # Имитируем чтение комментариев
            await natural_scroll_comments(self.page, panel_box)

            # Закрываем панель комментариев через кнопку exit в хедере
            close_info = await self.page.evaluate('''() => {
                const closeBtn = document.querySelector('[class*="CommentHeader"] button[aria-label="exit"], [class*="CommentHeader"] button, button[aria-label="exit"], [data-e2e="comment-close-icon"]');
                if (closeBtn) {
                    const r = closeBtn.getBoundingClientRect();
                    return { x: r.x + r.width / 2, y: r.y + r.height / 2 };
                }
                return null;
            }''')

            if close_info:
                await natural_click(self.page, close_info["x"], close_info["y"])
                await asyncio.sleep(random.uniform(0.5, 0.8))
            else:
                await self.page.keyboard.press("Escape")

            self.log("[Комментарии] Просмотр комментариев завершен.")
            await asyncio.sleep(random.uniform(0.5, 0.8))
            return True

        except Exception as e:
            self.log(f"Предупреждение при просмотре комментариев: {e}")
            try:
                await self.page.keyboard.press("Escape")
            except Exception:
                pass
        return False

    async def next_video(self) -> bool:
        """Переход к следующему видео."""
        return await human_next_video(self.page, platform="tiktok")
