"""Модуль управления жизненным циклом прогрева профиля (Dolphin{anty} / BitBrowser)."""

from __future__ import annotations
import asyncio
import logging
import random
import sys
from typing import Any, Optional
from playwright.async_api import async_playwright, Page

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

from config import Config
from layout_manager import calculate_window_geometry
from gestures import natural_move
from tiktok_bot import TikTokBot
from youtube_bot import YouTubeBot
from base_bot import BasePlatformBot

logger = logging.getLogger("warmer")


async def _run_cookie_warmup(page: Page, tag: str):
    """
    Выполняет предварительный серфинг по 1-2 нейтральным сайтам (Google, Wikipedia, новости)
    для сбора фоновых cookies и истории перед переходом в соцсети.
    """
    if not Config.COOKIE_WARMUP or not Config.COOKIE_WARMUP_SITES:
        return

    sites_to_visit = random.sample(
        Config.COOKIE_WARMUP_SITES,
        k=min(len(Config.COOKIE_WARMUP_SITES), random.randint(1, 2))
    )
    print(f"[{tag}] [*] Старт этапа «нагуливания куков» ({len(sites_to_visit)} сайтов)...")

    for idx, site in enumerate(sites_to_visit, 1):
        print(f"[{tag}] [{idx}/{len(sites_to_visit)}] Посещение нейтрального ресурса: {site}")
        try:
            await page.goto(site, wait_until="domcontentloaded", timeout=30000)
            await asyncio.sleep(random.uniform(3.0, 6.0))

            # Имитируем легкое движение мыши и скролл на странице
            viewport = page.viewport_size or {"width": 430, "height": 800}
            rx = viewport["width"] * random.uniform(0.3, 0.7)
            ry = viewport["height"] * random.uniform(0.4, 0.6)
            await natural_move(page, rx, ry)

            # Легкий скролл страницы
            await page.mouse.wheel(0, random.randint(150, 350))
            await asyncio.sleep(random.uniform(5.0, 10.0))

        except Exception as e:
            print(f"[{tag}] Предупреждение при нагуливании на {site}: {e}")

    print(f"[{tag}] [+] Нагуливание куков успешно завершено. Переходим к основной сессии.")
    await asyncio.sleep(2.0)


async def _execute_feed_cycle(bot: BasePlatformBot, num_videos: int, tag: str):
    """Выполняет цикл просмотра и реакций для заданного бота платформы."""
    print(f"[{tag} | {bot.platform_name}] [*] Запланировано просмотров: {num_videos} роликов.")
    await bot.init_session()

    for i in range(1, num_videos + 1):
        # Защита от ухода на сторонний рекламный сайт (Navigation Guard)
        current_url = bot.page.url.lower()
        if bot.platform_name.lower() == "tiktok" and "tiktok.com" not in current_url:
            print(f"[{tag} | {bot.platform_name}] [Защита] Страница перенаправлена на сторонний сайт ({bot.page.url[:50]}). Возвращаемся в ленту TikTok...")
            try:
                await bot.page.goto(Config.TIKTOK_START_URL, wait_until="domcontentloaded")
                await asyncio.sleep(2.0)
            except Exception:
                pass
        elif bot.platform_name.lower() == "youtube" and "youtube.com" not in current_url:
            print(f"[{tag} | {bot.platform_name}] [Защита] Страница перенаправлена на сторонний сайт ({bot.page.url[:50]}). Возвращаемся в YouTube Shorts...")
            try:
                await bot.page.goto(Config.YOUTUBE_START_URL, wait_until="domcontentloaded")
                await asyncio.sleep(2.0)
            except Exception:
                pass

        # 1. Просмотр видео
        await bot.watch_video(video_idx=i, total_videos=num_videos)

        # 2. Реакции (лайк / подписка / закладки)
        liked = await bot.maybe_like()
        if liked:
            await asyncio.sleep(random.uniform(0.3, 0.7))

        secondary = await bot.maybe_secondary_action()
        if secondary:
            await asyncio.sleep(random.uniform(0.3, 0.7))

        # 3. Чтение комментариев
        await bot.maybe_explore_comments()

        # 4. Небольшая пауза перед перелистыванием
        await asyncio.sleep(random.uniform(0.3, 0.8))

        # 5. Органический переход к следующему видео
        await bot.next_video()

    print(f"[{tag} | {bot.platform_name}] [+] Прогрев {bot.platform_name} успешно завершен ({num_videos} роликов).")


async def run_profile_warmer(
    profile_id: str,
    profile_index: int,
    total_profiles: int,
    browser_api: Any,
    semaphore: asyncio.Semaphore,
    platform_mode: str = "tiktok"
):
    """
    Выполняет полный цикл прогрева для одного профиля (Dolphin / BitBrowser):
    1. Ротация мобильного прокси (если задана ссылка).
    2. Запуск профиля в заданной экранной позиции через Local API.
    3. Выдержка паузы на инжекцию отпечатков Dolphin.
    4. Подключение Playwright CDP + инжекция скрытия автоматизации (navigator.webdriver).
    5. Этап нагуливания куков (опционально).
    6. Прогрев целевой платформы (TikTok / YouTube Shorts).
    7. Двухфазное корректное закрытие: сначала CDP, затем API остановки профиля.
    """
    tag = f"Аккаунт #{profile_index + 1}"

    async with semaphore:
        print(f"\n==========================================")
        print(f"[{tag}] Старт сессии прогрева (ID: {profile_id}, Режим: {platform_mode.upper()})...")
        print(f"==========================================")

        # 1. Ротация мобильного прокси (если задан URL)
        if hasattr(browser_api, "rotate_proxy") and Config.PROXY_ROTATION_URL:
            await browser_api.rotate_proxy(Config.PROXY_ROTATION_URL, Config.PROXY_ROTATION_DELAY)

        # Вычисляем экранные координаты окна с учетом текущей ОС (macOS / Windows)
        x, y, w, h = calculate_window_geometry(
            profile_index=profile_index,
            total_profiles=total_profiles,
            preferred_width=Config.WINDOW_WIDTH,
            preferred_height=Config.WINDOW_HEIGHT
        )

        # 2. Запуск браузера через Local API
        try:
            browser_info = await browser_api.open_profile(
                profile_id=profile_id,
                window_x=x,
                window_y=y,
                window_width=w,
                window_height=h
            )
            cdp_endpoint = browser_info["endpoint"]
            print(f"[{tag}] Окно открыто в позиции ({x}, {y}) размером {w}x{h}.")
        except Exception as e:
            print(f"[{tag}] [!] Ошибка запуска профиля через Local API: {e}")
            return

        # 3. Пауза на инжекцию отпечатков и запуск Chromium
        startup_delay = getattr(Config, "DOLPHIN_STARTUP_DELAY", 4.0)
        print(f"[{tag}] Пауза {startup_delay:.1f} сек для полной сборки отпечатков браузера...")
        await asyncio.sleep(startup_delay)

        # 4. Подключение Playwright через CDP
        async with async_playwright() as p:
            browser = None
            try:
                browser = await p.chromium.connect_over_cdp(cdp_endpoint)
                context = browser.contexts[0] if browser.contexts else await browser.new_context()

                # Скрытие флага автоматизации navigator.webdriver
                try:
                    await context.add_init_script("""
                        Object.defineProperty(navigator, 'webdriver', {
                            get: () => undefined
                        });
                    """)
                except Exception:
                    pass

                page = context.pages[-1] if context.pages else await context.new_page()
                try:
                    await page.bring_to_front()
                except Exception:
                    pass

                # Защитник от всплывающих рекламных вкладок (Popup Guardian)
                def _on_new_page(new_pg: Page):
                    async def _guard():
                        try:
                            await asyncio.sleep(0.6)
                            u = new_pg.url.lower()
                            if u and not any(d in u for d in ["tiktok.com", "youtube.com", "google.com", "about:blank"]):
                                print(f"[{tag}] [Защита] Обнаружена внешняя рекламная вкладка ({new_pg.url[:55]}...). Закрываем!")
                                await new_pg.close()
                        except Exception:
                            pass
                    asyncio.create_task(_guard())

                context.on("page", _on_new_page)

                # 5. Опциональное нагуливание куков
                await _run_cookie_warmup(page=page, tag=tag)

                # 6. Основной цикл прогрева соцсетей
                total_session_videos = random.randint(
                    Config.VIDEOS_PER_SESSION_MIN,
                    Config.VIDEOS_PER_SESSION_MAX
                )

                if platform_mode == "youtube":
                    bot = YouTubeBot(page=page, profile_id=profile_id, profile_tag=tag)
                    await _execute_feed_cycle(bot, total_session_videos, tag)

                elif platform_mode == "tiktok":
                    bot = TikTokBot(page=page, profile_id=profile_id, profile_tag=tag)
                    await _execute_feed_cycle(bot, total_session_videos, tag)

                elif platform_mode == "combined":
                    yt_count = max(10, total_session_videos // 2)
                    tt_count = max(10, total_session_videos - yt_count)

                    print(f"[{tag}] Запуск комбинированного режима: {yt_count} Shorts + {tt_count} TikTok.")

                    yt_bot = YouTubeBot(page=page, profile_id=profile_id, profile_tag=tag)
                    await _execute_feed_cycle(yt_bot, yt_count, tag)

                    pause_between = random.uniform(3.0, 6.0)
                    print(f"[{tag}] Пауза между платформами: {pause_between:.1f} сек...")
                    await asyncio.sleep(pause_between)

                    tt_bot = TikTokBot(page=page, profile_id=profile_id, profile_tag=tag)
                    await _execute_feed_cycle(tt_bot, tt_count, tag)

                else:
                    print(f"[{tag}] [!] Неизвестный режим: {platform_mode}")

                print(f"[{tag}] [+] Все запланированные видео успешно просмотрены! Завершение сессии.")

            except Exception as e:
                print(f"[{tag}] [!] Ошибка во время выполнения прогрева: {e}")

            finally:
                # 7. Корректное двухфазное закрытие профиля (защищено от отмены через asyncio.shield)
                async def _graceful_shutdown():
                    # Фаза 1: Отключение Playwright CDP
                    try:
                        if browser:
                            await browser.close()
                    except Exception:
                        pass

                    # Фаза 2: Остановка через Local API и сохранение данных профиля
                    try:
                        await browser_api.close_profile(profile_id)
                    except Exception as err:
                        print(f"[{tag}] Предупреждение при остановке через API: {err}")

                try:
                    await asyncio.shield(_graceful_shutdown())
                    print(f"[{tag}] Профиль корректно закрыт и сессия сохранена.")
                except Exception:
                    pass
