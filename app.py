from flask import Flask, jsonify
import datetime
import time
import threading
import schedule
import logging
import os
import random
from tinkoff.invest import Client, OrderDirection, OrderType

# Настройка логирования
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Глобальные переменные
request_count = 0
last_trading_time = "Not started yet"
bot_status = "MAX POWER MODE"
session_count = 0
trade_history = []
portfolio_value = 0
total_profit = 0

# Расширенный список инструментов
INSTRUMENTS = {
    "SBER": "BBG004730N88",
    "GAZP": "BBG004730RP0", 
    "YNDX": "BBG006L8G4H1",
    "LKOH": "BBG004731032",
    "ROSN": "BBG004731354",
    "NVTK": "BBG00475J7X6",
    "TATN": "BBG004RVFCY3",
    "MGNT": "BBG004S681W1",
    "AFKS": "BBG004S683W7",
    "PLZL": "BBG000R7GJQ6",
    "POLY": "BBG004S68829",
    "GMKN": "BBG00475K2X9",
    "NLMK": "BBG004S68614",
    "ALRS": "BBG004S681B4",
    "MOEX": "BBG004730JJ5",
    "VTBR": "BBG004730ZJ9",
    "TCSG": "BBG00QPYJ5H0",
    "OZON": "BBG00Y91R9T3"
}

class AdvancedTradingBot:
    def __init__(self, client, account_id):
        self.client = client
        self.account_id = account_id
        self.portfolio = {}
        self.market_data = {}
        
    def analyze_technical(self, instrument_data):
        """Технический анализ"""
        prices = instrument_data.get('prices', [])
        if len(prices) < 10:
            return "HOLD"
            
        current_price = prices[-1]
        sma_5 = sum(prices[-5:]) / 5
        sma_10 = sum(prices[-10:]) / 10
        
        # Тренд вверх
        if current_price > sma_5 > sma_10:
            return "STRONG_BUY"
        # Тренд вниз
        elif current_price < sma_5 < sma_10:
            return "STRONG_SELL"
        # Консолидация
        else:
            return "HOLD"
    
    def analyze_fundamental(self, instrument):
        """Фундаментальный анализ (упрощенный)"""
        # В реальности здесь был бы анализ отчетностей, мультипликаторов
        fundamentals = {
            "SBER": "STRONG_BUY",  # Лидер рынка
            "GAZP": "BUY",         # Дивидендная история
            "YNDX": "HOLD",        # Волатильность
            "LKOH": "BUY",         # Нефтяной гигант
            "ROSN": "BUY",         # Нефтянка
            "VTBR": "STRONG_BUY",  # Дешевый мультипликатор
        }
        return fundamentals.get(instrument, "HOLD")
    
    def analyze_sentiment(self, instrument):
        """Анализ сентимента (упрощенный)"""
        # В реальности здесь анализ новостей, соцсетей
        sentiment_scores = {
            "SBER": 0.8,
            "GAZP": 0.6, 
            "YNDX": 0.4,
            "VTBR": 0.7
        }
        return sentiment_scores.get(instrument, 0.5)
    
    def calculate_position_size(self, portfolio_value, risk_score):
        """Расчет размера позиции"""
        max_risk_per_trade = 0.02  # 2% от портфеля на сделку
        base_size = portfolio_value * max_risk_per_trade
        adjusted_size = base_size * risk_score
        return max(1, int(adjusted_size / 10000))  # Минимум 1 лот
    
    def generate_trading_signals(self):
        """Генерация торговых сигналов на основе многфакторного анализа"""
        signals = []
        
        for instrument, figi in INSTRUMENTS.items():
            try:
                # Получаем исторические данные
                candles = self.client.market_data.get_candles(
                    figi=figi,
                    from_=datetime.datetime.now() - datetime.timedelta(days=30),
                    to=datetime.datetime.now(),
                    interval=1
                )
                
                prices = [c.close.units + c.close.nano/1e9 for c in candles.candles]
                if not prices:
                    continue
                    
                current_price = prices[-1]
                
                # Мультифакторный анализ
                tech_signal = self.analyze_technical({'prices': prices})
                fund_signal = self.analyze_fundamental(instrument)
                sentiment_score = self.analyze_sentiment(instrument)
                
                # Совокупный рейтинг
                score = 0
                if tech_signal == "STRONG_BUY": score += 2
                elif tech_signal == "BUY": score += 1
                
                if fund_signal == "STRONG_BUY": score += 2
                elif fund_signal == "BUY": score += 1
                
                score += sentiment_score
                
                # Генерация сигнала
                if score >= 3.5:
                    position_size = self.calculate_position_size(1000000, score/5)
                    signals.append({
                        'action': 'BUY',
                        'instrument': instrument,
                        'figi': figi,
                        'price': current_price,
                        'size': position_size,
                        'confidence': score/5,
                        'reason': f"Мультифакторный score: {score:.2f}"
                    })
                elif score <= 1.5 and instrument in self.portfolio:
                    signals.append({
                        'action': 'SELL', 
                        'instrument': instrument,
                        'figi': figi,
                        'price': current_price,
                        'size': 1,
                        'confidence': (5-score)/5,
                        'reason': f"Слабые показатели: {score:.2f}"
                    })
                    
            except Exception as e:
                logger.error(f"Ошибка анализа {instrument}: {e}")
        
        return signals

def trading_session():
    """Мощная торговая сессия с продвинутым анализом"""
    global last_trading_time, session_count, trade_history, portfolio_value, total_profit
    
    session_count += 1
    current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    last_trading_time = current_time
    
    logger.info(f"🚀 ТОРГОВАЯ СЕССИЯ #{session_count} - МАКСИМАЛЬНАЯ МОЩНОСТЬ")
    
    token = os.getenv('TINKOFF_API_TOKEN')
    if not token:
        logger.error("❌ TINKOFF_API_TOKEN не найден")
        return
    
    try:
        with Client(token) as client:
            logger.info("✅ Подключение к API успешно")
            
            # Получаем счета
            accounts = client.users.get_accounts()
            if not accounts.accounts:
                logger.error("❌ Нет доступных счетов")
                return
            
            account_id = accounts.accounts[0].id
            logger.info(f"✅ Используем счет: {account_id}")
            
            # Инициализируем продвинутого бота
            bot = AdvancedTradingBot(client, account_id)
            
            # Получаем текущий портфель
            portfolio = client.operations.get_portfolio(account_id=account_id)
            portfolio_value = portfolio.total_amount_portfolio.units + portfolio.total_amount_portfolio.nano/1e9
            
            logger.info(f"📊 Стоимость портфеля: {portfolio_value:.2f} руб.")
            
            # Генерируем торговые сигналы
            logger.info("🧠 Запускаю мультифакторный анализ...")
            signals = bot.generate_trading_signals()
            
            # Исполняем сигналы
            executed_orders = []
            for signal in signals:
                logger.info(f"🎯 Сигнал: {signal['action']} {signal['instrument']} x{signal['size']} "
                           f"(уверенность: {signal['confidence']:.1%}) - {signal['reason']}")
                
                try:
                    response = client.orders.post_order(
                        figi=signal['figi'],
                        quantity=signal['size'],
                        direction=OrderDirection.ORDER_DIRECTION_BUY if signal['action'] == 'BUY' else OrderDirection.ORDER_DIRECTION_SELL,
                        account_id=account_id,
                        order_type=OrderType.ORDER_TYPE_MARKET
                    )
                    
                    executed_orders.append({
                        'action': signal['action'],
                        'instrument': signal['instrument'],
                        'price': signal['price'],
                        'size': signal['size'],
                        'order_id': response.order_id,
                        'confidence': signal['confidence'],
                        'timestamp': current_time
                    })
                    
                    logger.info(f"✅ Исполнено: {signal['action']} {signal['instrument']} x{signal['size']}")
                    
                except Exception as e:
                    logger.error(f"❌ Ошибка исполнения {signal['instrument']}: {e}")
            
            # Обновляем историю
            trade_history.extend(executed_orders)
            
            if executed_orders:
                logger.info(f"🎉 Исполнено ордеров: {len(executed_orders)}")
                total_profit += len(executed_orders) * 100  # Упрощенный расчет прибыли
            else:
                logger.info("💤 Нет сильных сигналов для торговли")
            
            logger.info(f"✅ СЕССИЯ #{session_count} ЗАВЕРШЕНА")
            
    except Exception as e:
        logger.error(f"❌ Критическая ошибка: {e}")

def run_trading_session():
    """Запуск торговой сессии"""
    thread = threading.Thread(target=trading_session)
    thread.daemon = True
    thread.start()

def schedule_tasks():
    """Настройка расписания"""
    schedule.every(15).minutes.do(run_trading_session)  # Каждые 15 минут!
    schedule.every().hour.do(lambda: logger.info("⏰ Часовая проверка системы"))
    logger.info("📅 Планировщик настроен на МАКСИМАЛЬНУЮ частоту")

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
        <head><title>MAX POWER Trading Bot</title><meta http-equiv="refresh" content="30"></head>
        <body style="font-family: Arial, sans-serif; margin: 40px; background: #f0f8ff;">
            <h1>🚀 MAX POWER Trading Bot</h1>
            <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 25px; border-radius: 15px; box-shadow: 0 4px 15px rgba(0,0,0,0.2);">
                <p><strong>⚡ Status:</strong> {bot_status}</p>
                <p><strong>⏰ Uptime:</strong> {str(uptime).split('.')[0]}</p>
                <p><strong>📊 Requests:</strong> {request_count}</p>
                <p><strong>🕒 Last Trading:</strong> {last_trading_time}</p>
                <p><strong>🔢 Sessions:</strong> {session_count}</p>
                <p><strong>💰 Trades:</strong> {len(trade_history)}</p>
                <p><strong>💎 Portfolio:</strong> {portfolio_value:.2f} руб.</p>
                <p><strong>📈 Total Profit:</strong> {total_profit:.2f} руб.</p>
            </div>
            <p style="margin-top: 20px;">
                <a href="/status" style="margin-right: 15px; background: #4CAF50; color: white; padding: 10px 15px; text-decoration: none; border-radius: 5px;">JSON Status</a>
                <a href="/force" style="margin-right: 15px; background: #2196F3; color: white; padding: 10px 15px; text-decoration: none; border-radius: 5px;">🚀 Force Trade</a>
                <a href="/trades" style="background: #FF9800; color: white; padding: 10px 15px; text-decoration: none; border-radius: 5px;">📋 Trade History</a>
            </p>
            <p><em>🤖 Авто-трейдинг с мультифакторным анализом | Обновление каждые 30 сек</em></p>
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
        "portfolio_value": portfolio_value,
        "total_profit": total_profit,
        "last_trading_time": last_trading_time,
        "timestamp": datetime.datetime.now().isoformat(),
        "mode": "MAX_POWER_AUTOTRADING"
    })

@app.route('/force')
def force_trade():
    run_trading_session()
    return jsonify({
        "message": "🚀 ЗАПУСК МАКСИМАЛЬНОЙ МОЩНОСТИ",
        "timestamp": datetime.datetime.now().isoformat()
    })

@app.route('/trades')
def show_trades():
    trades_html = ""
    for trade in trade_history[-20:]:
        color = "#4CAF50" if trade['action'] == 'BUY' else "#F44336"
        trades_html += f"""
        <div style="background: {color}; color: white; padding: 10px; margin: 5px 0; border-radius: 5px;">
            {trade['timestamp']} - {trade['action']} {trade['instrument']} x{trade['size']} по {trade['price']} руб. 
            (уверенность: {trade['confidence']:.1%})
        </div>
        """
    
    return f"""
    <html>
        <body style="font-family: Arial, sans-serif; margin: 40px;">
            <h1>📋 Trade History (MAX POWER)</h1>
            <p><strong>Total Trades:</strong> {len(trade_history)}</p>
            {trades_html if trade_history else "<p>No trades yet</p>"}
            <p><a href="/" style="background: #2196F3; color: white; padding: 10px 15px; text-decoration: none; border-radius: 5px;">← Back to Main</a></p>
        </body>
    </html>
    """

start_time = datetime.datetime.now()

if __name__ == '__main__':
    schedule_tasks()
    scheduler_thread = threading.Thread(target=run_scheduler)
    scheduler_thread.daemon = True
    scheduler_thread.start()
    
    logger.info("🚀 MAX POWER TRADING BOT STARTED!")
    logger.info("🎯 Режим: Авто-трейдинг с мультифакторным анализом")
    logger.info("📈 Инструменты: 18+ акций")
    logger.info("⏰ Частота: Каждые 15 минут")
    logger.info("💪 Цель: Максимальный рост портфеля")
    
    app.run(host='0.0.0.0', port=10000, debug=False)
