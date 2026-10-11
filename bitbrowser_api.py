import asyncio
import logging
from typing import Any, Dict, List, Optional
import aiohttp

logger = logging.getLogger("bitbrowser_api")

class BitBrowserAPI:
    """Асинхронный клиент для взаимодействия с Local API BitBrowser."""

    def __init__(self, base_url: str = "http://127.0.0.1:54345"):
        self.base_url = base_url.rstrip("/")

    async def check_connection(self) -> bool:
        """Проверяет, запущен ли BitBrowser и отвечает ли его Local API."""
        try:
            async with aiohttp.ClientSession() as session:
                url = f"{self.base_url}/browser/list"
                payload = {"page": 0, "pageSize": 1}
                async with session.post(url, json=payload, timeout=aiohttp.ClientTimeout(total=5)) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        return data.get("success", False) or "data" in data
        except Exception as e:
            logger.warning("Не удалось подключиться к BitBrowser Local API (%s): %s", self.base_url, e)
            return False
        return False

    async def get_profile_ids(self, limit: int = 10, platform: Optional[str] = None) -> List[str]:
        """
        Получает список ID существующих профилей из BitBrowser.
        Если указан platform ("youtube" или "tiktok"), отдает приоритет профилям с соответствующим именем/платформой.
        """
        try:
            async with aiohttp.ClientSession() as session:
                url = f"{self.base_url}/browser/list"
                payload = {"page": 0, "pageSize": 50}
                async with session.post(url, json=payload) as resp:
                    data = await resp.json()
                    if data.get("success") and "data" in data:
                        items = data["data"].get("list", [])
                        if platform and platform.lower() in ["youtube", "tiktok"]:
                            p_key = platform.lower()
                            matched = [
                                item["id"] for item in items
                                if "id" in item and (
                                    p_key in str(item.get("name", "")).lower()
                                    or p_key in str(item.get("platform", "")).lower()
                                )
                            ]
                            if matched:
                                return matched[:limit]

                        return [item["id"] for item in items if "id" in item][:limit]
        except Exception as e:
            logger.error("Ошибка при получении списка профилей: %s", e)
        return []

    async def open_profile(
        self,
        profile_id: str,
        window_x: int = 0,
        window_y: int = 0,
        window_width: int = 430,
        window_height: int = 800,
        max_retries: int = 3
    ) -> Dict[str, Any]:
        """
        Запускает профиль в BitBrowser с заданными координатами и размерами окна.
        Возвращает словарь с WebSocket URL ('ws') или портом отладки ('http').
        Включает авто-повтор при временных ошибках (например, 'socket hang up' после закрытия).
        """
        url = f"{self.base_url}/browser/open"
        chrome_args = [
            f"--window-position={window_x},{window_y}",
            f"--window-size={window_width},{window_height}",
            "--disable-notifications",
            "--mute-audio"
        ]

        payload = {
            "id": profile_id,
            "args": chrome_args,
            "loadExtensions": True,
            "extractIp": False
        }

        last_error = "Неизвестная ошибка"
        for attempt in range(1, max_retries + 1):
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.post(url, json=payload, timeout=aiohttp.ClientTimeout(total=30)) as resp:
                        data = await resp.json()
                        if not data.get("success"):
                            last_error = data.get("msg", "Неизвестная ошибка")
                            err_lower = str(last_error).lower()
                            if ("socket hang up" in err_lower or "busy" in err_lower or "failed" in err_lower) and attempt < max_retries:
                                print(f"[*] BitBrowser ещё завершает предыдущую сессию ('{last_error}'). Пауза 2.5 сек перед повтором ({attempt}/{max_retries})...")
                                # Посылаем команду закрытия на случай зависшего процесса
                                await self.close_profile(profile_id)
                                await asyncio.sleep(2.5)
                                continue

                            raise RuntimeError(f"BitBrowser API вернул ошибку при открытии {profile_id}: {last_error}")

                        browser_data = data.get("data", {})
                        ws_url = browser_data.get("ws")
                        http_addr = browser_data.get("http")

                        if not ws_url and not http_addr:
                            raise RuntimeError(f"BitBrowser не вернул адрес подключения CDP для {profile_id}: {data}")

                        endpoint = ws_url or f"http://{http_addr}"
                        return {
                            "endpoint": endpoint,
                            "raw_data": browser_data
                        }
            except aiohttp.ClientError as ce:
                last_error = str(ce)
                if attempt < max_retries:
                    await asyncio.sleep(2.0)
                    continue
                raise RuntimeError(f"Сетевая ошибка при обращении к BitBrowser API: {ce}")

        raise RuntimeError(f"BitBrowser API вернул ошибку при открытии {profile_id}: {last_error}")

    async def close_profile(self, profile_id: str) -> bool:
        """Закрывает профиль в BitBrowser."""
        url = f"{self.base_url}/browser/close"
        payload = {"id": profile_id}
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=payload, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                    data = await resp.json()
                    return data.get("success", False)
        except Exception as e:
            logger.warning("Ошибка при закрытии профиля %s: %s", profile_id, e)
            return False
