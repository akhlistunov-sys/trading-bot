import logging
import statistics
from datetime import datetime, time
import asyncio
import os
import json

try:
    from ai_core import AICore
    AI_AVAILABLE = True
except ImportError:
    AI_AVAILABLE = False
    logging.warning("❌ AI Core не доступен, используем локальную логику")

logger = logging.getLogger(__name__)

class PairsTradingStrategy:
    """Парный арбитраж LKOH/ROSN с ИИ-оптимизацией"""
    
    def __init__(self, client, account_id):
        self.client = client
        self.account_id = account_id
        self.name = "AI Oil Pairs Trading Pro"
        
        # История соотношения LKOH/(ROSN*3.5) - эмпирическое соотношение
        self.ratio_history = []
        self.max_history = 100
        
        # Инициализируем ИИ-ядро
        self.ai_core = None
        self.ai_enabled = False
        
        if AI_AVAILABLE:
            try:
                self.ai_core = AICore()
                self.ai_enabled = True
                logger.info("✅ ИИ-ядро для нефтяного арбитража инициализировано")
            except Exception as e:
                logger.error(f"❌ Ошибка инициализации ИИ: {e}")
                self.ai_core = None
        else:
            logger.warning("⚠️ ИИ недоступен, используем усиленную локальную логику")
        
        # Статистика
        self.stats = {
            'total_trades': 0,
            'ai_decisions': 0,
            'local_decisions': 0,
            'ai_success_rate': 0,
            'last_analysis': None,
            'pair': 'LKOH/ROSN'
        }
        
        self.trading_mode = os.getenv("TRADING_MODE", "AGGRESSIVE_TEST")
        logger.info(f"⚡ Режим торговли: {self.trading_mode}")
        logger.info(f"🎯 Пара: LKOH (Лукойл) vs ROSN (Роснефть)")
        logger.info(f"📊 Нормализация: 1 LKOH ≈ 3.5 ROSN")
    
    def normalize_rosneft_price(self, rosneft_price):
        """Нормализация ROSN к LKOH: 1 LKOH ≈ 3.5 ROSN (эмпирическое соотношение)"""
        return rosneft_price * 3.5
    
    def calculate_current_ratio(self, lkoh_price, rosneft_price):
        """Текущее соотношение LKOH к нормализованному ROSN"""
        normalized_rosneft = self.normalize_rosneft_price(rosneft_price)
        if normalized_rosneft == 0:
            return 0
        return lkoh_price / normalized_rosneft
    
    def should_analyze(self, force_mode=False):
        """ВСЕГДА разрешаем анализ для тестирования"""
        if force_mode:
            return True
            
        now = datetime.now()
        current_time = now.time()
        
        trading_mode = os.getenv("TRADING_MODE", "AGGRESSIVE_TEST")
        
        if trading_mode == "AGGRESSIVE_TEST":
            return True
        
        hour = now.hour
        
        # Торговые часы Мосбиржи: 7:00-19:00
        if hour < 7 or hour > 19:
            logger.info("🌙 Ночное время, анализ с ограничениями")
            return True
        
        return True
    
    def should_trade(self, signal, force_mode=False):
        """Проверяем можно ли торговать"""
        if force_mode:
            return True
            
        now = datetime.now()
        current_time = now.time()
        hour = now.hour
        
        # Основные торговые часы
        if hour < 10 or hour > 18:
            logger.info("⏰ Вне основных торговых часов (10:00-18:00)")
            return False
        
        # Избегаем начала и конца дня
        first_hour = time(10, 0) <= current_time <= time(11, 0)
        last_hour = time(17, 0) <= current_time <= time(18, 0)
        
        if first_hour or last_hour:
            logger.info("⚠️ Первый/последний час торгов - повышенная волатильность")
            return signal.get('confidence', 0) > 0.8
        
        return signal.get('confidence', 0) > 0.6
    
    async def analyze_with_ai_pro(self, market_data):
        """УСИЛЕННЫЙ анализ с ИИ для нефтяной пары"""
        if not self.ai_core or not self.ai_enabled:
            return []
        
        try:
            start_time = datetime.now()
            signals = await self.ai_core.get_trading_decision(market_data)
            analysis_time = (datetime.now() - start_time).total_seconds()
            
            self.stats['ai_decisions'] += 1
            self.stats['last_analysis'] = datetime.now().isoformat()
            
            if signals:
                logger.info(f"🧠 ИИ проанализировал нефтяную пару за {analysis_time:.2f}с → {len(signals)} сигналов")
                for signal in signals:
                    logger.info(f"   📢 {signal['action']} {signal['ticker']}: {signal['reason'][:80]}...")
            else:
                logger.info(f"🧠 ИИ не нашел сигналов для нефтяной пары ({analysis_time:.2f}с)")
            
            return signals
        except Exception as e:
            logger.error(f"❌ Ошибка ИИ-анализа нефтяной пары: {e}")
            return []
    
    def analyze_local_aggressive(self, market_data):
        """АГРЕССИВНАЯ локальная логика для нефтяной пары"""
        signals = []
        current_ratio = market_data.get('current_ratio', 0)
        mean_ratio = market_data.get('mean_ratio', 0)
        z_score = market_data.get('z_score', 0)
        prices = market_data.get('prices', {})
        
        lkoh_price = prices.get('LKOH', 0)
        rosneft_price = prices.get('ROSN', 0)
        
        trading_mode = os.getenv("TRADING_MODE", "AGGRESSIVE_TEST")
        
        if trading_mode == "AGGRESSIVE_TEST":
            tp_percent = 3.0
            sl_percent = 1.8
            confidence_boost = 1.2
            size_multiplier = 2  # Агрессивнее размер позиции
        else:
            tp_percent = 2.0
            sl_percent = 1.2
            confidence_boost = 1.0
            size_multiplier = 1
        
        # Для нефтяной пары используем размеры:
        # LKOH: 1-2 акции (дорогая ~7,000 руб)
        # ROSN: 10-20 акций (дешевле ~2,000 руб)
        
        if abs(z_score) > 1.8:
            confidence = min(0.95, (abs(z_score) / 3) * confidence_boost)
            
            if z_score < -1.8:  # ROSN недооценен относительно LKOH
                signals.extend([
                    {
                        'action': 'BUY',
                        'ticker': 'ROSN',
                        'price': rosneft_price,
                        'size': 10 * size_multiplier,  # 10-20 акций ROSN
                        'confidence': confidence,
                        'strategy': self.name + " (Aggressive Local)",
                        'reason': f"🔥 ROSN недооценен на {abs(z_score):.1f}σ. LKOH переоценен. Арбитражный вход!",
                        'take_profit': rosneft_price * (1 + tp_percent/100),
                        'stop_loss': rosneft_price * (1 - sl_percent/100),
                        'take_profit_percent': tp_percent,
                        'stop_loss_percent': sl_percent
                    },
                    {
                        'action': 'SELL',
                        'ticker': 'LKOH',
                        'price': lkoh_price,
                        'size': 1 * size_multiplier,  # 1-2 акции LKOH
                        'confidence': confidence,
                        'strategy': self.name + " (Aggressive Local)",
                        'reason': f"Парная продажа LKOH против переоценки ROSN",
                        'take_profit': lkoh_price * (1 - tp_percent/100),
                        'stop_loss': lkoh_price * (1 + sl_percent/100),
                        'take_profit_percent': tp_percent,
                        'stop_loss_percent': sl_percent
                    }
                ])
            else:  # ROSN переоценен относительно LKOH
                signals.extend([
                    {
                        'action': 'SELL',
                        'ticker': 'ROSN',
                        'price': rosneft_price,
                        'size': 10 * size_multiplier,
                        'confidence': confidence,
                        'strategy': self.name + " (Aggressive Local)",
                        'reason': f"🔥 ROSN переоценен на {z_score:.1f}σ. LKOH недооценен. Арбитражный шорт!",
                        'take_profit': rosneft_price * (1 - tp_percent/100),
                        'stop_loss': rosneft_price * (1 + sl_percent/100),
                        'take_profit_percent': tp_percent,
                        'stop_loss_percent': sl_percent
                    },
                    {
                        'action': 'BUY',
                        'ticker': 'LKOH',
                        'price': lkoh_price,
                        'size': 1 * size_multiplier,
                        'confidence': confidence,
                        'strategy': self.name + " (Aggressive Local)",
                        'reason': f"Парная покупка LKOH против недооценки ROSN",
                        'take_profit': lkoh_price * (1 + tp_percent/100),
                        'stop_loss': lkoh_price * (1 - sl_percent/100),
                        'take_profit_percent': tp_percent,
                        'stop_loss_percent': sl_percent
                    }
                ])
        
        self.stats['local_decisions'] += 1
        
        if signals:
            logger.info(f"💻 Локальная логика нефтяной пары: {len(signals)} сигналов (Z: {z_score:.2f})")
        
        return signals
    
    async def analyze(self, instruments, force_mode=False):
        """ОСНОВНАЯ ЛОГИКА для нефтяной пары LKOH/ROSN"""
        if not self.should_analyze(force_mode):
            logger.info("⏸️ Анализ нефтяной пары временно отключен")
            return []
        
        signals = []
        
        try:
            # Нефтяная пара LKOH/ROSN
            target_pairs = {'LKOH': 'BBG004731032', 'ROSN': 'BBG004731354'}
            prices = {}
            
            for ticker, figi in target_pairs.items():
                last_price = self.client.market_data.get_last_prices(figi=[figi])
                if last_price.last_prices:
                    price_obj = last_price.last_prices[0].price
                    price = price_obj.units + price_obj.nano / 1e9
                    prices[ticker] = price
            
            if 'LKOH' not in prices or 'ROSN' not in prices:
                logger.error("❌ Не удалось получить цены нефтяной пары")
                return []
            
            lkoh_price = prices['LKOH']
            rosneft_price = prices['ROSN']
            rosneft_normalized = self.normalize_rosneft_price(rosneft_price)
            
            # Детальный лог для проверки
            logger.info(f"🔢 НЕФТЯНАЯ ПАРА: LKOH={lkoh_price:.0f} руб, ROSN={rosneft_price:.0f} руб")
            logger.info(f"🔢 ROSN нормализованный (x3.5): {rosneft_normalized:.0f} руб")
            
            current_ratio = self.calculate_current_ratio(lkoh_price, rosneft_price)
            
            # Обновляем историю
            self.ratio_history.append(current_ratio)
            if len(self.ratio_history) > self.max_history:
                self.ratio_history.pop(0)
            
            now = datetime.now()
            hour = now.hour
            
            # Подготавливаем данные для ИИ
            market_data = {
                'timestamp': now.isoformat(),
                'prices': prices,
                'rosneft_normalized': rosneft_normalized,
                'current_ratio': current_ratio,
                'balance': 100000,
                'available_cash': 100000,
                'positions': {},
                'time_of_day': f"{hour:02d}:{now.minute:02d}",
                'market_hours': "Основная сессия" if 10 <= hour < 19 else "Вне основной сессии",
                'trading_day': "Будний день" if now.weekday() < 5 else "Выходной",
                'pair': 'LKOH/ROSN',
                'sector': 'Нефтегазовый',
                'history_length': len(self.ratio_history),
                'ratio_history_preview': str(self.ratio_history[-10:]) if len(self.ratio_history) >= 10 else str(self.ratio_history)
            }
            
            # Рассчитываем статистику если есть история
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
                    
                    logger.info(f"📈 Соотношение LKOH/ROSN: {current_ratio:.4f}")
                    logger.info(f"📊 Среднее: {mean_ratio:.4f}, Волатильность: {std_ratio:.4f}, Z-score: {z_score:.2f}σ")
            
            # Используем ИИ если доступен
            if self.ai_enabled and self.ai_core:
                ai_signals = await self.analyze_with_ai_pro(market_data)
                
                if ai_signals:
                    signals.extend(ai_signals)
                else:
                    local_signals = self.analyze_local_aggressive(market_data)
                    signals.extend(local_signals)
            else:
                local_signals = self.analyze_local_aggressive(market_data)
                signals.extend(local_signals)
            
            # Фильтруем сигналы по времени и confidence
            filtered_signals = []
            for signal in signals:
                if self.should_trade(signal, force_mode):
                    filtered_signals.append(signal)
            
            if filtered_signals:
                self.stats['total_trades'] += 1
                logger.info(f"🎯 Фильтрация нефтяной пары: {len(signals)} → {len(filtered_signals)} торговых сигналов")
                    
        except Exception as e:
            logger.error(f"❌ Критическая ошибка в стратегии нефтяной пары: {e}")
            
        return signals
    
    def get_stats(self):
        """Статистика стратегии"""
        total_decisions = self.stats['ai_decisions'] + self.stats['local_decisions']
        if total_decisions > 0:
            ai_percentage = (self.stats['ai_decisions'] / total_decisions) * 100
        else:
            ai_percentage = 0
            
        return {
            **self.stats,
            'ai_percentage': ai_percentage,
            'history_size': len(self.ratio_history),
            'ai_enabled': self.ai_enabled,
            'trading_mode': self.trading_mode,
            'pair': 'LKOH/ROSN'
        }
