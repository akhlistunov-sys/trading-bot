# finam_client.py - MOEX REAL-TIME + TICKER FIX
import logging
import aiohttp
import asyncio
import os
from datetime import datetime
from typing import Dict, Optional

logger = logging.getLogger(__name__)

class FinamClient:
    """
    Клиент MOEX ISS с коррекцией тикеров.
    Решает проблему редомициляции (YNDX -> YDEX и т.д.)
    """
    
    def __init__(self):
        self.price_cache = {} 
        self.last_update = {}
        
        # КАРТА ИСПРАВЛЕНИЙ ТИКЕРОВ
        # AI может выдавать старые названия, мы их меняем на актуальные для MOEX
        self.ticker_aliases = {
            'YNDX': 'YDEX',  # Яндекс (новый)
            'YANDEX': 'YDEX',
            'TCS': 'TCSG',   # Т-Банк
            'TINKOFF': 'TCSG',
            'POLY': 'PLZL',  # Полиметалл сложный, лучше смотреть Полюс
            'SBERP': 'SBER', # Приводим префы к обычке для простоты (или можно оставить)
            'TRANSNEFT': 'TRNFP'
        }
        
        logger.info("🏦 Market Data: Connected to MOEX ISS (Auto-Correction Enabled)")

    def _correct_ticker(self, ticker: str) -> str:
        """Исправляет старые тикеры на новые"""
        ticker = ticker.upper()
        return self.ticker_aliases.get(ticker, ticker)

    async def get_current_price(self, ticker: str) -> Optional[float]:
        # 1. Коррекция тикера
        original_ticker = ticker
        ticker = self._correct_ticker(ticker)
        
        if ticker != original_ticker:
            # logger.info(f"🔄 Ticker Correction: {original_ticker} -> {ticker}")
            pass

        # 2. Проверка кэша
        if ticker in self.price_cache:
            if (datetime.now() - self.last_update.get(ticker, datetime.min)).seconds < 5:
                return self.price_cache[ticker]

        # 3. Запрос к MOEX
        # TQBR = Т+1 (Основной режим торгов акциями)
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
                                # Пытаемся найти цену последней сделки
                                if 'LAST' in columns:
                                    last_idx = columns.index('LAST')
                                    val = marketdata[0][last_idx]
                                    
                                    if val is not None:
                                        price = float(val)
                                        self.price_cache[ticker] = price # Кэшируем по НОВОМУ тикеру
                                        self.price_cache[original_ticker] = price # И по СТАРОМУ тоже (для совместимости)
                                        self.last_update[ticker] = datetime.now()
                                        self.last_update[original_ticker] = datetime.now()
                                        return price
                            except Exception:
                                pass
                            
            # Если не нашли в TQBR, пробуем просто проверить кэш (вдруг там есть старая цена)
            return self.price_cache.get(ticker)

        except Exception as e:
            logger.error(f"❌ MOEX Price Error {ticker}: {e}")
            return self.price_cache.get(ticker)

    async def execute_order(self, ticker: str, action: str, quantity: int) -> Dict:
        """Виртуальное исполнение по реальной цене"""
        # Сначала получаем актуальную цену (с учетом коррекции тикера)
        price = await self.get_current_price(ticker)
        
        if not price:
            return {'status': 'FAILED', 'message': 'No price data'}
        
        # Симуляция рыночного исполнения
        return {
            'status': 'EXECUTED',
            'price': price,
            'message': 'MOEX Market Execution'
        }
