import logging
import os
from typing import Dict, List
from datetime import datetime

logger = logging.getLogger(__name__)

class DecisionEngine:
    """СУПЕР-АГРЕССИВНЫЙ движок для ТЕСТОВОЙ торговли"""
    
    def __init__(self):
        # УЛЬТРА-НИЗКИЕ пороги для тестов
        self.base_position_size = float(os.getenv("BASE_POSITION_SIZE", "8.0"))  # УВЕЛИЧЕНО
        self.base_stop_loss = float(os.getenv("BASE_STOP_LOSS", "1.5"))  # УМЕНЬШЕНО
        self.min_confidence = float(os.getenv("MIN_CONFIDENCE", "0.1"))  # ОЧЕНЬ НИЗКИЙ
        self.min_impact_score = int(os.getenv("MIN_IMPACT_SCORE", "1"))  # ОЧЕНЬ НИЗКИЙ
        
        logger.info("=" * 50)
        logger.info("🎯 DecisionEngine - СУПЕР-АГРЕССИВНЫЙ РЕЖИМ")
        logger.info(f"   • min_confidence = {self.min_confidence} (УЛЬТРА-НИЗКИЙ)")
        logger.info(f"   • min_impact_score = {self.min_impact_score} (УЛЬТРА-НИЗКИЙ)")
        logger.info(f"   • position_size = {self.base_position_size}% (БОЛЬШЕ)")
        logger.info(f"   • stop_loss = {self.base_stop_loss}% (МЕНЬШЕ)")
        logger.info("=" * 50)
        
        # СТАТИСТИКА
        self.stats = {
            'total_signals': 0,
            'buy_signals': 0,
            'sell_signals': 0,
            'hold_signals': 0
        }
    
    def determine_trade_action(self, analysis: Dict) -> str:
        """СУПЕР-АГРЕССИВНОЕ решение"""
        sentiment = analysis.get('sentiment', 'neutral')
        confidence = analysis.get('confidence', 0)
        
        # В ТЕСТАХ: почти ВСЕГДА BUY
        if sentiment == 'positive':
            return 'BUY'
        elif sentiment == 'negative' and confidence > 0.7:
            return 'SELL'
        else:
            # Neutral, mixed, low confidence -> BUY в тестах!
            return 'BUY' if confidence > self.min_confidence else 'HOLD'
    
    def generate_signals(self, analysis: Dict) -> List[Dict]:
        """Генерация сигналов с УЛЬТРА-НИЗКИМИ фильтрами"""
        signals = []
        
        confidence = analysis.get('confidence', 0)
        impact_score = analysis.get('impact_score', 0)
        relevance_score = analysis.get('relevance_score', 0)
        tickers = analysis.get('tickers', [])
        
        # УЛЬТРА-НИЗКИЕ пороги
        if (confidence < self.min_confidence or 
            impact_score < self.min_impact_score or 
            relevance_score < 20 or  # ОЧЕНЬ НИЗКИЙ
            not tickers):
            return signals
        
        logger.info(f"✅ Анализ ПРОШЁЛ: confidence={confidence:.2f}, tickers={tickers}")
        
        # Для КАЖДОГО тикера создаем сигнал
        for ticker in tickers[:3]:  # До 3 тикеров
            action = self.determine_trade_action(analysis)
            
            if action == 'HOLD':
                self.stats['hold_signals'] += 1
                continue
            
            # Расчет параметров
            position_size = self.base_position_size
            stop_loss = self.base_stop_loss
            take_profit = stop_loss * 2.5
            
            # Создаем сигнал
            signal = {
                'action': action,
                'ticker': ticker,
                'reason': analysis.get('summary', 'Агрессивный тестовый сигнал'),
                'confidence': confidence,
                'impact_score': impact_score,
                'relevance_score': relevance_score,
                'event_type': analysis.get('event_type', 'market_update'),
                'sentiment': analysis.get('sentiment', 'neutral'),
                'position_size_percent': position_size,
                'stop_loss_percent': stop_loss,
                'take_profit_percent': take_profit,
                'strategy': 'SUPER-AGGRESSIVE TEST',
                'ai_generated': analysis.get('ai_provider') != 'simple',
                'ai_provider': analysis.get('ai_provider', 'simple'),
                'news_id': analysis.get('news_id', ''),
                'timestamp': datetime.now().isoformat()
            }
            
            signals.append(signal)
            
            # Обновляем статистику
            if action == 'BUY':
                self.stats['buy_signals'] += 1
            else:
                self.stats['sell_signals'] += 1
            
            logger.info(f"🎯 СИГНАЛ: {action} {ticker} | Size: {position_size}%")
        
        self.stats['total_signals'] += len(signals)
        return signals
    
    def get_stats(self) -> Dict:
        """Статистика"""
        return {
            **self.stats,
            'parameters': {
                'min_confidence': self.min_confidence,
                'min_impact_score': self.min_impact_score,
                'position_size': self.base_position_size,
                'stop_loss': self.base_stop_loss,
                'mode': 'SUPER-AGGRESSIVE TEST'
            }
        }
