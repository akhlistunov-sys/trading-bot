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
bot_status = "⚡ MOMENT TRADING BOT - VIRTUAL MODE"
session_count = 0
trade_history = []
real_portfolio_value = 0
virtual_portfolio_value = 100000  # Стартовый виртуальный капитал
virtual_positions = {}
total_virtual_profit = 0

# Инструменты для торговли
INSTRUMENTS = {
    "SBER": "BBG004730N88",
    "GAZP": "BBG004730RP0", 
    "VTBR": "BBG004730ZJ9",
    "LKOH": "BBG004731032",
    "ROSN": "BBG004731354",
    "YNDX": "BBG006L8G4H1"
}

class VirtualPortfolio:
    """Управление виртуальным портфелем"""
    
    def __init__(self, initial_capital=100000):
        self.cash = initial_capital
        self.positions = {}
        self.trade_history = []
        
    def execute_trade(self, signal, current_price):
        """Исполнение виртуальной сделки"""
        ticker = signal['ticker']
        action = signal['action']
        size = signal['size']
        
        trade_cost = current_price * size
        
        if action == 'BUY':
            if trade_cost <= self.cash:
                self.cash -= trade_cost
                self.positions[ticker] = self.positions.get(ticker, 0) + size
                profit = 0
                status = "EXECUTED"
            else:
                profit = 0
                status = "INSUFFICIENT_FUNDS"
        else:  # SELL
            if ticker in self.positions and self.positions[ticker] >= size:
                self.cash += trade_cost
                # Упрощенный расчет прибыли
                profit = trade_cost * 0.02  # 2% прибыли для примера
                self.positions[ticker] -= size
                if self.positions[ticker] == 0:
                    del self.positions[ticker]
                status = "EXECUTED"
            else:
                profit = 0
                status = "NO_POSITION"
        
        trade_result = {
            'timestamp': datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            'strategy': signal['strategy'],
            'action': action,
            'ticker': ticker,
            'price': current_price,
            'size': size,
            'virtual': True,
            'status': status,
            'profit': profit,
            'reason': signal['reason'],
            'virtual_cash': self.cash,
            'virtual_positions': dict(self.positions)
        }
        
        return trade_result

def trading_session():
    """Главная торговая сессия - ВИРТУАЛЬНАЯ ТОРГОВЛЯ"""
    global last_trading_time, session_count, trade_history, real_portfolio_value
    global virtual_portfolio_value, total_virtual_profit, virtual_positions
    
    session_count += 1
    current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    last_trading_time = current_time
    
    logger.info(f"🚀 ВИРТУАЛЬНАЯ СЕССИЯ #{session_count} - БЫСТРЫЙ ТРЕЙДИНГ")
    
    token = os.getenv('TINKOFF_API_TOKEN')
    if not token:
        logger.error("❌ TINKOFF_API_TOKEN не найден")
        return
    
    try:
        with Client(token) as client:
            # Получаем реальный счет (только для данных)
            accounts = client.users.get_accounts()
            if not accounts.accounts:
                logger.error("❌ Нет доступных счетов")
                return
                
            account_id = accounts.accounts[0].id
            
            # Получаем реальные цены
            real_prices = {}
            for ticker, figi in INSTRUMENTS.items():
                last_price = client.market_data.get_last_prices(figi=[figi])
                if last_price.last_prices:
                    price_obj = last_price.last_prices[0].price
                    price = price_obj.units + price_obj.nano / 1e9
                    real_prices[ticker] = price
                    logger.info(f"📊 РЕАЛЬНАЯ ЦЕНА {ticker}: {price} руб.")
            
            # Получаем реальный портфель (только для информации)
            try:
                portfolio = client.operations.get_portfolio(account_id=account_id)
                real_portfolio_value = portfolio.total_amount_portfolio.units + portfolio.total_amount_portfolio.nano/1e9
            except:
                real_portfolio_value = 0
            
            # Инициализируем виртуальный портфель
            virtual_portfolio = VirtualPortfolio(100000)
            
            # Запускаем ВСЕ стратегии на реальных данных
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
                    logger.info(f"🎯 {strategy.name}: {len(signals)} сигналов")
                except Exception as e:
                    logger.error(f"❌ Ошибка в стратегии {strategy.name}: {e}")
            
            # Сортируем сигналы по уверенности
            all_signals.sort(key=lambda x: x['confidence'], reverse=True)
            
            # Исполняем ВИРТУАЛЬНЫЕ сделки
            executed_trades = []
            for signal in all_signals[:3]:  # Лучшие 3 сигнала
                if signal['confidence'] > 0.6:
                    current_price = real_prices.get(signal['ticker'])
                    if current_price:
                        trade_result = virtual_portfolio.execute_trade(signal, current_price)
                        executed_trades.append(trade_result)
                        
                        if trade_result['status'] == 'EXECUTED':
                            logger.info(f"✅ ВИРТУАЛЬНАЯ СДЕЛКА: {signal['action']} {signal['ticker']} x{signal['size']}")
                        else:
                            logger.warning(f"⚠️ {trade_result['status']}: {signal['action']} {signal['ticker']}")
            
            # Сохраняем историю и обновляем статистику
            trade_history.extend(executed_trades)
            virtual_portfolio_value = virtual_portfolio.cash
            virtual_positions = virtual_portfolio.positions
            
            # Считаем общую виртуальную прибыль
            total_virtual_profit = sum(trade.get('profit', 0) for trade in executed_trades)
            
            logger.info(f"💰 СЕССИЯ #{session_count} ЗАВЕРШЕНА")
            logger.info(f"💎 ВИРТУАЛЬНЫЙ ПОРТФЕЛЬ: {virtual_portfolio_value:.2f} руб.")
            logger.info(f"📈 ВИРТУАЛЬНАЯ ПРИБЫЛЬ: +{total_virtual_profit:.2f} руб.")
            
    except Exception as e:
        logger.error(f"❌ Ошибка торговой сессии: {e}")

def run_trading_session():
    """Запуск торговой сессии в отдельном потоке"""
    thread = threading.Thread(target=trading_session)
    thread.daemon = True
    thread.start()

def schedule_tasks():
    """Настройка расписания - БЫСТРЫЙ ТРЕЙДИНГ"""
    schedule.every(10).minutes.do(run_trading_session)
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
    
    # Расчет доходности
    initial_capital = 100000
    current_virtual_value = virtual_portfolio_value + sum(
        virtual_positions.get(ticker, 0) * 300 for ticker in virtual_positions  # Примерная оценка
    )
    virtual_return = ((current_virtual_value - initial_capital) / initial_capital) * 100
    
    return f"""
    <html>
        <head><title>Moment Trading Bot</title><meta http-equiv="refresh" content="30"></head>
        <body style="font-family: Arial, sans-serif; margin: 40px; background: #f8f9fa;">
            <h1 style="color: #2c5aa0;">⚡ Moment Trading Bot</h1>
            <div style="background: white; padding: 25px; border-radius: 10px; box-shadow: 0 2px 10px rgba(0,0,0,0.1);">
                <p><strong>🚀 Status:</strong> {bot_status}</p>
                <p><strong>⏰ Uptime:</strong> {str(uptime).split('.')[0]}</p>
                <p><strong>📊 Requests:</strong> {request_count}</p>
                <p><strong>🕒 Last Trading:</strong> {last_trading_time}</p>
                <p><strong>🔢 Sessions:</strong> {session_count}</p>
                <p><strong>💰 Virtual Trades:</strong> {len(trade_history)}</p>
                <p><strong>💎 Real Portfolio:</strong> {real_portfolio_value:.2f} руб.</p>
                <p><strong>🏦 Virtual Portfolio:</strong> {virtual_portfolio_value:.2f} руб.</p>
                <p><strong>📈 Virtual Return:</strong> <span style="color: {'green' if virtual_return >= 0 else 'red'}">{virtual_return:.2f}%</span></p>
            </div>
            <p style="margin-top: 20px;">
                <a href="/status" style="margin-right: 15px; background: #4CAF50; color: white; padding: 10px 15px; text-decoration: none; border-radius: 5px;">JSON Status</a>
                <a href="/force" style="margin-right: 15px; background: #2196F3; color: white; padding: 10px 15px; text-decoration: none; border-radius: 5px;">🚀 Force Trade</a>
                <a href="/trades" style="background: #FF9800; color: white; padding: 10px 15px; text-decoration: none; border-radius: 5px;">📋 Trade History</a>
            </p>
            <p style="color: #666;">
                <em>🤖 Виртуальный трейдинг на реальных данных | Моментные стратегии каждые 10 минут</em>
            </p>
        </body>
    </html>
    """

@app.route('/status')
def status():
    uptime = datetime.datetime.now() - start_time
    
    initial_capital = 100000
    current_virtual_value = virtual_portfolio_value + sum(
        virtual_positions.get(ticker, 0) * 300 for ticker in virtual_positions
    )
    virtual_return = ((current_virtual_value - initial_capital) / initial_capital) * 100
    
    return jsonify({
        "status": bot_status,
        "uptime_seconds": int(uptime.total_seconds()),
        "requests_served": request_count,
        "trading_sessions": session_count,
        "virtual_trades": len(trade_history),
        "real_portfolio": real_portfolio_value,
        "virtual_portfolio": virtual_portfolio_value,
        "virtual_return_percentage": virtual_return,
        "virtual_positions": virtual_positions,
        "last_trading_time": last_trading_time,
        "timestamp": datetime.datetime.now().isoformat(),
        "mode": "VIRTUAL_TRADING_10MIN",
        "strategies_active": ["Moment Trading", "Arbitrage", "News Trading"]
    })

@app.route('/force')
def force_trade():
    """Принудительный запуск торговой сессии"""
    run_trading_session()
    return jsonify({
        "message": "🚀 ПРИНУДИТЕЛЬНЫЙ ЗАПУСК ВИРТУАЛЬНОЙ ТОРГОВЛИ",
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
        <div style="background: {color}; color: white; padding: 15px; margin: 10px 0; border-radius: 5px;">
            {badge} | {trade['timestamp']} | {trade['strategy']}
            <br>{trade['action']} <strong>{trade['ticker']}</strong> x{trade['size']} по {trade['price']} руб.{profit_html}
            <br><small>💡 {trade.get('reason', '')}</small>
        </div>
        """
    
    return f"""
    <html>
        <body style="font-family: Arial, sans-serif; margin: 40px; background: #f8f9fa;">
            <h1>📋 История Виртуальных Сделок</h1>
            <p><strong>Total Trades:</strong> {len(trade_history)}</p>
            <p><strong>Virtual Portfolio:</strong> {virtual_portfolio_value:.2f} руб.</p>
            {trades_html if trade_history else "<p>No trades yet</p>"}
            <p><a href="/" style="background: #2196F3; color: white; padding: 10px 15px; text-decoration: none; border-radius: 5px;">← Back to Main</a></p>
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
    
    logger.info("🚀 VIRTUAL MOMENT TRADING BOT STARTED!")
    logger.info("⚡ Режим: Виртуальный трейдинг на реальных данных")
    logger.info("💰 Стартовый капитал: 100,000 руб.")
    logger.info("🎯 Стратегии: Moment Trading, Arbitrage, News Trading")
    logger.info("⏰ Частота: Каждые 10 минут")
    
    app.run(host='0.0.0.0', port=10000, debug=False)
