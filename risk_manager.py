# risk_manager.py - ПОЛНЫЙ ФАЙЛ (NO SHORTS)
import logging
from datetime import datetime
from typing import Dict, Optional

logger = logging.getLogger(__name__)

class RiskManager:
    """Управление рисками: Без шортов, с защитой капитала"""
    
    def __init__(self, initial_capital: float = 100000):
        # --- НАСТРОЙКИ РИСКА ---
        self.risk_per_trade = 2.0      # Риск на сделку 2%
        self.max_risk_per_ticker = 15.0 # Максимум 15% портфеля в одну акцию
        
        self.stop_loss_pct = 2.0       # Стоп-лосс 2% (расширил, чтобы не выбивало шумом)
        self.take_profit_pct = 6.0     # Тейк 6% (соотношение 1 к 3)
        
        # ВАЖНО: Список разрешенных шортов ПУСТ
        self.allowed_short_list = []   # Шорты ОТКЛЮЧЕНЫ
        
        self.initial_capital = initial_capital
        self.current_capital = initial_capital
        self.open_positions = {}
        self.daily_pnl = 0
        
        # Размеры лотов (можно дополнить)
        self.lot_sizes = {
            'SBER': 10, 'GAZP': 10, 'LKOH': 1, 'ROSN': 10, 'VTBR': 10000,
            'SNGS': 100, 'MOEX': 10, 'NLMK': 10, 'CHMF': 1, 'ALRS': 10
        }
        
        logger.info("🛡️ RiskManager инициализирован: ШОРТЫ ЗАПРЕЩЕНЫ")

    def prepare_signal(self, analysis: Dict, verification: Dict, current_prices: Dict) -> Optional[Dict]:
        """Фильтрация сигнала и расчет объема"""
        
        ticker = verification.get('primary_ticker')
        if not ticker or ticker not in current_prices:
            return None
            
        current_price = current_prices[ticker]
        
        # Определяем действие
        # Если это технический сигнал - берем действие оттуда
        if analysis.get('ai_provider') == 'technical':
            action = analysis.get('action', 'HOLD')
        else:
            # Для новостей: позитив = BUY, негатив = SELL
            sentiment = analysis.get('sentiment', 'neutral')
            if sentiment == 'positive': action = 'BUY'
            elif sentiment == 'negative': action = 'SELL'
            else: return None
        
        # --- БЛОКИРОВКА ШОРТОВ ---
        # Если сигнал SELL, но у нас нет этой акции в портфеле -> это открытие шорта -> ЗАПРЕТИТЬ
        if action == 'SELL':
            # Проверяем, есть ли позиция, которую нужно закрыть
            # (Логику закрытия обрабатывает VirtualPortfolio, здесь мы фильтруем ВХОДЫ)
            # Поэтому RiskManager блокирует любые новые SELL сигналы
            if ticker not in self.allowed_short_list:
                return None
        
        # Расчет стопов
        stop_loss = current_price * (1 - self.stop_loss_pct/100)
        take_profit = current_price * (1 + self.take_profit_pct/100)
        
        # Расчет размера позиции (Риск менеджмент)
        # Рискуем 2% от капитала. Если стоп 2%, то позиция = 100% капитала? Нет.
        # Формула: (Капитал * Риск%) / (Цена входа - Стоп лосс)
        risk_money = self.current_capital * (self.risk_per_trade / 100)
        stop_diff = current_price - stop_loss
        
        if stop_diff <= 0: return None
        
        shares = int(risk_money / stop_diff)
        
        # Ограничение макс. доли в портфеле
        max_shares = int((self.current_capital * (self.max_risk_per_ticker / 100)) / current_price)
        shares = min(shares, max_shares)
        
        # Учет лотности
        lot = self.lot_sizes.get(ticker, 1)
        shares = (shares // lot) * lot
        
        if shares < lot: return None
        
        return {
            'action': action,
            'ticker': ticker,
            'position_size': shares,
            'current_price': current_price,
            'stop_loss': stop_loss,
            'take_profit': take_profit,
            'take_profit_percent': self.take_profit_pct,
            'stop_loss_percent': self.stop_loss_pct,
            'reason': analysis.get('reason', 'Signal'),
            'ai_provider': analysis.get('ai_provider', 'unknown'),
            'confidence': analysis.get('confidence', 0.5),
            'impact_score': analysis.get('impact_score', 5),
            'strategy': 'Momentum Hybrid',
            'timestamp': datetime.now().isoformat()
        }

    def update_positions(self, positions: Dict):
        self.open_positions = positions
    
    def update_pnl(self, profit: float):
        self.daily_pnl += profit
