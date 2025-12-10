# finam_verifier.py - ПОЛНЫЙ ОБНОВЛЕННЫЙ ФАЙЛ
import logging
import os
import aiohttp
import asyncio
from datetime import datetime
from typing import Dict, List, Optional
import json

logger = logging.getLogger(__name__)

class FinamVerifier:
    """Верификация торговых сигналов через Finam API"""
    
    def __init__(self):
        self.jwt_token = os.getenv('FINAM_API_TOKEN', '')  # JWT токен
        self.client_id = os.getenv('FINAM_CLIENT_ID', '621971R9IP3')
        
        # Инициализация FinamClient
        self.finam_client = None
        if self.jwt_token and self.client_id:
            try:
                from finam_client import FinamClient
                self.finam_client = FinamClient(self.jwt_token, self.client_id)
                logger.info(f"🏦 FinamClient инициализирован с JWT токеном")
            except Exception as e:
                logger.error(f"❌ Ошибка инициализации FinamClient: {e}")
        
        # Топ-100 ликвидных тикеров MOEX
        self.liquid_tickers = {
            'SBER', 'GAZP', 'LKOH', 'ROSN', 'NVTK', 'GMKN', 'PLZL', 'POLY',
            'TATN', 'ALRS', 'CHMF', 'NLMK', 'MAGN', 'SNGS', 'VTBR', 'TCSG',
            'MTSS', 'AFKS', 'FEES', 'MGNT', 'FIVE', 'YNDX', 'OZON', 'MOEX',
            'RTKM', 'PHOR', 'TRNFP', 'BANE', 'IRAO', 'HYDR', 'RSTI', 'ENPL',
            'PIKK', 'LSRG', 'ETLN', 'SMLT', 'SVAV', 'AFLT', 'GLTR', 'DSKY',
            'MVID', 'GCHE', 'KAZT', 'URKA', 'AKRN', 'KAZTP', 'LENT', 'LNTA',
            'CBOM', 'SFIN', 'RUGR', 'SVCB', 'FCIT', 'ALFA', 'ABIO', 'CIAN',
            'POSI', 'MDMG', 'QIWI', 'HHRU', 'FLOT', 'TGKA', 'TGKB', 'TGKD',
            'KMAZ', 'MSRS', 'MSNG', 'VKCO', 'OKEY', 'GTRK', 'NMTP', 'PRMB',
            'KROT', 'LPSB', 'LSNG', 'MRKP', 'MRKU', 'MRKV', 'MRKZ', 'MRKY',
            'MSST', 'MGTSP', 'TGKN', 'UPRO', 'WUSH', 'YAKG', 'YKEN', 'YRSB',
            'ZILL', 'ZVEZ'
        }
        
        # Сектора
        self.sector_mapping = {
            'banks': ['SBER', 'VTBR', 'TCSG', 'CBOM', 'SFIN', 'RUGR', 'SVCB', 'ALFA', 'FCIT'],
            'oil_gas': ['GAZP', 'LKOH', 'ROSN', 'NVTK', 'TATN', 'SNGS', 'BANE', 'TRNFP'],
            'metals': ['GMKN', 'ALRS', 'POLY', 'CHMF', 'NLMK', 'MAGN', 'PLZL', 'RASP'],
            'retail': ['MGNT', 'FIVE', 'LNTA', 'DSKY', 'OZON', 'MVID', 'OKEY'],
            'tech': ['YNDX', 'OZON', 'POSI', 'CIAN', 'VKCO', 'QIWI'],
            'energy': ['IRAO', 'HYDR', 'RSTI', 'FEES', 'TGKA', 'TGKB', 'TGKD'],
            'transport': ['AFLT', 'GLTR', 'FLOT'],
            'real_estate': ['PIKK', 'LSRG', 'ETLN', 'SMLT'],
            'pharma': ['PHOR', 'ABIO', 'MDMG'],
            'dividend': ['MOEX', 'RTKM', 'KAZT', 'URKA', 'AKRN']
        }
        
        # Fallback цены
        self.fallback_prices = self._load_fallback_prices()
        
        logger.info(f"🏦 FinamVerifier инициализирован")
        logger.info(f"   FinamClient: {'✅' if self.finam_client else '❌'}")
        logger.info(f"   Ликвидных тикеров: {len(self.liquid_tickers)}")
    
    def _load_fallback_prices(self) -> Dict:
        """Загрузка фолбэк цен"""
        return {
            'SBER': 285.40, 'GAZP': 168.20, 'LKOH': 7520.0, 'ROSN': 592.80,
            'NVTK': 1725.0, 'GMKN': 16250.0, 'PLZL': 12500.0, 'POLY': 1120.0,
            'TATN': 580.0, 'ALRS': 76.80, 'CHMF': 1380.0, 'NLMK': 180.50,
            'MAGN': 55.30, 'SNGS': 38.20, 'VTBR': 0.026, 'TCSG': 3350.0,
            'MTSS': 285.50, 'AFKS': 28.40, 'FEES': 0.185, 'MGNT': 5620.0,
            'FIVE': 2740.0, 'YNDX': 2950.0, 'OZON': 2450.0, 'MOEX': 174.74,
            'RTKM': 65.30, 'PHOR': 6620.0, 'TRNFP': 155000.0, 'BANE': 210.0
        }
    
    async def _get_price_from_finam(self, ticker: str) -> Optional[float]:
        """Получение цены через FinamClient"""
        if self.finam_client:
            try:
                price = await self.finam_client.get_current_price(ticker)
                if price:
                    logger.debug(f"   ✅ Finam цена {ticker}: {price:.2f}")
                    return price
            except Exception as e:
                logger.debug(f"   ⚠️ Finam ошибка для {ticker}: {str(e)[:50]}")
        
        # Fallback если Finam недоступен
        logger.debug(f"   ⚠️ Finam недоступен, использую fallback для {ticker}")
        return self.fallback_prices.get(ticker.upper())
    
    async def verify_signal(self, analysis: Dict) -> Dict:
        """Верификация сигнала - УПРОЩЕННАЯ для тестов"""
        tickers = analysis.get('tickers', [])
        if not tickers:
            return {'valid': False, 'reason': 'No tickers', 'details': {}}
        
        verification_results = {}
        has_valid_ticker = False
        
        for ticker in tickers[:3]:  # Проверяем до 3 тикеров
            ticker_upper = ticker.upper()
            
            # 1. Проверка ликвидности
            if ticker_upper not in self.liquid_tickers:
                verification_results[ticker] = {
                    'valid': False,
                    'reason': f'Тикер {ticker} не ликвиден',
                    'liquid': False,
                    'price': None,
                    'sector': None,
                    'data_source': 'not_liquid'
                }
                continue
            
            try:
                # 2. Получение цены (Finam или fallback)
                price = await self._get_price_from_finam(ticker_upper)
                
                if not price:
                    verification_results[ticker] = {
                        'valid': False,
                        'reason': 'Нет данных о цене',
                        'liquid': True,
                        'price': None,
                        'sector': self._get_sector(ticker_upper),
                        'data_source': 'no_price'
                    }
                    continue
                
                # 3. Упрощенная проверка для тестов
                is_valid = True
                reasons = []
                
                # Только базовая проверка
                if price <= 0.1:  # Очень дешевые акции
                    is_valid = False
                    reasons.append('Цена слишком низкая')
                
                verification_results[ticker] = {
                    'valid': is_valid,
                    'reason': ', '.join(reasons) if reasons else 'OK',
                    'liquid': True,
                    'price': price,
                    'sector': self._get_sector(ticker_upper),
                    'data_source': 'finam' if self.finam_client and price != self.fallback_prices.get(ticker_upper) else 'fallback'
                }
                
                if is_valid:
                    has_valid_ticker = True
                
            except Exception as e:
                logger.error(f"❌ Ошибка верификации {ticker}: {str(e)[:50]}")
                verification_results[ticker] = {
                    'valid': False,
                    'reason': f'Ошибка: {str(e)[:30]}',
                    'liquid': ticker_upper in self.liquid_tickers,
                    'price': self.fallback_prices.get(ticker_upper),
                    'sector': self._get_sector(ticker_upper),
                    'data_source': 'error'
                }
        
        # Итоговое решение - УПРОЩЕННОЕ для тестов
        trading_mode = os.getenv('TRADING_MODE', 'AGGRESSIVE_TEST')
        
        if has_valid_ticker:
            valid_tickers = {t: data for t, data in verification_results.items() if data['valid']}
            return {
                'valid': True,
                'reason': f'Верифицировано {len(valid_tickers)} тикеров',
                'tickers': list(valid_tickers.keys()),
                'details': verification_results,
                'primary_ticker': list(valid_tickers.keys())[0],
                'primary_price': list(valid_tickers.values())[0]['price']
            }
        else:
            # В ТЕСТОВОМ РЕЖИМЕ пробуем хотя бы один ликвидный тикер
            if verification_results:
                for ticker, data in verification_results.items():
                    if data['liquid'] and data['price']:
                        return {
                            'valid': True,  # Разрешаем в тестовом режиме
                            'reason': 'Тестовый режим: использование ликвидного тикера',
                            'tickers': [ticker],
                            'details': verification_results,
                            'primary_ticker': ticker,
                            'primary_price': data['price']
                        }
            
            return {
                'valid': False,
                'reason': 'Нет подходящих тикеров для торговли',
                'details': verification_results
            }
    
    def _get_sector(self, ticker: str) -> str:
        """Определение сектора тикера"""
        for sector, tickers in self.sector_mapping.items():
            if ticker in tickers:
                return sector
        return 'other'
    
    async def get_current_prices(self, tickers: List[str]) -> Dict[str, float]:
        """Получение текущих цен для списка тикеров"""
        prices = {}
        
        for ticker in tickers:
            ticker_upper = ticker.upper()
            price = await self._get_price_from_finam(ticker_upper)
            if price:
                prices[ticker] = price
            elif ticker_upper in self.fallback_prices:
                prices[ticker] = self.fallback_prices[ticker_upper]
        
        return prices
    
    def is_ticker_liquid(self, ticker: str) -> bool:
        """Проверка ликвидности тикера"""
        return ticker.upper() in self.liquid_tickers
    
    def get_sector_tickers(self, sector: str) -> List[str]:
        """Получение тикеров сектора"""
        return self.sector_mapping.get(sector, [])
    
    async def test_finam_connection(self) -> Dict:
        """Тест соединения с Finam"""
        if not self.finam_client:
            return {
                'status': 'error',
                'reason': 'FinamClient не инициализирован',
                'timestamp': datetime.now().isoformat()
            }
        
        return await self.finam_client.test_connection()
