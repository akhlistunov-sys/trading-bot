# strategies.py
import logging
import datetime
import statistics
import numpy as np

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
    """Серьезная арбитражная стратегия между связанными акциями"""
    
    def __init__(self, client, account_id):
        self.client = client
        self.account_id = account_id
        self.name = "Arbitrage Trading PRO"
        
        # Хранение исторических данных
        self.price_history = {}
        self.ratio_history = {}
        self.position_history = {}
        
        # Параметры стратегии
        self.z_score_threshold = 2.0  # Порог для входа
        self.max_position_size = 10   # Макс лотов на позицию
        self.min_history_points = 20  # Минимум точек для анализа
        
        # Арбитражные пары с весами
        self.arbitrage_pairs = [
            {
                'pair': ('SBER', 'VTBR'),
                'sector': 'banking',
                'weight': 1.0,
                'description': 'Банковский сектор'
            },
            {
                'pair': ('GAZP', 'LKOH'),
                'sector': 'oil_gas',
                'weight': 0.8,
                'description': 'Нефтегазовый сектор'
            },
            {
                'pair': ('GAZP', 'ROSN'),
                'sector': 'oil_gas', 
                'weight': 0.8,
                'description': 'Нефтегазовый сектор'
            },
            {
                'pair': ('GMKN', 'NLMK'),
                'sector': 'metals',
                'weight': 0.6,
                'description': 'Металлургия'
            }
        ]
        
        logger.info(f"✅ {self.name} инициализирована с {len(self.arbitrage_pairs)} парами")
    
    def update_price_history(self, ticker, price):
        """Обновление истории цен"""
        if ticker not in self.price_history:
            self.price_history[ticker] = []
        
        self.price_history[ticker].append(price)
        
        # Ограничиваем размер истории
        if len(self.price_history[ticker]) > 100:
            self.price_history[ticker].pop(0)
    
    def calculate_ratio(self, price1, price2):
        """Расчет соотношения цен между двумя акциями"""
        if price2 == 0:
            return 0
        # Для VTBR умножаем на 1000 для сопоставимости с SBER
        if price2 < 1:  # Это VTBR или подобная дешевая акция
            return price1 / (price2 * 1000)
        return price1 / price2
    
    def get_pair_ratio_stats(self, ticker1, ticker2):
        """Получение статистики по паре"""
        if (ticker1 in self.price_history and ticker2 in self.price_history and
            len(self.price_history[ticker1]) >= self.min_history_points and
            len(self.price_history[ticker2]) >= self.min_history_points):
            
            ratios = []
            min_len = min(len(self.price_history[ticker1]), len(self.price_history[ticker2]))
            
            for i in range(min_len):
                price1 = self.price_history[ticker1][i]
                price2 = self.price_history[ticker2][i]
                ratio = self.calculate_ratio(price1, price2)
                ratios.append(ratio)
            
            if ratios:
                mean_ratio = np.mean(ratios)
                std_ratio = np.std(ratios) if len(ratios) > 1 else 0.01
                current_ratio = self.calculate_ratio(
                    self.price_history[ticker1][-1],
                    self.price_history[ticker2][-1]
                )
                
                z_score = (current_ratio - mean_ratio) / std_ratio if std_ratio > 0 else 0
                
                return {
                    'mean': mean_ratio,
                    'std': std_ratio,
                    'current': current_ratio,
                    'z_score': z_score,
                    'data_points': len(ratios)
                }
        
        return None
    
    def analyze_pair(self, pair_config, prices):
        """Анализ конкретной арбитражной пары"""
        signals = []
        ticker1, ticker2 = pair_config['pair']
        
        if ticker1 in prices and ticker2 in prices:
            price1 = prices[ticker1]
            price2 = prices[ticker2]
            
            # Обновляем историю цен
            self.update_price_history(ticker1, price1)
            self.update_price_history(ticker2, price2)
            
            # Получаем статистику пары
            stats = self.get_pair_ratio_stats(ticker1, ticker2)
            
            if stats and stats['data_points'] >= self.min_history_points:
                z_score = stats['z_score']
                
                # Определяем силу сигнала
                signal_strength = min(abs(z_score) / 3, 0.9)
                
                # Генерируем торговые сигналы
                if z_score > self.z_score_threshold:
                    # ticker1 перекуплен относительно ticker2
                    signals.append({
                        'action': 'SELL',
                        'ticker': ticker1,
                        'pair_ticker': ticker2,
                        'price': price1,
                        'size': min(self.max_position_size, int(5 * pair_config['weight'])),
                        'confidence': signal_strength,
                        'strategy': self.name,
                        'reason': f"{ticker1} перекуплен относительно {ticker2} (Z-score: {z_score:.2f})",
                        'z_score': z_score,
                        'sector': pair_config['sector']
                    })
                    signals.append({
                        'action': 'BUY',
                        'ticker': ticker2,
                        'pair_ticker': ticker1,
                        'price': price2,
                        'size': min(self.max_position_size, int(5 * pair_config['weight'])),
                        'confidence': signal_strength,
                        'strategy': self.name,
                        'reason': f"{ticker2} недооценен относительно {ticker1} (Z-score: {z_score:.2f})",
                        'z_score': z_score,
                        'sector': pair_config['sector']
                    })
                    
                elif z_score < -self.z_score_threshold:
                    # ticker1 недооценен относительно ticker2
                    signals.append({
                        'action': 'BUY',
                        'ticker': ticker1,
                        'pair_ticker': ticker2,
                        'price': price1,
                        'size': min(self.max_position_size, int(5 * pair_config['weight'])),
                        'confidence': signal_strength,
                        'strategy': self.name,
                        'reason': f"{ticker1} недооценен относительно {ticker2} (Z-score: {z_score:.2f})",
                        'z_score': z_score,
                        'sector': pair_config['sector']
                    })
                    signals.append({
                        'action': 'SELL',
                        'ticker': ticker2,
                        'pair_ticker': ticker1,
                        'price': price2,
                        'size': min(self.max_position_size, int(5 * pair_config['weight'])),
                        'confidence': signal_strength,
                        'strategy': self.name,
                        'reason': f"{ticker2} перекуплен относительно {ticker1} (Z-score: {z_score:.2f})",
                        'z_score': z_score,
                        'sector': pair_config['sector']
                    })
        
        return signals
    
    def analyze(self, instruments):
        """Основной анализ всех арбитражных пар"""
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
            
            # Анализируем все арбитражные пары
            pair_signals_count = 0
            for pair_config in self.arbitrage_pairs:
                pair_signals = self.analyze_pair(pair_config, prices)
                signals.extend(pair_signals)
                pair_signals_count += len(pair_signals)
            
            # Логируем статистику
            if signals:
                logger.info(f"📊 {self.name}: {pair_signals_count} арбитражных сигналов")
                
                # Логируем статистику по парам
                for pair_config in self.arbitrage_pairs:
                    ticker1, ticker2 = pair_config['pair']
                    if ticker1 in prices and ticker2 in prices:
                        stats = self.get_pair_ratio_stats(ticker1, ticker2)
                        if stats:
                            logger.info(f"   {ticker1}/{ticker2}: Z={stats['z_score']:.2f}, Mean={stats['mean']:.3f}")
                    
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
