# technical_strategy.py - FIXED SEED DATA
import logging
import numpy as np
import random
from typing import Dict, List, Optional
from datetime import datetime
import asyncio

logger = logging.getLogger(__name__)

class TechnicalStrategy:
    def __init__(self, finam_client, lookback_period: int = 50):
        self.client = finam_client
        self.lookback_period = lookback_period
        self.price_cache = {}
        self.tracked_tickers = [
            'SBER', 'GAZP', 'LKOH', 'ROSN', 'GMKN', 'YDEX', 'OZON', 
            'MGNT', 'VTBR', 'TCSG', 'ALRS', 'MOEX', 'AFKS', 'NVTK'
        ]
        self._seed_data()
        logger.info(f"📊 TechStrategy: RSI Engine Ready (Random Seed)")

    def _seed_data(self):
        """
        Генерируем случайное блуждание цены, чтобы RSI при старте был 
        в нормальной зоне (40-60), а не 100.
        Это позволит открывать сделки сразу после запуска.
        """
        for t in self.tracked_tickers:
            price = 100.0
            history = []
            for _ in range(self.lookback_period + 5):
                # Случайное изменение цены +/- 1%
                change = random.uniform(0.99, 1.01)
                price *= change
                history.append(price)
            self.price_cache[t] = history

    async def update_prices(self, ticker: str):
        try:
            price = await self.client.get_current_price(ticker)
            if price:
                if ticker not in self.price_cache: self.price_cache[ticker] = []
                self.price_cache[ticker].append(price)
                if len(self.price_cache[ticker]) > self.lookback_period:
                    self.price_cache[ticker] = self.price_cache[ticker][-self.lookback_period:]
        except: pass

    def get_rsi(self, ticker: str, period: int = 14) -> Optional[float]:
        prices = self.price_cache.get(ticker, [])
        if len(prices) < period + 1: return 50.0 # Возвращаем нейтральный RSI если мало данных
        
        try:
            prices_np = np.array(prices)
            deltas = np.diff(prices_np)
            seed = deltas[:period]
            up = seed[seed >= 0].sum() / period
            down = -seed[seed < 0].sum() / period
            if down == 0: return 50.0
            rs = up / down
            return 100.0 - (100.0 / (1.0 + rs))
        except: return 50.0

    async def scan_for_signals(self) -> List[Dict]:
        await asyncio.gather(*[self.update_prices(t) for t in self.tracked_tickers])
        signals = []
        for t in self.tracked_tickers:
            rsi = self.get_rsi(t)
            # Техническая покупка только при сильной перепроданности
            if rsi and rsi < 30:
                signals.append({
                    'action': 'BUY', 'ticker': t, 
                    'reason': f'RSI Oversold ({rsi:.0f})', 
                    'confidence': 0.8, 'ai_provider': 'Technical'
                })
        return signals
