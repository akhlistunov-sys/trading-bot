# risk_manager.py - ИСПРАВЛЕННЫЙ ДЛЯ AGGRESSIVE_TEST
import logging
import os
from datetime import datetime
from typing import Dict, List, Optional, Tuple
import math

logger = logging.getLogger(__name__)

class RiskManager:
    """Управление рисками и расчёт параметров сделок - АГРЕССИВНЫЙ РЕЖИМ"""
    
    def __init__(self, initial_capital: float = 100000):
        # Параметры риска ИЗ ТВОИХ ПЕРЕМЕННЫХ ОКРУЖЕНИЯ
        self.risk_per_trade = float(os.getenv("RISK_PER_TRADE", "1.5"))
        self.max_risk_per_ticker = float(os.getenv("MAX_RISK_PER_TICKER", "4.0"))
        self.max_risk_per_sector = float(os.getenv("MAX_RISK_PER_SECTOR", "10.0"))
        self.stop_loss_pct = float(os.getenv("STOP_LOSS_PCT", "2.0"))
        self.take_profit_pct = float(os.getenv("TAKE_PROFIT_PCT", "5.0"))
        self.trailing_start = self.take_profit_pct * 0.4  # 40% от тейк-профита
        self.trailing_step = self.stop_loss_pct * 0.5     # 50% от стоп-лосса
        
        # Для AGGRESSIVE_TEST
        self.min_confidence = float(os.getenv("MIN_CONFIDENCE", "0.45"))
        self.min_impact_score = int(os.getenv("MIN_IMPACT_SCORE", "2"))
        
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
        
        # Сектора
        self.sectors = {
            'banks': ['SBER', 'VTBR', 'TCSG', 'CBOM', 'SFIN', 'RUGR', 'SVCB', 'ALFA', 'FCIT'],
            'oil_gas': ['GAZP', 'LKOH', 'ROSN', 'NVTK', 'TATN', 'SNGS', 'BANE', 'TRNFP'],
            'metals': ['GMKN', 'ALRS', 'POLY', 'CHMF', 'NLMK', 'MAGN', 'PLZL', 'RASP'],
            'retail': ['MGNT', 'FIVE', 'LNTA', 'DSKY', 'OZON', 'MVID', 'OKEY'],
            'tech': ['YNDX', 'OZON', 'POSI', 'CIAN', 'VKCO', 'QIWI'],
            'other': []  # Остальные
        }
        
        # Открытые позиции (для расчёта рисков)
        self.open_positions = {}  # ticker -> {size, avg_price, sector}
        
        logger.info("🎯 RiskManager инициализирован (АГРЕССИВНЫЙ ТЕСТ)")
        logger.info(f"   • Риск на сделку: {self.risk_per_trade}%")
        logger.info(f"   • Стоп-лосс: {self.stop_loss_pct}%")
        logger.info(f"   • Тейк-профит: {self.take_profit_pct}%")
        logger.info(f"   • MIN_CONFIDENCE: {self.min_confidence}")
        logger.info(f"   • MIN_IMPACT_SCORE: {self.min_impact_score}")
    
    def prepare_signal(self, analysis: Dict, verification: Dict, current_prices: Dict) -> Optional[Dict]:
        """Подготовка торгового сигнала с учётом рисков - АГРЕССИВНЫЙ РЕЖИМ"""
        
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
        
        # 1. Проверка на дубли (уже есть позиция)
        if self._has_position(primary_ticker):
            logger.debug(f"⚠️ Уже есть позиция {primary_ticker}")
            # Можно разрешить усреднение при определённых условиях
            if not self._can_average(primary_ticker, analysis, current_price):
                return None
        
        # 2. Проверка секторального риска
        sector = verification['details'][primary_ticker].get('sector', 'other')
        sector_risk = self._get_sector_risk(sector, current_price)
        
        if sector_risk >= self.max_risk_per_sector:
            logger.debug(f"⚠️ Превышен секторальный риск {sector}: {sector_risk:.1f}%")
            return None
        
        # 3. Проверка риска на тикер
        ticker_risk = self._get_ticker_risk(primary_ticker, current_price)
        
        if ticker_risk >= self.max_risk_per_ticker:
            logger.debug(f"⚠️ Превышен риск на тикер {primary_ticker}: {ticker_risk:.1f}%")
            return None
        
        # 4. Расчёт размера позиции
        position_size = self._calculate_position_size(
            analysis=analysis,
            ticker=primary_ticker,
            current_price=current_price,
            sector_risk=sector_risk,
            ticker_risk=ticker_risk
        )
        
        if position_size <= 0:
            logger.debug(f"❌ Нулевой размер позиции для {primary_ticker}")
            return None
        
        # 5. Определение действия - АГРЕССИВНЫЙ РЕЖИМ!
        action = self._determine_action_aggressive(analysis)
        
        if action == 'HOLD':
            logger.debug(f"⚠️ Сигнал {primary_ticker}: HOLD (не торгуем)")
            return None
        
        # 6. Расчёт стоп-лосса и тейк-профита
        stop_loss = current_price * (1 - self.stop_loss_pct / 100)
        take_profit = current_price * (1 + self.take_profit_pct / 100)
        
        # 7. Создание сигнала
        signal = {
            'action': action,
            'ticker': primary_ticker,
            'reason': analysis.get('summary', 'Анализ новости'),
            'confidence': analysis.get('confidence', 0.5),
            'impact_score': analysis.get('impact_score', 5),
            'event_type': analysis.get('event_type', 'market_update'),
            'sentiment': analysis.get('sentiment', 'neutral'),
            'current_price': current_price,
            'position_size': position_size,
            'position_value': position_size * current_price,
            'stop_loss': stop_loss,
            'take_profit': take_profit,
            'stop_loss_percent': self.stop_loss_pct,
            'take_profit_percent': self.take_profit_pct,
            'trailing_start': self.trailing_start,
            'trailing_step': self.trailing_step,
            'risk_per_trade': self.risk_per_trade,
            'sector': sector,
            'sector_risk_before': sector_risk,
            'ticker_risk_before': ticker_risk,
            'ai_provider': analysis.get('ai_provider', 'simple'),
            'news_id': analysis.get('news_id', ''),
            'strategy': 'Enhanced News Trading',
            'timestamp': datetime.now().isoformat()
        }
        
        logger.info(f"🎯 Подготовлен сигнал: {action} {primary_ticker} x{position_size}")
        logger.info(f"   💰 Размер: {position_size * current_price:.0f} руб.")
        logger.info(f"   🛑 Стоп: {stop_loss:.2f} (-{self.stop_loss_pct}%)")
        logger.info(f"   ✅ Тейк: {take_profit:.2f} (+{self.take_profit_pct}%)")
        
        return signal
    
    def _calculate_position_size(self, analysis: Dict, ticker: str, 
                               current_price: float, sector_risk: float,
                               ticker_risk: float) -> int:
        """Расчёт количества акций с учётом рисков"""
        
        # Базовый риск на сделку в рублях
        risk_amount = self.current_capital * self.risk_per_trade / 100
        
        # Корректировка риска на основе качества сигнала
        confidence = analysis.get('confidence', 0.5)
        impact_score = analysis.get('impact_score', 5)
        event_type = analysis.get('event_type', 'market_update')
        
        risk_multiplier = 1.0
        
        # Увеличиваем риск для сильных сигналов
        if confidence > 0.8:
            risk_multiplier *= 1.2
        if impact_score >= 7:
            risk_multiplier *= 1.3
        if event_type in ['dividend', 'earnings_report']:
            risk_multiplier *= 1.5
        
        # Уменьшаем риск если сектор/тикер близки к лимиту
        sector_multiplier = max(0.1, 1 - (sector_risk / self.max_risk_per_sector))
        ticker_multiplier = max(0.1, 1 - (ticker_risk / self.max_risk_per_ticker))
        
        risk_multiplier *= min(sector_multiplier, ticker_multiplier)
        
        # Финальный риск
        adjusted_risk_amount = risk_amount * risk_multiplier
        
        # Расчёт количества акций
        stop_distance = current_price * (self.stop_loss_pct / 100)
        if stop_distance <= 0:
            return 0
        
        shares = int(adjusted_risk_amount / stop_distance)
        
        # Округляем до лота
        lot_size = self.lot_sizes.get(ticker.upper(), 1)
        if lot_size > 1:
            shares = (shares // lot_size) * lot_size
        
        # Минимум 1 лот, максимум по доступному капиталу
        min_shares = max(1, lot_size)
        max_shares_by_capital = int(self.current_capital * 0.1 / current_price)  # Не более 10% капитала
        
        shares = max(min_shares, min(shares, max_shares_by_capital))
        
        # Проверка стоимости
        position_value = shares * current_price
        if position_value > self.current_capital * 0.15:  # Не более 15% капитала в одной позиции
            shares = int(self.current_capital * 0.15 / current_price)
            if lot_size > 1:
                shares = (shares // lot_size) * lot_size
        
        return max(min_shares, shares)
    
    def _determine_action_aggressive(self, analysis: Dict) -> str:
        """Определение действия - АГРЕССИВНЫЙ РЕЖИМ для тестов"""
        sentiment = analysis.get('sentiment', 'neutral')
        event_type = analysis.get('event_type', 'market_update')
        confidence = analysis.get('confidence', 0.5)
        
        # Для AGGRESSIVE_TEST снижаем пороги!
        
        # ПРАВИЛА ДЛЯ АГРЕССИВНОГО ТЕСТА:
        # 1. Любые дивиденды или отчёты → BUY
        if event_type == 'dividend' or event_type == 'earnings_report':
            return 'BUY'
        
        # 2. Позитивная тональность → BUY
        if sentiment == 'positive':
            return 'BUY'
        
        # 3. Негативная тональность → SELL
        if sentiment == 'negative':
            return 'SELL'
        
        # 4. Нейтральная с высокой уверенностью → BUY
        if confidence >= self.min_confidence:  # 0.45 из твоих переменных
            return 'BUY'
        
        # 5. Всё остальное → HOLD (но мы не возвращаем HOLD, фильтруем выше)
        return 'HOLD'
    
    def _determine_action(self, analysis: Dict) -> str:
        """Оригинальный метод для совместимости"""
        return self._determine_action_aggressive(analysis)
    
    def _has_position(self, ticker: str) -> bool:
        """Проверка наличия позиции"""
        return ticker.upper() in self.open_positions and self.open_positions[ticker.upper()]['size'] > 0
    
    def _can_average(self, ticker: str, analysis: Dict, current_price: float) -> bool:
        """Можно ли усреднять позицию"""
        if ticker not in self.open_positions:
            return False
        
        position = self.open_positions[ticker]
        avg_price = position['avg_price']
        
        # Усредняем только при просадке и сильном сигнале
        drawdown = (current_price - avg_price) / avg_price * 100
        
        if drawdown <= -2.0:  # Просадка более 2%
            confidence = analysis.get('confidence', 0)
            impact_score = analysis.get('impact_score', 0)
            
            if confidence > 0.8 and impact_score >= 7:
                return True
        
        return False
    
    def _get_sector_risk(self, sector: str, new_position_value: float = 0) -> float:
        """Расчёт текущего риска сектора в % от капитала"""
        sector_value = 0
        
        for ticker, pos in self.open_positions.items():
            if self._get_ticker_sector(ticker) == sector:
                sector_value += pos.get('current_value', pos['size'] * pos['avg_price'])
        
        # Добавляем новую позицию
        sector_value += new_position_value
        
        # ФИКС: Используем initial_capital как базу если current_capital невалиден
        capital_base = self.current_capital if self.current_capital > 0 else self.initial_capital
        
        if capital_base <= 0:
            return 0.0
        
        return (sector_value / capital_base) * 100
    
    def _get_ticker_risk(self, ticker: str, new_position_value: float = 0) -> float:
        """Расчёт текущего риска тикера в % от капитала"""
        ticker_value = 0
        
        if ticker in self.open_positions:
            pos = self.open_positions[ticker]
            ticker_value = pos.get('current_value', pos['size'] * pos['avg_price'])
        
        # Добавляем новую позицию
        ticker_value += new_position_value
        
        # ФИКС: Используем initial_capital как базу если current_capital невалиден
        capital_base = self.current_capital if self.current_capital > 0 else self.initial_capital
        
        if capital_base <= 0:
            return 0.0
        
        return (ticker_value / capital_base) * 100
    
    def _get_ticker_sector(self, ticker: str) -> str:
        """Получение сектора тикера"""
        ticker_upper = ticker.upper()
        
        for sector, tickers in self.sectors.items():
            if ticker_upper in tickers:
                return sector
        
        return 'other'
    
    def update_positions(self, positions: Dict):
        """Обновление информации об открытых позициях"""
        self.open_positions = positions
        
        # ФИКС: Восстанавливаем капитал если он обнулился
        if self.current_capital <= 0 or self.current_capital != self.initial_capital:
            self.current_capital = self.initial_capital
            logger.info(f"💰 RiskManager: восстановлен капитал {self.current_capital:.0f} руб.")
    
    def get_risk_stats(self) -> Dict:
        """Получение статистики рисков"""
        sector_risks = {}
        
        for sector in self.sectors.keys():
            risk = self._get_sector_risk(sector)
            sector_risks[sector] = 0.0 if risk is None else risk
        
        return {
            'current_capital': self.current_capital,
            'risk_per_trade': self.risk_per_trade,
            'max_risk_per_ticker': self.max_risk_per_ticker,
            'max_risk_per_sector': self.max_risk_per_sector,
            'sector_risks': sector_risks,
            'open_positions_count': len(self.open_positions),
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
