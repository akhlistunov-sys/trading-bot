# finam_client.py - MOEX DIRECT CONNECTION (REAL PRICES)
import logging
import aiohttp
import asyncio
import os
from datetime import datetime
from typing import Dict, Optional

logger = logging.getLogger(__name__)

class FinamClient:
    """
    Клиент для получения цен. 
    Использует прямой шлюз Московской Биржи (MOEX ISS) для получения 
    абсолютно точных рыночных данных без задержек и смс.
    """
    
    def __init__(self):
        self.price_cache = {} 
        self.last_update = {}
        logger.info("🏦 Market Data: Connected to MOEX ISS (Public API)")

    async def get_current_price(self, ticker: str) -> Optional[float]:
        ticker = ticker.upper()
        
        # 1. Проверка кэша (чтобы не спамить биржу чаще раза в 5 сек)
        if ticker in self.price_cache:
            if (datetime.now() - self.last_update.get(ticker, datetime.min)).seconds < 5:
                return self.price_cache[ticker]

        # 2. Запрос к Мосбирже (Режим TQBR - Т+1 Акции и ДР)
        url = f"https://iss.moex.com/iss/engines/stock/markets/shares/boards/TQBR/securities/{ticker}.json"
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=5.0) as response:
                    if response.status == 200:
                        data = await response.json()
                        
                        # Парсинг ответа MOEX ISS
                        # Нам нужен блок 'marketdata' и колонка 'LAST'
                        marketdata = data.get('marketdata', {}).get('data', [])
                        columns = data.get('marketdata', {}).get('columns', [])
                        
                        if not marketdata or not columns:
                            logger.warning(f"⚠️ MOEX: Нет данных для {ticker}")
                            return None
                            
                        try:
                            last_idx = columns.index('LAST')
                            val = marketdata[0][last_idx]
                            
                            # Если торги закрыты, цена может быть None, берем цену закрытия
                            if val is None:
                                close_idx = columns.index('LCURRENTPRICE') # Текущая официальная
                                val = marketdata[0][close_idx]
                            
                            if val:
                                price = float(val)
                                self.price_cache[ticker] = price
                                self.last_update[ticker] = datetime.now()
                                # logger.info(f"💵 Price {ticker}: {price} RUB") # (можно раскомментить для отладки)
                                return price
                        except ValueError:
                            pass
                            
            return None

        except Exception as e:
            logger.error(f"❌ MOEX Price Error {ticker}: {e}")
            return self.price_cache.get(ticker) # Возвращаем старую цену если есть

    async def execute_order(self, ticker: str, action: str, quantity: int) -> Dict:
        """Исполнение ордера (Виртуальное)"""
        price = await self.get_current_price(ticker) or 0.0
        
        # Симуляция проскальзывания на 0.05%
        import random
        slippage = random.uniform(0.9995, 1.0005)
        exec_price = price * slippage
        
        return {
            'status': 'EXECUTED',
            'price': exec_price,
            'message': 'MOEX Execution'
        }
