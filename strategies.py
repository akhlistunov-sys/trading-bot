import logging
import statistics
from datetime import datetime, time
import asyncio
import os

# Импортируем ИИ-ядро
try:
    from ai_core import AICore
    AI_AVAILABLE = True
except ImportError:
    AI_AVAILABLE = False
    logging.warning("❌ AI Core не доступен, используем локальную логику")

logger = logging.getLogger(__name__)

class PairsTradingStrategy:
    """Парный арбитраж SBER/VTBR с ИИ-оптимизацией"""
    
    def __init__(self, client, account_id):
        self.client = client
        self.account_id = account_id
        self.name = "AI Pairs Trading"
        
        # История соотношения SBER/(VTBR*1000)
        self.ratio_history = []
        self.max_history = 50
        
        # Инициализируем ИИ-ядро
        self.ai_core = None
        if AI_AVAILABLE:
            try:
                self.ai_core = AICore()
                logger.info("✅ ИИ-ядро инициализировано")
            except Exception as e:
                logger.error(f"❌ Ошибка инициализации ИИ: {e}")
                self.ai_core = None
        
        # Статистика
        self.total_trades = 0
        self.ai_decisions = 0
        self.local_decisions = 0
        
    def normalize_vtbr_price(self, vtbr_price):
        """Нормализация VTBR: умножаем на 1000 для сравнения с SBER"""
        return vtbr_price * 1000
    
    def calculate_current_ratio(self, sber_price, vtbr_price):
        """Текущее соотношение SBER к нормализованному VTBR"""
        normalized_vtbr = self.normalize_vtbr_price(vtbr_price)
        if normalized_vtbr == 0:
            return 0
        return sber_price / normalized_vtbr
    
    def should_trade_time(self):
        """Торгуем только в активные часы"""
        now = datetime.now()
        current_time = now.time()
        hour = now.hour
        minute = now.minute
        
        # Активные часы Мосбиржи (8 проверок)
        active_periods = [
            (10, 5), (10, 30),
            (11, 15),
            (15, 0), (15, 30),
            (16, 45),
            (18, 50), (19, 20)
        ]
        
        for h, m in active_periods:
            if hour == h and minute == m:
                return True
        
        if time(13, 0) <= current_time <= time(14, 30):
            return False
            
        return False
    
    async def analyze_with_ai(self, market_data):
        """Анализ с помощью ИИ"""
        if not self.ai_core:
            return []
        
        try:
            signals = await self.ai_core.get_trading_decision(market_data)
            self.ai_decisions += 1
            return signals
        except Exception as e:
            logger.error(f"❌ Ошибка ИИ-анализа: {e}")
            return []
    
    def analyze_local(self, market_data):
        """Локальный анализ (если ИИ не доступен)"""
        signals = []
        current_ratio = market_data.get('current_ratio', 0)
        mean_ratio = market_data.get('mean_ratio', 0)
        z_score = market_data.get('z_score', 0)
        prices = market_data.get('prices', {})
        
        if abs(z_score) > 2.0:
            if z_score < -2.0:  # VTBR недооценен
                signals.extend([
                    {
                        'action': 'BUY',
                        'ticker': 'VTBR',
                        'price': prices.get('VTBR', 0),
                        'size': 100,
                        'confidence': min(0.9, abs(z_score) / 3),
                        'strategy': self.name + " (Local)",
                        'reason': f"VTBR недооценен на {abs(z_score):.1f}σ",
                        'take_profit': prices.get('VTBR', 0) * 1.015,
                        'stop_loss': prices.get('VTBR', 0) * 0.99
                    },
                    {
                        'action': 'SELL',
                        'ticker': 'SBER',
                        'price': prices.get('SBER', 0),
                        'size': 1,
                        'confidence': min(0.9, abs(z_score) / 3),
                        'strategy': self.name + " (Local)",
                        'reason': f"SBER переоценен для парной торговли",
                        'take_profit': prices.get('SBER', 0) * 0.985,
                        'stop_loss': prices.get('SBER', 0) * 1.01
                    }
                ])
            else:  # VTBR переоценен
                signals.extend([
                    {
                        'action': 'SELL',
                        'ticker': 'VTBR',
                        'price': prices.get('VTBR', 0),
                        'size': 100,
                        'confidence': min(0.9, abs(z_score) / 3),
                        'strategy': self.name + " (Local)",
                        'reason': f"VTBR переоценен на {z_score:.1f}σ",
                        'take_profit': prices.get('VTBR', 0) * 0.985,
                        'stop_loss': prices.get('VTBR', 0) * 1.01
                    },
                    {
                        'action': 'BUY',
                        'ticker': 'SBER',
                        'price': prices.get('SBER', 0),
                        'size': 1,
                        'confidence': min(0.9, abs(z_score) / 3),
                        'strategy': self.name + " (Local)",
                        'reason': f"SBER недооценен для парной торговли",
                        'take_profit': prices.get('SBER', 0) * 1.015,
                        'stop_loss': prices.get('SBER', 0) * 0.99
                    }
                ])
        
        self.local_decisions += 1
        return signals
    
    async def analyze(self, instruments):
        """Основная логика с ИИ или локальным анализом"""
        if not self.should_trade_time():
            logger.info("⏸️ Неактивное время для торговли")
            return []
        
        signals = []
        
        try:
            # Получаем цены
            target_pairs = {'SBER': 'BBG004730N88', 'VTBR': 'BBG004730ZJ9'}
            prices = {}
            
            for ticker, figi in target_pairs.items():
                last_price = self.client.market_data.get_last_prices(figi=[figi])
                if last_price.last_prices:
                    price_obj = last_price.last_prices[0].price
                    price = price_obj.units + price_obj.nano / 1e9
                    prices[ticker] = price
            
            if 'SBER' not in prices or 'VTBR' not in prices:
                return []
            
            sber_price = prices['SBER']
            vtbr_price = prices['VTBR']
            
            # Рассчитываем текущее соотношение
            current_ratio = self.calculate_current_ratio(sber_price, vtbr_price)
            
            # Обновляем историю
            self.ratio_history.append(current_ratio)
            if len(self.ratio_history) > self.max_history:
                self.ratio_history.pop(0)
            
            # Подготавливаем данные для ИИ
            market_data = {
                'timestamp': datetime.now().isoformat(),
                'prices': prices,
                'current_ratio': current_ratio,
                'balance': 100000,  # Пример
                'positions': {}
            }
            
            # Добавляем статистику если есть история
            if len(self.ratio_history) >= 20:
                mean_ratio = statistics.mean(self.ratio_history)
                std_ratio = statistics.stdev(self.ratio_history) if len(self.ratio_history) > 1 else 0.01
                
                if std_ratio > 0:
                    z_score = (current_ratio - mean_ratio) / std_ratio
                    market_data.update({
                        'mean_ratio': mean_ratio,
                        'std_ratio': std_ratio,
                        'z_score': z_score
                    })
                    
                    logger.info(f"📈 Соотношение: {current_ratio:.4f} (среднее: {mean_ratio:.4f}, Z: {z_score:.2f})")
            
            # Используем ИИ если доступен, иначе локальную логику
            if self.ai_core:
                signals = await self.analyze_with_ai(market_data)
                if signals:
                    logger.info(f"🧠 ИИ принял решение: {len(signals)} сигналов")
            else:
                signals = self.analyze_local(market_data)
                if signals:
                    logger.info(f"💻 Локальная логика: {len(signals)} сигналов")
            
            if signals:
                self.total_trades += 1
                    
        except Exception as e:
            logger.error(f"❌ Ошибка в парной стратегии: {e}")
            
        return signals
