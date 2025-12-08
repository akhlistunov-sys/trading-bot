import logging
import os
import aiohttp
import asyncio
from typing import Dict, Optional, List
import json

logger = logging.getLogger(__name__)

class TinkoffExecutor:
    """Исполнительный модуль с MOEX API вместо Tinkoff"""
    
    def __init__(self):
        # Убираем Tinkoff токен - он не нужен для MOEX
        self.moex_available = True
        
        # Маппинг тикеров MOEX (правильные тикеры для MOEX)
        self.ticker_mapping = {
            'LKOH': 'LKOH', 'ROSN': 'ROSN',
            'GAZP': 'GAZP', 'NVTK': 'NVTK',
            'SBER': 'SBER', 'VTBR': 'VTBR',
            'TCSG': 'TCSG', 'GMKN': 'GMKN',
            'ALRS': 'ALRS', 'POLY': 'POLY',
            'MGNT': 'MGNT', 'FIVE': 'FIVE',
            'MTSS': 'MTSS', 'MOEX': 'MOEX',
            'PHOR': 'PHOR', 'CHMF': 'CHMF',
            'YNDX': 'YNDX', 'OZON': 'OZON',
            'TATN': 'TATN', 'SNGS': 'SNGS',
            'BANE': 'BANE', 'TRNFP': 'TRNFP'
        }
        
        # Фолбэк цены (актуальные примерные цены на декабрь 2024)
        self.fallback_prices = {
            'SBER': 285.40,    # ~285 руб
            'GAZP': 168.20,    # ~168 руб
            'LKOH': 7520.0,    # ~7520 руб
            'ROSN': 592.80,    # ~593 руб
            'VTBR': 0.026,     # ~0.026 руб
            'NVTK': 1725.0,    # ~1725 руб
            'TCSG': 3350.0,    # ~3350 руб
            'GMKN': 16250.0,   # ~16250 руб
            'ALRS': 76.80,     # ~77 руб
            'POLY': 1120.0,    # ~1120 руб
            'MGNT': 5620.0,    # ~5620 руб
            'FIVE': 2740.0,    # ~2740 руб
            'MTSS': 285.50,    # ~285 руб
            'MOEX': 152.30,    # ~152 руб
            'PHOR': 6620.0,    # ~6620 руб
            'CHMF': 1380.0,    # ~1380 руб
            'YNDX': 2950.0,    # ~2950 руб
            'OZON': 2450.0,    # ~2450 руб
        }
        
        logger.info("🏦 MOEX Executor инициализирован")
        logger.info(f"📊 Загружено {len(self.ticker_mapping)} тикеров")
        logger.info("💰 Источник цен: MOEX API (бесплатный)")
    
    async def get_price_from_moex(self, ticker: str) -> Optional[float]:
        """Получение цены с MOEX API (основной метод)"""
        moex_ticker = self.ticker_mapping.get(ticker.upper())
        if not moex_ticker:
            logger.warning(f"⚠️ Тикер {ticker} не найден в маппинге MOEX")
            return None
        
        urls = [
            # Основной URL для акций
            f"https://iss.moex.com/iss/engines/stock/markets/shares/boards/TQBR/securities/{moex_ticker}.json?iss.meta=off&iss.json=extended",
            # Резервный URL
            f"https://iss.moex.com/iss/engines/stock/markets/shares/securities/{moex_ticker}.json?iss.meta=off"
        ]
        
        for url in urls:
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(url, timeout=10, ssl=False) as response:
                        if response.status == 200:
                            data = await response.json()
                            
                            # Парсим разные форматы ответов MOEX
                            price = None
                            
                            # Формат 1: extended JSON
                            if isinstance(data, list) and len(data) > 1:
                                marketdata = data[1]
                                if 'marketdata' in marketdata:
                                    columns = marketdata['columns']
                                    data_rows = marketdata['data']
                                    if data_rows:
                                        # Ищем колонку с LAST ценой
                                        if 'LAST' in columns:
                                            idx = columns.index('LAST')
                                            price = data_rows[0][idx]
                                        elif 'LCURRENTPRICE' in columns:
                                            idx = columns.index('LCURRENTPRICE')
                                            price = data_rows[0][idx]
                            
                            # Формат 2: обычный JSON
                            elif 'marketdata' in data:
                                columns = data['marketdata'].get('columns', [])
                                data_rows = data['marketdata'].get('data', [])
                                if data_rows:
                                    if 'LAST' in columns:
                                        idx = columns.index('LAST')
                                        price = data_rows[0][idx]
                                    elif 'LCURRENTPRICE' in columns:
                                        idx = columns.index('LCURRENTPRICE')
                                        price = data_rows[0][idx]
                            
                            if price and price > 0:
                                logger.info(f"✅ MOEX: {ticker} = {price:.2f} руб.")
                                return float(price)
                                
            except asyncio.TimeoutError:
                logger.warning(f"⏰ MOEX таймаут для {ticker}")
                continue
            except Exception as e:
                logger.debug(f"🔧 MOEX ошибка для {ticker}: {str(e)[:50]}")
                continue
        
        return None
    
    async def get_current_price(self, ticker: str) -> Optional[float]:
        """Получение текущей цены акции (MOEX → фолбэк)"""
        
        ticker_upper = ticker.upper()
        
        # 1. Пробуем MOEX API
        moex_price = await self.get_price_from_moex(ticker_upper)
        if moex_price:
            return moex_price
        
        # 2. Фолбэк на фиксированные цены
        if ticker_upper in self.fallback_prices:
            price = self.fallback_prices[ticker_upper]
            logger.info(f"💰 ФОЛБЭК цена {ticker}: {price:.2f} руб.")
            return price
        
        logger.warning(f"⚠️ Цена не найдена для {ticker}")
        return None
    
    async def execute_order(self, signal: Dict, virtual_mode: bool = True) -> Dict:
        """Исполнение ордера (виртуальное)"""
        
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
        
        # Всегда виртуальный режим для тестов
        return {
            'status': 'EXECUTED_VIRTUAL',
            'ticker': ticker,
            'action': action,
            'size': size,
            'price': current_price,
            'total_value': current_price * size,
            'message': f'Виртуальный ордер: {action} {ticker} x{size} по {current_price:.2f} руб.',
            'virtual': True,
            'price_source': 'MOEX' if ticker.upper() in self.ticker_mapping else 'FALLBACK'
        }
    
    def get_ticker_info(self, ticker: str) -> Dict:
        """Получение информации о тикере"""
        
        available = ticker.upper() in self.ticker_mapping
        
        return {
            'ticker': ticker.upper(),
            'available': available,
            'has_moex_data': available,
            'fallback_price': self.fallback_prices.get(ticker.upper()),
            'message': 'Тикер доступен в MOEX' if available else 'Тикер не найден'
        }
    
    def get_available_tickers(self) -> List[str]:
        """Получение списка доступных тикеров"""
        return list(self.ticker_mapping.keys())
    
    async def test_moex_connection(self) -> Dict:
        """Тест соединения с MOEX API"""
        test_ticker = 'SBER'
        price = await self.get_price_from_moex(test_ticker)
        
        return {
            'moex_available': self.moex_available,
            'test_ticker': test_ticker,
            'price_received': price is not None,
            'price': price,
            'fallback_price': self.fallback_prices.get(test_ticker),
            'tickers_count': len(self.ticker_mapping)
        }
