from flask import Flask, jsonify
import datetime
import time
import threading
import schedule
import logging
import os
from tinkoff.invest import Client
from strategies import PairsTradingStrategy  # ТОЛЬКО ОДНА СТРАТЕГИЯ

# Настройка логирования
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Глобальные переменные
request_count = 0
last_trading_time = "Not started yet"
bot_status = "🤖 AI PAIRS TRADING BOT - PROFIT MODE"
session_count = 0
trade_history = []
real_portfolio_value = 0
virtual_portfolio_value = 100000  # Стартовый виртуальный капитал
virtual_positions = {}
total_virtual_profit = 0
total_virtual_return = 0.0

# ИНСТРУМЕНТЫ - ТОЛЬКО SBER и VTBR
INSTRUMENTS = {
    "SBER": "BBG004730N88",
    "VTBR": "BBG004730ZJ9"
}

class VirtualPortfolio:
    """Управление виртуальным портфелем с тейк-профитами и стоп-лоссами"""
    
    def __init__(self, initial_capital=100000):
        self.cash = initial_capital
        self.positions = {}  # {ticker: {'size': X, 'avg_price': Y, 'take_profit': Z, 'stop_loss': W}}
        self.trade_history = []
        self.initial_capital = initial_capital
        
    def check_exit_conditions(self, current_prices):
        """Проверяем тейк-профиты и стоп-лоссы"""
        exit_signals = []
        
        for ticker, pos_info in list(self.positions.items()):
            if ticker in current_prices:
                current_price = current_prices[ticker]
                avg_price = pos_info['avg_price']
                
                # Проверяем тейк-профит
                if 'take_profit' in pos_info and current_price >= pos_info['take_profit']:
                    exit_signals.append({
                        'action': 'SELL',
                        'ticker': ticker,
                        'price': current_price,
                        'size': pos_info['size'],
                        'strategy': 'Take Profit',
                        'reason': f"Тейк-профит достигнут: {current_price:.2f} > {pos_info['take_profit']:.2f}",
                        'profit': (current_price - avg_price) * pos_info['size']
                    })
                
                # Проверяем стоп-лосс
                elif 'stop_loss' in pos_info and current_price <= pos_info['stop_loss']:
                    exit_signals.append({
                        'action': 'SELL',
                        'ticker': ticker,
                        'price': current_price,
                        'size': pos_info['size'],
                        'strategy': 'Stop Loss',
                        'reason': f"Стоп-лосс сработал: {current_price:.2f} < {pos_info['stop_loss']:.2f}",
                        'profit': (current_price - avg_price) * pos_info['size']
                    })
        
        return exit_signals
    
    def execute_trade(self, signal, current_price):
        """Исполнение виртуальной сделки с тейк-профитами"""
        ticker = signal['ticker']
        action = signal['action']
        size = signal.get('size', 1)
        
        # Для упрощения: 1 акция (в реальности нужно умножать на лотность)
        trade_cost = current_price * size
        
        if action == 'BUY':
            if trade_cost <= self.cash:
                self.cash -= trade_cost
                
                # Обновляем среднюю цену, если уже есть позиция
                if ticker in self.positions:
                    old_pos = self.positions[ticker]
                    total_size = old_pos['size'] + size
                    total_cost = (old_pos['avg_price'] * old_pos['size']) + trade_cost
                    new_avg_price = total_cost / total_size
                    
                    self.positions[ticker] = {
                        'size': total_size,
                        'avg_price': new_avg_price,
                        'take_profit': signal.get('take_profit', current_price * 1.02),
                        'stop_loss': signal.get('stop_loss', current_price * 0.98)
                    }
                else:
                    self.positions[ticker] = {
                        'size': size,
                        'avg_price': current_price,
                        'take_profit': signal.get('take_profit', current_price * 1.02),
                        'stop_loss': signal.get('stop_loss', current_price * 0.98)
                    }
                
                profit = 0
                status = "EXECUTED"
            else:
                profit = 0
                status = "INSUFFICIENT_FUNDS"
        else:  # SELL
            if ticker in self.positions and self.positions[ticker]['size'] >= size:
                position = self.positions[ticker]
                profit = (current_price - position['avg_price']) * size
                self.cash += trade_cost
                
                # Уменьшаем позицию или удаляем
                if position['size'] == size:
                    del self.positions[ticker]
                else:
                    position['size'] -= size
                
                status = "EXECUTED"
            else:
                profit = 0
                status = "NO_POSITION"
        
        trade_result = {
            'timestamp': datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            'strategy': signal.get('strategy', 'Unknown'),
            'action': action,
            'ticker': ticker,
            'price': current_price,
            'size': size,
            'virtual': True,
            'status': status,
            'profit': profit,
            'reason': signal.get('reason', ''),
            'virtual_cash': self.cash,
            'virtual_positions': dict(self.positions)
        }
        
        self.trade_history.append(trade_result)
        return trade_result

    def get_total_value(self, current_prices):
        """Общая стоимость портфеля (деньги + позиции)"""
        total = self.cash
        for ticker, pos in self.positions.items():
            if ticker in current_prices:
                total += current_prices[ticker] * pos['size']
        return total

def trading_session():
    """Торговая сессия - ТОЛЬКО ПАРНЫЙ АРБИТРАЖ"""
    global last_trading_time, session_count, trade_history, real_portfolio_value
    global virtual_portfolio_value, total_virtual_profit, virtual_positions, total_virtual_return
    
    session_count += 1
    current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    last_trading_time = current_time
    
    logger.info(f"🚀 ПАРНАЯ ТОРГОВЛЯ #{session_count} - {current_time}")
    
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
            current_prices = {}
            for ticker, figi in INSTRUMENTS.items():
                last_price = client.market_data.get_last_prices(figi=[figi])
                if last_price.last_prices:
                    price_obj = last_price.last_prices[0].price
                    price = price_obj.units + price_obj.nano / 1e9
                    current_prices[ticker] = price
            
            # Получаем реальный портфель (только для информации)
            try:
                portfolio = client.operations.get_portfolio(account_id=account_id)
                real_portfolio_value = portfolio.total_amount_portfolio.units + portfolio.total_amount_portfolio.nano/1e9
            except:
                real_portfolio_value = 0
            
            # Инициализируем виртуальный портфель
            if 'virtual_portfolio' not in globals():
                global virtual_portfolio
                virtual_portfolio = VirtualPortfolio(100000)
            
            # ЗАПУСКАЕМ ТОЛЬКО ПАРНУЮ СТРАТЕГИЮ
            strategy = PairsTradingStrategy(client, account_id)
            
            # Получаем сигналы
            signals = strategy.analyze(INSTRUMENTS)
            
            # Проверяем тейк-профиты и стоп-лоссы для текущих позиций
            exit_signals = virtual_portfolio.check_exit_conditions(current_prices)
            
            # Исполняем ВСЕ сигналы (входы + выходы)
            all_signals = signals + exit_signals
            executed_trades = []
            
            for signal in all_signals:
                ticker = signal['ticker']
                if ticker in current_prices:
                    trade_result = virtual_portfolio.execute_trade(signal, current_prices[ticker])
                    executed_trades.append(trade_result)
                    
                    if trade_result['status'] == 'EXECUTED':
                        action_icon = "🟢" if signal['action'] == 'BUY' else "🔴"
                        logger.info(f"{action_icon} {signal['action']} {ticker}: {signal.get('reason', '')}")
                        if trade_result['profit'] != 0:
                            logger.info(f"   💰 Прибыль: {trade_result['profit']:.2f} руб.")
            
            # Сохраняем историю и обновляем статистику
            trade_history.extend(executed_trades)
            
            # Конвертируем позиции в простой формат для отображения
            virtual_positions = {}
            for ticker, pos in virtual_portfolio.positions.items():
                virtual_positions[ticker] = f"{pos['size']} акций по {pos['avg_price']:.2f}"
            
            # Считаем общую виртуальную прибыль за сессию
            session_profit = sum(trade.get('profit', 0) for trade in executed_trades)
            total_virtual_profit += session_profit
            
            # Общая доходность
            total_value = virtual_portfolio.get_total_value(current_prices)
            virtual_portfolio_value = total_value
            total_virtual_return = ((total_value - 100000) / 100000) * 100
            
            logger.info(f"💰 СЕССИЯ #{session_count} ЗАВЕРШЕНА")
            logger.info(f"💎 ПОРТФЕЛЬ: {total_value:.2f} руб.")
            logger.info(f"📈 ДОХОДНОСТЬ: {total_virtual_return:+.2f}%")
            logger.info(f"🎯 ПРИБЫЛЬ ЗА СЕССИЮ: {session_profit:+.2f} руб.")
            logger.info(f"🏦 ПОЗИЦИИ: {virtual_positions}")
            
    except Exception as e:
        logger.error(f"❌ Ошибка торговой сессии: {e}")

def run_trading_session():
    """Запуск торговой сессии в отдельном потоке"""
    thread = threading.Thread(target=trading_session)
    thread.daemon = True
    thread.start()

def schedule_tasks():
    """Оптимальное расписание - 8 проверок в день"""
    schedule.clear()
    
    # Утренние прорывы
    schedule.every().day.at("10:05").do(run_trading_session)
    schedule.every().day.at("10:30").do(run_trading_session)
    
    # Середина утра
    schedule.every().day.at("11:15").do(run_trading_session)
    
    # Вечерний тренд
    schedule.every().day.at("15:00").do(run_trading_session)
    schedule.every().day.at("15:30").do(run_trading_session)
    
    # Перед закрытием
    schedule.every().day.at("16:45").do(run_trading_session)
    
    # Вечерняя сессия
    schedule.every().day.at("18:50").do(run_trading_session)
    schedule.every().day.at("19:20").do(run_trading_session)
    
    logger.info("📅 Планировщик настроен на 8 проверок в день")

def run_scheduler():
    """Запуск планировщика в фоновом режиме"""
    while True:
        schedule.run_pending()
        time.sleep(1)

@app.route('/')
def home():
    global request_count
    request_count += 1
    start_time = datetime.datetime.now() - datetime.timedelta(hours=1)  # Пример
    uptime = datetime.datetime.now() - start_time
    
    return f"""
    <html>
        <head><title>AI Pairs Trading Bot</title><meta http-equiv="refresh" content="30"></head>
        <body style="font-family: Arial, sans-serif; margin: 40px; background: #f8f9fa;">
            <h1 style="color: #2c5aa0;">🤖 AI Pairs Trading Bot</h1>
            <div style="background: white; padding: 25px; border-radius: 10px; box-shadow: 0 2px 10px rgba(0,0,0,0.1);">
                <p><strong>🚀 Status:</strong> {bot_status}</p>
                <p><strong>⏰ Uptime:</strong> {str(uptime).split('.')[0]}</p>
                <p><strong>📊 Requests:</strong> {request_count}</p>
                <p><strong>🕒 Last Trading:</strong> {last_trading_time}</p>
                <p><strong>🔢 Sessions:</strong> {session_count}</p>
                <p><strong>💰 Virtual Trades:</strong> {len(trade_history)}</p>
                <p><strong>💎 Real Portfolio:</strong> {real_portfolio_value:.2f} руб.</p>
                <p><strong>🏦 Virtual Portfolio:</strong> {virtual_portfolio_value:.2f} руб.</p>
                <p><strong>📈 Virtual Return:</strong> <span style="color: {'green' if total_virtual_return >= 0 else 'red'}">{total_virtual_return:+.2f}%</span></p>
                <p><strong>📊 Total Profit:</strong> <span style="color: {'green' if total_virtual_profit >= 0 else 'red'}">{total_virtual_profit:+.2f} руб.</span></p>
                <p><strong>🎯 Positions:</strong> {virtual_positions if virtual_positions else 'Нет позиций'}</p>
            </div>
            <p style="margin-top: 20px;">
                <a href="/status" style="margin-right: 15px; background: #4CAF50; color: white; padding: 10px 15px; text-decoration: none; border-radius: 5px;">JSON Status</a>
                <a href="/force" style="margin-right: 15px; background: #2196F3; color: white; padding: 10px 15px; text-decoration: none; border-radius: 5px;">🚀 Force Trade</a>
                <a href="/trades" style="background: #FF9800; color: white; padding: 10px 15px; text-decoration: none; border-radius: 5px;">📋 Trade History</a>
            </p>
            <p style="color: #666;">
                <em>🤖 Парный арбитраж SBER/VTBR | 8 проверок в день | AI-оптимизированные параметры</em>
            </p>
        </body>
    </html>
    """

@app.route('/status')
def status():
    start_time = datetime.datetime.now() - datetime.timedelta(hours=1)
    uptime = datetime.datetime.now() - start_time
    
    return jsonify({
        "status": bot_status,
        "uptime_seconds": int(uptime.total_seconds()),
        "requests_served": request_count,
        "trading_sessions": session_count,
        "virtual_trades": len(trade_history),
        "real_portfolio": real_portfolio_value,
        "virtual_portfolio": virtual_portfolio_value,
        "virtual_return_percentage": total_virtual_return,
        "total_profit": total_virtual_profit,
        "virtual_positions": virtual_positions,
        "last_trading_time": last_trading_time,
        "timestamp": datetime.datetime.now().isoformat(),
        "strategy": "SBER/VTBR Pairs Trading",
        "trading_schedule": ["10:05", "10:30", "11:15", "15:00", "15:30", "16:45", "18:50", "19:20"]
    })

@app.route('/force')
def force_trade():
    """Принудительный запуск торговой сессии"""
    run_trading_session()
    return jsonify({
        "message": "🚀 ПРИНУДИТЕЛЬНЫЙ ЗАПУСК ТОРГОВЛИ",
        "timestamp": datetime.datetime.now().isoformat()
    })

@app.route('/trades')
def show_trades():
    trades_html = ""
    for trade in trade_history[-15:]:
        color = "#4CAF50" if trade['action'] == 'BUY' else "#F44336"
        badge = "🟢 ВИРТУАЛЬНАЯ" if trade.get('virtual') else "🔴 РЕАЛЬНАЯ"
        profit_html = f" | Прибыль: {trade.get('profit', 0):+.2f} руб." if trade.get('profit', 0) != 0 else ""
        
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
            <h1>📋 История Сделок</h1>
            <p><strong>Total Trades:</strong> {len(trade_history)}</p>
            <p><strong>Virtual Portfolio:</strong> {virtual_portfolio_value:.2f} руб. ({total_virtual_return:+.2f}%)</p>
            {trades_html if trade_history else "<p>No trades yet</p>"}
            <p><a href="/" style="background: #2196F3; color: white; padding: 10px 15px; text-decoration: none; border-radius: 5px;">← Back to Main</a></p>
        </body>
    </html>
    """

if __name__ == '__main__':
    # Запускаем планировщик
    schedule_tasks()
    scheduler_thread = threading.Thread(target=run_scheduler)
    scheduler_thread.daemon = True
    scheduler_thread.start()
    
    logger.info("🚀 AI PAIRS TRADING BOT STARTED!")
    logger.info("🎯 Стратегия: Парный арбитраж SBER/VTBR")
    logger.info("💰 Стартовый капитал: 100,000 руб.")
    logger.info("⏰ Расписание: 8 проверок в день (10:05, 10:30, 11:15, 15:00, 15:30, 16:45, 18:50, 19:20)")
    logger.info("📊 Параметры: Z-score > 2.0 для входа, тейк-профит +1.5%, стоп-лосс -1%")
    
    app.run(host='0.0.0.0', port=10000, debug=False)
