# finam_client.py - ПОЛНЫЙ РАБОЧИЙ ФАЙЛ
import logging
import time
import aiohttp
import asyncio
from typing import Dict, Optional
import json

logger = logging.getLogger(__name__)

class FinamClient:
    """Клиент для Finam API v1 с JWT авторизацией"""
    
    def __init__(self, api_token: str):
        self.api_token = api_token  # bbae67bd-2578-4b00-84bb-f8423f17756d
        self.jwt_token = None
        self.jwt_expiry = 0
        self.base_url = "https://api.finam.ru/v1"
        
    async def get_fresh_jwt(self) -> Optional[str]:
        """Получение свежего JWT токена"""
        if not self.jwt_token or time.time() > self.jwt_expiry - 120:
            jwt = await self._get_jwt_token()
            if jwt:
                self.jwt_token = jwt
                self.jwt_expiry = time.time() + 900  # 15 минут
        return self.jwt_token
    
    async def _get_jwt_token(self) -> Optional[str]:
        """Получение JWT токена"""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.base_url}/sessions",
                    json={"secret": self.api_token},
                    timeout=10
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        return data.get("token")
        except Exception as e:
            logger.error(f"Finam JWT error: {e}")
        return None
    
    async def get_current_price(self, ticker: str) -> Optional[float]:
        """Получение текущей цены"""
        jwt = await self.get_fresh_jwt()
        if not jwt:
            return None
        
        try:
            headers = {"Authorization": f"Bearer {jwt}"}
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{self.base_url}/securities/{ticker}/quotes",
                    headers=headers,
                    timeout=10
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        # Парсим цену из ответа Finam
                        return float(data.get("last", 0))
        except Exception as e:
            logger.debug(f"Finam price error {ticker}: {e}")
        return None
