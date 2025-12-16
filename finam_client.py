# finam_client.py - MOEX DIRECT + TICKER FIXER
import logging
import aiohttp
import asyncio
import os
from datetime import datetime
from typing import Dict, Optional

logger = logging.getLogger(__name__)

class FinamClient:
    """
    Клиент MOEX ISS.
    1. Тянет реальные цены (TQBR).
    2. Исправляет тикеры (YNDX -> YDEX), чтобы AI не ошибался.
    """
    
    def __init__(self):
        self.price_cache = {} 
        self.last_update = {}
        
        # Словарь алиасов: {Старый: Новый}
        self.ticker_aliases = {
            'YNDX': 'YDEX',   # Яндекс
            'YANDEX': 'YDEX',
            'TCS': 'TCSG',    # Т-Банк
            'TINKOFF': 'TCSG',
            'POLY': 'PLZL',   # Заменяем сложный Полиметалл на Полюс
            'MAIL': 'VKCO',   # VK
            'SBERP': 'SBER',  # Приводим префы к обычке
            'TRANSNEFT': 'TRNFP'
        }
        
        logger.info("🏦 Market Data: MOEX ISS (Real-Time + Auto-Fix)")

    def _correct_ticker(self, ticker: str) -> str:
        return self.ticker_aliases.get(ticker.upper(), ticker.upper())

    async def get_current_price(self, ticker: str) -> Optional[float]:
        # Коррекция тикера перед запросом
        ticker = self._correct_ticker(ticker)
        
        # Кэш 5 секунд
        if ticker in self.price_cache:
            if (datetime.now() - self.last_update.get(ticker, datetime.min)).seconds < 5:
                return self.price_cache[ticker]

        # Запрос к MOEX TQBR
        url = f"https://iss.moex.com/iss/engines/stock/markets/shares/boards/TQBR/securities/{ticker}.json"
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=5.0) as response:
                    if response.status == 200:
                        data = await response.json()
                        marketdata = data.get('marketdata', {}).get('data', [])
                        columns = data.get('marketdata', {}).get('columns', [])
                        
                        if marketdata and columns:
                            try:
                                # Ищем цену последней сделки (LAST)
                                if 'LAST' in columns:
                                    last_idx = columns.index('LAST')
                                    val = marketdata[0][last_idx]
                                    
                                    # Если LAST нет (вечер/утро), берем LCURRENTPRICE
                                    if val is None and 'LCURRENTPRICE' in columns:
                                        val = marketdata[0][columns.index('LCURRENTPRICE')]
                                    
                                    if val is not None:
                                        price = float(val)
                                        self.price_cache[ticker] = price
                                        self.last_update[ticker] = datetime.now()
                                        return price
                            except: pass
            return None
        except Exception as e:
            logger.error(f"❌ MOEX Error ({ticker}): {e}")
            return None

    async def execute_order(self, ticker: str, action: str, quantity: int) -> Dict:
        """Исполнение по рынку"""
        price = await self.get_current_price(ticker)
        if not price:
            return {'status': 'FAILED', 'message': 'No price'}
            
        return {
            'status': 'EXECUTED',
            'price': price,
            'message': 'MOEX Market Execution'
        }
