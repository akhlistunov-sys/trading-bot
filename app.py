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
bot_status = "REAL ANALYTICS + VIRTUAL TRADING"
session_count = 0
trade_history = []
portfolio_value = 0
total_profit = 0
learning_data = []

# Основные инструменты для анализа
INSTRUMENTS = {
    "SBER": "BBG004730N88",
    "GAZP": "BBG004730RP0", 
    "YNDX": "BBG006L8G4H1",
    "VTBR": "BBG004730ZJ9",
    "LKOH": "BBG004731032",
    "ROSN": "BBG004731354"
}

class LearningTrader:
    def __init__(self, client, account_id):
        self.client = client
        self.account_id = account_id
        self.virtual_portfolio = 100000  # Виртуальные 100,000 руб.
        self.virtual_positions = {}
        self.trade_history = []
        
    def get_real_market_data(self):
        """Получение реальных рыночных данных"""
        real_prices = {}
        try:
            for name, figi in INSTRUMENTS.items():
                last_price = self.client.market_data.get_last_prices(figi=[figi])
                if last_price.last_prices:
                    price_obj = last_price.last_prices[0].price
                    price = price_obj.units + price_obj.nano / 1e9
                    real_prices[name] = price
                    logger.info(f"📊 РЕАЛЬНАЯ ЦЕНА {name}: {price} руб.")
        except Exception as e:
            logger.error(f"❌ Ошибка получения цен: {e}")
        
        return real_prices
    
    def analyze_market_conditions(self, real_prices):
        """Анализ рыночных условий на реальных данных"""
        signals = []
        
        for instrument, current_price in real_prices.items():
            # Простая стратегия на реальных данных
            if instrument == "SBER":
                if current_price < 300:
                    signals.append({
                        'action': 'BUY',
                        'instrument': instrument,
                        'price': current_price,
                        'size': 10,
                        'reason': f"SBER ниже 300 руб. (текущая: {current_price})",
                        'confidence': 0.8
                    })
                elif current_price > 320 and instrument in self.virtual_positions:
                    signals.append({
                        'action': 'SELL',
                        'instrument': instrument, 
                        'price': current_price,
                        'size': self.virtual_positions[instrument],
                        'reason': f"SBER выше 320 руб. (текущая: {current_price})",
                        'confidence': 0.7
                    })
            
            elif instrument == "GAZP":
                if current_price < 130:
                    signals.append({
                        'action': 'BUY',
                        'instrument': instrument,
                        'price': current_price,
                        'size': 20,
                        'reason': f"GAZP ниже 130 руб. (текущая: {current_price})",
                        'confidence': 0.75
                    })
                elif current_price > 140 and instrument in self.virtual_positions:
                    signals.append({
                        'action': 'SELL',
                        'instrument': instrument,
                        'price': current_price,
                        'size': self.virtual_positions[instrument],
                        'reason': f"GAZP выше 140 руб. (текущая: {current_price})",
                        'confidence': 0.7
                    })
            
            elif instrument == "VTBR":
                if current_price < 0.025:
                    signals.append({
                        'action': 'BUY',
                        'instrument': instrument,
                        'price': current_price,
                        'size': 1000,
                        'reason': f"VTBR ниже 0.025 руб. (текущая: {current_price})",
                        'confidence': 0.9
                    })
                elif current_price > 0.03 and instrument in self.virtual_positions:
                    signals.append({
                        'action': 'SELL', 
                        'instrument': instrument,
                        'price': current_price,
                        'size': self.virtual_positions[instrument],
                        'reason': f"VTBR выше 0.03 руб. (текущая: {current_price})",
                        'confidence': 0.8
                    })
        
        return signals
    
    def execute_virtual_trade(self, signal, real_prices):
        """Исполнение виртуальной сделки"""
        instrument = signal['instrument']
        action = signal['action']
        price = signal['price']
        size = signal['size']
        
        trade_result = {
            'timestamp': datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            'action': action,
            'instrument': instrument,
            'price': price,
            'size': size,
            'virtual': True,
            'real_price': real_prices.get(instrument),
            'confidence': signal['confidence'],
            'reason': signal['reason']
        }
        
        if action == 'BUY':
            cost = price * size
            if cost <= self.virtual_portfolio:
                self.virtual_portfolio -= cost
                self.virtual_positions[instrument] = self.virtual_positions.get(instrument, 0) + size
                trade_result['virtual_portfolio'] = self.virtual_portfolio
                trade_result['profit'] = 0
                logger.info(f"🎯 ВИРТУАЛЬНАЯ ПОКУПКА: {instrument} x{size} по {price} руб.")
            else:
                trade_result['error'] = "Недостаточно виртуальных средств"
                logger.warning(f"⚠️ Не хватает виртуальных средств для покупки {instrument}")
        
        elif action == 'SELL':
            if instrument in self.virtual_positions and self.virtual_positions[instrument] >= size:
                revenue = price * size
                self.virtual_portfolio += revenue
                
                # Расчет прибыли
                avg_buy_price = price * 0.95  # Упрощенный расчет
                profit = (price - avg_buy_price) * size
                
                self.virtual_positions[instrument] -= size
                if self.virtual_positions[instrument] == 0:
                    del self.virtual_positions[instrument]
                
                trade_result['virtual_portfolio'] = self.virtual_portfolio
                trade_result['profit'] = profit
                logger.info(f"🎯 ВИРТУАЛЬНАЯ ПРОДАЖА: {instrument} x{size} по {price} руб. Прибыль: {profit:.2f} руб.")
            else:
                trade_result['error'] = "Недостаточно позиций для продажи"
                logger.warning(f"⚠️ Недостаточно {instrument} для продажи")
        
        return trade_result
    
    def calculate_performance(self):
        """Расчет эффективности виртуальной торговли"""
        total_invested = 100000 - self.virtual_portfolio
        current_value = self.virtual_portfolio
        
        for instrument, quantity in self.virtual_positions.items():
            # Используем последние реальные цены для оценки
            try:
                last_price = self.client.market_data.get_last_prices(figi=[INSTRUMENTS[instrument]])
                if last_price.last_prices:
                    price = last_price.last_prices[0].price.units + last_price.last_prices[0].price.nano/1e9
                    current_value += price * quantity
            except:
                pass
        
        performance = {
            'virtual_portfolio': self.virtual_portfolio,
            'current_total_value': current_value,
            'total_positions': len(self.virtual_positions),
            'return_percentage': ((current_value - 100000) / 100000) * 100,
            'positions': self.virtual_positions
        }
        
        return performance

def trading_session():
    """Сессия реальной аналитики и виртуальной торговли"""
    global last_trading_time, session_count, trade_history, portfolio_value, total_profit, learning_data
    
    session_count += 1
    current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    last_trading_time = current_time
    
    logger.info(f"🚀 СЕССИЯ #{session_count}: РЕАЛЬНАЯ АНАЛИТИКА + ВИРТУАЛЬНАЯ ТОРГОВЛЯ")
    
    token = os.getenv('TINKOFF_API_TOKEN')
    if not token:
        logger.error("❌ TINKOFF_API_TOKEN не найден")
        return
    
    try:
        with Client(token) as client:
            logger.info("✅ Подключение к реальному API успешно")
            
            # Получаем реальные счета
            accounts = client.users.get_accounts()
            if not accounts.accounts:
                logger.error("❌ Нет доступных счетов")
                return
            
            account_id = accounts.accounts[0].id
            
            # Получаем реальный портфель
            portfolio = client.operations.get_portfolio(account_id=account_id)
            portfolio_value = portfolio.total_amount_portfolio.units + portfolio.total_amount_portfolio.nano/1e9
            logger.info(f"📊 РЕАЛЬНЫЙ ПОРТФЕЛЬ: {portfolio_value:.2f} руб.")
            
            # Инициализируем обучающегося трейдера
            trader = LearningTrader(client, account_id)
            
            # Получаем реальные рыночные данные
            logger.info("📈 Получаем реальные рыночные данные...")
            real_prices = trader.get_real_market_data()
            
            if not real_prices:
                logger.error("❌ Не удалось получить реальные данные")
                return
            
            # Анализируем рынок на реальных данных
            logger.info("🧠 Анализируем рыночные условия...")
            signals = trader.analyze_market_conditions(real_prices)
            
            # Исполняем виртуальные сделки
            executed_trades = []
            for signal in signals:
                logger.info(f"🎯 СИГНАЛ: {signal['action']} {signal['instrument']} - {signal['reason']}")
                
                # Исполняем виртуальную сделку
                trade_result = trader.execute_virtual_trade(signal, real_prices)
                executed_trades.append(trade_result)
            
            # Сохраняем историю
            trade_history.extend(executed_trades)
            
            # Расчет эффективности
            performance = trader.calculate_performance()
            
            # Сохраняем данные для обучения
            learning_data.append({
                'timestamp': current_time,
                'real_prices': real_prices,
                'signals_count': len(signals),
                'executed_trades': len(executed_trades),
                'performance': performance,
                'virtual_portfolio': trader.virtual_portfolio
            })
            
            # Обновляем общую статистику
            total_profit = performance['current_total_value'] - 100000
            
            logger.info(f"✅ СЕССИЯ #{session_count} ЗАВЕРШЕНА")
            logger.info(f"💎 ВИРТУАЛЬНЫЙ РЕЗУЛЬТАТ: {performance['return_percentage']:.2f}%")
            logger.info(f"📊 ВИРТУАЛЬНЫЙ ПОРТФЕЛЬ: {trader.virtual_portfolio:.2f} руб.")
            
    except Exception as e:
        logger.error(f"❌ Ошибка в торговой сессии: {e}")

def run_trading_session():
    """Запуск торговой сессии"""
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
    
    # Расчет текущей эффективности
    current_return = (total_profit / 100000) * 100 if total_profit != 0 else 0
    
    return f"""
    <html>
        <head><title>Learning Trading Bot</title><meta http-equiv="refresh" content="30"></head>
        <body style="font-family: Arial, sans-serif; margin: 40px; background: #f8f9fa;">
            <h1>🎯 Learning Trading Bot</h1>
            <div style="background: white; padding: 25px; border-radius: 10px; box-shadow: 0 2px 10px rgba(0,0,0,0.1);">
                <p><strong>⚡ Status:</strong> {bot_status}</p>
                <p><strong>⏰ Uptime:</strong> {str(uptime).split('.')[0]}</p>
                <p><strong>📊 Requests:</strong> {request_count}</p>
                <p><strong>🕒 Last Trading:</strong> {last_trading_time}</p>
                <p><strong>🔢 Sessions:</strong> {session_count}</p>
                <p><strong>💰 Virtual Trades:</strong> {len(trade_history)}</p>
                <p><strong>💎 Real Portfolio:</strong> {portfolio_value:.2f} руб.</p>
                <p><strong>📈 Virtual Return:</strong> <span style="color: {'green' if current_return >= 0 else 'red'}">{current_return:.2f}%</span></p>
                <p><strong>💡 Learning Data:</strong> {len(learning_data)} записей</p>
            </div>
            <p style="margin-top: 20px;">
                <a href="/status" style="margin-right: 15px; background: #4CAF50; color: white; padding: 10px 15px; text-decoration: none; border-radius: 5px;">JSON Status</a>
                <a href="/force" style="margin-right: 15px; background: #2196F3; color: white; padding: 10px 15px; text-decoration: none; border-radius: 5px;">🚀 Force Trade</a>
                <a href="/trades" style="margin-right: 15px; background: #FF9800; color: white; padding: 10px 15px; text-decoration: none; border-radius: 5px;">📋 Trade History</a>
                <a href="/performance" style="background: #9C27B0; color: white; padding: 10px 15px; text-decoration: none; border-radius: 5px;">📊 Performance</a>
            </p>
            <p><em>🤖 Реальная аналитика + Виртуальная торговля | Обучение на реальных данных</em></p>
        </body>
    </html>
    """

@app.route('/status')
def status():
    uptime = datetime.datetime.now() - start_time
    current_return = (total_profit / 100000) * 100 if total_profit != 0 else 0
    
    return jsonify({
        "status": bot_status,
        "uptime_seconds": int(uptime.total_seconds()),
        "requests_served": request_count,
        "trading_sessions": session_count,
        "virtual_trades": len(trade_history),
        "real_portfolio": portfolio_value,
        "virtual_return_percentage": current_return,
        "virtual_profit": total_profit,
        "learning_data_points": len(learning_data),
        "last_trading_time": last_trading_time,
        "timestamp": datetime.datetime.now().isoformat(),
        "mode": "REAL_ANALYTICS_VIRTUAL_TRADING"
    })

@app.route('/force')
def force_trade():
    run_trading_session()
    return jsonify({
        "message": "🚀 Запуск сессии реальной аналитики и виртуальной торговли",
        "timestamp": datetime.datetime.now().isoformat()
    })

@app.route('/trades')
def show_trades():
    trades_html = ""
    for trade in trade_history[-15:]:
        color = "#4CAF50" if trade['action'] == 'BUY' else "#F44336"
        badge = "🟢 ВИРТУАЛЬНАЯ" if trade.get('virtual') else "🔴 РЕАЛЬНАЯ"
        profit_html = f" | Прибыль: {trade.get('profit', 0):.2f} руб." if trade.get('profit') else ""
        
        trades_html += f"""
        <div style="background: {color}; color: white; padding: 10px; margin: 5px 0; border-radius: 5px;">
            {badge} | {trade['timestamp']} | {trade['action']} {trade['instrument']} x{trade['size']} по {trade['price']} руб.{profit_html}
            <br><small>{trade.get('reason', '')}</small>
        </div>
        """
    
    return f"""
    <html>
        <body style="font-family: Arial, sans-serif; margin: 40px;">
            <h1>📋 История Сделок (Виртуальные)</h1>
            <p><strong>Total Trades:</strong> {len(trade_history)}</p>
            {trades_html if trade_history else "<p>No trades yet</p>"}
            <p><a href="/" style="background: #2196F3; color: white; padding: 10px 15px; text-decoration: none; border-radius: 5px;">← Back to Main</a></p>
        </body>
    </html>
    """

@app.route('/performance')
def show_performance():
    if not learning_data:
        return "<p>No performance data yet</p>"
    
    latest_perf = learning_data[-1]['performance']
    
    return f"""
    <html>
        <body style="font-family: Arial, sans-serif; margin: 40px;">
            <h1>📊 Эффективность Виртуальной Торговли</h1>
            <div style="background: #e8f5e8; padding: 20px; border-radius: 10px;">
                <p><strong>💼 Начальный депозит:</strong> 100,000 руб.</p>
                <p><strong>💰 Текущий портфель:</strong> {latest_perf['virtual_portfolio']:.2f} руб.</p>
                <p><strong>📈 Общая стоимость:</strong> {latest_perf['current_total_value']:.2f} руб.</p>
                <p><strong>🎯 Доходность:</strong> <span style="color: {'green' if latest_perf['return_percentage'] >= 0 else 'red'}; font-weight: bold">{latest_perf['return_percentage']:.2f}%</span></p>
                <p><strong>📊 Открытые позиции:</strong> {latest_perf['total_positions']}</p>
            </div>
            <p><a href="/" style="background: #2196F3; color: white; padding: 10px 15px; text-decoration: none; border-radius: 5px;">← Back to Main</a></p>
        </body>
    </html>
    """

@app.route('/check_token')
def check_token():
    """Проверка токена"""
    token = os.getenv('TINKOFF_API_TOKEN')
    
    info = {
        "token_exists": bool(token),
        "token_length": len(token) if token else 0,
        "token_starts_with_t": token.startswith('t.') if token else False,
        "token_preview": token[:20] + "..." if token and len(token) > 20 else token,
        "environment_loaded": 'TINKOFF_API_TOKEN' in os.environ
    }
    
    return jsonify(info)

start_time = datetime.datetime.now()

if __name__ == '__main__':
    schedule_tasks()
    scheduler_thread = threading.Thread(target=run_scheduler)
    scheduler_thread.daemon = True
    scheduler_thread.start()
    
    logger.info("🚀 LEARNING TRADING BOT STARTED!")
    logger.info("🎯 Режим: Реальная аналитика + Виртуальная торговля")
    logger.info("📊 Данные: Реальные цены с Tinkoff API") 
    logger.info("💡 Цель: Обучение на реальных рыночных данных")
    
    app.run(host='0.0.0.0', port=10000, debug=False)
