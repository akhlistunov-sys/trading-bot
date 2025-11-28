import os
import time
import schedule
from flask import Flask
import threading
from datetime import datetime

app = Flask(__name__)

# Флаг для отслеживания выполнения торговой сессии
is_trading_session_running = False

def trading_job():
    """Ваша основная торговая функция"""
    print(f"[{datetime.now()}] Запуск торговой сессии...")
    
    # ЗДЕСЬ БУДЕТ ВАША ОСНОВНАЯ ЛОГИКА
    # 1. Получение данных от Tinkoff API
    # 2. Анализ через DeepSeek
    # 3. Размещение ордеров
    
    print(f"[{datetime.now()}] Торговая сессия завершена")

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
    """Эндпоинт для проверки работоспособности и запуска торговой сессии"""
    global is_trading_session_running
    
    status = "RUNNING" if is_trading_session_running else "IDLE"
    
    # Если сессия не выполняется - запускаем
    if not is_trading_session_running:
        thread = threading.Thread(target=run_trading_session)
        thread.daemon = True
        thread.start()
        return f"Trading Bot Active | Status: Trading session STARTED | Time: {datetime.now()}"
    
    return f"Trading Bot Active | Status: {status} | Time: {datetime.now()}"

@app.route('/status')
def status():
    """Простой статус без запуска торговли"""
    global is_trading_session_running
    status = "RUNNING" if is_trading_session_running else "IDLE"
    return f"Status: {status} | Last check: {datetime.now()}"

# Планировщик для регулярного выполнения
def scheduled_job():
    if not is_trading_session_running:
        run_trading_session()

# Настройка расписания (каждые 30 минут)
schedule.every(30).minutes.do(scheduled_job)

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
    
    # Запускаем Flask приложение
    app.run(host='0.0.0.0', port=10000, debug=False)
