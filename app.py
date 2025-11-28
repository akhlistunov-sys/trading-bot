from flask import Flask, jsonify
import datetime
import time
import threading
import schedule
import logging
import os
from tinkoff.invest import Client, OrderDirection, OrderType

# Настройка логирования
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Глобальные переменные
request_count = 0
last_trading_time = "Not started yet"
bot_status = "ACTIVE"
session_count = 0
trade_history = []

# Инструменты для торговли
INSTRUMENTS = {
    "SBER": "BBG004730N88",
    "GAZP": "BBG004730RP0", 
    "YNDX": "BBG006L8G4H1"
}

def trading_session():
    """Упрощенная торговая сессия для теста"""
    global last_trading_time, session_count, trade_history
    
    session_count += 1
    current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    last_trading_time = current_time
    
    logger.info(f"🚀 Торговая сессия #{session_count} запущена")
    
    token = os.getenv('TINKOFF_API_TOKEN')
    if not token:
        logger.error("❌ TINKOFF_API_TOKEN не найден")
        return
    
    try:
        # Простая проверка подключения
        with Client(token) as client:
            logger.info("✅ Подключение к API успешно")
            
            # Просто получаем цены (это должно работать)
            prices = {}
            for name, figi in INSTRUMENTS.items():
                try:
                    last_price = client.market_data.get_last_prices(figi=[figi])
                    if last_price.last_prices:
                        price_obj = last_price.last_prices[0].price
                        price = price_obj.units + price_obj.nano / 1e9
                        prices[name] = price
                        logger.info(f"✅ {name}: {price} руб.")
                    else:
                        logger.warning(f"⚠️ Нет данных по {name}")
                except Exception as e:
                    logger.error(f"❌ Ошибка получения цены {name}: {e}")
            
            # Симулируем торговлю если получили цены
            if prices:
                trade_history.append({
                    'action': 'BUY',
                    'instrument': 'SBER',
                    'price': prices.get('SBER', 280),
                    'timestamp': current_time,
                    'mode': 'REAL_API'
                })
                logger.info("✅ Торговая сессия завершена с реальными данными")
            
    except Exception as e:
        logger.error(f"❌ Критическая ошибка: {e}")

def run_trading_session():
    """Запуск торговой сессии в отдельном потоке"""
    thread = threading.Thread(target=trading_session)
    thread.daemon = True
    thread.start()

def schedule_tasks():
    """Настройка расписания"""
    schedule.every(30).minutes.do(run_trading_session)
    logger.info("📅 Планировщик настроен")

def run_scheduler():
    """Запуск планировщика"""
    while True:
        schedule.run_pending()
        time.sleep(1)

@app.route('/')
def home():
    global request_count
    request_count += 1
    uptime = datetime.datetime.now() - start_time
    
    return f"""
    <html>
        <head><title>Trading Bot</title><meta http-equiv="refresh" content="30"></head>
        <body style="font-family: Arial, sans-serif; margin: 40px;">
            <h1>🤖 Trading Bot</h1>
            <div style="background: #f0f0f0; padding: 20px; border-radius: 10px;">
                <p><strong>🟢 Status:</strong> {bot_status}</p>
                <p><strong>⏰ Uptime:</strong> {str(uptime).split('.')[0]}</p>
                <p><strong>📊 Requests:</strong> {request_count}</p>
                <p><strong>🕒 Last Trading:</strong> {last_trading_time}</p>
                <p><strong>🔢 Sessions:</strong> {session_count}</p>
                <p><strong>💰 Trades:</strong> {len(trade_history)}</p>
                <p><strong>🎯 Mode:</strong> Tinkoff API Test</p>
            </div>
            <p>
                <a href="/status">JSON Status</a> |
                <a href="/force">Force Trade</a> |
                <a href="/trades">Trade History</a> |
                <a href="/check_token">Check Token</a>
            </p>
        </body>
    </html>
    """

@app.route('/status')
def status():
    uptime = datetime.datetime.now() - start_time
    return jsonify({
        "status": bot_status,
        "uptime_seconds": int(uptime.total_seconds()),
        "requests_served": request_count,
        "trading_sessions": session_count,
        "total_trades": len(trade_history),
        "last_trading_time": last_trading_time,
        "timestamp": datetime.datetime.now().isoformat()
    })

@app.route('/force')
def force_trade():
    run_trading_session()
    return jsonify({"message": "Торговая сессия запущена", "timestamp": datetime.datetime.now().isoformat()})

@app.route('/trades')
def show_trades():
    trades_html = ""
    for trade in trade_history[-10:]:
        trades_html += f"<p>{trade['timestamp']} - {trade['action']} {trade['instrument']} по {trade['price']} руб. ({trade['mode']})</p>"
    
    return f"""
    <html>
        <body>
            <h1>📋 Trade History</h1>
            <p><strong>Total Trades:</strong> {len(trade_history)}</p>
            {trades_html if trade_history else "<p>No trades yet</p>"}
            <p><a href="/">Back to Main</a></p>
        </body>
    </html>
    """

@app.route('/check_token')
def check_token():
    """Проверка токена"""
    token = os.getenv('TINKOFF_API_TOKEN')
    
    if not token:
        return "❌ Токен не найден в переменных окружения"
    
    token_preview = token[:10] + "..." if len(token) > 10 else token
    token_starts_with_t = token.startswith('t.')
    
    return f"""
    <html>
        <body>
            <h1>🔐 Проверка токена</h1>
            <p><strong>Токен существует:</strong> {'✅' if token else '❌'}</p>
            <p><strong>Начинается с 't.':</strong> {'✅' if token_starts_with_t else '❌'}</p>
            <p><strong>Префикс токена:</strong> {token_preview}</p>
            <p><strong>Длина токена:</strong> {len(token)} символов</p>
            <p><a href="/">На главную</a></p>
        </body>
    </html>
    """

start_time = datetime.datetime.now()

if __name__ == '__main__':
    schedule_tasks()
    scheduler_thread = threading.Thread(target=run_scheduler)
    scheduler_thread.daemon = True
    scheduler_thread.start()
    
    logger.info("🚀 Trading Bot started!")
    app.run(host='0.0.0.0', port=10000, debug=False)
