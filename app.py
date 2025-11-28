from flask import Flask, jsonify
import datetime
import time
import threading
import schedule
import logging

# Настройка логирования
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Глобальные переменные для отслеживания состояния
request_count = 0
last_trading_time = "Not started yet"
bot_status = "ACTIVE"
session_count = 0

def trading_session():
    """Имитация торговой сессии"""
    global last_trading_time, session_count
    
    session_count += 1
    current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    last_trading_time = current_time
    
    logger.info(f"🚀 Торговая сессия #{session_count} запущена в {current_time}")
    
    # Имитация анализа рынка
    logger.info("📊 Анализируем рынок...")
    time.sleep(1)
    
    # Имитация проверки условий
    logger.info("🔍 Проверяем торговые условия...")
    time.sleep(1)
    
    # Имитация принятия решения
    logger.info("🤖 Принимаем торговое решение...")
    
    logger.info(f"✅ Торговая сессия #{session_count} завершена")

def run_trading_session():
    """Запуск торговой сессии в отдельном потоке"""
    try:
        trading_session()
    except Exception as e:
        logger.error(f"❌ Ошибка в торговой сессии: {e}")

def schedule_tasks():
    """Настройка расписания задач"""
    # Запускать торговую сессию каждые 30 минут
    schedule.every(30).minutes.do(run_trading_session)
    
    # Дополнительные проверки каждые 10 минут
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
            <h1>🤖 Trading Bot</h1>
            <div style="background: #f0f0f0; padding: 20px; border-radius: 10px;">
                <p><strong>🟢 Status:</strong> {bot_status}</p>
                <p><strong>⏰ Uptime:</strong> {str(uptime).split('.')[0]}</p>
                <p><strong>📊 Requests:</strong> {request_count}</p>
                <p><strong>🕒 Last Trading:</strong> {last_trading_time}</p>
                <p><strong>🔢 Sessions:</strong> {session_count}</p>
                <p><strong>🐍 Python:</strong> Flask + Schedule</p>
            </div>
            <p>
                <a href="/status" style="margin-right: 15px;">JSON Status</a>
                <a href="/health" style="margin-right: 15px;">Health Check</a>
                <a href="/force">Force Trade</a>
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
        "last_trading_time": last_trading_time,
        "timestamp": datetime.datetime.now().isoformat(),
        "service": "trading-bot",
        "version": "1.1"
    })

@app.route('/health')
def health():
    return jsonify({"status": "healthy", "timestamp": datetime.datetime.now().isoformat()})

@app.route('/force')
def force_trade():
    """Принудительный запуск торговой сессии"""
    thread = threading.Thread(target=run_trading_session)
    thread.daemon = True
    thread.start()
    
    return jsonify({
        "message": "Торговая сессия запущена принудительно",
        "timestamp": datetime.datetime.now().isoformat()
    })

@app.route('/logs')
def show_logs():
    """Показать последние события"""
    return f"""
    <html>
        <body>
            <h1>📋 System Logs</h1>
            <p><strong>Last Trading:</strong> {last_trading_time}</p>
            <p><strong>Total Sessions:</strong> {session_count}</p>
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
    logger.info("📅 Scheduler activated - auto-trading every 30 minutes")
    logger.info("🌐 Web server starting on port 10000")
    
    app.run(host='0.0.0.0', port=10000, debug=False)
