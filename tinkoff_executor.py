# tinkoff_executor.py - OFFICIAL T-BANK SDK INTEGRATION
import logging
import os
import asyncio
from typing import Optional, Dict
from datetime import datetime, timedelta
from tinkoff.invest import (
    Client, AsyncClient, CandleInterval, OrderDirection, OrderType, 
    MoneyValue, Quotation
)
from tinkoff.invest.services import Services
from tinkoff.invest.utils import quotation_to_decimal, now

logger = logging.getLogger(__name__)

class TinkoffExecutor:
    """Официальный клиент Тинькофф Инвестиции (Песочница + Реал)"""
    
    def __init__(self):
        self.token = os.getenv('TINKOFF_API_TOKEN')
        # Режим торговли: SANDBOX (Песочница) или REAL (Реальный счет)
        # Берем из переменной окружения, по умолчанию SANDBOX для безопасности
        self.mode = os.getenv('TRADING_MODE', 'SANDBOX').upper() 
        self.account_id = None
        
        # Кэш FIGI (Тикер -> Уникальный ID)
        self.figi_cache = {
            'SBER': 'BBG004730N88', 'GAZP': 'BBG0047315Y7', 'LKOH': 'BBG004731032',
            'ROSN': 'BBG004731354', 'GMKN': 'BBG004731489', 'NVTK': 'BBG00475KKY4',
            'YNDX': 'BBG006L8G4H1', 'OZON': 'BBG00ZYWC248', 'MGNT': 'BBG004RVFCY3',
            'FIVE': 'BBG004S686W0', 'TATN': 'BBG004731427', 'SNGS': 'BBG004731427',
            'VTBR': 'BBG004730ZJ9', 'TCSG': 'BBG00QPYJ5H0', 'ALRS': 'BBG004S682Z6',
            'MOEX': 'BBG004730RP0', 'MTSS': 'BBG0047315D0', 'AFKS': 'BBG004731AD5'
        }
        
        if not self.token:
            logger.critical("❌ НЕТ TINKOFF_API_TOKEN! Торговля невозможна.")
        else:
            logger.info(f"🏦 TinkoffExecutor: Режим {self.mode}")
            # При старте проверяем счет
            asyncio.create_task(self._init_account())

    async def _init_account(self):
        """Инициализация счета (открытие песочницы если нет)"""
        if not self.token: return
        
        try:
            async with AsyncClient(self.token) as client:
                if self.mode == 'SANDBOX':
                    accounts = await client.sandbox.get_sandbox_accounts()
                    if not accounts.accounts:
                        logger.info("🥪 Создаю новый счет в Песочнице...")
                        resp = await client.sandbox.open_sandbox_account()
                        self.account_id = resp.account_id
                    else:
                        self.account_id = accounts.accounts[0].id
                    logger.info(f"🥪 Песочница готова. Account ID: {self.account_id}")
                    
                else: # REAL MODE
                    accounts = await client.users.get_accounts()
                    # Берем первый брокерский счет
                    for acc in accounts.accounts:
                        if acc.type == 1: # Tinkoff
                            self.account_id = acc.id
                            break
                    logger.info(f"💰 РЕАЛЬНЫЙ СЧЕТ ПОДКЛЮЧЕН. Account ID: {self.account_id}")
                    
        except Exception as e:
            logger.error(f"❌ Ошибка инициализации Тинькофф: {e}")

    async def get_current_price(self, ticker: str) -> Optional[float]:
        """Получение цены через MarketData"""
        if not self.token: return None
        
        ticker = ticker.upper()
        figi = self.figi_cache.get(ticker)
        
        # Если FIGI нет в кэше, пробуем найти (но лучше заполнить кэш)
        if not figi: 
            # Здесь можно добавить поиск инструмента, но для скорости пока пропустим
            logger.warning(f"⚠️ Нет FIGI для {ticker}, пропускаем")
            return None

        try:
            async with AsyncClient(self.token) as client:
                response = await client.market_data.get_last_prices(figi=[figi])
                if response.last_prices:
                    price = quotation_to_decimal(response.last_prices[0].price)
                    return float(price)
        except Exception as e:
            logger.error(f"⚠️ Ошибка цены Тинькофф {ticker}: {e}")
            return None

    async def execute_order(self, ticker: str, action: str, quantity: int) -> Dict:
        """Исполнение заявки (Рыночная)"""
        if not self.token or not self.account_id:
            return {'status': 'ERROR', 'message': 'Нет токена или счета'}

        figi = self.figi_cache.get(ticker.upper())
        if not figi:
            return {'status': 'ERROR', 'message': f'Неизвестный тикер {ticker}'}

        direction = OrderDirection.ORDER_DIRECTION_BUY if action == 'BUY' else OrderDirection.ORDER_DIRECTION_SELL
        
        try:
            async with AsyncClient(self.token) as client:
                # 1. Проверяем лотность (нужно знать сколько акций в 1 лоте)
                instrument = await client.instruments.get_instrument_by(id_type=1, id=figi)
                lot_size = instrument.instrument.lot
                
                # Приводим штуки к лотам
                lots_to_trade = max(1, quantity // lot_size)
                
                logger.info(f"🏦 Отправка ордера: {action} {lots_to_trade} лотов {ticker} ({self.mode})...")
                
                if self.mode == 'SANDBOX':
                    resp = await client.sandbox.post_sandbox_order(
                        account_id=self.account_id,
                        figi=figi,
                        quantity=lots_to_trade,
                        direction=direction,
                        order_type=OrderType.ORDER_TYPE_MARKET,
                        order_id=datetime.now().strftime("%Y%m%d%H%M%S%f")
                    )
                else:
                    # REAL TRADING
                    resp = await client.orders.post_order(
                        account_id=self.account_id,
                        figi=figi,
                        quantity=lots_to_trade,
                        direction=direction,
                        order_type=OrderType.ORDER_TYPE_MARKET,
                        order_id=datetime.now().strftime("%Y%m%d%H%M%S%f")
                    )
                
                status = "EXECUTED" if resp.execution_report_status == 1 else "PENDING"
                
                return {
                    'status': 'EXECUTED',
                    'price': float(quotation_to_decimal(resp.initial_order_price_pt) or 0) / lots_to_trade, # Примерная цена
                    'lots': lots_to_trade,
                    'message': f"Ордер {action} принят биржей"
                }
                
        except Exception as e:
            logger.error(f"❌ Ошибка ордера Тинькофф: {e}")
            return {'status': 'ERROR', 'message': str(e)}

    def get_accounts(self):
        return self.account_id
