import logging
import statistics
from datetime import datetime, time
import math

logger = logging.getLogger(__name__)

class PairsTradingStrategy:
    """ЕДИНСТВЕННАЯ стратегия - арбитраж SBER/VTBR с ИИ-оптимизацией"""
    
    def __init__(self, client, account_id):
        self.client = client
        self.account_id = account_id
        self.name = "AI Pairs Trading"
        
        # История соотношения SBER/(VTBR*1000)
        self.ratio_history = []
        self.max_history = 50  # 50 последних значений
        
        # Текущие позиции для отслеживания
        self.active_positions = {
            'sber': {'size': 0, 'avg_price': 0},
            'vtbr': {'size': 0, 'avg_price': 0}
        }
        
        # Статистика
        self.total_trades = 0
        self.profitable_trades = 0
        
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
        
        # Активные часы Мосбиржи
        active_periods = [
            (10, 0), (10, 30),   # Утренние прорывы
            (11, 15),             # Середина утра
            (15, 0), (15, 30),   # Вечерний тренд
            (16, 45),             # Перед закрытием
            (18, 50), (19, 20)   # Вечерняя сессия
        ]
        
        # Проверяем, совпадает ли текущее время с одним из периодов
        for h, m in active_periods:
            if hour == h and now.minute == m:
                return True
        
        # Не торгуем в обед (13:00-14:30)
        if time(13, 0) <= current_time <= time(14, 30):
            return False
            
        return False
    
    def analyze(self, instruments):
        """Основная логика арбитражного трейдинга"""
        if not self.should_trade_time():
            logger.info("⏸️ Неактивное время для торговли")
            return []
        
        signals = []
        
        try:
            # Получаем ТОЛЬКО SBER и VTBR
            target_pairs = {'SBER': 'BBG004730N88', 'VTBR': 'BBG004730ZJ9'}
            prices = {}
            
            for ticker, figi in target_pairs.items():
                last_price = self.client.market_data.get_last_prices(figi=[figi])
                if last_price.last_prices:
                    price_obj = last_price.last_prices[0].price
                    price = price_obj.units + price_obj.nano / 1e9
                    prices[ticker] = price
                    logger.info(f"📊 {ticker}: {price:.2f} руб.")
            
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
            
            # Нужно минимум 20 значений для статистики
            if len(self.ratio_history) >= 20:
                mean_ratio = statistics.mean(self.ratio_history)
                std_ratio = statistics.stdev(self.ratio_history) if len(self.ratio_history) > 1 else 0.01
                
                # Рассчитываем Z-score отклонения
                if std_ratio > 0:
                    z_score = (current_ratio - mean_ratio) / std_ratio
                    
                    # 📈 ПРАВИЛА ТОРГОВЛИ ОТ ИИ (оптимизированы)
                    # Если VTBR недооценен относительно SBER (z < -2.0)
                    if z_score < -2.0:
                        # VTBR дешевле, чем должен быть → ПОКУПАЕМ VTBR, ПРОДАЁМ SBER
                        signals.append({
                            'action': 'BUY',
                            'ticker': 'VTBR',
                            'price': vtbr_price,
                            'size': self.calculate_position_size(vtbr_price, 0.02),  # 2% риска
                            'confidence': min(0.9, abs(z_score) / 3),
                            'strategy': self.name,
                            'reason': f"VTBR недооценен на {abs(z_score):.1f}σ (соотношение: {current_ratio:.4f})",
                            'take_profit': vtbr_price * 1.015,  # +1.5%
                            'stop_loss': vtbr_price * 0.99      # -1%
                        })
                        
                        signals.append({
                            'action': 'SELL',
                            'ticker': 'SBER',
                            'price': sber_price,
                            'size': self.calculate_position_size(sber_price, 0.02),
                            'confidence': min(0.9, abs(z_score) / 3),
                            'strategy': self.name,
                            'reason': f"SBER переоценен для парной торговли с VTBR",
                            'take_profit': sber_price * 0.985,  # -1.5%
                            'stop_loss': sber_price * 1.01      # +1%
                        })
                    
                    # Если VTBR переоценен относительно SBER (z > 2.0)
                    elif z_score > 2.0:
                        # VTBR дороже, чем должен быть → ПРОДАЁМ VTBR, ПОКУПАЕМ SBER
                        signals.append({
                            'action': 'SELL',
                            'ticker': 'VTBR',
                            'price': vtbr_price,
                            'size': self.calculate_position_size(vtbr_price, 0.02),
                            'confidence': min(0.9, abs(z_score) / 3),
                            'strategy': self.name,
                            'reason': f"VTBR переоценен на {z_score:.1f}σ (соотношение: {current_ratio:.4f})",
                            'take_profit': vtbr_price * 0.985,  # -1.5%
                            'stop_loss': vtbr_price * 1.01      # +1%
                        })
                        
                        signals.append({
                            'action': 'BUY',
                            'ticker': 'SBER',
                            'price': sber_price,
                            'size': self.calculate_position_size(sber_price, 0.02),
                            'confidence': min(0.9, abs(z_score) / 3),
                            'strategy': self.name,
                            'reason': f"SBER недооценен для парной торговли с VTBR",
                            'take_profit': sber_price * 1.015,  # +1.5%
                            'stop_loss': sber_price * 0.99      # -1%
                        })
                    
                    # Логируем статистику
                    logger.info(f"📈 Соотношение SBER/VTBR: {current_ratio:.4f} (среднее: {mean_ratio:.4f}, Z: {z_score:.2f})")
            
            if signals:
                logger.info(f"🎯 {self.name}: {len(signals)} сигналов")
                self.total_trades += 1
                    
        except Exception as e:
            logger.error(f"❌ Ошибка в парной стратегии: {e}")
            
        return signals
    
    def calculate_position_size(self, price, risk_percent=0.02):
        """Рассчитываем размер позиции на основе 2% риска"""
        # Для теста: 1 лот для VTBR, 1 лот для SBER
        # В реальности: (капитал * риск%) / (цена * волатильность)
        return 1  # Упрощённо, для теста
