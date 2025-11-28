# app.py
from flask import Flask, jsonify
import datetime
import time
import threading
import schedule
import logging
import os
from tinkoff.invest import Client
from strategies import MomentTradingStrategy, ArbitrageStrategy, NewsTradingStrategy

# Настройка логирования
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Глобальные переменные
request_count = 0
last_trading_time = "Not started yet"
bot_status = "MOMENT TRADING BOT"
session_count = 0
trade_history = []
portfolio_value = 0

# Инструменты для торговли
INSTRUMENTS = {
    "SBER": "BBG004730N88",
    "GAZP": "BBG004730RP0", 
    "VTBR": "BBG004730ZJ9",
    "LKOH": "BBG004731032"
}

def trading_session():
    """Главная торговая сессия"""
    global last_trading_time, session_count, trade_history, portfolio_value
    
    session_count += 1
    current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    last_trading_time = current_time
    
    logger.info(f"🚀 МОМЕНТНАЯ СЕССИЯ #{session_count}")
    
    token = os.getenv('TINKOFF_API_TOKEN')
    if not token:
        logger.error("❌ TINKOFF_API_TOKEN не найден")
        return
    
    try:
        with Client(token) as client:
            # Получаем счет
            accounts = client.users.get_accounts()
            if not accounts.accounts:
                return
            account_id = accounts.accounts[0].id
            
            # Запускаем ВСЕ стратегии
            strategies = [
                MomentTradingStrategy(client, account_id),
                ArbitrageStrategy(client, account_id),
                NewsTradingStrategy(client, account_id)
            ]
            
            all_signals = []
            for strategy in strategies:
                signals = strategy.analyze(INSTRUMENTS)
                all_signals.extend(signals)
                logger.info(f"📊 {strategy.name}: {len(signals)} сигналов")
            
            # Исполняем лучшие сигналы
            executed_trades = []
            for signal in all_signals:
                if signal['confidence'] > 0.7:  # Только уверенные сигналы
                    try:
                        figi = INSTRUMENTS[signal['ticker']]
                        response = client.orders.post_order(
                            figi=figi,
                            quantity=signal['size'],
                            direction=OrderDirection.ORDER_DIRECTION_BUY if signal['action'] == 'BUY' else OrderDirection.ORDER_DIRECTION_SELL,
                            account_id=account_id,
                            order_type=OrderType.ORDER_TYPE_MARKET
                        )
                        
                        trade_result = {
                            'timestamp': current_time,
                            'strategy': signal['strategy'],
                            'action': signal['action'],
                            'ticker': signal['ticker'],
                            'price': signal['price'],
                            'size': signal['size'],
                            'reason': signal['reason'],
                            'order_id': response.order_id
                        }
                        executed_trades.append(trade_result)
                        logger.info(f"✅ {signal['strategy']}: {signal['action']} {signal['ticker']}")
                        
                    except Exception as e:
                        logger.error(f"❌ Ошибка исполнения: {e}")
            
            trade_history.extend(executed_trades)
            
            # Обновляем портфель
            portfolio = client.operations.get_portfolio(account_id=account_id)
            portfolio_value = portfolio.total_amount_portfolio.units + portfolio.total_amount_portfolio.nano/1e9
            
            logger.info(f"💰 СЕССИЯ #{session_count} ЗАВЕРШЕНА: {len(executed_trades)} сделок")
            
    except Exception as e:
        logger.error(f"❌ Ошибка сессии: {e}")

# ... остальной код Flask (маршруты) без изменений ...
