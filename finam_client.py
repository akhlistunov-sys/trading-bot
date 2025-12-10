# finam_client.py - ПОЛНОСТЬЮ ПЕРЕРАБОТАННЫЙ ДЛЯ REST API
import logging
import aiohttp
import asyncio
from typing import Dict, Optional, List
import json
from datetime import datetime

logger = logging.getLogger(__name__)

class FinamClient:
    """Клиент для Finam REST API с JWT токеном"""
    
    def __init__(self, jwt_token: str, client_id: str):
        self.jwt_token = jwt_token
        self.client_id = client_id
        self.base_url = "https://tradeapi.finam.ru"
        
        # Кэш цен
        self.price_cache = {}
        self.cache_timeout = 60  # секунд
        
        logger.info(f"🏦 FinamClient инициализирован")
        logger.info(f"   Client ID: {client_id}")
        logger.info(f"   Token starts with: {jwt_token[:20]}...")
    
    def _get_headers(self) -> Dict:
        """Получение заголовков для запросов"""
        return {
            'Authorization': f'Bearer {self.jwt_token}',
            'X-Client-ID': self.client_id,
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        }
    
    async def get_security_quotes(self, security_code: str) -> Optional[Dict]:
        """Получение котировок бумаги"""
        try:
            url = f"{self.base_url}/api/v1/securities/{security_code}/quotes"
            
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    url, 
                    headers=self._get_headers(),
                    timeout=10,
                    ssl=False
                ) as response:
                    
                    if response.status == 200:
                        data = await response.json()
                        logger.debug(f"✅ Finam quotes для {security_code}: {data}")
                        return data
                    elif response.status == 401:
                        logger.error("❌ Finam: Неавторизован (проверь JWT токен)")
                    elif response.status == 404:
                        logger.debug(f"⚠️ Finam: Бумага {security_code} не найдена")
                    else:
                        logger.error(f"❌ Finam ошибка {response.status}: {await response.text()[:100]}")
                    return None
                        
        except asyncio.TimeoutError:
            logger.warning(f"⏰ Finam таймаут для {security_code}")
            return None
        except Exception as e:
            logger.error(f"❌ Ошибка Finam запроса {security_code}: {str(e)[:100]}")
            return None
    
    async def get_current_price(self, ticker: str) -> Optional[float]:
        """Получение текущей цены бумаги"""
        # Проверка кэша
        cache_key = ticker.upper()
        if cache_key in self.price_cache:
            cached_time, cached_price = self.price_cache[cache_key]
            if (datetime.now() - cached_time).seconds < self.cache_timeout:
                return cached_price
        
        try:
            data = await self.get_security_quotes(cache_key)
            
            if data and 'data' in data:
                quotes = data['data']
                if quotes and len(quotes) > 0:
                    # Ищем последнюю цену
                    last_price = None
                    
                    # Пробуем разные поля
                    price_fields = ['last', 'close', 'current', 'price']
                    
                    for field in price_fields:
                        if field in quotes[0]:
                            last_price = quotes[0][field]
                            break
                    
                    if last_price:
                        price = float(last_price)
                        # Обновляем кэш
                        self.price_cache[cache_key] = (datetime.now(), price)
                        logger.info(f"💰 Finam цена {ticker}: {price:.2f} руб.")
                        return price
            
            logger.warning(f"⚠️ Не удалось получить цену {ticker} из Finam")
            return None
            
        except Exception as e:
            logger.error(f"❌ Ошибка получения цены {ticker}: {str(e)[:50]}")
            return None
    
    async def test_connection(self) -> Dict:
        """Тест соединения с Finam API"""
        test_ticker = "SBER"
        
        try:
            # Тест 1: Получение котировок
            quotes_data = await self.get_security_quotes(test_ticker)
            
            # Тест 2: Получение цены
            price = await self.get_current_price(test_ticker)
            
            return {
                'status': 'success' if quotes_data else 'error',
                'test_ticker': test_ticker,
                'quotes_received': bool(quotes_data),
                'price_received': price,
                'quotes_sample': quotes_data['data'][0] if quotes_data and 'data' in quotes_data and quotes_data['data'] else None,
                'token_valid': quotes_data is not None,
                'timestamp': datetime.now().isoformat()
            }
            
        except Exception as e:
            return {
                'status': 'error',
                'error': str(e),
                'test_ticker': test_ticker,
                'timestamp': datetime.now().isoformat()
            }
