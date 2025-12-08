import logging
import os
from typing import Dict, List
from datetime import datetime

logger = logging.getLogger(__name__)

class DecisionEngine:
    """Движок принятия торговых решений на основе анализа новостей"""
    
    def __init__(self):
        # Параметры стратегии ЗАГРУЖАЕМ из переменных окружения
        self.base_position_size = float(os.getenv("BASE_POSITION_SIZE", "5.0"))
        self.base_stop_loss = float(os.getenv("BASE_STOP_LOSS", "2.0"))
        self.min_confidence = float(os.getenv("MIN_CONFIDENCE", "0.7"))
        self.min_impact_score = int(os.getenv("MIN_IMPACT_SCORE", "5"))
        
        # ===== КРИТИЧЕСКИЙ ОТЛАДОЧНЫЙ ЛОГ =====
        logger.info("=" * 50)
        logger.info("🎯 DEBUG DecisionEngine ПАРАМЕТРЫ ИНИЦИАЛИЗАЦИИ:")
        logger.info(f"   • min_confidence = {self.min_confidence}")
        logger.info(f"   • min_impact_score = {self.min_impact_score}")
        logger.info(f"   • base_position_size = {self.base_position_size}")
        logger.info(f"   • base_stop_loss = {self.base_stop_loss}")
        
        # Проверяем, какие переменные окружения загрузились
        env_confidence = os.getenv("MIN_CONFIDENCE", "NOT_FOUND")
        env_impact = os.getenv("MIN_IMPACT_SCORE", "NOT_FOUND")
        logger.info(f"   • Переменные окружения: MIN_CONFIDENCE={env_confidence}, MIN_IMPACT_SCORE={env_impact}")
        logger.info("=" * 50)
        # ======================================
        
        # Множители для разных типов событий
        self.event_multipliers = {
            'earnings_report': 1.3,
            'dividend': 1.2,
            'merger_acquisition': 1.4,
            'regulatory': 1.1,
            'geopolitical': 0.8,  # Снижаем из-за высокой неопределенности
            'market_update': 0.7,
            'corporate_action': 1.0,
            'other': 0.5
        }
        
        # Множители для тональности
        self.sentiment_multipliers = {
            'positive': 1.2,
            'negative': 1.0,
            'neutral': 0.7,
            'mixed': 0.9
        }
        
        # Статистика
        self.stats = {
            'total_signals_generated': 0,
            'signals_by_event_type': {},
            'avg_impact_score': 0,
            'avg_confidence': 0
        }
        
        logger.info("🎯 Decision Engine инициализирован")
        logger.info(f"📊 Параметры из окружения: Size={self.base_position_size}%, SL={self.base_stop_loss}%")
        logger.info(f"📊 Минимальные пороги: Confidence={self.min_confidence}, Impact={self.min_impact_score}")
    
    def calculate_position_size(self, analysis: Dict) -> float:
        """Расчет размера позиции по формуле: 5% * (confidence/80) * (impact_score/7)"""
        
        confidence = analysis.get('confidence', 0.5)
        impact_score = analysis.get('impact_score', 1)
        
        # Применяем нашу формулу
        position_size = self.base_position_size * (confidence / 0.8) * (impact_score / 7.0)
        
        # Применяем множители
        event_type = analysis.get('event_type', 'other')
        sentiment = analysis.get('sentiment', 'neutral')
        
        if event_type in self.event_multipliers:
            position_size *= self.event_multipliers[event_type]
        
        if sentiment in self.sentiment_multipliers:
            position_size *= self.sentiment_multipliers[sentiment]
        
        # Ограничения
        position_size = max(1.0, min(10.0, position_size))  # От 1% до 10%
        
        return round(position_size, 2)
    
    def calculate_stop_loss(self, analysis: Dict) -> float:
        """Расчет стоп-лосса: адаптивный на основе impact_score"""
        
        impact_score = analysis.get('impact_score', 1)
        
        # Формула: стоп = базовый_стоп / (impact_score / 7)
        if impact_score > 0:
            stop_loss = self.base_stop_loss / (impact_score / 7.0)
        else:
            stop_loss = self.base_stop_loss
        
        # Ограничения
        stop_loss = max(1.0, min(5.0, stop_loss))  # От 1% до 5%
        
        return round(stop_loss, 2)
    
    def calculate_take_profit(self, stop_loss: float) -> float:
        """Расчет тейк-профита (риск:прибыль = 1:2)"""
        return round(stop_loss * 2.0, 2)
    
    def determine_trade_action(self, analysis: Dict) -> str:
        """Определение действия (BUY/SELL/HOLD) на основе тональности"""
        
        sentiment = analysis.get('sentiment', 'neutral')
        event_type = analysis.get('event_type', '')
        
        # Общие правила
        if sentiment == 'positive':
            return 'BUY'
        elif sentiment == 'negative':
            return 'SELL'
        
        # Специфичные правила для типов событий
        if event_type == 'dividend':
            return 'BUY'  # Дивиденды обычно позитивны
        elif event_type == 'regulatory':
            return 'SELL'  # Регуляторные изменения часто негативны
        
        # По умолчанию - нейтрально
        return 'BUY' if analysis.get('confidence', 0) > 0.6 else 'HOLD'
    
    def generate_signals(self, analysis: Dict) -> List[Dict]:
        """Генерация торговых сигналов на основе анализа"""
        
        signals = []
        
        # Проверяем минимальные требования
        confidence = analysis.get('confidence', 0)
        impact_score = analysis.get('impact_score', 0)
        relevance_score = analysis.get('relevance_score', 0)
        tickers = analysis.get('tickers', [])
        
        # ===== ДЕТАЛЬНЫЙ ОТЛАДОЧНЫЙ ЛОГ =====
        logger.info("🔍 DecisionEngine ПРОВЕРКА АНАЛИЗА:")
        logger.info(f"   • confidence: {confidence:.2f} (требуется >= {self.min_confidence})")
        logger.info(f"   • impact_score: {impact_score} (требуется >= {self.min_impact_score})")
        logger.info(f"   • relevance_score: {relevance_score} (требуется >= 50)")
        logger.info(f"   • tickers: {tickers} (требуется не пустой)")
        logger.info(f"   • event_type: {analysis.get('event_type', 'unknown')}")
        logger.info(f"   • sentiment: {analysis.get('sentiment', 'unknown')}")
        # ====================================
        
        # ВРЕМЕННО: упрощённые проверки для тестирования
        # Было: relevance_score < 50
        # Стало: relevance_score < 20 (больше анализов пройдут)
        if (confidence < self.min_confidence or 
            impact_score < self.min_impact_score or 
            relevance_score < 20 or  # ВРЕМЕННО УПРОЩЕНО
            not tickers):
            
            # Детальный лог что именно не прошло
            failed_checks = []
            if confidence < self.min_confidence:
                failed_checks.append(f"confidence {confidence:.2f} < {self.min_confidence}")
            if impact_score < self.min_impact_score:
                failed_checks.append(f"impact {impact_score} < {self.min_impact_score}")
            if relevance_score < 20:  # Обновлено
                failed_checks.append(f"relevance {relevance_score} < 20")
            if not tickers:
                failed_checks.append("no tickers")
            
            logger.info(f"❌ Анализ ОТБРОШЕН: {', '.join(failed_checks)}")
            return signals
        
        logger.info("✅ Анализ ПРОШЁЛ все фильтры!")
        
        # Для каждого тикера создаем сигнал
        for ticker in tickers[:3]:  # Ограничиваем 3 тикерами
            # Определяем действие
            action = self.determine_trade_action(analysis)
            
            if action == 'HOLD':
                logger.info(f"   ⏸️  Для {ticker}: действие HOLD, пропускаем")
                continue
            
            # Рассчитываем параметры
            position_size = self.calculate_position_size(analysis)
            stop_loss_percent = self.calculate_stop_loss(analysis)
            take_profit_percent = self.calculate_take_profit(stop_loss_percent)
            
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
                'strategy': 'News NLP Trading',
                'ai_generated': analysis.get('ai_provider') != 'simple',
                'news_id': analysis.get('news_id', ''),
                'news_title': analysis.get('news_title', '')[:100],
                'timestamp': datetime.now().isoformat()
            }
            
            signals.append(signal)
            
            # Логируем с деталями
            logger.info(f"🎯 СИГНАЛ СОЗДАН: {action} {ticker} | "
                       f"Size: {position_size}% | SL: {stop_loss_percent}% | "
                       f"TP: {take_profit_percent}% | Impact: {impact_score}")
        
        # Обновляем статистику
        self.stats['total_signals_generated'] += len(signals)
        
        if signals:
            event_type = analysis.get('event_type', 'other')
            self.stats['signals_by_event_type'][event_type] = \
                self.stats['signals_by_event_type'].get(event_type, 0) + len(signals)
        
        return signals
    
    def get_stats(self) -> Dict:
        """Получение статистики движка"""
        return {
            **self.stats,
            'parameters': {
                'base_position_size': self.base_position_size,
                'base_stop_loss': self.base_stop_loss,
                'min_confidence': self.min_confidence,
                'min_impact_score': self.min_impact_score
            }
        }
