# technical_strategy.py - МОДУЛЬ ТЕХНИЧЕСКОГО АНАЛИЗА
import logging
import pandas as pd
import numpy as np
from typing import Dict, List, Optional
from datetime import datetime, timedelta
import asyncio

logger = logging.getLogger(__name__)

class TechnicalStrategy:
    """Технический анализ на основе RSI и Bollinger Bands (лонг-стратегия)"""
    
    def __init__(self, tinkoff_executor, lookback_period: int = 50):
        self.executor = tinkoff_executor
        self.lookback_period = lookback_period
        # Кэш для хранения цен по тикерам: {'SBER': [(timestamp, price), ...]}
        self.price_cache = {}
        # Список отслеживаемых тикеров (можно расширить)
        self.tracked_tickers = ['SBER', 'GAZP', 'LKOH', 'ROSN', 'GMKN', 'MOEX']
        logger.info(f"📊 TechnicalStrategy инициализирован для {len(self.tracked_tickers)} тикеров")

    async def update_prices(self, ticker: str) -> None:
        """Обновляет кэш цен для тикера"""
        try:
            price = await self.executor.get_current_price(ticker)
            if price:
                if ticker not in self.price_cache:
                    self.price_cache[ticker] = []
                self.price_cache[ticker].append((datetime.now(), price))
                # Ограничиваем размер истории
                if len(self.price_cache[ticker]) > self.lookback_period * 2:
                    self.price_cache[ticker] = self.price_cache[ticker][-self.lookback_period:]
                logger.debug(f"📈 Обновлена цена {ticker}: {price:.2f}")
        except Exception as e:
            logger.debug(f"⚠️ Ошибка обновления цены {ticker}: {str(e)[:50]}")

    def calculate_rsi(self, prices: List[float], period: int = 14) -> Optional[float]:
        """Расчёт RSI (Relative Strength Index)"""
        if len(prices) < period + 1:
            return None
        deltas = np.diff(prices)
        seed = deltas[:period]
        up = seed[seed >= 0].sum() / period
        down = -seed[seed < 0].sum() / period
        if down == 0:
            return 100.0
        rs = up / down
        rsi = 100.0 - (100.0 / (1.0 + rs))
        
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
            if down == 0:
                rsi = 100.0
            else:
                rs = up / down
                rsi = 100.0 - (100.0 / (1.0 + rs))
        return rsi

    def calculate_bollinger_bands(self, prices: List[float], period: int = 20, std_dev: float = 2.0):
        """Расчёт Bollinger Bands"""
        if len(prices) < period:
            return None, None, None
        sma = np.mean(prices[-period:])
        std = np.std(prices[-period:])
        upper_band = sma + (std * std_dev)
        lower_band = sma - (std * std_dev)
        return upper_band, sma, lower_band

    async def scan_for_signals(self) -> List[Dict]:
        """Сканирование всех тикеров на наличие сигналов"""
        signals = []
        # 1. Обновляем цены для всех тикеров
        update_tasks = [self.update_prices(ticker) for ticker in self.tracked_tickers]
        await asyncio.gather(*update_tasks, return_exceptions=True)
        
        # 2. Анализируем каждый тикер
        for ticker in self.tracked_tickers:
            if ticker not in self.price_cache or len(self.price_cache[ticker]) < 30:
                continue
            prices = [price for _, price in self.price_cache[ticker]]
            current_price = prices[-1] if prices else 0
            
            # Рассчитываем индикаторы
            rsi = self.calculate_rsi(prices)
            upper_band, middle_band, lower_band = self.calculate_bollinger_bands(prices)
            
            if rsi is None or lower_band is None:
                continue
            
            # СТРАТЕГИЯ: Покупаем при RSI < 30 (перепроданность) И цена у нижней полосы Bollinger
            if rsi < 30.0 and current_price <= lower_band * 1.02:
                signal = {
                    'action': 'BUY',
                    'ticker': ticker,
                    'reason': f'Тех. сигнал: RSI={rsi:.1f}, цена у нижней полосы BB',
                    'confidence': min(0.9, (30 - rsi) / 30 * 0.5 + 0.5),
                    'impact_score': 6,
                    'event_type': 'technical_rsi_oversold',
                    'sentiment': 'positive',
                    'current_price': current_price,
                    'strategy': 'RSI_Bollinger_Long',
                    'ai_provider': 'technical',
                    'timestamp': datetime.now().isoformat()
                }
                signals.append(signal)
                logger.info(f"📈 Тех. сигнал на {ticker}: BUY (RSI={rsi:.1f})")
            
            # Дополнительно: Сигнал на продажу для фиксации прибыли (если позиция есть)
            elif rsi > 70.0 and current_price >= upper_band * 0.98:
                signal = {
                    'action': 'SELL',
                    'ticker': ticker,
                    'reason': f'Тех. сигнал: RSI={rsi:.1f}, цена у верхней полосы BB',
                    'confidence': min(0.9, (rsi - 70) / 30 * 0.5 + 0.5),
                    'impact_score': 6,
                    'event_type': 'technical_rsi_overbought',
                    'sentiment': 'neutral',
                    'current_price': current_price,
                    'strategy': 'RSI_Bollinger_Exit',
                    'ai_provider': 'technical',
                    'timestamp': datetime.now().isoformat()
                }
                signals.append(signal)
                logger.info(f"📉 Тех. сигнал на {ticker}: SELL для выхода (RSI={rsi:.1f})")
        
        return signals

    async def run_continuous_scan(self, interval_seconds: int = 60):
        """Непрерывное сканирование в фоновом режиме"""
        logger.info(f"🔄 Запуск непрерывного сканирования каждые {interval_seconds} сек.")
        while True:
            try:
                signals = await self.scan_for_signals()
                if signals:
                    logger.info(f"📊 Найдено {len(signals)} тех. сигналов")
                await asyncio.sleep(interval_seconds)
            except Exception as e:
                logger.error(f"❌ Ошибка в непрерывном сканировании: {str(e)[:100]}")
                await asyncio.sleep(interval_seconds)
