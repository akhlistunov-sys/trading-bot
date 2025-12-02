# strategies.py - ПОЛНЫЙ ОБНОВЛЕННЫЙ КОД
import logging
import datetime
import statistics
import numpy as np

logger = logging.getLogger(__name__)

class MomentTradingStrategy:
    """Моментный трейдинг с условиями выхода"""
    
    def __init__(self, client, account_id):
        self.client = client
        self.account_id = account_id
        self.name = "Moment Trading"
        self.position_history = {}  # История позиций: {ticker: [покупки]}
        
    def add_exit_signals(self, prices, current_positions):
        """Добавляем условия выхода для накопленных позиций"""
        exit_signals = []
        
        # Выход из SBER позиций
        sber_position = current_positions.get("SBER", 0)
        if sber_position > 0 and "SBER" in prices:
            current_price = prices["SBER"]
            
            # Если накопили много SBER и цена выросла - продаем часть
            if sber_position >= 20 and current_price > 305:
                exit_size = min(sber_position, 10)  # Продаем до 10 лотов
                exit_signals.append({
                    'action': 'SELL',
                    'ticker': 'SBER',
                    'price': current_price,
                    'size': exit_size,
                    'confidence': 0.8,
                    'strategy': self.name + " - Exit",
                    'reason': f"Фиксация прибыли: накоплено {sber_position} лотов"
                })
        
        return exit_signals
    
    def analyze(self, instruments):
        """Анализ для моментного трейдинга"""
        signals = []
        
        try:
            # Получаем текущие цены
            prices = {}
            for ticker, figi in instruments.items():
                last_price = self.client.market_data.get_last_prices(figi=[figi])
                if last_price.last_prices:
                    price_obj = last_price.last_prices[0].price
                    price = price_obj.units + price_obj.nano / 1e9
                    prices[ticker] = price
            
            # Упрощенная логика (позже заменим на серьезную)
            if "SBER" in prices and prices["SBER"] < 305:
                signals.append({
                    'action': 'BUY',
                    'ticker': "SBER",
                    'price': prices["SBER"],
                    'size': 2,  # Уменьшили размер
                    'confidence': 0.6,
                    'strategy': self.name,
                    'reason': f"SBER ниже 305 (текущая: {prices['SBER']})"
                })
                    
        except Exception as e:
            logger.error(f"❌ Ошибка в моментной стратегии: {e}")
            
        return signals

class ArbitrageStrategy:
    """Серьезная арбитражная стратегия между связанными акциями"""
    
    def __init__(self, client, account_id):
        self.client = client
        self.account_id = account_id
        self.name = "Arbitrage Trading PRO"
        
        # Хранение исторических данных
        self.price_history = {}
        self.ratio_history = {}
        
        # Параметры стратегии
        self.z_score_threshold = 2.0
        self.max_position_size = 5
        self.min_history_points = 20
        
        # Арбитражные пары
        self.arbitrage_pairs = [
            ('SBER', 'VTBR'),   # Банковский сектор
            ('GAZP', 'LKOH'),   # Нефтегаз
            ('GAZP', 'ROSN'),   # Нефтегаз
        ]
        
        logger.info(f"✅ {self.name} инициализирована")
    
    def update_price_history(self, ticker, price):
        """Обновление истории цен"""
        if ticker not in self.price_history:
            self.price_history[ticker] = []
        
        self.price_history[ticker].append(price)
        
        if len(self.price_history[ticker]) > 100:
            self.price_history[ticker].pop(0)
    
    def calculate_ratio(self, price1, price2):
        """Расчет соотношения цен"""
        if price2 == 0:
            return 0
        # Для VTBR умножаем на 1000 для сопоставимости
        if price2 < 1:
            return price1 / (price2 * 1000)
        return price1 / price2
    
    def get_pair_stats(self, ticker1, ticker2):
        """Статистика по паре"""
        if (ticker1 in self.price_history and ticker2 in self.price_history and
            len(self.price_history[ticker1]) >= self.min_history_points and
            len(self.price_history[ticker2]) >= self.min_history_points):
            
            ratios = []
            min_len = min(len(self.price_history[ticker1]), len(self.price_history[ticker2]))
            
            for i in range(min_len):
                ratio = self.calculate_ratio(
                    self.price_history[ticker1][i],
                    self.price_history[ticker2][i]
                )
                ratios.append(ratio)
            
            if ratios:
                mean = np.mean(ratios)
                std = np.std(ratios) if len(ratios) > 1 else 0.01
                current = self.calculate_ratio(
                    self.price_history[ticker1][-1],
                    self.price_history[ticker2][-1]
                )
                
                z_score = (current - mean) / std if std > 0 else 0
                
                return mean, std, current, z_score
        
        return None, None, None, None
    
    def analyze(self, instruments):
        """Основной анализ арбитражных пар"""
        signals = []
        
        try:
            # Получаем текущие цены
            prices = {}
            for ticker, figi in instruments.items():
                last_price = self.client.market_data.get_last_prices(figi=[figi])
                if last_price.last_prices:
                    price_obj = last_price.last_prices[0].price
                    price = price_obj.units + price_obj.nano / 1e9
                    prices[ticker] = price
                    self.update_price_history(ticker, price)
            
            # Анализируем пары
            for ticker1, ticker2 in self.arbitrage_pairs:
                if ticker1 in prices and ticker2 in prices:
                    mean, std, current, z_score = self.get_pair_stats(ticker1, ticker2)
                    
                    if z_score is not None and abs(z_score) > self.z_score_threshold:
                        signal_strength = min(abs(z_score) / 3, 0.9)
                        
                        if z_score > 0:  # ticker1 дороже относительно ticker2
                            signals.extend([
                                {
                                    'action': 'SELL',
                                    'ticker': ticker1,
                                    'price': prices[ticker1],
                                    'size': self.max_position_size,
                                    'confidence': signal_strength,
                                    'strategy': self.name,
                                    'reason': f"{ticker1} перекуплен (Z={z_score:.2f})"
                                },
                                {
                                    'action': 'BUY',
                                    'ticker': ticker2,
                                    'price': prices[ticker2],
                                    'size': self.max_position_size,
                                    'confidence': signal_strength,
                                    'strategy': self.name,
                                    'reason': f"{ticker2} недооценен (Z={z_score:.2f})"
                                }
                            ])
                        else:  # ticker1 дешевле относительно ticker2
                            signals.extend([
                                {
                                    'action': 'BUY',
                                    'ticker': ticker1,
                                    'price': prices[ticker1],
                                    'size': self.max_position_size,
                                    'confidence': signal_strength,
                                    'strategy': self.name,
                                    'reason': f"{ticker1} недооценен (Z={z_score:.2f})"
                                },
                                {
                                    'action': 'SELL',
                                    'ticker': ticker2,
                                    'price': prices[ticker2],
                                    'size': self.max_position_size,
                                    'confidence': signal_strength,
                                    'strategy': self.name,
                                    'reason': f"{ticker2} перекуплен (Z={z_score:.2f})"
                                }
                            ])
            
            if signals:
                logger.info(f"📊 {self.name}: {len(signals)} сигналов")
                    
        except Exception as e:
            logger.error(f"❌ Ошибка в арбитражной стратегии: {e}")
            
        return signals

class NewsTradingStrategy:
    """Упрощенный новостной трейдинг"""
    
    def __init__(self, client, account_id):
        self.client = client
        self.account_id = account_id
        self.name = "News Trading"
        
    def analyze(self, instruments):
        """Новостной анализ"""
        # Пока возвращаем пустой список - добавим позже
        return []
