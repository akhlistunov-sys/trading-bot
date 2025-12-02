# arbitrage_strategy.py
import logging
import datetime
import statistics

logger = logging.getLogger(__name__)

class ArbitrageStrategy:
    """Арбитражная стратегия между связанными акциями"""
    
    def __init__(self, client, account_id):
        self.client = client
        self.account_id = account_id
        self.name = "Arbitrage Trading"
        self.price_history = {}  # Храним историю цен
        self.position_history = {}  # Храним позиции
        
    def calculate_ratio(self, price1, price2):
        """Расчет соотношения цен между двумя акциями"""
        if price2 == 0:
            return 0
        return price1 / price2
    
    def get_historical_ratio_stats(self, ticker1, ticker2):
        """Получение статистики исторического соотношения"""
        if ticker1 in self.price_history and ticker2 in self.price_history:
            ratios = []
            for i in range(min(len(self.price_history[ticker1]), len(self.price_history[ticker2]))):
                ratio = self.calculate_ratio(
                    self.price_history[ticker1][i],
                    self.price_history[ticker2][i]
                )
                ratios.append(ratio)
            
            if ratios:
                mean_ratio = statistics.mean(ratios)
                std_ratio = statistics.stdev(ratios) if len(ratios) > 1 else 0
                return mean_ratio, std_ratio
        
        return None, None
    
    def analyze_pair(self, ticker1, ticker2, price1, price2):
        """Анализ арбитражной пары"""
        signals = []
        
        # Сохраняем историю цен
        for ticker, price in [(ticker1, price1), (ticker2, price2)]:
            if ticker not in self.price_history:
                self.price_history[ticker] = []
            self.price_history[ticker].append(price)
            if len(self.price_history[ticker]) > 100:  # Храним последние 100 цен
                self.price_history[ticker].pop(0)
        
        # Рассчитываем текущее соотношение
        current_ratio = self.calculate_ratio(price1, price2)
        
        # Получаем историческую статистику
        mean_ratio, std_ratio = self.get_historical_ratio_stats(ticker1, ticker2)
        
        if mean_ratio and std_ratio:
            # Z-score отклонения от среднего
            if std_ratio > 0:
                z_score = (current_ratio - mean_ratio) / std_ratio
                
                # Правила арбитража
                if z_score > 2.0:  # ticker1 перекуплен относительно ticker2
                    signals.append({
                        'action': 'SELL',
                        'ticker': ticker1,
                        'pair_ticker': ticker2,
                        'price': price1,
                        'size': 5,
                        'confidence': min(0.9, abs(z_score) / 3),
                        'strategy': self.name,
                        'reason': f"{ticker1} перекуплен относительно {ticker2} (Z-score: {z_score:.2f})",
                        'z_score': z_score
                    })
                    signals.append({
                        'action': 'BUY',
                        'ticker': ticker2,
                        'pair_ticker': ticker1,
                        'price': price2,
                        'size': 5,
                        'confidence': min(0.9, abs(z_score) / 3),
                        'strategy': self.name,
                        'reason': f"{ticker2} недооценен относительно {ticker1} (Z-score: {z_score:.2f})",
                        'z_score': z_score
                    })
                
                elif z_score < -2.0:  # ticker1 перепродан относительно ticker2
                    signals.append({
                        'action': 'BUY',
                        'ticker': ticker1,
                        'pair_ticker': ticker2,
                        'price': price1,
                        'size': 5,
                        'confidence': min(0.9, abs(z_score) / 3),
                        'strategy': self.name,
                        'reason': f"{ticker1} недооценен относительно {ticker2} (Z-score: {z_score:.2f})",
                        'z_score': z_score
                    })
                    signals.append({
                        'action': 'SELL',
                        'ticker': ticker2,
                        'pair_ticker': ticker1,
                        'price': price2,
                        'size': 5,
                        'confidence': min(0.9, abs(z_score) / 3),
                        'strategy': self.name,
                        'reason': f"{ticker2} перекуплен относительно {ticker1} (Z-score: {z_score:.2f})",
                        'z_score': z_score
                    })
        
        return signals
    
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
            
            # Анализируем арбитражные пары
            pairs = [
                ("SBER", "VTBR"),  # Банковский сектор
                ("GAZP", "LKOH"),  # Нефтегазовый сектор
                ("GAZP", "ROSN"),  # Нефтегазовый сектор
                ("GMKN", "ALRS"),  # Металлургия
            ]
            
            for ticker1, ticker2 in pairs:
                if ticker1 in prices and ticker2 in prices:
                    pair_signals = self.analyze_pair(
                        ticker1, ticker2, 
                        prices[ticker1], 
                        prices[ticker2]
                    )
                    signals.extend(pair_signals)
            
            # Логируем статистику
            if signals:
                logger.info(f"📊 {self.name}: {len(signals)} арбитражных сигналов")
                    
        except Exception as e:
            logger.error(f"❌ Ошибка в арбитражной стратегии: {e}")
            
        return signals
