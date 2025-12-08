import logging
import os
from typing import Dict, Optional, List

# ==== ИСПРАВЛЕННЫЙ ИМПОРТ ====
try:
    from tinkoff.invest import Client
    from tinkoff.invest.constants import INVEST_GRPC_API_SANDBOX
    TINKOFF_AVAILABLE = True
except ImportError as e:
    print(f"❌ Ошибка импорта Tinkoff: {e}")
    print("⚠️  Установите: pip install tinkoff-investments")
    TINKOFF_AVAILABLE = False
# ==== КОНЕЦ ИСПРАВЛЕНИЯ ====

logger = logging.getLogger(__name__)

class TinkoffExecutor:
    """Исполнительный модуль для работы с Tinkoff Invest API"""
    
    def __init__(self):
        self.token = os.getenv("TINKOFF_API_TOKEN")
        
        if not self.token:
            logger.error("❌ TINKOFF_API_TOKEN не найден")
            self.available = False
            return
        
        self.available = TINKOFF_AVAILABLE
        self.account_id = None
        
        # Маппинг тикеров на FIGI
        self.ticker_to_figi = {
            'LKOH': 'BBG004731032', 'ROSN': 'BBG004731354',
            'GAZP': 'BBG004730RP0', 'NVTK': 'BBG00475J7T5',
            'SBER': 'BBG004730N88', 'VTBR': 'BBG004730ZJ9',
            'TCSG': 'BBG0110F3P74', 'GMKN': 'BBG004731489',
            'ALRS': 'BBG004S681W4', 'POLY': 'BBG004S683W7',
            'MGNT': 'BBG004S681B4', 'FIVE': 'BBG00F6NKQ13',
            'MTSS': 'BBG00475K6C3', 'MOEX': 'BBG004730JJ5',
            'PHOR': 'BBG004S68507', 'CHMF': 'BBG00475K6X6',
        }
        
        # Фолбэк цены (если API не работает)
        self.fallback_prices = {
            'SBER': 280.50, 'GAZP': 165.30, 'VTBR': 0.025,
            'LKOH': 7400.0, 'ROSN': 580.75, 'NVTK': 1700.0,
            'TCSG': 3300.0, 'GMKN': 16000.0, 'ALRS': 75.40,
            'POLY': 1100.0, 'MGNT': 5500.0, 'FIVE': 2700.0,
            'MTSS': 280.0, 'MOEX': 150.0, 'PHOR': 6500.0,
            'CHMF': 1350.0
        }
        
        logger.info("🏦 Tinkoff Executor инициализирован")
        logger.info(f"📊 Загружено {len(self.ticker_to_figi)} тикеров")
        logger.info(f"🔑 Tinkoff доступен: {'✅' if self.available else '❌'}")
    
    async def get_current_price(self, ticker: str) -> Optional[float]:
        """Получение текущей цены акции (с фолбэком)"""
        
        # Если API доступен, пробуем получить реальную цену
        if self.available and self.token:
            figi = self.ticker_to_figi.get(ticker.upper())
            if not figi:
                logger.warning(f"⚠️ FIGI не найден для тикера {ticker}")
                # Пробуем фолбэк
                if ticker.upper() in self.fallback_prices:
                    price = self.fallback_prices[ticker.upper()]
                    logger.info(f"💰 ФОЛБЭК цена {ticker}: {price:.2f} руб.")
                    return price
                return None
            
            try:
                with Client(self.token) as client:
                    last_prices = client.market_data.get_last_prices(figi=[figi])
                    
                    if last_prices.last_prices:
                        price_obj = last_prices.last_prices[0].price
                        price = price_obj.units + price_obj.nano / 1e9
                        
                        logger.info(f"💰 РЕАЛЬНАЯ цена {ticker}: {price:.2f} руб.")
                        return price
            
            except Exception as e:
                logger.error(f"❌ Ошибка получения цены {ticker}: {e}")
                # Продолжаем к фолбэку
        
        # Фолбэк на фиксированные цены
        if ticker.upper() in self.fallback_prices:
            price = self.fallback_prices[ticker.upper()]
            logger.info(f"💰 ФОЛБЭК цена {ticker}: {price:.2f} руб.")
            return price
        
        logger.warning(f"⚠️ Цена не найдена для {ticker}")
        return None
    
    async def execute_order(self, signal: Dict, virtual_mode: bool = True) -> Dict:
        """Исполнение ордера (виртуальное или реальное)"""
        
        ticker = signal.get('ticker', '')
        action = signal.get('action', '')
        size = signal.get('size', 0)
        
        if not ticker or not action or size <= 0:
            return {
                'status': 'ERROR',
                'message': 'Неверные параметры ордера',
                'ticker': ticker,
                'action': action,
                'size': size
            }
        
        current_price = await self.get_current_price(ticker)
        if not current_price:
            return {
                'status': 'ERROR',
                'message': f'Не удалось получить цену для {ticker}',
                'ticker': ticker
            }
        
        if virtual_mode:
            return {
                'status': 'EXECUTED_VIRTUAL',
                'ticker': ticker,
                'action': action,
                'size': size,
                'price': current_price,
                'total_value': current_price * size,
                'message': f'Виртуальный ордер: {action} {ticker} x{size} по {current_price:.2f} руб.',
                'virtual': True
            }
        else:
            if not self.available:
                return {
                    'status': 'ERROR',
                    'message': 'Tinkoff API недоступен для реального исполнения',
                    'ticker': ticker
                }
            
            try:
                return {
                    'status': 'SIMULATED',
                    'ticker': ticker,
                    'action': action,
                    'size': size,
                    'price': current_price,
                    'message': f'Реальный ордер симулирован (тестовый режим)',
                    'virtual': False
                }
                
            except Exception as e:
                logger.error(f"❌ Ошибка исполнения ордера {ticker}: {e}")
                return {
                    'status': 'ERROR',
                    'message': str(e)[:100],
                    'ticker': ticker
                }
    
    def get_ticker_info(self, ticker: str) -> Dict:
        """Получение информации о тикере"""
        
        figi = self.ticker_to_figi.get(ticker.upper())
        
        if figi:
            return {
                'ticker': ticker.upper(),
                'figi': figi,
                'available': True
            }
        else:
            return {
                'ticker': ticker.upper(),
                'available': False,
                'message': 'Тикер не найден в базе'
            }
    
    def get_available_tickers(self) -> List[str]:
        """Получение списка доступных тикеров"""
        return list(self.ticker_to_figi.keys())
