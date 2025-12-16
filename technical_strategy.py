# technical_strategy.py - RSI ON DEMAND
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
        # Расширенный список для сбора истории
        self.tracked_tickers = [
            'SBER', 'GAZP', 'LKOH', 'ROSN', 'GMKN', 'YDEX', 'OZON', 
            'MGNT', 'VTBR', 'TCSG', 'ALRS', 'MOEX', 'AFKS', 'NVTK'
        ]
        self._seed_data()
        logger.info(f"📊 TechStrategy: RSI Engine Ready")

    def _seed_data(self):
        # Фейковая история для старта, пока не накопятся реальные тики
        for t in self.tracked_tickers:
            self.price_cache[t] = [100.0] * 20 

    async def update_prices(self, ticker: str):
        # Этот метод вызывается регулярно, чтобы копить историю
        try:
            price = await self.client.get_current_price(ticker)
            if price:
                if ticker not in self.price_cache: self.price_cache[ticker] = []
                self.price_cache[ticker].append(price)
                if len(self.price_cache[ticker]) > self.lookback_period:
                    self.price_cache[ticker] = self.price_cache[ticker][-self.lookback_period:]
        except: pass

    def get_rsi(self, ticker: str, period: int = 14) -> Optional[float]:
        """Возвращает текущий RSI для тикера"""
        prices = self.price_cache.get(ticker, [])
        if len(prices) < period + 1: return None
        
        prices_np = np.array(prices)
        deltas = np.diff(prices_np)
        seed = deltas[:period]
        up = seed[seed >= 0].sum() / period
        down = -seed[seed < 0].sum() / period
        if down == 0: return 100.0
        rs = up / down
        return 100.0 - (100.0 / (1.0 + rs))

    async def scan_for_signals(self) -> List[Dict]:
        # Обновляем цены для всех
        await asyncio.gather(*[self.update_prices(t) for t in self.tracked_tickers])
        signals = []
        for t in self.tracked_tickers:
            rsi = self.get_rsi(t)
            if rsi and rsi < 30:
                signals.append({
                    'action': 'BUY', 'ticker': t, 
                    'reason': f'RSI Oversold ({rsi:.0f})', 
                    'confidence': 0.8, 'ai_provider': 'Technical'
                })
        return signals
