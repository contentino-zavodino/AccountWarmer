"""Менеджер экранного пространства: расстановка окон браузера на мониторе.
Поддерживает Windows, macOS и Linux с безопасным откатом на базовые значения.
"""

from __future__ import annotations
import re
import subprocess
import sys
from typing import Tuple

def get_screen_resolution() -> Tuple[int, int]:
    """Определяет разрешение основного монитора кроссплатформенно."""
    # 1. Попытка через Tkinter (работает на Mac, Win, Linux и возвращает логические координаты)
    try:
        import tkinter
        root = tkinter.Tk()
        root.withdraw()
        w = root.winfo_screenwidth()
        h = root.winfo_screenheight()
        root.destroy()
        if w > 0 and h > 0:
            return int(w), int(h)
    except Exception:
        pass

    # 2. Windows: через user32
    if sys.platform == "win32":
        try:
            import ctypes
            user32 = ctypes.windll.user32
            user32.SetProcessDPIAware()
            width = user32.GetSystemMetrics(0)
            height = user32.GetSystemMetrics(1)
            if width > 0 and height > 0:
                return int(width), int(height)
        except Exception:
            pass

    # 3. macOS fallback: через system_profiler
    if sys.platform == "darwin":
        try:
            output = subprocess.check_output(
                ["system_profiler", "SPDisplaysDataType"],
                stderr=subprocess.DEVNULL,
                text=True,
                timeout=3
            )
            match = re.search(r"Resolution:\s*(\d+)\s*x\s*(\d+)", output)
            if match:
                return int(match.group(1)), int(match.group(2))
        except Exception:
            pass

    # 4. Базовый безопасный fallback
    return 1920, 1080


def calculate_window_geometry(
    profile_index: int,
    total_profiles: int,
    preferred_width: int = 430,
    preferred_height: int = 800
) -> Tuple[int, int, int, int]:
    """
    Рассчитывает координаты (x, y) и размеры (width, height) для окна с заданным индексом.
    Размещает окна аккуратной шеренгой или компактной сеткой без перекрытия.
    """
    screen_w, screen_h = get_screen_resolution()

    # Отступы от краев экрана
    available_w = max(400, screen_w - 20)
    available_h = max(600, screen_h - 70)

    # Если профили помещаются в один ряд:
    fits_in_one_row = (total_profiles * preferred_width) <= available_w

    if fits_in_one_row:
        win_w = preferred_width
        win_h = min(preferred_height, available_h)
        x = 10 + profile_index * (win_w + 8)
        y = 10
    else:
        # Пробуем пропорционально сжать ширину, чтобы уместить все в 1 ряд (до 340px)
        dynamic_width = (available_w // total_profiles) - 6
        if dynamic_width >= 340:
            win_w = dynamic_width
            win_h = min(preferred_height, available_h)
            x = 10 + profile_index * (win_w + 6)
            y = 10
        else:
            # Иначе делим на 2 ряда
            cols = max(1, (total_profiles + 1) // 2)
            row = profile_index // cols
            col = profile_index % cols
            win_w = min(preferred_width, available_w // cols - 10)
            win_h = min(preferred_height, available_h // 2 - 20)
            x = 10 + col * (win_w + 8)
            y = 10 + row * (win_h + 30)

    return int(x), int(y), int(win_w), int(win_h)
