# risk_manager.py - АГРЕССИВНЫЙ РЕЖИМ С УЧЁТОМ IMPACT_SCORE
import logging
import os
from datetime import datetime
from typing import Dict, Optional
import math

logger = logging.getLogger(__name__)

class RiskManager:
    """Управление рисками с учётом качества сигнала от GigaChat"""
    
    def __init__(self, initial_capital: float = 100000):
        # ПАРАМЕТРЫ ДЛЯ AGGRESSIVE_TEST (из твоих переменных + усиленные)
        self.risk_per_trade = 2.5  # БАЗОВЫЙ риск 2.5% (было 1.5%)
        self.max_risk_per_ticker = 7.5  # МАКС. на тикер 7.5% (было 4.0%)
        self.max_risk_per_sector = 15.0  # МАКС. на сектор 15% (было 10%)
        self.stop_loss_pct = 1.5  # СТОП-ЛОСС 1.5% (ужесточили!)
        self.take_profit_pct = 6.0  # ТЕЙК-ПРОФИТ 6.0% (увеличили!)
        self.trailing_start = self.take_profit_pct * 0.4  # 40% от тейка
        self.trailing_step = self.stop_loss_pct * 0.5  # 50% от стопа
        
        # ДИНАМИЧЕСКИЕ МНОЖИТЕЛИ НА ОСНОВЕ IMPACT_SCORE
        self.impact_multipliers = {
            1: 0.3,  # Слабый сигнал - 30% от базового риска
            2: 0.4,
            3: 0.5,
            4: 0.6,
            5: 0.8,  # Средний - 80%
            6: 1.0,  # Базовый риск
            7: 1.3,  # Сильный +30%
            8: 1.6,  # Очень сильный +60%
            9: 2.0,  # Максимальный +100%
            10: 2.5  # Исключительный +150%
        }
        
        # МИНИМАЛЬНЫЕ ПОРОГИ (из твоих переменных)
        self.min_confidence = 0.45  # MIN_CONFIDENCE
        self.min_impact_score = 2   # MIN_IMPACT_SCORE
        
        self.initial_capital = initial_capital
        self.current_capital = initial_capital
        
        # Лоты MOEX (минимальные торгуемые лоты)
        self.lot_sizes = {
            'SBER': 10, 'GAZP': 10, 'LKOH': 1, 'ROSN': 10,
            'NVTK': 1, 'GMKN': 1, 'PLZL': 1, 'POLY': 1,
            'TATN': 1, 'ALRS': 10, 'CHMF': 10, 'NLMK': 1,
            'MAGN': 10, 'SNGS': 100, 'VTBR': 10000, 'TCSG': 1,
            'MTSS': 10, 'AFKS': 100, 'FEES': 100, 'MGNT': 1,
            'FIVE': 1, 'YNDX': 1, 'OZON': 1, 'MOEX': 10,
            'RTKM': 100, 'PHOR': 1, 'TRNFP': 1, 'BANE': 10
        }
        
        # Сектора для контроля рисков
        self.sectors = {
            'banks': ['SBER', 'VTBR', 'TCSG', 'CBOM', 'SFIN', 'RUGR', 'SVCB', 'ALFA', 'FCIT'],
            'oil_gas': ['GAZP', 'LKOH', 'ROSN', 'NVTK', 'TATN', 'SNGS', 'BANE', 'TRNFP'],
            'metals': ['GMKN', 'ALRS', 'POLY', 'CHMF', 'NLMK', 'MAGN', 'PLZL', 'RASP'],
            'retail': ['MGNT', 'FIVE', 'LNTA', 'DSKY', 'OZON', 'MVID', 'OKEY'],
            'tech': ['YNDX', 'OZON', 'POSI', 'CIAN', 'VKCO', 'QIWI'],
            'other': []
        }
        
        # Открытые позиции
        self.open_positions = {}
        
        # Портфельные лимиты
        self.portfolio_limits = {
            'max_position_value': 0.15,  # Не более 15% капитала в одной позиции
            'max_daily_loss': -0.07,     # STOP ALL при -7% за день
            'max_consecutive_losses': 3, # После 3 убыточных сделок снижаем риск
            'avg_position_size': 0.10    # Цель - 10% на позицию
        }
        
        # Статистика
        self.consecutive_losses = 0
        self.daily_pnl = 0
        self.total_trades = 0
        
        logger.info("🎯 AGGRESSIVE RiskManager инициализирован")
        logger.info(f"   • Базовый риск: {self.risk_per_trade}%")
        logger.info(f"   • Динамический множитель по impact_score: ДА")
        logger.info(f"   • Стоп: {self.stop_loss_pct}% | Тейк: {self.take_profit_pct}%")
        logger.info(f"   • Пороги: confidence>{self.min_confidence}, impact>{self.min_impact_score}")
    
    def prepare_signal(self, analysis: Dict, verification: Dict, current_prices: Dict) -> Optional[Dict]:
        """Подготовка торгового сигнала с ДИНАМИЧЕСКИМ РИСКОМ"""
        
        # 0. Проверка верификации
        if not verification.get('valid'):
            logger.debug("❌ Сигнал не верифицирован")
            return None
        
        primary_ticker = verification.get('primary_ticker')
        if not primary_ticker:
            logger.debug("❌ Нет основного тикера")
            return None
        
        if primary_ticker not in current_prices:
            logger.debug(f"❌ Нет цены для {primary_ticker}")
            return None
        
        current_price = current_prices[primary_ticker]
        
        # 1. ПРОВЕРКА ПОРОГОВ
        confidence = analysis.get('confidence', 0)
        impact_score = analysis.get('impact_score', 0)
        
        if confidence < self.min_confidence:
            logger.debug(f"❌ Low confidence: {confidence} < {self.min_confidence}")
            return None
        
        if impact_score < self.min_impact_score:
            logger.debug(f"❌ Low impact: {impact_score} < {self.min_impact_score}")
            return None
        
        # 2. ПРОВЕРКА ПОРТФЕЛЬНЫХ ЛИМИТОВ
        if not self._check_portfolio_limits():
            logger.warning("⚠️ Достигнут портфельный лимит, пропускаем сигнал")
            return None
        
        # 3. ДИНАМИЧЕСКИЙ РАСЧЁТ РИСКА НА ОСНОВЕ IMPACT_SCORE
        risk_multiplier = self.impact_multipliers.get(impact_score, 1.0)
        adjusted_risk_pct = self.risk_per_trade * risk_multiplier
        
        # Ограничиваем максимальный риск
        max_allowed_risk = min(self.max_risk_per_ticker, 5.0)  # Не более 5% даже для impact=10
        final_risk_pct = min(adjusted_risk_pct, max_allowed_risk)
        
        # 4. РАСЧЁТ РАЗМЕРА ПОЗИЦИИ
        position_size = self._calculate_dynamic_position_size(
            ticker=primary_ticker,
            current_price=current_price,
            risk_percent=final_risk_pct,
            impact_score=impact_score,
            confidence=confidence
        )
        
        if position_size <= 0:
            logger.debug(f"❌ Нулевой размер позиции для {primary_ticker}")
            return None
        
        # 5. ОПРЕДЕЛЕНИЕ ДЕЙСТВИЯ
        action = self._determine_action(analysis)
        if action == 'HOLD':
            logger.debug(f"⚠️ Сигнал {primary_ticker}: HOLD")
            return None
        
        # 6. ДИНАМИЧЕСКИЕ СТОПЫ И ТЕЙКИ
        stop_loss_pct, take_profit_pct = self._calculate_dynamic_stops(impact_score, confidence)
        
        stop_loss = current_price * (1 - stop_loss_pct / 100)
        take_profit = current_price * (1 + take_profit_pct / 100)
        
        # 7. СОЗДАНИЕ СИГНАЛА
        signal = {
            'action': action,
            'ticker': primary_ticker,
            'reason': analysis.get('summary', 'Анализ GigaChat'),
            'confidence': confidence,
            'impact_score': impact_score,
            'event_type': analysis.get('event_type', 'ai_analyzed'),
            'sentiment': analysis.get('sentiment', 'neutral'),
            'current_price': current_price,
            'position_size': position_size,
            'position_value': position_size * current_price,
            'stop_loss': stop_loss,
            'take_profit': take_profit,
            'stop_loss_percent': stop_loss_pct,
            'take_profit_percent': take_profit_pct,
            'risk_per_trade': final_risk_pct,
            'risk_multiplier': risk_multiplier,
            'portfolio_share': (position_size * current_price) / self.current_capital,
            'ai_provider': analysis.get('ai_provider', 'gigachat'),
            'news_id': analysis.get('news_id', ''),
            'strategy': 'GigaChat Dynamic Risk',
            'timestamp': datetime.now().isoformat()
        }
        
        logger.info(f"🎯 Сигнал: {action} {primary_ticker} x{position_size}")
        logger.info(f"   💰 Размер: {position_size * current_price:.0f} руб. ({signal['portfolio_share']*100:.1f}% портфеля)")
        logger.info(f"   🎯 Риск: {final_risk_pct:.1f}% (impact={impact_score}, множитель={risk_multiplier:.1f}x)")
        logger.info(f"   🛑 Стоп: {stop_loss:.2f} (-{stop_loss_pct}%)")
        logger.info(f"   ✅ Тейк: {take_profit:.2f} (+{take_profit_pct}%)")
        
        return signal
    
    def _calculate_dynamic_position_size(self, ticker: str, current_price: float, 
                                       risk_percent: float, impact_score: int, 
                                       confidence: float) -> int:
        """Динамический расчёт размера позиции"""
        
        # Базовый риск в рублях
        risk_amount = self.current_capital * risk_percent / 100
        
        # Расстояние до стопа
        stop_pct = self.stop_loss_pct
        if impact_score >= 8:
            stop_pct = self.stop_loss_pct * 0.8  # Ужеще стоп для сильных сигналов
        elif impact_score <= 3:
            stop_pct = self.stop_loss_pct * 1.2  # Шире стоп для слабых
        
        stop_distance = current_price * (stop_pct / 100)
        if stop_distance <= 0:
            return 0
        
        # Расчёт количества акций по формуле Келли (упрощенная)
        shares = int(risk_amount / stop_distance)
        
        # Округление до лота
        lot_size = self.lot_sizes.get(ticker.upper(), 1)
        if lot_size > 1:
            shares = (shares // lot_size) * lot_size
        
        # Минимальный размер (1 лот)
        min_shares = max(1, lot_size)
        
        # Максимальный размер по капиталу
        max_shares_by_capital = int(self.current_capital * self.portfolio_limits['max_position_value'] / current_price)
        
        shares = max(min_shares, min(shares, max_shares_by_capital))
        
        # Проверка на абсурдные значения
        position_value = shares * current_price
        if position_value > self.current_capital * 0.5:  # Аварийная проверка
            shares = int(self.current_capital * 0.15 / current_price)
            if lot_size > 1:
                shares = (shares // lot_size) * lot_size
        
        return max(min_shares, shares)
    
    def _calculate_dynamic_stops(self, impact_score: int, confidence: float) -> tuple:
        """Динамические стоп-лосс и тейк-профит"""
        
        # Базовые значения
        base_stop = self.stop_loss_pct
        base_take = self.take_profit_pct
        
        # Корректировка на основе impact_score
        if impact_score >= 8:
            # Сильные сигналы - ужеще стоп, шире тейк
            stop_adj = base_stop * 0.8
            take_adj = base_take * 1.3
        elif impact_score >= 5:
            # Средние сигналы
            stop_adj = base_stop
            take_adj = base_take
        else:
            # Слабые сигналы - шире стоп, ужеще тейк
            stop_adj = base_stop * 1.2
            take_adj = base_take * 0.7
        
        # Дополнительная корректировка по confidence
        if confidence > 0.8:
            stop_adj *= 0.9  # Ужеще на 10%
            take_adj *= 1.1  # Шире на 10%
        
        return round(stop_adj, 2), round(take_adj, 2)
    
    def _determine_action(self, analysis: Dict) -> str:
        """Определение действия на основе анализа GigaChat"""
        sentiment = analysis.get('sentiment', 'neutral')
        event_type = analysis.get('event_type', 'ai_analyzed')
        impact_score = analysis.get('impact_score', 5)
        
        # ПРАВИЛА ДЛЯ АГРЕССИВНОГО ТЕСТА:
        
        # 1. Дивиденды или отчеты → BUY
        if 'dividend' in event_type or 'earnings' in event_type:
            return 'BUY'
        
        # 2. Сильные позитивные сигналы → BUY
        if sentiment == 'positive' and impact_score >= 6:
            return 'BUY'
        
        # 3. Сильные негативные сигналы → SELL
        if sentiment == 'negative' and impact_score >= 7:
            return 'SELL'
        
        # 4. Нейтральные с высокой уверенностью → BUY (в тестовом режиме)
        if sentiment == 'neutral' and impact_score >= 6:
            return 'BUY'
        
        # 5. Всё остальное → HOLD
        return 'HOLD'
    
    def _check_portfolio_limits(self) -> bool:
        """Проверка портфельных лимитов"""
        
        # STOP ALL при дневной просадке -7%
        if self.daily_pnl / self.initial_capital <= self.portfolio_limits['max_daily_loss']:
            logger.error(f"🚨 STOP ALL! Дневная просадка: {self.daily_pnl/self.initial_capital*100:.1f}%")
            return False
        
        # После 3 убыточных сделок подряд снижаем агрессивность
        if self.consecutive_losses >= self.portfolio_limits['max_consecutive_losses']:
            logger.warning(f"⚠️ {self.consecutive_losses} убыточных сделок подряд, снижаем риск")
            # Можно добавить автоматическое снижение risk_per_trade
        
        return True
    
    def update_positions(self, positions: Dict):
        """Обновление информации об открытых позициях"""
        self.open_positions = positions
        
        # Восстановление капитала если нужно
        if self.current_capital <= 0:
            self.current_capital = self.initial_capital
            logger.warning("💰 Восстановлен начальный капитал")
    
    def update_pnl(self, profit: float):
        """Обновление дневной P&L и статистики"""
        self.daily_pnl += profit
        self.total_trades += 1
        
        if profit > 0:
            self.consecutive_losses = 0
        else:
            self.consecutive_losses += 1
    
    def get_risk_stats(self) -> Dict:
        """Получение статистики рисков"""
        sector_risks = {}
        
        for sector in self.sectors.keys():
            risk = self._get_sector_risk(sector)
            sector_risks[sector] = 0.0 if risk is None else risk
        
        return {
            'current_capital': self.current_capital,
            'daily_pnl': self.daily_pnl,
            'total_trades': self.total_trades,
            'consecutive_losses': self.consecutive_losses,
            'risk_per_trade': self.risk_per_trade,
            'impact_multipliers': self.impact_multipliers,
            'max_risk_per_ticker': self.max_risk_per_ticker,
            'max_risk_per_sector': self.max_risk_per_sector,
            'sector_risks': sector_risks,
            'open_positions_count': len(self.open_positions),
            'portfolio_limits': self.portfolio_limits,
            'parameters': {
                'stop_loss_pct': self.stop_loss_pct,
                'take_profit_pct': self.take_profit_pct,
                'trailing_start': self.trailing_start,
                'trailing_step': self.trailing_step
            },
            'aggressive_mode': {
                'min_confidence': self.min_confidence,
                'min_impact_score': self.min_impact_score
            }
        }
    
    def _get_sector_risk(self, sector: str) -> float:
        """Расчёт риска сектора"""
        sector_value = 0
        
        for ticker, pos in self.open_positions.items():
            if self._get_ticker_sector(ticker) == sector:
                sector_value += pos.get('current_value', pos['size'] * pos['avg_price'])
        
        if self.current_capital <= 0:
            return 0.0
        
        return (sector_value / self.current_capital) * 100
    
    def _get_ticker_sector(self, ticker: str) -> str:
        """Получение сектора тикера"""
        ticker_upper = ticker.upper()
        
        for sector, tickers in self.sectors.items():
            if ticker_upper in tickers:
                return sector
        
        return 'other'
