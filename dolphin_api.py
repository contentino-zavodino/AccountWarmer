"""Модуль работы с Local API антидетект-браузера Dolphin{anty} с поддержкой правил безопасности."""

from __future__ import annotations
import asyncio
import logging
import urllib.parse
from typing import Any, Dict, List, Optional, Tuple
import aiohttp

logger = logging.getLogger("dolphin_api")

class DolphinAPI:
    """Асинхронный клиент для взаимодействия с Local API и Cloud API Dolphin{anty}."""

    def __init__(self, base_url: str = "http://127.0.0.1:3001", api_token: str = ""):
        self.base_url = base_url.rstrip("/")
        self.api_token = api_token.strip()
        self.cloud_api_url = "https://dolphin-anty-api.com"

    def _get_headers(self) -> Dict[str, str]:
        """Возвращает заголовки авторизации с токеном Dolphin."""
        headers = {}
        if self.api_token:
            token = self.api_token.strip()
            if not token.lower().startswith("bearer "):
                headers["Authorization"] = f"Bearer {token}"
            else:
                headers["Authorization"] = token
        return headers

    async def check_connection(self) -> Tuple[bool, str]:
        """
        Проверяет доступность Dolphin{anty} Local API.
        Использует публичный эндпоинт /v1.0/browser_profiles/running.
        """
        headers = self._get_headers()
        check_endpoints = [
            f"{self.base_url}/v1.0/browser_profiles/running",
            f"{self.base_url}/v1.0/browser_profiles/active",
            f"{self.base_url}/v1.0/browser/active-list"
        ]

        for url in check_endpoints:
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=4)) as resp:
                        if resp.status in [200, 201, 204]:
                            return True, "connected"
            except Exception:
                continue

        return False, "offline"

    async def rotate_proxy(self, rotation_url: str, delay: int = 8) -> bool:
        """
        Выполняет ротацию IP мобильного прокси через отправку GET-запроса по ссылке смены IP
        и выдерживает необходимую паузу перед подключением.
        """
        if not rotation_url:
            return True

        clean_url = rotation_url.strip()
        print(f"[*] Ротация мобильного прокси: запрос по ссылке смены IP...")
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(clean_url, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                    status = resp.status
                    print(f"[+] Запрос на смену IP отправлен (HTTP {status}). Ожидание {delay} сек для смены оператора...")
            await asyncio.sleep(delay)
            return True
        except Exception as e:
            print(f"[!] Ошибка при ротации мобильного прокси: {e}")
            await asyncio.sleep(delay)
            return False

    async def get_profile_ids(self, limit: int = 10, platform: Optional[str] = None) -> List[str]:
        """
        Получает список ID профилей из Cloud API Dolphin{anty} по API-токену.
        """
        if not self.api_token:
            return []

        try:
            async with aiohttp.ClientSession() as session:
                url = f"{self.cloud_api_url}/browser_profiles?limit={limit}"
                headers = self._get_headers()
                async with session.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=8)) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        items = data.get("data", [])
                        return [str(item["id"]) for item in items if "id" in item]
        except Exception as e:
            logger.error("Ошибка при получении профилей через Dolphin Cloud API: %s", e)
        return []

    async def open_profile(
        self,
        profile_id: str,
        window_x: int = 0,
        window_y: int = 0,
        window_width: int = 430,
        window_height: int = 800
    ) -> Dict[str, Any]:
        """
        Запускает профиль в Dolphin{anty} с заданными координатами и размерами окна.
        """
        headers = self._get_headers()
        custom_args = (
            f"--window-position={window_x},{window_y} "
            f"--window-size={window_width},{window_height} "
            f"--disable-notifications --mute-audio"
        )
        encoded_args = urllib.parse.quote(custom_args)

        candidate_urls = [
            f"{self.base_url}/v1.0/browser_profiles/{profile_id}/start?automation=1&custom_args={encoded_args}",
            f"{self.base_url}/v1.0/browser/start/{profile_id}?custom_args={encoded_args}"
        ]

        last_error = None
        async with aiohttp.ClientSession() as session:
            for url in candidate_urls:
                try:
                    async with session.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=45)) as resp:
                        if resp.status not in [200, 201]:
                            continue
                        data = await resp.json()
                        if data.get("success"):
                            automation = data.get("automation", {})
                            port = automation.get("port")
                            ws_endpoint = automation.get("wsEndpoint")

                            if not port:
                                continue

                            return {
                                "endpoint": f"http://127.0.0.1:{port}",
                                "port": port,
                                "ws_endpoint": f"ws://127.0.0.1:{port}{ws_endpoint}" if ws_endpoint else None,
                                "raw_data": data
                            }
                        else:
                            last_error = data.get("msg") or data.get("message")
                except Exception as e:
                    last_error = str(e)
                    continue

        raise RuntimeError(f"Не удалось запустить профиль {profile_id} в Dolphin: {last_error or 'проверьте статус Dolphin'}")

    async def close_profile(self, profile_id: str) -> bool:
        """
        Останавливает профиль в Dolphin{anty} и корректно синхронизирует локальную БД.
        """
        headers = self._get_headers()
        candidate_urls = [
            f"{self.base_url}/v1.0/browser_profiles/{profile_id}/stop",
            f"{self.base_url}/v1.0/browser/stop/{profile_id}"
        ]

        async with aiohttp.ClientSession() as session:
            for url in candidate_urls:
                try:
                    async with session.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                        if resp.status in [200, 204]:
                            data = await resp.json()
                            if data.get("success", True):
                                return True
                except Exception:
                    continue
        return False
