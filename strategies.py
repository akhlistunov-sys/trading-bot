# strategies.py
import logging
import datetime
from tinkoff.invest import OrderDirection, OrderType

logger = logging.getLogger(__name__)

class MomentTradingStrategy:
    """Моментный трейдинг - скальпинг каждые 5-15 минут"""
    
    def __init__(self, client, account_id):
        self.client = client
        self.account_id = account_id
        self.name = "Moment Trading"
        
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
            
            # Стратегия 1: Микро-тренды (5-15 минут)
            for ticker, current_price in prices.items():
                # Простая логика для теста - в реальности сложный анализ
                if ticker == "SBER" and current_price < 305:
                    signals.append({
                        'action': 'BUY',
                        'ticker': ticker,
                        'price': current_price,
                        'size': 5,
                        'confidence': 0.7,
                        'strategy': self.name,
                        'reason': f"SBER ниже 305 (текущая: {current_price})"
                    })
                elif ticker == "GAZP" and current_price < 128:
                    signals.append({
                        'action': 'BUY', 
                        'ticker': ticker,
                        'price': current_price,
                        'size': 10,
                        'confidence': 0.8,
                        'strategy': self.name,
                        'reason': f"GAZP ниже 128 (текущая: {current_price})"
                    })
                elif ticker == "VTBR" and current_price < 0.026:
                    signals.append({
                        'action': 'BUY',
                        'ticker': ticker,
                        'price': current_price,
                        'size': 100,
                        'confidence': 0.75,
                        'strategy': self.name,
                        'reason': f"VTBR ниже 0.026 (текущая: {current_price})"
                    })
                    
        except Exception as e:
            logger.error(f"❌ Ошибка в моментной стратегии: {e}")
            
        return signals

class ArbitrageStrategy:
    """Арбитражные стратегии между связанными акциями"""
    
    def __init__(self, client, account_id):
        self.client = client
        self.account_id = account_id
        self.name = "Arbitrage Trading"
        
    def analyze(self, instruments):
        """Арбитражный анализ"""
        signals = []
        
        try:
            # Получаем цены для арбитража
            prices = {}
            for ticker, figi in instruments.items():
                last_price = self.client.market_data.get_last_prices(figi=[figi])
                if last_price.last_prices:
                    price_obj = last_price.last_prices[0].price
                    price = price_obj.units + price_obj.nano / 1e9
                    prices[ticker] = price
            
            # Простой арбитраж: SBER vs VTBR
            if "SBER" in prices and "VTBR" in prices:
                sber_price = prices["SBER"]
                vtbr_price = prices["VTBR"] * 1000  # Приводим к сопоставимому виду
                
                # Если VTBR дешевле относительно SBER
                if vtbr_price < sber_price * 0.3:
                    signals.append({
                        'action': 'BUY',
                        'ticker': 'VTBR',
                        'price': prices['VTBR'],
                        'size': 100,
                        'confidence': 0.75,
                        'strategy': self.name,
                        'reason': f"VTBR дешевле SBER (VTBR: {vtbr_price:.1f} vs SBER: {sber_price})"
                    })
            
            # Арбитраж: GAZP vs LKOH
            if "GAZP" in prices and "LKOH" in prices:
                gazp_price = prices["GAZP"]
                lkoh_price = prices["LKOH"]
                
                # Если GAZP значительно дешевле относительно LKOH
                if gazp_price * 50 < lkoh_price:  # Примерное соотношение
                    signals.append({
                        'action': 'BUY',
                        'ticker': 'GAZP',
                        'price': gazp_price,
                        'size': 20,
                        'confidence': 0.7,
                        'strategy': self.name,
                        'reason': f"GAZP дешевле LKOH (GAZP: {gazp_price} vs LKOH: {lkoh_price})"
                    })
                    
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
        """Новостной анализ на основе ценовых движений"""
        signals = []
        
        try:
            # Получаем цены для анализа "новостных" движений
            prices = {}
            for ticker, figi in instruments.items():
                last_price = self.client.market_data.get_last_prices(figi=[figi])
                if last_price.last_prices:
                    price_obj = last_price.last_prices[0].price
                    price = price_obj.units + price_obj.nano / 1e9
                    prices[ticker] = price
            
            # Ищем аномальные движения (возможно вызванные новостями)
            for ticker, current_price in prices.items():
                # Если цена резко упала - возможна перепродажа из-за новостей
                if ticker == "SBER" and current_price < 300:
                    signals.append({
                        'action': 'BUY',
                        'ticker': ticker,
                        'price': current_price,
                        'size': 5,
                        'confidence': 0.6,
                        'strategy': self.name,
                        'reason': f"SBER резкое падение (покупка на снижении)"
                    })
                elif ticker == "YNDX" and current_price > 4100:
                    signals.append({
                        'action': 'SELL',
                        'ticker': ticker,
                        'price': current_price,
                        'size': 2,
                        'confidence': 0.65,
                        'strategy': self.name,
                        'reason': f"YNDX сильный рост (фиксация прибыли)"
                    })
                    
        except Exception as e:
            logger.error(f"❌ Ошибка в новостной стратегии: {e}")
            
        return signals
