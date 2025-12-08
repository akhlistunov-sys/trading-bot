# decision_engine.py - ПОЛНЫЙ ОБНОВЛЁННЫЙ ФАЙЛ
import logging
import os
from datetime import datetime
from typing import Dict, List, Optional  # ← ДОБАВИТЬ Optional

logger = logging.getLogger(__name__)

class DecisionEngine:
    """Движок принятия решений с интеграцией RiskManager"""
    
    def __init__(self, risk_manager=None):
        # Используем переданный risk_manager или создаём новый
        self.risk_manager = risk_manager
        
        # Базовые параметры (если risk_manager не передан)
        if not risk_manager:
            self.risk_per_trade = float(os.getenv("RISK_PER_TRADE", "1.5"))
            self.stop_loss_pct = float(os.getenv("STOP_LOSS_PCT", "1.5"))
            self.take_profit_pct = float(os.getenv("TAKE_PROFIT_PCT", "3.0"))
            self.min_confidence = float(os.getenv("MIN_CONFIDENCE", "0.6"))
            self.min_impact_score = int(os.getenv("MIN_IMPACT_SCORE", "5"))
        
        logger.info("🎯 DecisionEngine инициализирован")
        if risk_manager:
            logger.info("   Интегрирован с RiskManager")
        else:
            logger.info("   Автономный режим")
    
    def generate_signals(self, signal_data: Dict) -> List[Dict]:
        """Генерация сигналов из данных"""
        
        signals = []
        
        # Если пришёл готовый сигнал от SignalPipeline
        if signal_data.get('action'):
            # Это уже готовый сигнал
            signals.append(signal_data)
            logger.info(f"🎯 Передан готовый сигнал: {signal_data['action']} {signal_data['ticker']}")
        
        # Если пришёл анализ новости (для совместимости)
        elif 'tickers' in signal_data:
            analysis = signal_data
            
            # Проверяем минимальные требования
            confidence = analysis.get('confidence', 0)
            impact_score = analysis.get('impact_score', 0)
            tickers = analysis.get('tickers', [])
            
            if (confidence < self.min_confidence or 
                impact_score < self.min_impact_score or 
                not tickers):
                return signals
            
            # Для каждого тикера создаём сигнал
            for ticker in tickers[:2]:  # До 2 тикеров
                signal = self._create_signal_from_analysis(analysis, ticker)
                if signal:
                    signals.append(signal)
        
        return signals
    
    def _create_signal_from_analysis(self, analysis: Dict, ticker: str) -> Optional[Dict]:
        """Создание сигнала из анализа (для совместимости)"""
        
        # Определяем действие
        action = self._determine_action(analysis)
        if action == 'HOLD':
            return None
        
        # Базовый сигнал
        signal = {
            'action': action,
            'ticker': ticker,
            'reason': analysis.get('summary', 'Анализ новости'),
            'confidence': analysis.get('confidence', 0.5),
            'impact_score': analysis.get('impact_score', 5),
            'event_type': analysis.get('event_type', 'market_update'),
            'sentiment': analysis.get('sentiment', 'neutral'),
            'position_size': 1,  # По умолчанию
            'stop_loss_percent': self.stop_loss_pct,
            'take_profit_percent': self.take_profit_pct,
            'strategy': 'News Trading',
            'ai_provider': analysis.get('ai_provider', 'simple'),
            'news_id': analysis.get('news_id', ''),
            'timestamp': datetime.now().isoformat()
        }
        
        logger.info(f"🎯 Создан сигнал: {action} {ticker}")
        return signal
    
    def _determine_action(self, analysis: Dict) -> str:
        """Определение действия на основе анализа"""
        sentiment = analysis.get('sentiment', 'neutral')
        event_type = analysis.get('event_type', 'market_update')
        confidence = analysis.get('confidence', 0.5)
        
        # Дивиденды и отчёты → BUY если позитивные
        if event_type == 'dividend' and sentiment == 'positive':
            return 'BUY'
        elif event_type == 'earnings_report' and sentiment == 'positive':
            return 'BUY'
        elif sentiment == 'positive':
            return 'BUY'
        elif sentiment == 'negative':
            return 'SELL'
        else:
            # Neutral
            if confidence > 0.7:
                return 'BUY'  # В агрессивном режиме
            else:
                return 'HOLD'
    
    def get_stats(self) -> Dict:
        """Статистика DecisionEngine"""
        if self.risk_manager:
            risk_stats = self.risk_manager.get_risk_stats()
        else:
            risk_stats = {
                'risk_per_trade': getattr(self, 'risk_per_trade', 1.5),
                'stop_loss_pct': getattr(self, 'stop_loss_pct', 1.5),
                'take_profit_pct': getattr(self, 'take_profit_pct', 3.0),
                'min_confidence': getattr(self, 'min_confidence', 0.6),
                'min_impact_score': getattr(self, 'min_impact_score', 5)
            }
        
        return {
            'engine_version': '2.0',
            'integrated_with_risk_manager': self.risk_manager is not None,
            'risk_stats': risk_stats,
            'timestamp': datetime.now().isoformat()
        }
