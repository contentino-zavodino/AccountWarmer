"""Продвинутая имитация естественных движений человека (жесты, свайпы, кривые Безье, чтение)."""

from __future__ import annotations
import asyncio
import math
import random
from typing import Any, List, Optional, Tuple

try:
    from playwright.async_api import Page
except ImportError:
    Page = Any  # type: ignore


def _bezier_point(p0: float, p1: float, p2: float, p3: float, t: float) -> float:
    """Вычисляет координату кубической кривой Безье для параметра t [0, 1]."""
    return (
        (1 - t) ** 3 * p0
        + 3 * (1 - t) ** 2 * t * p1
        + 3 * (1 - t) * t ** 2 * p2
        + t ** 3 * p3
    )


def generate_bezier_trajectory(
    start: Tuple[float, float],
    end: Tuple[float, float],
    steps: int = 15
) -> List[Tuple[float, float]]:
    """Генерирует естественную человеческую траекторию между двумя точками с микро-дрожанием."""
    x0, y0 = start
    x3, y3 = end

    dx = x3 - x0
    dy = y3 - y0
    dist = math.hypot(dx, dy)

    # Случайное дугообразное искривление траектории
    deviation = random.uniform(-0.15, 0.15) * (dist if dist > 0 else 1)
    x1 = x0 + dx * 0.3 + deviation
    y1 = y0 + dy * 0.3
    x2 = x0 + dx * 0.7 - deviation
    y2 = y0 + dy * 0.7

    points = []
    for i in range(steps + 1):
        t = i / steps
        eased_t = t * t * (3 - 2 * t)  # Плавный разгон и замедление

        px = _bezier_point(x0, x1, x2, x3, eased_t)
        py = _bezier_point(y0, y1, y2, y3, eased_t)

        if 0 < i < steps:
            px += random.gauss(0, 0.7)
            py += random.gauss(0, 0.7)

        points.append((px, py))

    return points


async def get_viewport_dimensions(page: Page) -> Tuple[float, float]:
    """Возвращает актуальные размеры видимой области страницы с учетом CDP."""
    try:
        dim = await page.evaluate("() => ({ width: window.innerWidth, height: window.innerHeight })")
        if dim and dim.get("width") and dim.get("height"):
            return float(dim["width"]), float(dim["height"])
    except Exception:
        pass
    vp = getattr(page, "viewport_size", None) or {"width": 430, "height": 800}
    return float(vp["width"]), float(vp["height"])


async def natural_move(
    page: Page,
    target_x: float,
    target_y: float,
    start_pos: Optional[Tuple[float, float]] = None
):
    """Плавно перемещает курсор к целевой точке по кривой Безье."""
    if start_pos is None:
        vw, vh = await get_viewport_dimensions(page)
        start_pos = (
            vw * random.uniform(0.3, 0.7),
            vh * random.uniform(0.3, 0.7)
        )

    points = generate_bezier_trajectory(start_pos, (target_x, target_y), steps=random.randint(10, 16))
    for px, py in points:
        await page.mouse.move(px, py)
        await asyncio.sleep(random.uniform(0.005, 0.012))


async def natural_click(page: Page, x: float, y: float):
    """Выполняет клик с естественным подводом курсора и задержкой удержания."""
    await natural_move(page, x, y)
    await asyncio.sleep(random.uniform(0.05, 0.12))
    await page.mouse.down()
    await asyncio.sleep(random.uniform(0.06, 0.11))
    await page.mouse.up()


async def natural_double_click(page: Page, x: float, y: float):
    """Выполняет двойной клик (удобно для нативного лайка в TikTok)."""
    await natural_move(page, x, y)
    await asyncio.sleep(random.uniform(0.04, 0.08))
    # Клик 1
    await page.mouse.down()
    await asyncio.sleep(random.uniform(0.04, 0.08))
    await page.mouse.up()
    # Пауза между кликами (60-120мс)
    await asyncio.sleep(random.uniform(0.06, 0.12))
    # Клик 2
    await page.mouse.down()
    await asyncio.sleep(random.uniform(0.04, 0.08))
    await page.mouse.up()


async def human_next_video(page: Page, platform: str = "tiktok") -> bool:
    """
    Органический переход к следующему видео без аномальных двойных действий:
    1. Легкое случайное смещение курсора в нейтральную область.
    2. Естественная пауза размышления.
    3. Четкий переход к следующему видео через клавишу ArrowDown или скролл колесиком.
    """
    vw, vh = await get_viewport_dimensions(page)

    # Случайное микродвижение курсора перед переключением
    target_x = vw * random.uniform(0.35, 0.65)
    target_y = vh * random.uniform(0.40, 0.70)
    await natural_move(page, target_x, target_y)
    await asyncio.sleep(random.uniform(0.1, 0.3))

async def smooth_human_scroll(
    page: Page,
    delta_y: float,
    steps: int = 14,
    min_delay: float = 0.012,
    max_delay: float = 0.025
):
    """
    Плавно прокручивает страницу серией микро-шагов с физической инерцией,
    полностью имитируя естественный жест пальцем по тачпаду macOS.
    """
    if abs(delta_y) < 5:
        return

    # Синусоидальное распределение ускорения и замедления (easing)
    weights = [math.sin((i / steps) * math.pi) + 0.15 for i in range(steps)]
    total_w = sum(weights)

    for w in weights:
        step_delta = int((w / total_w) * delta_y)
        if step_delta != 0:
            await page.mouse.wheel(0, step_delta)
            await asyncio.sleep(random.uniform(min_delay, max_delay))


async def decisive_flick_scroll(
    page: Page,
    delta_y: Optional[float] = None,
    strength: float = 1.0
):
    """
    Выполняет уверенный, энергичный свайп (флик) для переключения видео.
    Имитирует быстрый и четкий жест пальцем по тачпаду/колесику мыши с достаточной
    силой импульса, чтобы гарантированно преодолеть порог scroll-snap (CSS Scroll Snapping).
    """
    vw, vh = await get_viewport_dimensions(page)
    # Сила свайпа должна гарантированно преодолеть порог текущего ролика (950-1200px)
    if delta_y is None:
        delta_y = max(950.0, vh * 1.25) * strength

    # Быстрый импульсный свайп: 4-6 шагов с резким начальным ускорением
    steps = random.randint(4, 6)
    weights = [0.42, 0.30, 0.18, 0.07, 0.03][:steps]
    total_w = sum(weights)

    for w in weights:
        step_delta = int((w / total_w) * delta_y)
        if step_delta != 0:
            await page.mouse.wheel(0, step_delta)
            await asyncio.sleep(random.uniform(0.008, 0.016))


async def human_next_video(page: Page, platform: str = "tiktok") -> bool:
    """
    Органический переход к следующему видео с гарантированным переключением:
    1. Снимает фокус с кнопок (лайк, комменты), чтобы клавиши точно управляли лентой.
    2. Выполняет естественное легкое смещение курсора.
    3. Применяет уверенный переход (ArrowDown или энергичный импульсный свайп),
       гарантируя преодоление порога scroll-snap (исключая «слабый слайд»).
    4. Для YouTube Shorts проверяет смену URL и при необходимости делает мягкую доводку.
    """
    vw, vh = await get_viewport_dimensions(page)

    # 1. Снимаем фокус с ранее нажатых кнопок
    try:
        await page.evaluate("""() => {
            if (document.activeElement && document.activeElement !== document.body) {
                document.activeElement.blur();
            }
        }""")
    except Exception:
        pass

    # 2. Небольшое естественное движение мыши в нейтральную область
    target_x = vw * random.uniform(0.35, 0.65)
    target_y = vh * random.uniform(0.40, 0.65)
    await natural_move(page, target_x, target_y)
    await asyncio.sleep(random.uniform(0.1, 0.25))

    url_before = page.url

    # 3. Выполняем переключение: 70% клавиша ArrowDown, 30% энергичный свайп
    flip_method = "key" if random.random() < 0.70 else "wheel"

    try:
        if flip_method == "key":
            await page.keyboard.press("ArrowDown")
        else:
            await decisive_flick_scroll(page, strength=random.uniform(1.0, 1.25))

        await asyncio.sleep(random.uniform(0.5, 0.8))

        # 4. Если на YouTube Shorts URL не сменился (слабый слайд застрял), доводим переход
        if platform == "youtube" and page.url == url_before:
            try:
                next_btn = await page.query_selector(
                    '#navigation-button-down button, button[aria-label*="Next video"], button[aria-label*="Следующее видео"]'
                )
                if next_btn and await next_btn.is_visible():
                    box = await next_btn.bounding_box()
                    if box:
                        await natural_click(page, box["x"] + box["width"]/2, box["y"] + box["height"]/2)
                        await asyncio.sleep(random.uniform(0.4, 0.7))
                        return True
            except Exception:
                pass

            # Если кнопки нет — делаем уверенный флик колесиком
            await decisive_flick_scroll(page, strength=1.2)

        return True

    except Exception:
        try:
            await page.keyboard.press("ArrowDown")
            await asyncio.sleep(0.5)
            return True
        except Exception:
            return False


async def natural_scroll_comments(page: Page, container_box: Optional[dict] = None):
    """
    Имитирует чтение комментариев человеком:
    Плавно прокручивает блок комментариев микро-шагами с паузами на чтение.
    """
    vw, vh = await get_viewport_dimensions(page)

    if container_box:
        # Удерживаем курсор строго внутри видимой области экрана
        box_y = float(container_box.get("y", 100))
        box_h = float(container_box.get("height", 400))
        min_y = max(80.0, box_y)
        max_y = min(vh - 80.0, box_y + box_h)
        if max_y > min_y + 40:
            cy = random.uniform(min_y + 20, max_y - 20)
        else:
            cy = vh * 0.5
        cx = float(container_box.get("x", vw * 0.75)) + float(container_box.get("width", 300)) * random.uniform(0.3, 0.7)
    else:
        cx = vw * random.uniform(0.70, 0.85)
        cy = vh * random.uniform(0.40, 0.65)

    # Наводим курсор на область комментариев
    await natural_move(page, cx, cy)
    await asyncio.sleep(random.uniform(0.5, 0.9))

    # Делаем 2-3 плавных микро-скролла с паузами на чтение
    scroll_cycles = random.randint(2, 3)
    for _ in range(scroll_cycles):
        scroll_delta = random.randint(120, 200)
        await smooth_human_scroll(page, scroll_delta, steps=random.randint(10, 15))
        # Пауза на чтение (1.5 - 3.0 сек)
        await asyncio.sleep(random.uniform(1.5, 3.0))

        # С вероятностью 20% делаем естественный микро-откат назад
        if random.random() < 0.20:
            rollback = -random.randint(30, 60)
            await smooth_human_scroll(page, rollback, steps=random.randint(6, 10))
            await asyncio.sleep(random.uniform(0.8, 1.5))
