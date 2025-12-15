# technical_strategy.py
import logging
import numpy as np
from typing import Dict, List, Optional
from datetime import datetime
import asyncio

logger = logging.getLogger(__name__)

class TechnicalStrategy:
    """Технический анализ: Momentum & Trend Following"""
    
    def __init__(self, tinkoff_executor, lookback_period: int = 50):
        self.executor = tinkoff_executor
        self.lookback_period = lookback_period
        self.price_cache = {}
        
        self.tracked_tickers = [
            'SBER', 'GAZP', 'LKOH', 'ROSN', 'GMKN', 'NVTK', 'YNDX', 'OZON', 
            'MGNT', 'FIVE', 'TATN', 'SNGS', 'VTBR', 'TCSG', 'ALRS', 'CHMF', 
            'NLMK', 'MAGN', 'PLZL', 'POLY', 'MOEX', 'AFKS', 'MTSS', 'PHOR'
        ]
        logger.info(f"📊 TechnicalStrategy инициализирован для {len(self.tracked_tickers)} тикеров")

    async def update_prices(self, ticker: str) -> None:
        try:
            price = await self.executor.get_current_price(ticker)
            if price:
                if ticker not in self.price_cache:
                    self.price_cache[ticker] = []
                self.price_cache[ticker].append(price)
                # Храним историю
                if len(self.price_cache[ticker]) > self.lookback_period * 2:
                    self.price_cache[ticker] = self.price_cache[ticker][-self.lookback_period:]
        except Exception as e:
            # Логируем только реальные ошибки, а не отсутствие данных
            pass

    def calculate_rsi(self, prices: List[float], period: int = 14) -> Optional[float]:
        if len(prices) < period + 1: return None
        
        try:
            prices_np = np.array(prices)
            deltas = np.diff(prices_np)
            seed = deltas[:period]
            
            up = seed[seed >= 0].sum() / period
            down = -seed[seed < 0].sum() / period
            
            if down == 0: return 100.0
            rs = up / down
            rsi = 100.0 - (100.0 / (1.0 + rs))
            
            # Сглаживание
            for i in range(period, len(deltas)):
                delta = deltas[i]
                if delta > 0:
                    up_val = delta
                    down_val = 0.0
                else:
                    up_val = 0.0
                    down_val = -delta
                
                up = (up * (period - 1) + up_val) / period
                down = (down * (period - 1) + down_val) / period
                
                if down == 0: rsi = 100.0
                else:
                    rs = up / down
                    rsi = 100.0 - (100.0 / (1.0 + rs))
            
            return rsi
        except Exception:
            return None

    async def scan_for_signals(self) -> List[Dict]:
        signals = []
        # Параллельное обновление цен
        update_tasks = [self.update_prices(ticker) for ticker in self.tracked_tickers]
        await asyncio.gather(*update_tasks, return_exceptions=True)
        
        for ticker in self.tracked_tickers:
            if ticker not in self.price_cache or len(self.price_cache[ticker]) < 20:
                continue
            
            prices = self.price_cache[ticker]
            rsi = self.calculate_rsi(prices)
            
            if rsi is None: continue
            
            # Стратегия RSI (перепроданность)
            if 30 <= rsi <= 40: 
                 signal = {
                    'action': 'BUY',
                    'ticker': ticker,
                    'reason': f'Technical: RSI Oversold ({rsi:.1f})',
                    'confidence': 0.7,
                    'impact_score': 6,
                    'ai_provider': 'technical',
                    'timestamp': datetime.now().isoformat()
                }
                 signals.append(signal)

        return signals
