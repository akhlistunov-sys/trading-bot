from flask import Flask, jsonify
import datetime
import time
import threading
import schedule
import logging
import os
try:
    from tinkoff.invest import Client, OrderDirection, OrderType
    from tinkoff.invest.sandbox.client import SandboxClient
except ImportError:
    # Fallback для совместимости
    print("⚠️ Tinkoff invest API not available, using simulation mode")
    # Заглушки для совместимости
    class OrderDirection:
        ORDER_DIRECTION_BUY = "buy"
        ORDER_DIRECTION_SELL = "sell"
    class OrderType:
        ORDER_TYPE_MARKET = "market"

# Настройка логирования
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Глобальные переменные для отслеживания состояния
request_count = 0
last_trading_time = "Not started yet"
bot_status = "ACTIVE"
session_count = 0
total_profit = 0
open_positions = {}
trade_history = []

# Конфигурация инструментов
INSTRUMENTS = {
    "SBER": "BBG004730N88",
    "GAZP": "BBG004730RP0", 
    "YNDX": "BBG006L8G4H1",
    "VTBR": "BBG004730ZJ9"
}

def get_sandbox_client():
    """Создание клиента для Sandbox режима"""
    token = os.getenv('TINKOFF_API_TOKEN')
    if not token:
        logger.error("❌ TINKOFF_API_TOKEN not found in environment variables")
        return None
    
    try:
        # Используем SandboxClient для тестового режима
        client = SandboxClient(token=token)
        logger.info("✅ Sandbox client created successfully")
        return client
    except Exception as e:
        logger.error(f"❌ Error creating Sandbox client: {e}")
        return None

def open_sandbox_account(client):
    """Открытие счета в песочнице"""
    try:
        accounts = client.users.get_accounts()
        if not accounts.accounts:
            # Создаем новый счет в песочнице
            account_id = client.sandbox.open_sandbox_account()
            logger.info(f"✅ Sandbox account created: {account_id}")
            return account_id
        else:
            account_id = accounts.accounts[0].id
            logger.info(f"✅ Using existing sandbox account: {account_id}")
            return account_id
    except Exception as e:
        logger.error(f"❌ Error opening sandbox account: {e}")
        return None

def get_portfolio(client, account_id):
    """Получение текущего портфеля"""
    try:
        portfolio = client.operations.get_portfolio(account_id=account_id)
        return portfolio
    except Exception as e:
        logger.error(f"❌ Error getting portfolio: {e}")
        return None

def get_current_prices(client):
    """Получение текущих цен инструментов"""
    prices = {}
    try:
        for name, figi in INSTRUMENTS.items():
            last_price = client.market_data.get_last_prices(figi=[figi])
            if last_price.last_prices:
                price_obj = last_price.last_prices[0].price
                price = price_obj.units + price_obj.nano / 1e9
                prices[name] = price
                logger.info(f"💰 {name}: {price} руб.")
    except Exception as e:
        logger.error(f"❌ Error getting prices: {e}")
    
    return prices

def place_order(client, account_id, figi, direction, quantity=1):
    """Размещение ордера в песочнице"""
    try:
        response = client.orders.post_order(
            figi=figi,
            quantity=quantity,
            direction=direction,
            account_id=account_id,
            order_type=OrderType.ORDER_TYPE_MARKET,
            price=None  # Рыночная цена
        )
        
        order_id = response.order_id
        logger.info(f"✅ Order placed: {direction} {quantity} lots, Order ID: {order_id}")
        return order_id
    except Exception as e:
        logger.error(f"❌ Error placing order: {e}")
        return None

def trading_strategy(prices, portfolio):
    """Простая торговая стратегия"""
    signals = []
    
    for name, figi in INSTRUMENTS.items():
        current_price = prices.get(name)
        if not current_price:
            continue
            
        # Простая стратегия: покупаем если цена ниже 300, продаем если выше 350
        if current_price < 280:
            signals.append({
                "action": "BUY",
                "instrument": name,
                "figi": figi,
                "price": current_price,
                "reason": f"Цена ниже 280 руб. (текущая: {current_price})"
            })
        elif current_price > 320:
            signals.append({
                "action": "SELL", 
                "instrument": name,
                "figi": figi,
                "price": current_price,
                "reason": f"Цена выше 320 руб. (текущая: {current_price})"
            })
    
    return signals

def trading_session():
    """Основная торговая сессия"""
    global last_trading_time, session_count, trade_history
    
    session_count += 1
    current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    last_trading_time = current_time
    
    logger.info(f"🚀 Торговая сессия #{session_count} запущена в {current_time}")
    
    client = get_sandbox_client()
    if not client:
        logger.error("❌ Cannot start trading session: no client")
        return
    
    try:
        # Открываем счет в песочнице
        account_id = open_sandbox_account(client)
        if not account_id:
            logger.error("❌ Cannot get sandbox account")
            return
        
        # Получаем текущие цены
        logger.info("📊 Получаем текущие цены...")
        prices = get_current_prices(client)
        
        # Получаем текущий портфель
        portfolio = get_portfolio(client, account_id)
        
        # Анализируем и получаем торговые сигналы
        logger.info("🤖 Анализируем рынок...")
        signals = trading_strategy(prices, portfolio)
        
        # Исполняем сигналы
        executed_trades = []
        for signal in signals:
            logger.info(f"📈 Сигнал: {signal['action']} {signal['instrument']} - {signal['reason']}")
            
            if signal['action'] == 'BUY':
                order_id = place_order(client, account_id, signal['figi'], OrderDirection.ORDER_DIRECTION_BUY, 1)
                if order_id:
                    executed_trades.append({
                        'action': 'BUY',
                        'instrument': signal['instrument'],
                        'price': signal['price'],
                        'order_id': order_id,
                        'timestamp': current_time
                    })
            elif signal['action'] == 'SELL':
                order_id = place_order(client, account_id, signal['figi'], OrderDirection.ORDER_DIRECTION_SELL, 1)
                if order_id:
                    executed_trades.append({
                        'action': 'SELL', 
                        'instrument': signal['instrument'],
                        'price': signal['price'],
                        'order_id': order_id,
                        'timestamp': current_time
                    })
        
        # Сохраняем историю trades
        trade_history.extend(executed_trades)
        
        if executed_trades:
            logger.info(f"✅ Исполнено ордеров: {len(executed_trades)}")
        else:
            logger.info("ℹ️ Нет подходящих сигналов для торговли")
            
    except Exception as e:
        logger.error(f"❌ Ошибка в торговой сессии: {e}")
    finally:
        logger.info(f"✅ Торговая сессия #{session_count} завершена")

def run_trading_session():
    """Запуск торговой сессии в отдельном потоке"""
    thread = threading.Thread(target=trading_session)
    thread.daemon = True
    thread.start()

def schedule_tasks():
    """Настройка расписания задач"""
    # Запускать торговую сессию каждые 30 минут
    schedule.every(30).minutes.do(run_trading_session)
    
    # Фоновая проверка каждые 10 минут
    schedule.every(10).minutes.do(lambda: logger.info("🔔 Фоновая проверка системы"))
    
    logger.info("📅 Планировщик задач настроен")

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
    
    return f"""
    <html>
        <head>
            <title>Trading Bot</title>
            <meta http-equiv="refresh" content="30">
        </head>
        <body style="font-family: Arial, sans-serif; margin: 40px;">
            <h1>🤖 Trading Bot (SANDBOX)</h1>
            <div style="background: #f0f0f0; padding: 20px; border-radius: 10px;">
                <p><strong>🟢 Status:</strong> {bot_status}</p>
                <p><strong>⏰ Uptime:</strong> {str(uptime).split('.')[0]}</p>
                <p><strong>📊 Requests:</strong> {request_count}</p>
                <p><strong>🕒 Last Trading:</strong> {last_trading_time}</p>
                <p><strong>🔢 Sessions:</strong> {session_count}</p>
                <p><strong>💰 Trades:</strong> {len(trade_history)}</p>
                <p><strong>🎯 Mode:</strong> Tinkoff Sandbox</p>
            </div>
            <p>
                <a href="/status" style="margin-right: 15px;">JSON Status</a>
                <a href="/health" style="margin-right: 15px;">Health Check</a>
                <a href="/force" style="margin-right: 15px;">Force Trade</a>
                <a href="/trades">Trade History</a>
            </p>
            <p><em>Auto-refresh every 30 seconds</em></p>
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
        "timestamp": datetime.datetime.now().isoformat(),
        "service": "trading-bot",
        "mode": "sandbox",
        "version": "2.0"
    })

@app.route('/health')
def health():
    return jsonify({"status": "healthy", "timestamp": datetime.datetime.now().isoformat()})

@app.route('/force')
def force_trade():
    """Принудительный запуск торговой сессии"""
    run_trading_session()
    
    return jsonify({
        "message": "Торговая сессия запущена принудительно",
        "timestamp": datetime.datetime.now().isoformat()
    })

@app.route('/trades')
def show_trades():
    """Показать историю trades"""
    trades_html = ""
    for trade in trade_history[-10:]:  # Последние 10 trades
        trades_html += f"<p>{trade['timestamp']} - {trade['action']} {trade['instrument']} по {trade['price']} руб.</p>"
    
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

# Глобальная переменная времени старта
start_time = datetime.datetime.now()

if __name__ == '__main__':
    # Настраиваем планировщик
    schedule_tasks()
    
    # Запускаем планировщик в фоновом потоке
    scheduler_thread = threading.Thread(target=run_scheduler)
    scheduler_thread.daemon = True
    scheduler_thread.start()
    
    logger.info("🚀 Trading Bot started successfully!")
    logger.info("🎯 Mode: Tinkoff Sandbox API")
    logger.info("📅 Scheduler activated - auto-trading every 30 minutes")
    logger.info("🌐 Web server starting on port 10000")
    
    app.run(host='0.0.0.0', port=10000, debug=False)
