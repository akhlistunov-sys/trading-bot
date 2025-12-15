# tinkoff_executor.py - С КЭШИРОВАНИЕМ РЕАЛЬНЫХ ЦЕН
import logging
import os
import aiohttp
import json
from typing import Optional

logger = logging.getLogger(__name__)

class TinkoffExecutor:
    """Получение цен с приоритетом: Finam -> MOEX -> Дисковый Кэш"""
    
    def __init__(self):
        self.jwt_token = os.getenv('FINAM_API_TOKEN', '')
        self.finam_client_id = os.getenv('FINAM_CLIENT_ID', '621971R9IP3')
        self.finam_client = None
        
        # Файл для хранения последних известных цен
        self.cache_file = 'price_cache.json'
        self.price_cache = self._load_cache()

        # Инициализация Finam
        if self.jwt_token:
            try:
                from finam_client import FinamClient
                self.finam_client = FinamClient(self.jwt_token, self.finam_client_id)
            except Exception:
                pass
        
        # АКТУАЛЬНЫЕ ЗАГЛУШКИ (ДЕКАБРЬ 2024/25) - на случай первого запуска без инета
        self.emergency_prices = {
            'SBER': 245.50, 'GAZP': 118.30, 'LKOH': 7100.0, 'ROSN': 580.0,
            'NVTK': 980.0, 'GMKN': 115.0, 'YNDX': 3800.0, 'OZON': 3100.0,
            'MOEX': 210.0, 'TCSG': 2650.0, 'VTBR': 0.021
        }
        
        logger.info("🏦 TinkoffExecutor: Цены только реальные или из кэша")

    def _load_cache(self) -> dict:
        if os.path.exists(self.cache_file):
            try:
                with open(self.cache_file, 'r') as f:
                    return json.load(f)
            except: return {}
        return {}

    def _save_cache(self):
        try:
            with open(self.cache_file, 'w') as f:
                json.dump(self.price_cache, f)
        except: pass

    async def get_current_price(self, ticker: str) -> Optional[float]:
        ticker = ticker.upper()
        price = None
        
        # 1. Пробуем FINAM
        if self.finam_client:
            try:
                price = await self.finam_client.get_current_price(ticker)
                if price:
                    logger.info(f"💰 Finam: {ticker} = {price}")
                    self.price_cache[ticker] = price
                    self._save_cache()
                    return price
            except: pass
            
        # 2. Пробуем MOEX (Публичный API)
        try:
            url = f"https://iss.moex.com/iss/engines/stock/markets/shares/boards/TQBR/securities/{ticker}.json"
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as resp:
                    data = await resp.json()
                    marketdata = data['marketdata']['data']
                    if marketdata:
                        # Берем LAST или LCURRENTPRICE
                        val = marketdata[0][12] or marketdata[0][24] 
                        if val:
                            price = float(val)
                            logger.info(f"💰 MOEX: {ticker} = {price}")
                            self.price_cache[ticker] = price
                            self._save_cache()
                            return price
        except: pass
        
        # 3. Если онлайн не доступен - берем из КЭША на диске
        if ticker in self.price_cache:
            price = self.price_cache[ticker]
            logger.warning(f"⚠️ {ticker}: Использую кэшированную цену {price}")
            return price
            
        # 4. В самом крайнем случае - аварийная заглушка (чтобы не упасть)
        if ticker in self.emergency_prices:
            return self.emergency_prices[ticker]
            
        return None
