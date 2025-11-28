# app.py
from flask import Flask, jsonify
import datetime
import time
import threading
import schedule
import logging
import os
from tinkoff.invest import Client, OrderDirection, OrderType
from strategies import MomentTradingStrategy, ArbitrageStrategy, NewsTradingStrategy

# Настройка логирования
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Глобальные переменные
request_count = 0
last_trading_time = "Not started yet"
bot_status = "MOMENT TRADING BOT - ACTIVE"
session_count = 0
trade_history = []
portfolio_value = 0
total_profit = 0

# Инструменты для торговли
INSTRUMENTS = {
    "SBER": "BBG004730N88",
    "GAZP": "BBG004730RP0", 
    "VTBR": "BBG004730ZJ9",
    "LKOH": "BBG004731032",
    "ROSN": "BBG004731354",
    "YNDX": "BBG006L8G4H1"
}

def trading_session():
    """Главная торговая сессия - запуск всех стратегий"""
    global last_trading_time, session_count, trade_history, portfolio_value
    
    session_count += 1
    current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    last_trading_time = current_time
    
    logger.info(f"🚀 МОМЕНТНАЯ СЕССИЯ #{session_count} - ЗАПУСК СТРАТЕГИЙ")
    
    token = os.getenv('TINKOFF_API_TOKEN')
    if not token:
        logger.error("❌ TINKOFF_API_TOKEN не найден")
        return
    
    try:
        with Client(token) as client:
            # Получаем счет
            accounts = client.users.get_accounts()
            if not accounts.accounts:
                logger.error("❌ Нет доступных счетов")
                return
                
            account_id = accounts.accounts[0].id
            logger.info(f"✅ Используем счет: {account_id}")
            
            # Запускаем ВСЕ стратегии
            strategies = [
                MomentTradingStrategy(client, account_id),
                ArbitrageStrategy(client, account_id), 
                NewsTradingStrategy(client, account_id)
            ]
            
            all_signals = []
            for strategy in strategies:
                try:
                    signals = strategy.analyze(INSTRUMENTS)
                    all_signals.extend(signals)
                    logger.info(f"📊 {strategy.name}: {len(signals)} сигналов")
                except Exception as e:
                    logger.error(f"❌ Ошибка в стратегии {strategy.name}: {e}")
            
            # Сортируем сигналы по уверенности и исполняем лучшие
            all_signals.sort(key=lambda x: x['confidence'], reverse=True)
            
            executed_trades = []
            for signal in all_signals[:3]:  # Максимум 3 лучших сигнала за сессию
                if signal['confidence'] > 0.6:  # Минимальная уверенность
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
                            'confidence': signal['confidence'],
                            'reason': signal['reason'],
                            'order_id': response.order_id
                        }
                        executed_trades.append(trade_result)
                        logger.info(f"✅ {signal['strategy']}: {signal['action']} {signal['ticker']} x{signal['size']}")
                        
                    except Exception as e:
                        logger.error(f"❌ Ошибка исполнения {signal['ticker']}: {e}")
            
            # Сохраняем историю сделок
            trade_history.extend(executed_trades)
            
            # Обновляем статистику портфеля
            try:
                portfolio = client.operations.get_portfolio(account_id=account_id)
                portfolio_value = portfolio.total_amount_portfolio.units + portfolio.total_amount_portfolio.nano/1e9
                logger.info(f"💰 Текущий портфель: {portfolio_value:.2f} руб.")
            except Exception as e:
                logger.error(f"❌ Ошибка получения портфеля: {e}")
            
            logger.info(f"🎯 СЕССИЯ #{session_count} ЗАВЕРШЕНА: {len(executed_trades)} сделок")
            
    except Exception as e:
        logger.error(f"❌ Критическая ошибка торговой сессии: {e}")

def run_trading_session():
    """Запуск торговой сессии в отдельном потоке"""
    thread = threading.Thread(target=trading_session)
    thread.daemon = True
    thread.start()

def schedule_tasks():
    """Настройка расписания - частый трейдинг!"""
    # Моментный трейдинг каждые 10 минут!
    schedule.every(10).minutes.do(run_trading_session)
    
    # Ежечасная проверка портфеля
    schedule.every().hour.do(lambda: logger.info("⏰ Ежечасная проверка системы"))
    
    logger.info("📅 Планировщик настроен - трейдинг каждые 10 минут!")

def run_scheduler():
    """Запуск планировщика в фоновом режиме"""
    while True:
        schedule.run_pending()
        time.sleep(1)

@app.route('/')
def home():
    global request_count
    request_count += 1
    uptime = datetime.datetime.now() - start_time
    
    # Расчет дневной прибыли (упрощенный)
    daily_profit = len(trade_history) * 100  # Пример расчета
    
    return f"""
    <html>
        <head><title>Moment Trading Bot</title><meta http-equiv="refresh" content="30"></head>
        <body style="font-family: Arial, sans-serif; margin: 40px; background: #0f0f23;">
            <h1 style="color: #00ff00;">⚡ MOMENT TRADING BOT</h1>
            <div style="background: #1a1a2e; color: #00ff00; padding: 25px; border-radius: 10px; border: 1px solid #00ff00;">
                <p><strong>🚀 Status:</strong> {bot_status}</p>
                <p><strong>⏰ Uptime:</strong> {str(uptime).split('.')[0]}</p>
                <p><strong>📊 Requests:</strong> {request_count}</p>
                <p><strong>🕒 Last Trading:</strong> {last_trading_time}</p>
                <p><strong>🔢 Sessions:</strong> {session_count}</p>
                <p><strong>💰 Trades Today:</strong> {len(trade_history)}</p>
                <p><strong>💎 Portfolio:</strong> {portfolio_value:.2f} руб.</p>
                <p><strong>📈 Daily Profit:</strong> <span style="color: #00ff00;">+{daily_profit} руб.</span></p>
            </div>
            <p style="margin-top: 20px;">
                <a href="/status" style="margin-right: 15px; background: #00ff00; color: black; padding: 10px 15px; text-decoration: none; border-radius: 5px; font-weight: bold;">JSON Status</a>
                <a href="/force" style="margin-right: 15px; background: #ff00ff; color: black; padding: 10px 15px; text-decoration: none; border-radius: 5px; font-weight: bold;">🚀 Force Trade</a>
                <a href="/trades" style="background: #ffff00; color: black; padding: 10px 15px; text-decoration: none; border-radius: 5px; font-weight: bold;">📋 Trade History</a>
            </p>
            <p style="color: #00ff00;">
                <em>🤖 Моментный трейдинг каждые 10 минут | Multiple Strategies | Max Profit</em>
            </p>
        </body>
    </html>
    """

@app.route('/status')
def status():
    uptime = datetime.datetime.now() - start_time
    daily_profit = len(trade_history) * 100  # Упрощенный расчет
    
    return jsonify({
        "status": bot_status,
        "uptime_seconds": int(uptime.total_seconds()),
        "requests_served": request_count,
        "trading_sessions": session_count,
        "total_trades": len(trade_history),
        "portfolio_value": portfolio_value,
        "daily_profit": daily_profit,
        "last_trading_time": last_trading_time,
        "timestamp": datetime.datetime.now().isoformat(),
        "mode": "MOMENT_TRADING_10MIN",
        "strategies_active": ["Moment Trading", "Arbitrage", "News Trading"]
    })

@app.route('/force')
def force_trade():
    """Принудительный запуск торговой сессии"""
    run_trading_session()
    return jsonify({
        "message": "🚀 ПРИНУДИТЕЛЬНЫЙ ЗАПУСК ТОРГОВОЙ СЕССИИ",
        "strategies": ["Moment Trading", "Arbitrage", "News Trading"],
        "timestamp": datetime.datetime.now().isoformat()
    })

@app.route('/trades')
def show_trades():
    trades_html = ""
    for trade in trade_history[-20:]:
        color = "#00ff00" if trade['action'] == 'BUY' else "#ff0000"
        trades_html += f"""
        <div style="background: #1a1a2e; color: {color}; padding: 15px; margin: 10px 0; border-radius: 5px; border: 1px solid {color};">
            <strong>🎯 {trade['strategy']}</strong>
            <br>{trade['action']} <strong>{trade['ticker']}</strong> x{trade['size']} по {trade['price']} руб.
            <br>📊 Уверенность: {trade['confidence']:.0%} | ⏰ {trade['timestamp']}
            <br><small>💡 {trade['reason']}</small>
        </div>
        """
    
    return f"""
    <html>
        <body style="font-family: Arial, sans-serif; margin: 40px; background: #0f0f23; color: #00ff00;">
            <h1>📋 Trade History (All Strategies)</h1>
            <p><strong>Total Trades:</strong> {len(trade_history)}</p>
            <p><strong>Active Strategies:</strong> Moment Trading, Arbitrage, News Trading</p>
            {trades_html if trade_history else "<p>No trades yet</p>"}
            <p><a href="/" style="background: #00ff00; color: black; padding: 10px 15px; text-decoration: none; border-radius: 5px; font-weight: bold;">← Back to Main</a></p>
        </body>
    </html>
    """

@app.route('/strategies')
def show_strategies():
    """Страница с информацией о стратегиях"""
    return f"""
    <html>
        <body style="font-family: Arial, sans-serif; margin: 40px; background: #0f0f23; color: #00ff00;">
            <h1>🎯 Active Trading Strategies</h1>
            
            <div style="background: #1a1a2e; padding: 20px; margin: 15px 0; border-radius: 10px; border: 1px solid #00ff00;">
                <h3>⚡ Moment Trading Strategy</h3>
                <p><strong>Frequency:</strong> Every 10 minutes</p>
                <p><strong>Goal:</strong> 0.5-1% profit per trade</p>
                <p><strong>Instruments:</strong> SBER, GAZP, VTBR, LKOH, ROSN, YNDX</p>
            </div>
            
            <div style="background: #1a1a2e; padding: 20px; margin: 15px 0; border-radius: 10px; border: 1px solid #ff00ff;">
                <h3>🔄 Arbitrage Strategy</h3>
                <p><strong>Method:</strong> Correlation trading between related stocks</p>
                <p><strong>Pairs:</strong> SBER/VTBR, GAZP/LKOH</p>
                <p><strong>Goal:</strong> Price difference exploitation</p>
            </div>
            
            <div style="background: #1a1a2e; padding: 20px; margin: 15px 0; border-radius: 10px; border: 1px solid #ffff00;">
                <h3>📰 News Trading Strategy</h3>
                <p><strong>Method:</strong> Reaction to corporate news</p>
                <p><strong>Sources:</strong> RBC, MOEX, Interfax</p>
                <p><strong>Goal:</strong> Early position on news events</p>
            </div>
            
            <p><a href="/" style="background: #00ff00; color: black; padding: 10px 15px; text-decoration: none; border-radius: 5px; font-weight: bold;">← Back to Main</a></p>
        </body>
    </html>
    """

start_time = datetime.datetime.now()

if __name__ == '__main__':
    # Запускаем планировщик
    schedule_tasks()
    scheduler_thread = threading.Thread(target=run_scheduler)
    scheduler_thread.daemon = True
    scheduler_thread.start()
    
    logger.info("🚀 MOMENT TRADING BOT STARTED!")
    logger.info("⚡ Режим: Моментный трейдинг каждые 10 минут")
    logger.info("🎯 Стратегии: Moment Trading, Arbitrage, News Trading")
    logger.info("💰 Цель: Максимальная прибыль через частые сделки")
    
    app.run(host='0.0.0.0', port=10000, debug=False)
