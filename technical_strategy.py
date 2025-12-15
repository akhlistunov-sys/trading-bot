# technical_strategy.py - ТЕХ. АНАЛИЗ НА ДАННЫХ FINAM
import logging
import numpy as np
from typing import Dict, List, Optional
from datetime import datetime
import asyncio

logger = logging.getLogger(__name__)

class TechnicalStrategy:
    """Momentum & Trend Following"""
    
    def __init__(self, finam_client, lookback_period: int = 50):
        self.client = finam_client
        self.lookback_period = lookback_period
        self.price_cache = {}
        
        # Основные голубые фишки РФ
        self.tracked_tickers = [
            'SBER', 'GAZP', 'LKOH', 'ROSN', 'GMKN', 'YNDX', 'OZON', 
            'MGNT', 'VTBR', 'TCSG', 'ALRS', 'MOEX'
        ]
        logger.info(f"📊 TechStrategy: отслеживаем {len(self.tracked_tickers)} тикеров через Finam")

    async def update_prices(self, ticker: str) -> None:
        try:
            # Используем Finam Client вместо Tinkoff
            price = await self.client.get_current_price(ticker)
            if price:
                if ticker not in self.price_cache:
                    self.price_cache[ticker] = []
                self.price_cache[ticker].append(price)
                # Храним историю
                if len(self.price_cache[ticker]) > self.lookback_period * 2:
                    self.price_cache[ticker] = self.price_cache[ticker][-self.lookback_period:]
        except Exception as e:
            pass

    def calculate_rsi(self, prices: List[float], period: int = 14) -> Optional[float]:
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
        signals = []
        # Параллельное обновление цен
        update_tasks = [self.update_prices(ticker) for ticker in self.tracked_tickers]
        await asyncio.gather(*update_tasks, return_exceptions=True)
        
        for ticker in self.tracked_tickers:
            if ticker not in self.price_cache or len(self.price_cache[ticker]) < 15:
                continue
            
            prices = self.price_cache[ticker]
            rsi = self.calculate_rsi(prices)
            current_price = prices[-1]
            
            if rsi is None: continue
            
            # Логика: RSI перепродан (<30) -> BUY
            if rsi < 30: 
                 signal = {
                    'action': 'BUY',
                    'ticker': ticker,
                    'reason': f'RSI Oversold ({rsi:.1f})',
                    'confidence': 0.8,
                    'impact_score': 7,
                    'ai_provider': 'technical_finam',
                    'timestamp': datetime.now().isoformat()
                }
                 signals.append(signal)

        return signals
