# finam_client.py - Клиент для Finam API v1 с JWT авторизацией
import logging
import time
import aiohttp
import asyncio
from typing import Dict, Optional
import json

logger = logging.getLogger(__name__)

class FinamClient:
    """Клиент для Finam API v1 с автоматическим обновлением JWT токена"""
    
    def __init__(self, api_token: str):
        self.api_token = api_token  # bbae67bd-2578-4b00-84bb-f8423f17756d
        self.jwt_token = None
        self.jwt_expiry = 0
        self.account_id = None
        self.base_url = "https://api.finam.ru/v1"
        
        logger.info(f"🏦 FinamClient инициализирован (API токен: {api_token[:8]}...)")
    
    async def _get_jwt_token(self) -> Optional[str]:
        """Получение нового JWT токена (живет 15 минут)"""
        try:
            url = f"{self.base_url}/sessions"
            payload = {"secret": self.api_token}
            
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=payload, timeout=10) as response:
                    if response.status == 200:
                        data = await response.json()
                        jwt_token = data.get("token")
                        
                        if jwt_token:
                            # Получаем информацию о токене
                            token_info = await self._get_token_details(jwt_token)
                            if token_info:
                                # Парсим время экспирации (пример: "2025-07-24T08:06:30Z")
                                expires_at_str = token_info.get("expires_at")
                                if expires_at_str:
                                    # Конвертируем в timestamp (упрощенно)
                                    import datetime
                                    expiry_time = datetime.datetime.fromisoformat(
                                        expires_at_str.replace('Z', '+00:00')
                                    ).timestamp()
                                    self.jwt_expiry = expiry_time
                                
                                self.account_id = token_info.get("account_ids", [])[0] if token_info.get("account_ids") else None
                                logger.info(f"✅ JWT токен получен (истекает через 15 минут)")
                                return jwt_token
            
            logger.error("❌ Не удалось получить JWT токен")
            return None
            
        except Exception as e:
            logger.error(f"❌ Ошибка получения JWT токена: {str(e)[:100]}")
            return None
    
    async def _get_token_details(self, jwt_token: str) -> Optional[Dict]:
        """Получение информации о JWT токене"""
        try:
            url = f"{self.base_url}/sessions/details"
            payload = {"token": jwt_token}
            
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=payload, timeout=5) as response:
                    if response.status == 200:
                        return await response.json()
            return None
            
        except Exception as e:
            logger.debug(f"⚠️ Не удалось получить детали токена: {str(e)[:50]}")
            return None
    
    async def get_fresh_jwt(self) -> Optional[str]:
        """Получение свежего JWT токена (с кэшированием)"""
        # Если токен истек или скоро истекает (менее 5 минут)
        if not self.jwt_token or time.time() > self.jwt_expiry - 300:
            self.jwt_token = await self._get_jwt_token()
        
        return self.jwt_token
    
    async def get_security_quote(self, ticker: str) -> Optional[Dict]:
        """Получение котировки для тикера"""
        jwt_token = await self.get_fresh_jwt()
        if not jwt_token:
            return None
        
        try:
            url = f"{self.base_url}/securities/{ticker}/quotes"
            headers = {"Authorization": f"Bearer {jwt_token}"}
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers, timeout=10) as response:
                    if response.status == 200:
                        data = await response.json()
                        logger.debug(f"✅ Finam цена {ticker}: {data}")
                        return data
                    else:
                        logger.error(f"❌ Finam API ошибка {response.status}: {await response.text()[:100]}")
                        return None
                        
        except Exception as e:
            logger.error(f"❌ Ошибка запроса котировки {ticker}: {str(e)[:100]}")
            return None
    
    async def get_current_price(self, ticker: str) -> Optional[float]:
        """Получение текущей цены тикера"""
        quote_data = await self.get_security_quote(ticker)
        
        if quote_data:
            # Парсим ответ Finam (структура может отличаться)
            # Пример: {"last": 285.40, "bid": 285.30, "ask": 285.50, ...}
            price = quote_data.get("last") or quote_data.get("close") or quote_data.get("price")
            if price:
                return float(price)
        
        return None
