import os
import time
import schedule
import requests
from flask import Flask, jsonify
import threading
from datetime import datetime

app = Flask(__name__)

# Флаг для отслеживания выполнения торговой сессии
is_trading_session_running = False
last_trade_result = "Bot started in SIMULATION mode - Tinkoff API not configured"

def trading_job():
    """Основная торговая функция в режиме симуляции"""
    global last_trade_result
    
    print(f"[{datetime.now()}] 🚀 Запуск торговой сессии (СИМУЛЯЦИЯ)...")
    
    try:
        # Имитация получения цен
        simulated_prices = {
            'SBER': 280.50,
            'GAZP': 165.30,
            'YNDX': 2850.75
        }
        
        # Имитация анализа
        for ticker, price in simulated_prices.items():
            print(f"Анализируем {ticker}: {price} руб.")
            
            # Простая логика симуляции
            if price < 250:
                action = "BUY"
                reason = "Цена ниже 250"
            elif price > 350:
                action = "SELL" 
                reason = "Цена выше 350"
            else:
                action = "HOLD"
                reason = "Цена в нормальном диапазоне"
            
            print(f"Сигнал для {ticker}: {action} - {reason}")
        
        last_trade_result = f"SIMULATION: Analysis completed at {datetime.now()}. Prices: SBER={simulated_prices['SBER']}, GAZP={simulated_prices['GAZP']}"
        
    except Exception as e:
        last_trade_result = f"ERROR in trading session: {str(e)}"
        print(f"❌ {last_trade_result}")
    
    print(f"[{datetime.now()}] ✅ Торговая сессия завершена")

def run_trading_session():
    """Запуск торговой сессии в отдельном потоке"""
    global is_trading_session_running
    is_trading_session_running = True
    try:
        trading_job()
    except Exception as e:
        print(f"Ошибка в торговой сессии: {e}")
    finally:
        is_trading_session_running = False

@app.route('/')
def health_check():
    """Главная страница - проверка статуса и запуск торговой сессии"""
    global is_trading_session_running, last_trade_result
    
    status = "RUNNING" if is_trading_session_running else "IDLE"
    
    # Если сессия не выполняется - запускаем
    if not is_trading_session_running:
        thread = threading.Thread(target=run_trading_session)
        thread.daemon = True
        thread.start()
        return f"""
        <html>
            <body>
                <h1>🤖 Trading Bot Active</h1>
                <p><strong>Status:</strong> Trading session STARTED</p>
                <p><strong>Time:</strong> {datetime.now()}</p>
                <p><strong>Mode:</strong> SIMULATION</p>
                <p><strong>Last Result:</strong> {last_trade_result}</p>
                <p><a href="/status">Check Status</a> | <a href="/force">Force Start</a></p>
            </body>
        </html>
        """
    
    return f"""
    <html>
        <body>
            <h1>🤖 Trading Bot Active</h1>
            <p><strong>Status:</strong> {status}</p>
            <p><strong>Time:</strong> {datetime.now()}</p>
            <p><strong>Mode:</strong> SIMULATION</p>
            <p><strong>Last Result:</strong> {last_trade_result}</p>
            <p><a href="/status">Check Status</a> | <a href="/force">Force Start</a></p>
        </body>
    </html>
    """

@app.route('/status')
def status():
    """Статус без запуска торговли"""
    global is_trading_session_running, last_trade_result
    status = "RUNNING" if is_trading_session_running else "IDLE"
    
    return jsonify({
        "status": status,
        "mode": "simulation",
        "last_trade_result": last_trade_result,
        "last_check": datetime.now().isoformat(),
        "bot": "active"
    })

@app.route('/force')
def force_start():
    """Принудительный запуск торговой сессии"""
    global is_trading_session_running
    if not is_trading_session_running:
        thread = threading.Thread(target=run_trading_session)
        thread.daemon = True
        thread.start()
        return "Trading session FORCE STARTED (SIMULATION)"
    return "Trading session is already RUNNING"

# Планировщик для регулярного выполнения
def scheduled_job():
    if not is_trading_session_running:
        run_trading_session()

# Настройка расписания
schedule.every(30).minutes.do(scheduled_job)  # Каждые 30 минут

def run_scheduler():
    """Запуск планировщика в фоновом режиме"""
    while True:
        schedule.run_pending()
        time.sleep(1)

if __name__ == '__main__':
    # Запускаем планировщик в отдельном потоке
    scheduler_thread = threading.Thread(target=run_scheduler)
    scheduler_thread.daemon = True
    scheduler_thread.start()
    
    print("🤖 Trading Bot Started! (SIMULATION MODE)")
    print("📊 Available routes:")
    print("   / - Health check and auto-start")
    print("   /status - JSON status") 
    print("   /force - Force start trading session")
    
    # Запускаем Flask приложение
    app.run(host='0.0.0.0', port=10000, debug=False)
