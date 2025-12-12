# risk_manager.py - ГИБРИДНЫЙ RISK MANAGER С ШОРТАМИ
import logging
import os
from datetime import datetime
from typing import Dict, Optional
import math

logger = logging.getLogger(__name__)

class RiskManager:
    """Управление рисками с учётом гибридной стратегии (новости + технический анализ)"""
    
    def __init__(self, initial_capital: float = 100000):
        # ПАРАМЕТРЫ ДЛЯ ГИБРИДНОЙ СТРАТЕГИИ
        self.risk_per_trade = 2.5  # Базовый риск 2.5%
        self.max_risk_per_ticker = 7.5  # Макс. на тикер 7.5%
        self.max_risk_per_sector = 15.0  # Макс. на сектор 15%
        self.stop_loss_pct = 1.5  # Стоп-лосс 1.5%
        self.take_profit_pct = 6.0  # Тейк-профит 6.0%
        self.trailing_start = self.take_profit_pct * 0.4  # 40% от тейка
        self.trailing_step = self.stop_loss_pct * 0.5  # 50% от стопа
        
        # ДИНАМИЧЕСКИЕ МНОЖИТЕЛИ НА ОСНОВЕ IMPACT_SCORE
        self.impact_multipliers = {
            1: 0.3, 2: 0.4, 3: 0.5, 4: 0.6, 5: 0.8,
            6: 1.0, 7: 1.3, 8: 1.6, 9: 2.0, 10: 2.5
        }
        
        # МИНИМАЛЬНЫЕ ПОРОГИ ДЛЯ РАЗНЫХ ИСТОЧНИКОВ
        self.min_confidence = {'gigachat': 0.45, 'technical': 0.35, 'enhanced': 0.4}
        self.min_impact_score = {'gigachat': 2, 'technical': 4, 'enhanced': 3}
        
        # СПИСОК АКЦИЙ, ДОСТУПНЫХ ДЛЯ ШОРТА (пример, нужно обновлять)
        self.allowed_short_list = ['SBER', 'GAZP', 'LKOH', 'ROSN', 'MOEX', 'GMKN']
        
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
            'max_position_value': 0.15,
            'max_daily_loss': -0.07,
            'max_consecutive_losses': 3,
            'avg_position_size': 0.10,
            'max_short_exposure': 0.15  # Макс. доля шортов в портфеле
        }
        
        # Статистика
        self.consecutive_losses = 0
        self.daily_pnl = 0
        self.total_trades = 0
        self.short_exposure = 0.0  # Текущая доля шортов
        
        logger.info("🎯 ГИБРИДНЫЙ RiskManager инициализирован")
        logger.info(f"   Источники: GigaChat + Тех. анализ")
        logger.info(f"   Шорты доступны для: {', '.join(self.allowed_short_list[:5])}...")

    def prepare_signal(self, analysis: Dict, verification: Dict, current_prices: Dict) -> Optional[Dict]:
        """Подготовка торгового сигнала с проверкой доступности шорта"""
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
        ai_provider = analysis.get('ai_provider', 'gigachat')
        
        # 1. ПРОВЕРКА ПОРОГОВ ДЛЯ КОНКРЕТНОГО ИСТОЧНИКА
        confidence = analysis.get('confidence', 0)
        impact_score = analysis.get('impact_score', 0)
        min_conf = self.min_confidence.get(ai_provider, 0.4)
        min_impact = self.min_impact_score.get(ai_provider, 3)
        
        if confidence < min_conf:
            logger.debug(f"❌ Low confidence от {ai_provider}: {confidence} < {min_conf}")
            return None
        if impact_score < min_impact:
            logger.debug(f"❌ Low impact от {ai_provider}: {impact_score} < {min_impact}")
            return None
        
        # 2. ОПРЕДЕЛЕНИЕ ДЕЙСТВИЯ
        action = self._determine_action(analysis)
        if action == 'HOLD':
            logger.debug(f"⚠️ Сигнал {primary_ticker}: HOLD")
            return None
        
        # 3. ОСОБАЯ ПРОВЕРКА ДЛЯ ШОРТОВ
        if action == 'SELL':
            if primary_ticker not in self.allowed_short_list:
                logger.debug(f"❌ Шорт недоступен для {primary_ticker}")
                return None
            # Проверка лимита на шорты
            if self.short_exposure >= self.portfolio_limits['max_short_exposure']:
                logger.debug(f"❌ Достигнут лимит шортов: {self.short_exposure:.1%}")
                return None
        
        # 4. ПРОВЕРКА ПОРТФЕЛЬНЫХ ЛИМИТОВ
        if not self._check_portfolio_limits(action):
            logger.warning("⚠️ Достигнут портфельный лимит, пропускаем сигнал")
            return None
        
        # 5. ДИНАМИЧЕСКИЙ РАСЧЁТ РИСКА
        risk_multiplier = self.impact_multipliers.get(impact_score, 1.0)
        adjusted_risk_pct = self.risk_per_trade * risk_multiplier
        max_allowed_risk = min(self.max_risk_per_ticker, 5.0)
        final_risk_pct = min(adjusted_risk_pct, max_allowed_risk)
        
        # 6. РАСЧЁТ РАЗМЕРА ПОЗИЦИИ
        position_size = self._calculate_dynamic_position_size(
            ticker=primary_ticker,
            current_price=current_price,
            risk_percent=final_risk_pct,
            impact_score=impact_score,
            confidence=confidence,
            action=action
        )
        
        if position_size <= 0:
            logger.debug(f"❌ Нулевой размер позиции для {primary_ticker}")
            return None
        
        # 7. ДИНАМИЧЕСКИЕ СТОПЫ И ТЕЙКИ
        stop_loss_pct, take_profit_pct = self._calculate_dynamic_stops(impact_score, confidence, action)
        
        if action == 'SELL':  # Для шортов стопы инвертируем
            stop_loss = current_price * (1 + stop_loss_pct / 100)
            take_profit = current_price * (1 - take_profit_pct / 100)
        else:  # Для лонгов
            stop_loss = current_price * (1 - stop_loss_pct / 100)
            take_profit = current_price * (1 + take_profit_pct / 100)
        
        # 8. СОЗДАНИЕ СИГНАЛА
        signal = {
            'action': action,
            'ticker': primary_ticker,
            'reason': analysis.get('summary', f'Анализ {ai_provider}'),
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
            'ai_provider': ai_provider,
            'news_id': analysis.get('news_id', ''),
            'strategy': 'Hybrid GigaChat+Technical',
            'timestamp': datetime.now().isoformat()
        }
        
        logger.info(f"🎯 Сигнал: {action} {primary_ticker} x{position_size}")
        logger.info(f"   📊 Источник: {ai_provider}, Риск: {final_risk_pct:.1f}%")
        
        return signal

    def _determine_action(self, analysis: Dict) -> str:
        """Определение действия на основе анализа"""
        sentiment = analysis.get('sentiment', 'neutral')
        event_type = analysis.get('event_type', 'ai_analyzed')
        impact_score = analysis.get('impact_score', 5)
        ai_provider = analysis.get('ai_provider', 'gigachat')

        # ДЛЯ ТЕХНИЧЕСКОГО АНАЛИЗА: используем встроенную логику
        if ai_provider == 'technical':
            # Тех. анализ уже определил действие в своём модуле
            return analysis.get('action', 'HOLD')
        
        # ДЛЯ GIGACHAT И ENHANCED АНАЛИЗА:
        # ПРАВИЛО 1: Сильные позитивные -> BUY
        if sentiment == 'positive' and impact_score >= 7:
            return 'BUY'
        # ПРАВИЛО 2: Сильные негативные -> SELL (шорт)
        elif sentiment == 'negative' and impact_score >= 7:
            # Проверка типа события: только финансовый негатив
            financial_negatives = ['earnings_report_loss', 'dividend_cancel', 
                                   'regulatory_penalty', 'debt_default']
            if event_type in financial_negatives:
                return 'SELL'
            else:
                return 'HOLD'
        # ПРАВИЛО 3: Всё остальное -> HOLD
        else:
            return 'HOLD'

    def _calculate_dynamic_position_size(self, ticker: str, current_price: float, 
                                       risk_percent: float, impact_score: int, 
                                       confidence: float, action: str) -> int:
        """Динамический расчёт размера позиции с учётом типа сделки"""
        risk_amount = self.current_capital * risk_percent / 100
        
        # Корректировка стопа в зависимости от типа сделки
        if action == 'SELL':
            base_stop_pct = self.stop_loss_pct * 0.8  # Ужеще для шортов
        else:
            base_stop_pct = self.stop_loss_pct
        
        if impact_score >= 8:
            stop_pct = base_stop_pct * 0.8
        elif impact_score >= 5:
            stop_pct = base_stop_pct
        else:
            stop_pct = base_stop_pct * 1.2
        
        stop_distance = current_price * (stop_pct / 100)
        if stop_distance <= 0:
            return 0
        
        shares = int(risk_amount / stop_distance)
        lot_size = self.lot_sizes.get(ticker.upper(), 1)
        if lot_size > 1:
            shares = (shares // lot_size) * lot_size
        
        min_shares = max(1, lot_size)
        max_shares_by_capital = int(self.current_capital * self.portfolio_limits['max_position_value'] / current_price)
        shares = max(min_shares, min(shares, max_shares_by_capital))
        
        return max(min_shares, shares)

    def _calculate_dynamic_stops(self, impact_score: int, confidence: float, action: str) -> tuple:
        """Динамические стоп-лосс и тейк-профит"""
        base_stop = self.stop_loss_pct
        base_take = self.take_profit_pct
        
        if action == 'SELL':
            base_stop *= 0.8  # Ужеще стопы для шортов
            base_take *= 0.9  # Консервативнее тейки для шортов
        
        if impact_score >= 8:
            stop_adj = base_stop * 0.8
            take_adj = base_take * 1.3
        elif impact_score >= 5:
            stop_adj = base_stop
            take_adj = base_take
        else:
            stop_adj = base_stop * 1.2
            take_adj = base_take * 0.7
        
        if confidence > 0.8:
            stop_adj *= 0.9
            take_adj *= 1.1
        
        return round(stop_adj, 2), round(take_adj, 2)

    def _check_portfolio_limits(self, action: str) -> bool:
        """Проверка портфельных лимитов"""
        if self.daily_pnl / self.initial_capital <= self.portfolio_limits['max_daily_loss']:
            logger.error(f"🚨 STOP ALL! Дневная просадка: {self.daily_pnl/self.initial_capital*100:.1f}%")
            return False
        if self.consecutive_losses >= self.portfolio_limits['max_consecutive_losses']:
            logger.warning(f"⚠️ {self.consecutive_losses} убыточных сделок подряд, снижаем риск")
            self.risk_per_trade = max(1.0, self.risk_per_trade * 0.7)
        return True

    def update_positions(self, positions: Dict):
        """Обновление информации об открытых позициях"""
        self.open_positions = positions
        # Пересчитываем экспозицию по шортам
        self.short_exposure = 0.0
        for ticker, pos in positions.items():
            if pos.get('action') == 'SELL':
                self.short_exposure += pos.get('current_value', 0) / self.current_capital
        
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
            'short_exposure': round(self.short_exposure * 100, 2),
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
            'hybrid_mode': {
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
