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
    """УСИЛЕННЫЙ парный арбитраж SBER/VTBR с агрессивным ИИ"""
    
    def __init__(self, client, account_id):
        self.client = client
        self.account_id = account_id
        self.name = "AI Pairs Trading Pro"
        
        self.ratio_history = []
        self.max_history = 100
        
        self.ai_core = None
        self.ai_enabled = False
        
        if AI_AVAILABLE:
            try:
                self.ai_core = AICore()
                self.ai_enabled = True
                logger.info("✅ ИИ-ядро PRO инициализировано (агрессивный режим)")
            except Exception as e:
                logger.error(f"❌ Ошибка инициализации ИИ: {e}")
                self.ai_core = None
        else:
            logger.warning("⚠️ ИИ недоступен, используем усиленную локальную логику")
        
        self.stats = {
            'total_trades': 0,
            'ai_decisions': 0,
            'local_decisions': 0,
            'ai_success_rate': 0,
            'last_analysis': None
        }
        
        self.trading_mode = os.getenv("TRADING_MODE", "AGGRESSIVE_TEST")
        logger.info(f"⚡ Режим торговли: {self.trading_mode}")
    
    def normalize_vtbr_price(self, vtbr_price):
        return vtbr_price * 1000
    
    def calculate_current_ratio(self, sber_price, vtbr_price):
        normalized_vtbr = self.normalize_vtbr_price(vtbr_price)
        if normalized_vtbr == 0:
            return 0
        return sber_price / normalized_vtbr
    
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
        
        if hour < 7 or hour > 22:
            logger.info("🌙 Ночное время, анализ с ограничениями")
            return True
        
        return True
    
    def should_trade(self, signal, force_mode=False):
        """Проверяем можно ли торговать (более либеральные правила для теста)"""
        if force_mode:
            return True
            
        now = datetime.now()
        current_time = now.time()
        hour = now.hour
        minute = now.minute
        
        if hour < 10 or hour > 19:
            logger.info("⏰ Вне основных торговых часов")
            return False
        
        first_30_min = time(9, 50) <= current_time <= time(10, 30)
        last_30_min = time(18, 30) <= current_time <= time(19, 0)
        
        if first_30_min or last_30_min:
            logger.info("⚠️ Первые/последние 30 минут - повышенная волатильность")
            return signal.get('confidence', 0) > 0.8
        
        return signal.get('confidence', 0) > 0.6
    
    async def analyze_with_ai_pro(self, market_data):
        """УСИЛЕННЫЙ анализ с ИИ"""
        if not self.ai_core or not self.ai_enabled:
            return []
        
        try:
            start_time = datetime.now()
            signals = await self.ai_core.get_trading_decision(market_data)
            analysis_time = (datetime.now() - start_time).total_seconds()
            
            self.stats['ai_decisions'] += 1
            self.stats['last_analysis'] = datetime.now().isoformat()
            
            if signals:
                logger.info(f"🧠 ИИ проанализировал за {analysis_time:.2f}с → {len(signals)} сигналов")
                for signal in signals:
                    logger.info(f"   📢 {signal['action']} {signal['ticker']}: {signal['reason'][:80]}...")
            else:
                logger.info(f"🧠 ИИ не надел сигналов ({analysis_time:.2f}с)")
            
            return signals
        except Exception as e:
            logger.error(f"❌ Ошибка ИИ-анализа: {e}")
            return []
    
    def analyze_local_aggressive(self, market_data):
        """АГРЕССИВНАЯ локальная логика для тестирования"""
        signals = []
        current_ratio = market_data.get('current_ratio', 0)
        mean_ratio = market_data.get('mean_ratio', 0)
        z_score = market_data.get('z_score', 0)
        prices = market_data.get('prices', {})
        
        sber_price = prices.get('SBER', 0)
        vtbr_price = prices.get('VTBR', 0)
        
        trading_mode = os.getenv("TRADING_MODE", "AGGRESSIVE_TEST")
        
        if trading_mode == "AGGRESSIVE_TEST":
            tp_percent = 3.0
            sl_percent = 1.8
            confidence_boost = 1.2
        else:
            tp_percent = 2.0
            sl_percent = 1.2
            confidence_boost = 1.0
        
        if abs(z_score) > 1.8:
            confidence = min(0.95, (abs(z_score) / 3) * confidence_boost)
            
            if z_score < -1.8:
                signals.extend([
                    {
                        'action': 'BUY',
                        'ticker': 'VTBR',
                        'price': vtbr_price,
                        'size': 200,
                        'confidence': confidence,
                        'strategy': self.name + " (Aggressive Local)",
                        'reason': f"🔥 VTBR СИЛЬНО недооценен на {abs(z_score):.1f}σ. Агрессивный вход!",
                        'take_profit': vtbr_price * (1 + tp_percent/100),
                        'stop_loss': vtbr_price * (1 - sl_percent/100),
                        'take_profit_percent': tp_percent,
                        'stop_loss_percent': sl_percent
                    },
                    {
                        'action': 'SELL',
                        'ticker': 'SBER',
                        'price': sber_price,
                        'size': 2,
                        'confidence': confidence,
                        'strategy': self.name + " (Aggressive Local)",
                        'reason': f"Парная продажа SBER против переоценки VTBR",
                        'take_profit': sber_price * (1 - tp_percent/100),
                        'stop_loss': sber_price * (1 + sl_percent/100),
                        'take_profit_percent': tp_percent,
                        'stop_loss_percent': sl_percent
                    }
                ])
            else:
                signals.extend([
                    {
                        'action': 'SELL',
                        'ticker': 'VTBR',
                        'price': vtbr_price,
                        'size': 200,
                        'confidence': confidence,
                        'strategy': self.name + " (Aggressive Local)",
                        'reason': f"🔥 VTBR СИЛЬНО переоценен на {z_score:.1f}σ. Агрессивный шорт!",
                        'take_profit': vtbr_price * (1 - tp_percent/100),
                        'stop_loss': vtbr_price * (1 + sl_percent/100),
                        'take_profit_percent': tp_percent,
                        'stop_loss_percent': sl_percent
                    },
                    {
                        'action': 'BUY',
                        'ticker': 'SBER',
                        'price': sber_price,
                        'size': 2,
                        'confidence': confidence,
                        'strategy': self.name + " (Aggressive Local)",
                        'reason': f"Парная покупка SBER против недооценки VTBR",
                        'take_profit': sber_price * (1 + tp_percent/100),
                        'stop_loss': sber_price * (1 - sl_percent/100),
                        'take_profit_percent': tp_percent,
                        'stop_loss_percent': sl_percent
                    }
                ])
        
        self.stats['local_decisions'] += 1
        
        if signals:
            logger.info(f"💻 Локальная агрессивная логика: {len(signals)} сигналов (Z: {z_score:.2f})")
        
        return signals
    
    async def analyze(self, instruments, force_mode=False):
        """ОСНОВНАЯ ЛОГИКА с приоритетом ИИ"""
        if not self.should_analyze(force_mode):
            logger.info("⏸️ Анализ временно отключен")
            return []
        
        signals = []
        
        try:
            target_pairs = {'SBER': 'BBG004730N88', 'VTBR': 'BBG004730ZJ9'}
            prices = {}
            
            for ticker, figi in target_pairs.items():
                last_price = self.client.market_data.get_last_prices(figi=[figi])
                if last_price.last_prices:
                    price_obj = last_price.last_prices[0].price
                    price = price_obj.units + price_obj.nano / 1e9
                    prices[ticker] = price
            
            if 'SBER' not in prices or 'VTBR' not in prices:
                logger.error("❌ Не удалось получить цены")
                return []
            
            sber_price = prices['SBER']
            vtbr_price = prices['VTBR']
            vtbr_normalized = self.normalize_vtbr_price(vtbr_price)
            
            current_ratio = self.calculate_current_ratio(sber_price, vtbr_price)
            
            self.ratio_history.append(current_ratio)
            if len(self.ratio_history) > self.max_history:
                self.ratio_history.pop(0)
            
            now = datetime.now()
            hour = now.hour
            
            market_data = {
                'timestamp': now.isoformat(),
                'prices': prices,
                'vtbr_normalized': vtbr_normalized,
                'current_ratio': current_ratio,
                'balance': 100000,
                'available_cash': 100000,
                'positions': {},
                'time_of_day': f"{hour:02d}:{now.minute:02d}",
                'market_hours': "Основная сессия" if 10 <= hour < 19 else "Вне основной сессии",
                'trading_day': "Будний день" if now.weekday() < 5 else "Выходной",
                'history_length': len(self.ratio_history),
                'ratio_history_preview': str(self.ratio_history[-10:]) if len(self.ratio_history) >= 10 else str(self.ratio_history)
            }
            
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
                    
                    logger.info(f"📊 SBER: {sber_price:.2f}, VTBR: {vtbr_price:.3f} (x1000: {vtbr_normalized:.0f})")
                    logger.info(f"📈 Соотношение: {current_ratio:.4f} (ср: {mean_ratio:.4f}, Z: {z_score:.2f}σ, волатильность: {std_ratio:.4f})")
            
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
            
            filtered_signals = []
            for signal in signals:
                if self.should_trade(signal, force_mode):
                    filtered_signals.append(signal)
            
            if filtered_signals:
                self.stats['total_trades'] += 1
                logger.info(f"🎯 Фильтрация: {len(signals)} → {len(filtered_signals)} торговых сигналов")
                    
        except Exception as e:
            logger.error(f"❌ Критическая ошибка в стратегии: {e}")
            
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
            'trading_mode': self.trading_mode
        }
