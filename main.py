"""Главная точка входа: параллельный прогрев аккаунтов (Dolphin{anty} / BitBrowser)."""

from __future__ import annotations
import argparse
import asyncio
import sys

# Обеспечиваем корректный вывод UTF-8 в консоли Windows
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

from config import Config

def check_dependencies():
    """Проверяет установку aiohttp и playwright перед запуском работы."""
    try:
        import aiohttp
        import playwright
    except ImportError as err:
        print(f"\n[!] ВНИМАНИЕ: Не установлена необходимая библиотека ({err.name}).")
        print("Для работы скрипта установите зависимости:")
        print("   pip install -r requirements.txt")
        print("   playwright install chromium\n")
        sys.exit(1)


def select_platform_mode_interactive(cli_mode: str | None) -> str:
    """Определяет режим работы: из CLI аргументов, интерактивного меню или config.py."""
    if cli_mode and cli_mode.lower() in ["tiktok", "youtube", "combined"]:
        return cli_mode.lower()

    # Если скрипт запущен в интерактивном терминале
    if sys.stdin.isatty():
        default_choice = Config.DEFAULT_PLATFORM_MODE
        print("────────────────────────────────────────────────────────")
        print("Выберите платформу для прогрева аккаунтов:")
        print("  [1] TikTok (только лента For You)")
        print("  [2] YouTube Shorts (только лента Shorts)")
        print("  [3] Комбинированный режим (YouTube Shorts + TikTok)")
        print(f"  [Enter] По умолчанию: {default_choice.upper()}")
        print("────────────────────────────────────────────────────────")

        try:
            choice = input("Ваш выбор (1/2/3 или Enter): ").strip()
            if choice == "1":
                return "tiktok"
            elif choice == "2":
                return "youtube"
            elif choice == "3":
                return "combined"
            elif choice == "":
                return default_choice
            else:
                print(f"[*] Неизвестный ввод, используется режим по умолчанию: {default_choice}")
                return default_choice
        except (KeyboardInterrupt, EOFError):
            print("\nВыход.")
            sys.exit(0)

    return Config.DEFAULT_PLATFORM_MODE


async def main():
    parser = argparse.ArgumentParser(description="Автоматический прогрев аккаунтов TikTok и YouTube Shorts через антидетект-браузер")
    parser.add_argument(
        "--platform",
        choices=["tiktok", "youtube", "combined"],
        help="Режим прогрева: tiktok, youtube или combined"
    )
    parser.add_argument(
        "--browser",
        choices=["dolphin", "bitbrowser"],
        default=Config.BROWSER_TYPE,
        help="Тип браузера: dolphin или bitbrowser"
    )
    parser.add_argument(
        "--max-concurrent",
        type=int,
        default=Config.MAX_CONCURRENT_PROFILES,
        help="Максимальное число одновременно запущенных окон"
    )
    args = parser.parse_args()

    check_dependencies()
    from warmer import run_profile_warmer

    # Выбор типа браузера
    browser_type = (args.browser or Config.BROWSER_TYPE).lower()

    if browser_type == "dolphin":
        from dolphin_api import DolphinAPI
        browser_api = DolphinAPI(Config.DOLPHIN_API_URL, Config.DOLPHIN_API_TOKEN)
        browser_name = "Dolphin{anty}"
        api_url = Config.DOLPHIN_API_URL
    else:
        from bitbrowser_api import BitBrowserAPI
        browser_api = BitBrowserAPI(Config.BITBROWSER_API_URL)
        browser_name = "BitBrowser"
        api_url = Config.BITBROWSER_API_URL

    platform_mode = select_platform_mode_interactive(args.platform)

    mode_titles = {
        "tiktok": "TikTok For You",
        "youtube": "YouTube Shorts",
        "combined": "Комбинированный (YouTube Shorts + TikTok)"
    }

    print(f"""
    ========================================================
       🚀 Social Account Warmer ({browser_name} + Playwright)
       Платформа: {mode_titles.get(platform_mode, platform_mode)}
       Браузер:   {browser_name}
    ========================================================
    """)

    # 1. Проверяем связь с Local API
    print(f"[*] Проверка подключения к {browser_name} Local API ({api_url})...")
    conn_result = await browser_api.check_connection()
    if isinstance(conn_result, tuple):
        is_connected, status_msg = conn_result
    else:
        is_connected, status_msg = conn_result, "offline"

    if not is_connected:
        if status_msg == "unauthorized":
            print(f"\n[!] Dolphin{{anty}} запущен на порту 3001, но требует токен авторизации (API Token)!")
            print("Чтобы софт мог управлять профилями:")
            print(" 1. Откройте приложение Dolphin{anty}.")
            print(" 2. Нажмите на шестерёнку в левом нижнем углу («Настройки» / Settings).")
            print(" 3. Перейдите в раздел «API» и скопируйте ваш «API Token».")
            print(" 4. Вставьте его в файл config.py в поле:")
            print("       DOLPHIN_API_TOKEN = \"ваш_токен\"\n")
        else:
            print(f"\n[!] ОШИБКА: Не удалось подключиться к {browser_name} Local API ({api_url})!")
            print("Пожалуйста, убедитесь что:")
            print(f" 1. Приложение {browser_name} запущено на вашем компьютере.")
            if browser_type == "dolphin":
                print(" 2. Вы авторизованы в свой аккаунт Dolphin{anty}.")
                print(" 3. Порт 3001 открыт и не заблокирован брандмауэром Mac.")
            else:
                print(" 2. В настройках BitBrowser включен Local API (порт 54345).")
                print(" 3. Если порт другой, измените BITBROWSER_API_URL в файле config.py.")
        sys.exit(1)

    print(f"[+] Связь с {browser_name} успешно установлена!")

    # 2. Определяем список профилей
    target_profiles = Config.PROFILE_IDS

    if not target_profiles:
        print(f"[*] Список PROFILE_IDS в config.py пуст. Запрашиваем профили из {browser_name}...")
        found_profiles = await browser_api.get_profile_ids(limit=args.max_concurrent, platform=platform_mode)
        if not found_profiles:
            if browser_type == "dolphin":
                print(f"\n[!] ВНИМАНИЕ: Не удалось автоматически получить ID профилей из Dolphin{{anty}}.")
                print("Чтобы запустить прогрев, укажите ID ваших профилей в config.py:")
                print(" 1. Откройте приложение Dolphin{anty}.")
                print(" 2. Скопируйте ID созданного профиля (в таблице профилей, колонка ID).")
                print(" 3. Вставьте его в config.py в список PROFILE_IDS, например:")
                print("       PROFILE_IDS = [\"12345678\"]")
                print(" (Также можно указать DOLPHIN_API_TOKEN в config.py для авто-получения).\n")
            else:
                print(f"\n[!] ОШИБКА: В {browser_name} не найдено ни одного профиля!")
                print(f"Создайте профили в приложении {browser_name} или укажите их ID в config.py.")
            sys.exit(1)
        target_profiles = found_profiles
        print(f"[+] Автоматически обнаружено профилей: {len(target_profiles)}")
        for idx, pid in enumerate(target_profiles):
            print(f"   - Профиль {idx + 1}: {pid}")
    else:
        print(f"[*] Загружено {len(target_profiles)} профилей из config.py.")

    total_profiles = len(target_profiles)
    max_concurrent = min(args.max_concurrent, total_profiles)

    print(f"\n[*] Параллельный запуск: {max_concurrent} одновременно (всего аккаунтов: {total_profiles})")
    print(f"[*] Окна будут автоматически расставлены на экране (macOS / Windows).")
    print(f"[*] Для прерывания нажмите Ctrl+C в любой момент.\n")

    semaphore = asyncio.Semaphore(max_concurrent)

    # Формируем задачи прогрева
    tasks = [
        run_profile_warmer(
            profile_id=pid,
            profile_index=i,
            total_profiles=total_profiles,
            browser_api=browser_api,
            semaphore=semaphore,
            platform_mode=platform_mode
        )
        for i, pid in enumerate(target_profiles)
    ]

    try:
        await asyncio.gather(*tasks)
        print("\n[+] Все запланированные сессии прогрева успешно завершены!")
    except KeyboardInterrupt:
        print("\n[-] Прогрев принудительно остановлен пользователем.")
    except Exception as e:
        print(f"\n[!] Непредвиденная ошибка в основном цикле: {e}")


if __name__ == "__main__":
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

    asyncio.run(main())
