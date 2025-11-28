import os
import time
import schedule
import requests
from flask import Flask, jsonify
import threading
from datetime import datetime
from tinkoff.invest import Client, OrderDirection, OrderType

app = Flask(__name__)

# Флаг для отслеживания выполнения торговой сессии
is_trading_session_running = False
last_trade_result = "No trades yet"

# Конфигурация
FIGI_SBER = "BBG004730N88"
FIGI_GAZP = "BBG004730RP0"
FIGI_YNDX = "BBG006L8G4H1"

def get_stock_news(ticker):
    """Получение новостей по тикеру (заглушка)"""
    news_map = {
        "SBER": "Сбербанк объявил о рекордной прибыли по итогам квартала",
        "GAZP": "Газпром увеличил дивиденды по итогам собрания акционеров",
        "YNDX": "Яндекс запускает новый сервис доставки"
    }
    return news_map.get(ticker, "Новостей нет")

def analyze_with_ai(news_text, price_data):
    """Анализ ситуации с помощью AI (заглушка до получения DeepSeek API)"""
    # Здесь будет интеграция с DeepSeek API
    analysis_result = {
        "signal": "HOLD",
        "confidence": 0.7,
        "reason": "Стабильная ситуация",
        "recommended_action": "no_action"
    }
    
    # Простая логика на основе цены
    current_price = price_data.get('current_price', 0)
    if current_price < 250:
        analysis_result = {
            "signal": "BUY",
            "confidence": 0.8,
            "reason": "Цена ниже 250, возможен рост",
            "recommended_action": "buy"
        }
    elif current_price > 350:
        analysis_result = {
            "signal": "SELL", 
            "confidence": 0.6,
            "reason": "Цена выше 350, возможна коррекция",
            "recommended_action": "sell"
        }
    
    return analysis_result

def trading_job():
    """Основная торговая функция"""
    global last_trade_result
    
    print(f"[{datetime.now()}] 🚀 Запуск торговой сессии...")
    
    try:
        # Получаем токен из переменных окружения Render
        token = os.getenv('TINKOFF_API_TOKEN')
        if not token:
            last_trade_result = "ERROR: TINKOFF_API_TOKEN not set"
            print(last_trade_result)
            return
        
        with Client(token) as client:
            # 1. Получаем текущие цены
            prices = client.market_data.get_last_prices(figi=[FIGI_SBER, FIGI_GAZP, FIGI_YNDX])
            
            price_data = {}
            for price in prices.last_prices:
                if price.figi == FIGI_SBER:
                    price_data['SBER'] = {
                        'current_price': price.price.units + price.price.nano / 1e9,
                        'figi': FIGI_SBER
                    }
                elif price.figi == FIGI_GAZP:
                    price_data['GAZP'] = {
                        'current_price': price.price.units + price.price.nano / 1e9,
                        'figi': FIGI_GAZP
                    }
                elif price.figi == FIGI_YNDX:
                    price_data['YNDX'] = {
                        'current_price': price.price.units + price.price.nano / 1e9,
                        'figi': FIGI_YNDX
                    }
            
            # 2. Анализируем каждый инструмент
            for ticker, data in price_data.items():
                print(f"Анализируем {ticker}: {data['current_price']} руб.")
                
                # Получаем новости
                news = get_stock_news(ticker)
                
                # Анализируем с AI
                analysis = analyze_with_ai(news, data)
                
                print(f"AI Анализ {ticker}: {analysis}")
                
                # 3. Торговая логика (ЗАМЕНИТЕ НА СВОЮ)
                if analysis['recommended_action'] == 'buy' and analysis['confidence'] > 0.7:
                    # Пример размещения ордера на покупку
                    try:
                        # РАСКОММЕНТИРУЙТЕ ДЛЯ РЕАЛЬНОЙ ТОРГОВЛИ:
                        # response = client.orders.post_order(
                        #     figi=data['figi'],
                        #     quantity=1,
                        #     direction=OrderDirection.ORDER_DIRECTION_BUY,
                        #     order_type=OrderType.ORDER_TYPE_MARKET,
                        #     account_id=os.getenv('TINKOFF_ACCOUNT_ID')
                        # )
                        # last_trade_result = f"BUY {ticker} at {data['current_price']}"
                        last_trade_result = f"SIMULATION: BUY {ticker} at {data['current_price']} (режим тестирования)"
                        print(f"✅ {last_trade_result}")
                        
                    except Exception as e:
                        last_trade_result = f"ERROR in BUY {ticker}: {str(e)}"
                        print(f"❌ {last_trade_result}")
                
                elif analysis['recommended_action'] == 'sell' and analysis['confidence'] > 0.7:
                    # Пример размещения ордера на продажу
                    try:
                        # РАСКОММЕНТИРУЙТЕ ДЛЯ РЕАЛЬНОЙ ТОРГОВЛИ:
                        # response = client.orders.post_order(
                        #     figi=data['figi'],
                        #     quantity=1,
                        #     direction=OrderDirection.ORDER_DIRECTION_SELL,
                        #     order_type=OrderType.ORDER_TYPE_MARKET,
                        #     account_id=os.getenv('TINKOFF_ACCOUNT_ID')
                        # )
                        # last_trade_result = f"SELL {ticker} at {data['current_price']}"
                        last_trade_result = f"SIMULATION: SELL {ticker} at {data['current_price']} (режим тестирования)"
                        print(f"✅ {last_trade_result}")
                        
                    except Exception as e:
                        last_trade_result = f"ERROR in SELL {ticker}: {str(e)}"
                        print(f"❌ {last_trade_result}")
            
            # Если не было сделок
            if "SIMULATION" not in last_trade_result and "ERROR" not in last_trade_result:
                last_trade_result = f"Analysis completed. No trades executed. Prices: SBER={price_data.get('SBER', {}).get('current_price', 'N/A')}, GAZP={price_data.get('GAZP', {}).get('current_price', 'N/A')}"
                
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
        return "Trading session FORCE STARTED"
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
    
    print("🤖 Trading Bot Started!")
    print("📊 Available routes:")
    print("   / - Health check and auto-start")
    print("   /status - JSON status") 
    print("   /force - Force start trading session")
    
    # Запускаем Flask приложение
    app.run(host='0.0.0.0', port=10000, debug=False)
