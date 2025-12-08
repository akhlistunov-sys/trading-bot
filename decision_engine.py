import logging
import os
from typing import Dict, List
from datetime import datetime

logger = logging.getLogger(__name__)

class DecisionEngine:
    """Движок принятия торговых решений на основе анализа новостей (ИСПРАВЛЕННЫЙ)"""
    
    def __init__(self):
        # Параметры стратегии ЗАГРУЖАЕМ из переменных окружения
        self.base_position_size = float(os.getenv("BASE_POSITION_SIZE", "5.0"))
        self.base_stop_loss = float(os.getenv("BASE_STOP_LOSS", "2.0"))
        self.min_confidence = float(os.getenv("MIN_CONFIDENCE", "0.3"))  # НИЗКИЙ для тестирования
        self.min_impact_score = int(os.getenv("MIN_IMPACT_SCORE", "2"))  # НИЗКИЙ для тестирования
        
        # ===== КРИТИЧЕСКИЙ ОТЛАДОЧНЫЙ ЛОГ =====
        logger.info("=" * 50)
        logger.info("🎯 DecisionEngine v2.0 - АГРЕССИВНЫЙ РЕЖИМ ТЕСТИРОВАНИЯ")
        logger.info(f"   • min_confidence = {self.min_confidence} (НИЗКИЙ для тестов)")
        logger.info(f"   • min_impact_score = {self.min_impact_score} (НИЗКИЙ для тестов)")
        logger.info(f"   • base_position_size = {self.base_position_size}%")
        logger.info(f"   • base_stop_loss = {self.base_stop_loss}%")
        logger.info("=" * 50)
        
        # Множители для разных типов событий (УПРОЩЕНО для тестов)
        self.event_multipliers = {
            'earnings_report': 1.5,    # УВЕЛИЧЕНО
            'dividend': 1.4,           # УВЕЛИЧЕНО
            'merger_acquisition': 1.6, # УВЕЛИЧЕНО
            'regulatory': 1.0,         # НЕЙТРАЛЬНО
            'geopolitical': 0.9,       # Слегка снижаем
            'market_update': 1.2,      # УВЕЛИЧЕНО
            'corporate_action': 1.1,   # УВЕЛИЧЕНО
            'other': 1.0               # НЕЙТРАЛЬНО
        }
        
        # Множители для тональности (УПРОЩЕНО для тестов)
        self.sentiment_multipliers = {
            'positive': 1.5,   # СИЛЬНЫЙ буст
            'negative': 1.0,   # Нейтрально
            'neutral': 1.2,    # В тестах - BUY на neutral!
            'mixed': 1.1       # Слабый буст
        }
        
        # Статистика
        self.stats = {
            'total_signals_generated': 0,
            'buy_signals': 0,
            'sell_signals': 0,
            'hold_signals': 0,
            'signals_by_event_type': {},
            'avg_impact_score': 0,
            'avg_confidence': 0
        }
        
        logger.info("🎯 Decision Engine инициализирован (АГРЕССИВНЫЙ ТЕСТ-РЕЖИМ)")
    
    def calculate_position_size(self, analysis: Dict) -> float:
        """Расчет размера позиции (УПРОЩЕННАЯ формула для тестов)"""
        
        confidence = analysis.get('confidence', 0.5)
        impact_score = analysis.get('impact_score', 1)
        
        # ПРОСТАЯ формула: 5% * confidence * (impact_score/5)
        position_size = self.base_position_size * confidence * (impact_score / 5.0)
        
        # Применяем множители (упрощенно)
        event_type = analysis.get('event_type', 'other')
        sentiment = analysis.get('sentiment', 'neutral')
        
        if event_type in self.event_multipliers:
            position_size *= self.event_multipliers[event_type]
        
        if sentiment in self.sentiment_multipliers:
            position_size *= self.sentiment_multipliers[sentiment]
        
        # Ограничения (для тестов шире)
        position_size = max(2.0, min(15.0, position_size))  # От 2% до 15%
        
        return round(position_size, 2)
    
    def calculate_stop_loss(self, analysis: Dict) -> float:
        """Расчет стоп-лосса (УПРОЩЕННЫЙ)"""
        
        impact_score = analysis.get('impact_score', 1)
        
        # Простая формула: 2% для низкого impact, 1% для высокого
        if impact_score >= 7:
            stop_loss = 1.0
        elif impact_score >= 4:
            stop_loss = 1.5
        else:
            stop_loss = 2.0
        
        # Ограничения
        stop_loss = max(1.0, min(4.0, stop_loss))
        
        return round(stop_loss, 2)
    
    def calculate_take_profit(self, stop_loss: float) -> float:
        """Расчет тейк-профита (риск:прибыль = 1:2.5 для тестов)"""
        return round(stop_loss * 2.5, 2)
    
    def determine_trade_action(self, analysis: Dict) -> str:
        """Определение действия (ИСПРАВЛЕННЫЙ для тестирования)"""
        
        sentiment = analysis.get('sentiment', 'neutral')
        event_type = analysis.get('event_type', '')
        confidence = analysis.get('confidence', 0)
        impact_score = analysis.get('impact_score', 0)
        
        logger.debug(f"   📊 Action decision: sentiment={sentiment}, confidence={confidence:.2f}, impact={impact_score}")
        
        # АГРЕССИВНЫЙ РЕЖИМ ТЕСТИРОВАНИЯ:
        # 1. Positive → BUY (всегда)
        if sentiment == 'positive':
            return 'BUY'
        
        # 2. Negative → SELL (только при высокой уверенности)
        elif sentiment == 'negative':
            if confidence > 0.6 and impact_score >= 4:
                return 'SELL'
            else:
                return 'HOLD'
        
        # 3. Neutral → BUY в тестовом режиме!
        elif sentiment == 'neutral':
            # В тестовом режиме BUY на neutral с хорошими показателями
            if confidence > self.min_confidence and impact_score >= self.min_impact_score:
                return 'BUY'
            else:
                return 'HOLD'
        
        # 4. Mixed → BUY при хороших показателях
        elif sentiment == 'mixed':
            if confidence > 0.5 and impact_score >= 3:
                return 'BUY'
            else:
                return 'HOLD'
        
        # 5. Дивиденды и отчетность → BUY (в тестовом режиме)
        elif event_type in ['dividend', 'earnings_report']:
            return 'BUY'
        
        # 6. По умолчанию - агрессивный BUY в тестовом режиме
        else:
            if confidence > self.min_confidence:
                return 'BUY'
            else:
                return 'HOLD'
    
    def generate_signals(self, analysis: Dict) -> List[Dict]:
        """Генерация торговых сигналов на основе анализа (ИСПРАВЛЕННЫЙ)"""
        
        signals = []
        
        # Проверяем минимальные требования (УПРОЩЕНО для тестов)
        confidence = analysis.get('confidence', 0)
        impact_score = analysis.get('impact_score', 0)
        relevance_score = analysis.get('relevance_score', 0)
        tickers = analysis.get('tickers', [])
        
        logger.info("🔍 DecisionEngine анализ:")
        logger.info(f"   • confidence: {confidence:.2f} (требуется >= {self.min_confidence})")
        logger.info(f"   • impact_score: {impact_score} (требуется >= {self.min_impact_score})")
        logger.info(f"   • relevance_score: {relevance_score} (требуется >= 30)")
        logger.info(f"   • tickers: {tickers} (требуется не пустой)")
        logger.info(f"   • event_type: {analysis.get('event_type', 'unknown')}")
        logger.info(f"   • sentiment: {analysis.get('sentiment', 'unknown')}")
        
        # УПРОЩЕННЫЕ фильтры для тестирования
        if (confidence < self.min_confidence or 
            impact_score < self.min_impact_score or 
            relevance_score < 30 or  # НИЗКИЙ порог
            not tickers):
            
            failed_checks = []
            if confidence < self.min_confidence:
                failed_checks.append(f"confidence {confidence:.2f} < {self.min_confidence}")
            if impact_score < self.min_impact_score:
                failed_checks.append(f"impact {impact_score} < {self.min_impact_score}")
            if relevance_score < 30:
                failed_checks.append(f"relevance {relevance_score} < 30")
            if not tickers:
                failed_checks.append("no tickers")
            
            logger.info(f"   ❌ Анализ ОТБРОШЕН: {', '.join(failed_checks)}")
            return signals
        
        logger.info("✅ Анализ ПРОШЁЛ все фильтры!")
        
        # Для каждого тикера создаем сигнал (максимум 2 тикера для тестов)
        for ticker in tickers[:2]:
            # Определяем действие
            action = self.determine_trade_action(analysis)
            
            # Обновляем статистику
            if action == 'BUY':
                self.stats['buy_signals'] += 1
            elif action == 'SELL':
                self.stats['sell_signals'] += 1
            else:
                self.stats['hold_signals'] += 1
                logger.info(f"   ⏸️  Для {ticker}: действие HOLD, пропускаем")
                continue
            
            # Рассчитываем параметры
            position_size = self.calculate_position_size(analysis)
            stop_loss_percent = self.calculate_stop_loss(analysis)
            take_profit_percent = self.calculate_take_profit(stop_loss_percent)
            
            # Корректируем action если нужно (тестовый режим)
            # В тестовом режиме SELL → BUY если мало SELL сигналов
            if action == 'SELL' and self.stats['sell_signals'] > self.stats['buy_signals'] * 2:
                logger.info(f"   🔄 Корректирую {ticker}: SELL → BUY (балансировка)")
                action = 'BUY'
                self.stats['sell_signals'] -= 1
                self.stats['buy_signals'] += 1
            
            # Формируем сигнал
            signal = {
                'action': action,
                'ticker': ticker,
                'reason': analysis.get('summary', 'Торговый сигнал на основе анализа новостей'),
                'confidence': confidence,
                'impact_score': impact_score,
                'relevance_score': relevance_score,
                'event_type': analysis.get('event_type', 'other'),
                'sentiment': analysis.get('sentiment', 'neutral'),
                'position_size_percent': position_size,
                'stop_loss_percent': stop_loss_percent,
                'take_profit_percent': take_profit_percent,
                'strategy': 'News NLP Trading (Test Mode)',
                'ai_generated': analysis.get('ai_provider') != 'simple',
                'ai_provider': analysis.get('ai_provider', 'simple'),
                'news_id': analysis.get('news_id', ''),
                'news_title': analysis.get('news_title', '')[:100],
                'timestamp': datetime.now().isoformat()
            }
            
            signals.append(signal)
            
            # Логируем с деталями
            logger.info(f"🎯 СИГНАЛ СОЗДАН: {action} {ticker} | "
                       f"Size: {position_size}% | SL: {stop_loss_percent}% | "
                       f"TP: {take_profit_percent}% | Impact: {impact_score}")
            logger.info(f"   📝 Причина: {signal['reason'][:80]}...")
        
        # Обновляем статистику
        self.stats['total_signals_generated'] += len(signals)
        
        if signals:
            event_type = analysis.get('event_type', 'other')
            self.stats['signals_by_event_type'][event_type] = \
                self.stats['signals_by_event_type'].get(event_type, 0) + len(signals)
            
            # Обновляем средние значения
            total_signals = self.stats['total_signals_generated']
            self.stats['avg_impact_score'] = (
                (self.stats['avg_impact_score'] * (total_signals - len(signals)) + 
                 sum(s['impact_score'] for s in signals)) / total_signals
            )
            self.stats['avg_confidence'] = (
                (self.stats['avg_confidence'] * (total_signals - len(signals)) + 
                 sum(s['confidence'] for s in signals)) / total_signals
            )
        
        return signals
    
    def get_stats(self) -> Dict:
        """Получение статистики движка"""
        buy_ratio = (self.stats['buy_signals'] / self.stats['total_signals_generated'] * 100) if self.stats['total_signals_generated'] > 0 else 0
        sell_ratio = (self.stats['sell_signals'] / self.stats['total_signals_generated'] * 100) if self.stats['total_signals_generated'] > 0 else 0
        hold_ratio = (self.stats['hold_signals'] / (self.stats['total_signals_generated'] + self.stats['hold_signals']) * 100) if (self.stats['total_signals_generated'] + self.stats['hold_signals']) > 0 else 0
        
        return {
            **self.stats,
            'buy_ratio': round(buy_ratio, 1),
            'sell_ratio': round(sell_ratio, 1),
            'hold_ratio': round(hold_ratio, 1),
            'parameters': {
                'base_position_size': self.base_position_size,
                'base_stop_loss': self.base_stop_loss,
                'min_confidence': self.min_confidence,
                'min_impact_score': self.min_impact_score,
                'mode': 'AGGRESSIVE_TEST'
            },
            'performance': {
                'total_analysis': self.stats['total_signals_generated'] + self.stats['hold_signals'],
                'signals_generated': self.stats['total_signals_generated'],
                'signals_rejected': self.stats['hold_signals'],
                'success_rate': 'TESTING'
            }
        }
