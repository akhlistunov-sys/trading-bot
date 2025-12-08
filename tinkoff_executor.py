# tinkoff_executor.py - ПОЛНЫЙ ОБНОВЛЁННЫЙ ФАЙЛ С FINAM
import logging
import os
import aiohttp
import asyncio
from typing import Dict, Optional, List
import json

logger = logging.getLogger(__name__)

class TinkoffExecutor:
    """Исполнительный модуль с Finam API и MOEX"""
    
    def __init__(self):
        self.finam_token = os.getenv('FINAM_API_TOKEN', 'bbae67bd-2578-4b00-84bb-f8423f17756d')
        self.finam_client_id = os.getenv('FINAM_CLIENT_ID', '621971R9IP3')
        
        # Маппинг тикеров
        self.ticker_mapping = {
            'SBER': 'SBER', 'GAZP': 'GAZP', 'LKOH': 'LKOH', 'ROSN': 'ROSN',
            'NVTK': 'NVTK', 'GMKN': 'GMKN', 'PLZL': 'PLZL', 'POLY': 'POLY',
            'TATN': 'TATN', 'ALRS': 'ALRS', 'CHMF': 'CHMF', 'NLMK': 'NLMK',
            'MAGN': 'MAGN', 'SNGS': 'SNGS', 'VTBR': 'VTBR', 'TCSG': 'TCSG',
            'MTSS': 'MTSS', 'AFKS': 'AFKS', 'FEES': 'FEES', 'MGNT': 'MGNT',
            'FIVE': 'FIVE', 'YNDX': 'YNDX', 'OZON': 'OZON', 'MOEX': 'MOEX',
            'RTKM': 'RTKM', 'PHOR': 'PHOR', 'TRNFP': 'TRNFP', 'BANE': 'BANE',
            'IRAO': 'IRAO', 'HYDR': 'HYDR', 'RSTI': 'RSTI', 'ENPL': 'ENPL',
            'PIKK': 'PIKK', 'LSRG': 'LSRG', 'ETLN': 'ETLN', 'SMLT': 'SMLT',
            'AFLT': 'AFLT', 'GLTR': 'GLTR', 'DSKY': 'DSKY', 'MVID': 'MVID',
            'GCHE': 'GCHE', 'KAZT': 'KAZT', 'URKA': 'URKA', 'AKRN': 'AKRN',
            'CBOM': 'CBOM', 'SFIN': 'SFIN', 'RUGR': 'RUGR', 'SVCB': 'SVCB',
            'FCIT': 'FCIT', 'ALFA': 'ALFA', 'ABIO': 'ABIO', 'CIAN': 'CIAN',
            'POSI': 'POSI', 'VKCO': 'VKCO', 'QIWI': 'QIWI', 'OKEY': 'OKEY'
        }
        
        # Приоритет источников цен
        self.price_sources = ['finam', 'moex', 'fallback']
        
        # Фолбэк цены
        self.fallback_prices = {
            'SBER': 285.40, 'GAZP': 168.20, 'LKOH': 7520.0, 'ROSN': 592.80,
            'NVTK': 1725.0, 'GMKN': 16250.0, 'PLZL': 12500.0, 'POLY': 1120.0,
            'TATN': 580.0, 'ALRS': 76.80, 'CHMF': 1380.0, 'NLMK': 180.50,
            'MAGN': 55.30, 'SNGS': 38.20, 'VTBR': 0.026, 'TCSG': 3350.0,
            'MTSS': 285.50, 'AFKS': 28.40, 'FEES': 0.185, 'MGNT': 5620.0,
            'FIVE': 2740.0, 'YNDX': 2950.0, 'OZON': 2450.0, 'MOEX': 174.74,
            'RTKM': 65.30, 'PHOR': 6620.0, 'TRNFP': 155000.0, 'BANE': 210.0
        }
        
        logger.info("🏦 TinkoffExecutor инициализирован с Finam API")
        logger.info(f"   Finam токен: {self.finam_token[:8]}...")
        logger.info(f"   Источники цен: {', '.join(self.price_sources)}")
        logger.info(f"   Тикеров в маппинге: {len(self.ticker_mapping)}")
    
    async def get_price_from_finam(self, ticker: str) -> Optional[float]:
    """Получение цены с Finam API"""
    finam_ticker = self.ticker_mapping.get(ticker.upper())
    if not finam_ticker:
        return None
    
    try:
        url = f"https://trade-api.finam.ru/public/api/v1/securities/{finam_ticker}/quotes"
        
        headers = {
            'Authorization': f'Bearer {self.finam_token}',  # ✅ Bearer а не X-Api-Key
            'Accept': 'application/json',
            'Content-Type': 'application/json'
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers, timeout=10) as response:
                if response.status == 200:
                    data = await response.json()
                    
                    if data.get('status') == 'Ok':
                        quotes = data.get('data', {}).get('quotes', [])
                        if quotes:
                            last_price = quotes[0].get('last')
                            if last_price:
                                logger.debug(f"   ✅ Finam цена {ticker}: {last_price}")
                                return float(last_price)
        
        return None
        
    except Exception as e:
        logger.debug(f"   ⚠️ Finam price ошибка для {ticker}: {str(e)[:50]}")
        return None
    
    async def get_price_from_moex(self, ticker: str) -> Optional[float]:
        """Получение цены с MOEX (резерв)"""
        moex_ticker = self.ticker_mapping.get(ticker.upper())
        if not moex_ticker:
            return None
        
        urls = [
            f"https://iss.moex.com/iss/engines/stock/markets/shares/boards/TQBR/securities/{moex_ticker}.json?iss.meta=off&iss.json=extended",
            f"https://iss.moex.com/iss/engines/stock/markets/shares/securities/{moex_ticker}.json?iss.meta=off"
        ]
        
        for url in urls:
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(url, timeout=10, ssl=False) as response:
                        if response.status == 200:
                            data = await response.json()
                            
                            # Парсим разные форматы MOEX
                            price = None
                            
                            # Формат extended JSON
                            if isinstance(data, list) and len(data) > 1:
                                marketdata = data[1]
                                if 'marketdata' in marketdata:
                                    columns = marketdata['columns']
                                    data_rows = marketdata['data']
                                    if data_rows:
                                        if 'LAST' in columns:
                                            idx = columns.index('LAST')
                                            price = data_rows[0][idx]
                                        elif 'LCURRENTPRICE' in columns:
                                            idx = columns.index('LCURRENTPRICE')
                                            price = data_rows[0][idx]
                            
                            # Формат обычный JSON
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
                                logger.debug(f"   ✅ MOEX цена {ticker}: {price}")
                                return float(price)
                                    
            except Exception as e:
                logger.debug(f"   ⚠️ MOEX price ошибка для {ticker}: {str(e)[:50]}")
                continue
        
        return None
    
    async def get_current_price(self, ticker: str) -> Optional[float]:
        """Получение текущей цены (Finam → MOEX → Fallback)"""
        
        ticker_upper = ticker.upper()
        
        # Пробуем все источники по порядку
        for source in self.price_sources:
            if source == 'finam':
                price = await self.get_price_from_finam(ticker_upper)
                if price:
                    logger.info(f"💰 Finam цена {ticker}: {price:.2f} руб.")
                    return price
            
            elif source == 'moex':
                price = await self.get_price_from_moex(ticker_upper)
                if price:
                    logger.info(f"💰 MOEX цена {ticker}: {price:.2f} руб.")
                    return price
            
            elif source == 'fallback':
                if ticker_upper in self.fallback_prices:
                    price = self.fallback_prices[ticker_upper]
                    logger.info(f"💰 Fallback цена {ticker}: {price:.2f} руб.")
                    return price
        
        logger.warning(f"⚠️ Цена не найдена для {ticker}")
        return None
    
    async def execute_order(self, signal: Dict, virtual_mode: bool = True) -> Dict:
        """Исполнение ордера (виртуальное)"""
        
        ticker = signal.get('ticker', '')
        action = signal.get('action', '')
        size = signal.get('position_size', 1)
        
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
            'signal_source': signal.get('ai_provider', 'unknown'),
            'signal_confidence': signal.get('confidence', 0.5),
            'timestamp': datetime.now().isoformat()
        }
    
    def get_ticker_info(self, ticker: str) -> Dict:
        """Получение информации о тикере"""
        
        available = ticker.upper() in self.ticker_mapping
        
        return {
            'ticker': ticker.upper(),
            'available': available,
            'has_finam_data': available,
            'has_moex_data': available,
            'fallback_price': self.fallback_prices.get(ticker.upper()),
            'message': 'Тикер доступен' if available else 'Тикер не найден'
        }
    
    def get_available_tickers(self) -> List[str]:
        """Получение списка доступных тикеров"""
        return list(self.ticker_mapping.keys())
    
    async def test_connections(self) -> Dict:
        """Тест всех соединений"""
        test_ticker = 'SBER'
        
        finam_price = await self.get_price_from_finam(test_ticker)
        moex_price = await self.get_price_from_moex(test_ticker)
        
        return {
            'finam_available': finam_price is not None,
            'finam_price': finam_price,
            'moex_available': moex_price is not None,
            'moex_price': moex_price,
            'fallback_price': self.fallback_prices.get(test_ticker),
            'test_ticker': test_ticker,
            'tickers_count': len(self.ticker_mapping),
            'sources_priority': self.price_sources
        }
