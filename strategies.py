# strategies.py - БЕЗ NUMPY
import logging
import datetime
import math
import statistics

logger = logging.getLogger(__name__)

class MomentTradingStrategy:
    """Моментный трейдинг с условиями выхода"""
    
    def __init__(self, client, account_id):
        self.client = client
        self.account_id = account_id
        self.name = "Moment Trading"
        self.sber_buys = []  # История покупок SBER
        
    def add_exit_signals(self, prices):
        """Условия выхода для SBER"""
        exit_signals = []
        
        if "SBER" in prices and self.sber_buys:
            current_price = prices["SBER"]
            avg_price = sum(self.sber_buys) / len(self.sber_buys)
            
            # Продаем если цена выросла на 1.5%
            if current_price >= avg_price * 1.015:
                exit_size = min(len(self.sber_buys) // 2, 10)  # Продаем половину
                if exit_size > 0:
                    exit_signals.append({
                        'action': 'SELL',
                        'ticker': 'SBER',
                        'price': current_price,
                        'size': exit_size,
                        'confidence': 0.8,
                        'strategy': self.name + " - Exit",
                        'reason': f"Фиксация +{(current_price/avg_price-1)*100:.1f}%"
                    })
            
            # Стоп-лосс при падении 2%
            elif current_price <= avg_price * 0.98:
                exit_size = min(len(self.sber_buys), 5)
                exit_signals.append({
                    'action': 'SELL',
                    'ticker': 'SBER',
                    'price': current_price,
                    'size': exit_size,
                    'confidence': 0.9,
                    'strategy': self.name + " - Stop Loss",
                    'reason': f"Стоп-лосс -{(1-current_price/avg_price)*100:.1f}%"
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
            
            # Упрощенная логика
            if "SBER" in prices and prices["SBER"] < 305:
                signals.append({
                    'action': 'BUY',
                    'ticker': "SBER",
                    'price': prices["SBER"],
                    'size': 2,
                    'confidence': 0.6,
                    'strategy': self.name,
                    'reason': f"SBER ниже 305 ({prices['SBER']})"
                })
                self.sber_buys.append(prices["SBER"])
            
            # Добавляем сигналы выхода
            exit_signals = self.add_exit_signals(prices)
            signals.extend(exit_signals)
                    
        except Exception as e:
            logger.error(f"❌ Ошибка в моментной стратегии: {e}")
            
        return signals

class ArbitrageStrategy:
    """Арбитражная стратегия без numpy"""
    
    def __init__(self, client, account_id):
        self.client = client
        self.account_id = account_id
        self.name = "Arbitrage Trading"
        self.price_history = {}
        self.arbitrage_pairs = [('SBER', 'VTBR'), ('GAZP', 'LKOH')]
        
    def calculate_z_score(self, ticker1, ticker2):
        """Расчет Z-score без numpy"""
        if (ticker1 in self.price_history and ticker2 in self.price_history and
            len(self.price_history[ticker1]) > 10 and len(self.price_history[ticker2]) > 10):
            
            ratios = []
            min_len = min(len(self.price_history[ticker1]), len(self.price_history[ticker2]))
            
            for i in range(min_len):
                price1 = self.price_history[ticker1][i]
                price2 = self.price_history[ticker2][i]
                
                # Для VTBR умножаем на 1000
                if ticker2 == 'VTBR' and price2 < 1:
                    ratio = price1 / (price2 * 1000)
                else:
                    ratio = price1 / price2 if price2 != 0 else 0
                
                ratios.append(ratio)
            
            if len(ratios) > 5:
                current_ratio = ratios[-1]
                mean = statistics.mean(ratios)
                
                if len(ratios) > 1:
                    std = statistics.stdev(ratios)
                else:
                    std = 0.01
                
                if std > 0:
                    z_score = (current_ratio - mean) / std
                    return z_score, current_ratio, mean
        
        return None, None, None
    
    def analyze(self, instruments):
        """Арбитражный анализ"""
        signals = []
        
        try:
            # Получаем цены
            prices = {}
            for ticker, figi in instruments.items():
                last_price = self.client.market_data.get_last_prices(figi=[figi])
                if last_price.last_prices:
                    price_obj = last_price.last_prices[0].price
                    price = price_obj.units + price_obj.nano / 1e9
                    prices[ticker] = price
                    
                    # Сохраняем историю
                    if ticker not in self.price_history:
                        self.price_history[ticker] = []
                    self.price_history[ticker].append(price)
                    if len(self.price_history[ticker]) > 50:
                        self.price_history[ticker].pop(0)
            
            # Анализируем пары
            for ticker1, ticker2 in self.arbitrage_pairs:
                if ticker1 in prices and ticker2 in prices:
                    z_score, current_ratio, mean_ratio = self.calculate_z_score(ticker1, ticker2)
                    
                    if z_score is not None and abs(z_score) > 2.0:
                        if z_score > 2.0:  # ticker1 перекуплен
                            signals.extend([
                                {
                                    'action': 'SELL',
                                    'ticker': ticker1,
                                    'price': prices[ticker1],
                                    'size': 3,
                                    'confidence': min(0.9, abs(z_score) / 3),
                                    'strategy': self.name,
                                    'reason': f"{ticker1} дорогой (Z={z_score:.1f})"
                                },
                                {
                                    'action': 'BUY',
                                    'ticker': ticker2,
                                    'price': prices[ticker2],
                                    'size': 3,
                                    'confidence': min(0.9, abs(z_score) / 3),
                                    'strategy': self.name,
                                    'reason': f"{ticker2} дешевый (Z={z_score:.1f})"
                                }
                            ])
                        elif z_score < -2.0:  # ticker1 недооценен
                            signals.extend([
                                {
                                    'action': 'BUY',
                                    'ticker': ticker1,
                                    'price': prices[ticker1],
                                    'size': 3,
                                    'confidence': min(0.9, abs(z_score) / 3),
                                    'strategy': self.name,
                                    'reason': f"{ticker1} дешевый (Z={z_score:.1f})"
                                },
                                {
                                    'action': 'SELL',
                                    'ticker': ticker2,
                                    'price': prices[ticker2],
                                    'size': 3,
                                    'confidence': min(0.9, abs(z_score) / 3),
                                    'strategy': self.name,
                                    'reason': f"{ticker2} дорогой (Z={z_score:.1f})"
                                }
                            ])
            
            if signals:
                logger.info(f"📊 {self.name}: {len(signals)} сигналов")
                    
        except Exception as e:
            logger.error(f"❌ Ошибка в арбитражной стратегии: {e}")
            
        return signals

class NewsTradingStrategy:
    """Новостной трейдинг"""
    
    def __init__(self, client, account_id):
        self.client = client
        self.account_id = account_id
        self.name = "News Trading"
        
    def analyze(self, instruments):
        """Пока заглушка"""
        return []
