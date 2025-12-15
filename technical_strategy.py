# technical_strategy.py - ПОЛНЫЙ ФАЙЛ (MOMENTUM)
import logging
import numpy as np
from typing import Dict, List, Optional
from datetime import datetime
import asyncio

logger = logging.getLogger(__name__)

class TechnicalStrategy:
    """Технический анализ: Momentum & Trend Following (Покупка силы)"""
    
    def __init__(self, tinkoff_executor, lookback_period: int = 50):
        self.executor = tinkoff_executor
        self.lookback_period = lookback_period
        self.price_cache = {}
        
        # ТОП-25 Ликвидных акций РФ (Сбер, Газпром, IT, Ритейл)
        self.tracked_tickers = [
            'SBER', 'GAZP', 'LKOH', 'ROSN', 'GMKN', 'NVTK', 'YNDX', 'OZON', 
            'MGNT', 'FIVE', 'TATN', 'SNGS', 'VTBR', 'TCSG', 'ALRS', 'CHMF', 
            'NLMK', 'MAGN', 'PLZL', 'POLY', 'MOEX', 'AFKS', 'MTSS', 'PHOR', 'TRNFP'
        ]
        logger.info(f"📊 TechnicalStrategy (Momentum) инициализирован для {len(self.tracked_tickers)} тикеров")

    async def update_prices(self, ticker: str) -> None:
        """Обновляет кэш цен для тикера"""
        try:
            price = await self.executor.get_current_price(ticker)
            if price:
                if ticker not in self.price_cache:
                    self.price_cache[ticker] = []
                # Добавляем цену и время
                self.price_cache[ticker].append(price)
                # Храним только нужную историю
                if len(self.price_cache[ticker]) > self.lookback_period * 2:
                    self.price_cache[ticker] = self.price_cache[ticker][-self.lookback_period:]
        except Exception as e:
            logger.debug(f"⚠️ Ошибка обновления цены {ticker}: {str(e)[:50]}")

    def calculate_rsi(self, prices: List[float], period: int = 14) -> Optional[float]:
        """Расчет RSI без Pandas для скорости"""
        if len(prices) < period + 1: return None
        
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

    def calculate_bollinger_bands(self, prices: List[float], period: int = 20, std_dev: float = 2.0):
        """Расчет полос Боллинджера"""
        if len(prices) < period: return None, None, None
        
        # Берем последние N цен
        slice_prices = np.array(prices[-period:])
        sma = np.mean(slice_prices)
        std = np.std(slice_prices)
        
        upper_band = sma + (std * std_dev)
        lower_band = sma - (std * std_dev)
        
        return upper_band, sma, lower_band

    async def scan_for_signals(self) -> List[Dict]:
        """Сканирование рынка на импульс"""
        signals = []
        
        # Обновляем цены параллельно
        update_tasks = [self.update_prices(ticker) for ticker in self.tracked_tickers]
        await asyncio.gather(*update_tasks, return_exceptions=True)
        
        for ticker in self.tracked_tickers:
            if ticker not in self.price_cache or len(self.price_cache[ticker]) < 30:
                continue
            
            prices = self.price_cache[ticker]
            current_price = prices[-1]
            
            rsi = self.calculate_rsi(prices)
            upper, middle, lower = self.calculate_bollinger_bands(prices)
            
            if rsi is None or middle is None: continue
            
            # --- ЛОГИКА MOMENTUM (ИМПУЛЬС) ---
            # Покупаем, когда актив сильный, но еще не перегрет
            
            # Условие на ПОКУПКУ:
            # 1. RSI между 50 и 70 (Растущий тренд)
            # 2. Цена выше средней линии (Подтверждение тренда)
            if 50.0 <= rsi <= 75.0 and current_price > middle:
                strength = 5 + int((rsi - 50) / 5) # Сила сигнала 5-9
                
                signal = {
                    'action': 'BUY',
                    'ticker': ticker,
                    'reason': f'Momentum: RSI={rsi:.1f} (Рост), Цена > SMA',
                    'confidence': min(0.85, 0.5 + (rsi-50)/100),
                    'impact_score': strength,
                    'event_type': 'technical_momentum_up',
                    'sentiment': 'positive',
                    'current_price': current_price,
                    'strategy': 'Momentum_Trend',
                    'ai_provider': 'technical',
                    'timestamp': datetime.now().isoformat()
                }
                signals.append(signal)
            
            # Условие на ПРОДАЖУ (Выход):
            # 1. RSI упал ниже 45 (Тренд ослаб)
            # 2. ИЛИ Цена ушла под среднюю линию
            elif rsi < 45.0 and current_price < middle:
                signal = {
                    'action': 'SELL',
                    'ticker': ticker,
                    'reason': f'Тренд сломлен: RSI={rsi:.1f}, Цена < SMA',
                    'confidence': 0.8,
                    'impact_score': 7,
                    'event_type': 'technical_trend_break',
                    'sentiment': 'negative',
                    'current_price': current_price,
                    'strategy': 'Momentum_Exit',
                    'ai_provider': 'technical',
                    'timestamp': datetime.now().isoformat()
                }
                signals.append(signal)
        
        return signals
