from flask import Flask, jsonify
import datetime
import time
import threading
import schedule
import logging
import os
import asyncio
from tinkoff.invest import Client
from strategies import PairsTradingStrategy

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

app = Flask(__name__)

request_count = 0
last_trading_time = "Not started yet"
bot_status = "🤖 AI PAIRS TRADING BOT PRO - AGGRESSIVE TEST MODE"
session_count = 0
trade_history = []
real_portfolio_value = 0
virtual_portfolio_value = 100000
virtual_positions = {}
total_virtual_profit = 0
total_virtual_return = 0.0
is_trading = False
strategy_stats = {}
start_time = datetime.datetime.now()

INSTRUMENTS = {
    "LKOH": "BBG004731032",  # Лукойл
    "ROSN": "BBG004731354"   # Роснефть
}

class VirtualPortfolioPro:
    def __init__(self, initial_capital=100000):
        self.cash = initial_capital
        self.positions = {}
        self.trade_history = []
        self.initial_capital = initial_capital
        self.total_trades = 0
        self.winning_trades = 0
        self.total_profit = 0
        
    def check_exit_conditions(self, current_prices):
        exit_signals = []
        for ticker, pos_info in list(self.positions.items()):
            if ticker in current_prices:
                current_price = current_prices[ticker]
                avg_price = pos_info['avg_price']
                size = pos_info['size']
                
                profit_per_share = current_price - avg_price
                total_profit = profit_per_share * size
                profit_percent = (profit_per_share / avg_price) * 100
                
                take_profit_hit = False
                stop_loss_hit = False
                reason = ""
                
                if 'take_profit' in pos_info and current_price >= pos_info['take_profit']:
                    take_profit_hit = True
                    reason = f"✅ ТЕЙК-ПРОФИТ {pos_info.get('take_profit_percent', 2.5)}%: {current_price:.2f} > {pos_info['take_profit']:.2f}"
                elif 'stop_loss' in pos_info and current_price <= pos_info['stop_loss']:
                    stop_loss_hit = True
                    reason = f"🚨 СТОП-ЛОСС {pos_info.get('stop_loss_percent', 1.5)}%: {current_price:.2f} < {pos_info['stop_loss']:.2f}"
                elif 'ai_generated' in pos_info and pos_info['ai_generated']:
                    if 'take_profit_percent' in pos_info and 'stop_loss_percent' in pos_info:
                        tp_percent = pos_info['take_profit_percent']
                        sl_percent = pos_info['stop_loss_percent']
                        
                        if profit_percent >= tp_percent * 0.8:
                            reason = f"⚡ ИИ: Частичный выход при {profit_percent:.1f}% прибыли"
                            exit_size = int(size * 0.5)
                            if exit_size > 0:
                                exit_signals.append({
                                    'action': 'SELL',
                                    'ticker': ticker,
                                    'price': current_price,
                                    'size': exit_size,
                                    'strategy': 'AI Partial Exit',
                                    'reason': reason,
                                    'profit': total_profit * 0.5,
                                    'partial': True
                                })
                
                if take_profit_hit or stop_loss_hit:
                    exit_signals.append({
                        'action': 'SELL',
                        'ticker': ticker,
                        'price': current_price,
                        'size': size,
                        'strategy': 'Take Profit' if take_profit_hit else 'Stop Loss',
                        'reason': reason,
                        'profit': total_profit,
                        'profit_percent': profit_percent
                    })
        
        return exit_signals
    
    def execute_trade(self, signal, current_price):
        ticker = signal['ticker']
        action = signal['action']
        size = signal.get('size', 100 if ticker == 'VTBR' else 1)
        
        if 'partial' in signal and signal['partial'] and ticker in self.positions:
            current_position = self.positions[ticker]['size']
            size = min(size, current_position)
        
        trade_cost = current_price * size
        
        trade_result = {
            'timestamp': datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            'strategy': signal.get('strategy', 'AI Pairs Trading Pro'),
            'action': action,
            'ticker': ticker,
            'price': current_price,
            'size': size,
            'virtual': True,
            'status': 'PENDING',
            'profit': 0,
            'reason': signal.get('reason', ''),
            'ai_generated': signal.get('ai_generated', False),
            'confidence': signal.get('confidence', 0.5),
            'take_profit': signal.get('take_profit'),
            'stop_loss': signal.get('stop_loss'),
            'take_profit_percent': signal.get('take_profit_percent', 2.5),
            'stop_loss_percent': signal.get('stop_loss_percent', 1.5),
            'initial_cash': self.cash,
            'initial_positions': dict(self.positions)
        }
        
        if action == 'BUY':
            if trade_cost <= self.cash:
                self.cash -= trade_cost
                
                if ticker in self.positions:
                    old_pos = self.positions[ticker]
                    total_size = old_pos['size'] + size
                    total_cost = (old_pos['avg_price'] * old_pos['size']) + trade_cost
                    new_avg_price = total_cost / total_size
                    
                    self.positions[ticker] = {
                        'size': total_size,
                        'avg_price': new_avg_price,
                        'take_profit': signal.get('take_profit', current_price * 1.025),
                        'stop_loss': signal.get('stop_loss', current_price * 0.985),
                        'take_profit_percent': signal.get('take_profit_percent', 2.5),
                        'stop_loss_percent': signal.get('stop_loss_percent', 1.5),
                        'entry_time': datetime.datetime.now().isoformat(),
                        'ai_generated': signal.get('ai_generated', False)
                    }
                else:
                    self.positions[ticker] = {
                        'size': size,
                        'avg_price': current_price,
                        'take_profit': signal.get('take_profit', current_price * 1.025),
                        'stop_loss': signal.get('stop_loss', current_price * 0.985),
                        'take_profit_percent': signal.get('take_profit_percent', 2.5),
                        'stop_loss_percent': signal.get('stop_loss_percent', 1.5),
                        'entry_time': datetime.datetime.now().isoformat(),
                        'ai_generated': signal.get('ai_generated', False)
                    }
                
                trade_result['status'] = "EXECUTED"
                trade_result['message'] = f"Куплено {size} {ticker}"
                
                logger.info(f"🟢 ВИРТУАЛЬНАЯ ПОКУПКА: {size} {ticker} по {current_price:.2f}")
                if signal.get('ai_generated'):
                    logger.info(f"   🧠 ИИ сигнал (conf: {signal.get('confidence', 0):.2f})")
                
            else:
                trade_result['status'] = "INSUFFICIENT_FUNDS"
                trade_result['message'] = f"Недостаточно средств: {trade_cost:.2f} > {self.cash:.2f}"
                
        else:
            if ticker in self.positions and self.positions[ticker]['size'] >= size:
                position = self.positions[ticker]
                profit = (current_price - position['avg_price']) * size
                profit_percent = ((current_price - position['avg_price']) / position['avg_price']) * 100
                
                self.cash += trade_cost
                
                trade_result['profit'] = profit
                trade_result['profit_percent'] = profit_percent
                trade_result['avg_entry_price'] = position['avg_price']
                
                if profit > 0:
                    self.winning_trades += 1
                
                self.total_trades += 1
                self.total_profit += profit
                
                if position['size'] == size:
                    del self.positions[ticker]
                    trade_result['message'] = f"Продано {size} {ticker}. Позиция закрыта."
                else:
                    position['size'] -= size
                    trade_result['message'] = f"Продано {size} {ticker}. Осталось: {position['size']}."
                
                trade_result['status'] = "EXECUTED"
                
                profit_color = "🟢" if profit > 0 else "🔴"
                logger.info(f"{profit_color} ВИРТУАЛЬНАЯ ПРОДАЖА: {size} {ticker} по {current_price:.2f}")
                logger.info(f"   📊 Прибыль: {profit:+.2f} руб. ({profit_percent:+.1f}%)")
                if signal.get('reason'):
                    logger.info(f"   💡 Причина: {signal['reason']}")
                
            else:
                trade_result['status'] = "NO_POSITION"
                trade_result['message'] = f"Нет позиции {ticker} для продажи"
        
        trade_result['final_cash'] = self.cash
        trade_result['final_positions'] = dict(self.positions)
        self.trade_history.append(trade_result)
        
        return trade_result

    def get_total_value(self, current_prices):
        total = self.cash
        for ticker, pos in self.positions.items():
            if ticker in current_prices:
                total += current_prices[ticker] * pos['size']
        return total
    
    def get_stats(self):
        win_rate = (self.winning_trades / self.total_trades * 100) if self.total_trades > 0 else 0
        avg_profit = self.total_profit / self.total_trades if self.total_trades > 0 else 0
        
        return {
            'total_trades': self.total_trades,
            'winning_trades': self.winning_trades,
            'win_rate': win_rate,
            'total_profit': self.total_profit,
            'avg_profit': avg_profit,
            'current_positions': len(self.positions),
            'cash': self.cash
        }

async def trading_session_async(force_mode=False):
    global last_trading_time, session_count, trade_history, real_portfolio_value
    global virtual_portfolio_value, total_virtual_profit, virtual_positions, total_virtual_return, is_trading
    global strategy_stats, bot_status
    
    if is_trading:
        logger.info("⏸️ Торговая сессия уже выполняется")
        return
    
    is_trading = True
    session_count += 1
    current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    last_trading_time = current_time
    
    mode_label = "🚀 ПРИНУДИТЕЛЬНАЯ" if force_mode else "🤖 РАСПИСАНИЕ"
    logger.info(f"{mode_label} ТОРГОВАЯ СЕССИЯ #{session_count} - {current_time}")
    
    token = os.getenv('TINKOFF_API_TOKEN')
    if not token:
        logger.error("❌ TINKOFF_API_TOKEN не найден")
        is_trading = False
        return
    
    try:
        with Client(token) as client:
            accounts = client.users.get_accounts()
            if not accounts.accounts:
                logger.error("❌ Нет доступных счетов")
                is_trading = False
                return
                
            account_id = accounts.accounts[0].id
            
            current_prices = {}
            for ticker, figi in INSTRUMENTS.items():
                last_price = client.market_data.get_last_prices(figi=[figi])
                if last_price.last_prices:
                    price_obj = last_price.last_prices[0].price
                    price = price_obj.units + price_obj.nano / 1e9
                    current_prices[ticker] = price
            
            logger.info(f"📊 ЦЕНЫ: SBER={current_prices.get('SBER', 0):.2f}, VTBR={current_prices.get('VTBR', 0):.3f}")
            
            try:
                portfolio = client.operations.get_portfolio(account_id=account_id)
                real_portfolio_value = portfolio.total_amount_portfolio.units + portfolio.total_amount_portfolio.nano/1e9
            except:
                real_portfolio_value = 0
                logger.warning("⚠️ Не удалось получить реальный портфель")
            
            if 'virtual_portfolio' not in globals():
                global virtual_portfolio
                virtual_portfolio = VirtualPortfolioPro(100000)
            
            strategy = PairsTradingStrategy(client, account_id)
            
            exit_signals = virtual_portfolio.check_exit_conditions(current_prices)
            
            signals = await strategy.analyze(INSTRUMENTS, force_mode=force_mode)
            
            strategy_stats = strategy.get_stats()
            
            all_signals = signals + exit_signals
            executed_trades = []
            
            for signal in all_signals:
                ticker = signal['ticker']
                if ticker in current_prices:
                    trade_result = virtual_portfolio.execute_trade(signal, current_prices[ticker])
                    executed_trades.append(trade_result)
            
            trade_history.extend(executed_trades)
            
            virtual_positions = {}
            for ticker, pos in virtual_portfolio.positions.items():
                virtual_positions[ticker] = {
                    'size': pos['size'],
                    'avg_price': pos['avg_price'],
                    'current_value': current_prices.get(ticker, 0) * pos['size'],
                    'profit': (current_prices.get(ticker, 0) - pos['avg_price']) * pos['size'] if ticker in current_prices else 0
                }
            
            session_profit = sum(trade.get('profit', 0) for trade in executed_trades)
            total_virtual_profit += session_profit
            
            total_value = virtual_portfolio.get_total_value(current_prices)
            virtual_portfolio_value = total_value
            total_virtual_return = ((total_value - 100000) / 100000) * 100
            
            portfolio_stats = virtual_portfolio.get_stats()
            
            logger.info(f"💰 СЕССИЯ #{session_count} ЗАВЕРШЕНА")
            logger.info(f"💎 ПОРТФЕЛЬ: {total_value:.2f} руб. ({total_virtual_return:+.2f}%)")
            logger.info(f"🎯 ПРИБЫЛЬ ЗА СЕССИЮ: {session_profit:+.2f} руб.")
            logger.info(f"📊 СТАТИСТИКА: {portfolio_stats['total_trades']} сделок, Win Rate: {portfolio_stats['win_rate']:.1f}%")
            logger.info(f"🧠 ИИ СТАТИСТИКА: {strategy_stats.get('ai_decisions', 0)} решений ({strategy_stats.get('ai_percentage', 0):.1f}%)")
            
            if virtual_positions:
                logger.info(f"🏦 ПОЗИЦИИ:")
                for ticker, pos in virtual_positions.items():
                    logger.info(f"   {ticker}: {pos['size']} акций по {pos['avg_price']:.2f} (прибыль: {pos['profit']:+.2f})")
            
            bot_status = f"🤖 AI TRADING PRO - {total_virtual_return:+.1f}% ROI - Win Rate: {portfolio_stats['win_rate']:.1f}%"
            
    except Exception as e:
        logger.error(f"❌ Ошибка торговой сессии: {str(e)[:200]}")
    finally:
        is_trading = False

def run_trading_session(force_mode=False):
    thread = threading.Thread(target=lambda: asyncio.run(trading_session_async(force_mode)))
    thread.daemon = True
    thread.start()

def schedule_tasks():
    schedule.clear()
    
    check_interval = int(os.getenv("CHECK_INTERVAL_MINUTES", 15))
    
    if check_interval == 15:
        for hour in range(10, 20):
            schedule.every().day.at(f"{hour:02d}:00").do(lambda: run_trading_session(False))
            schedule.every().day.at(f"{hour:02d}:15").do(lambda: run_trading_session(False))
            schedule.every().day.at(f"{hour:02d}:30").do(lambda: run_trading_session(False))
            schedule.every().day.at(f"{hour:02d}:45").do(lambda: run_trading_session(False))
        logger.info(f"📅 Планировщик настроен: каждые 15 минут с 10:00 до 19:45")
    else:
        schedule.every(check_interval).minutes.do(lambda: run_trading_session(False))
        logger.info(f"📅 Планировщик настроен: каждые {check_interval} минут")

def run_scheduler():
    while True:
        schedule.run_pending()
        time.sleep(1)

@app.route('/')
def home():
    global request_count
    request_count += 1
    uptime = datetime.datetime.now() - start_time
    
    portfolio_stats = virtual_portfolio.get_stats() if 'virtual_portfolio' in globals() else {}
    
    return f"""
    <html>
        <head>
            <title>AI Pairs Trading Bot PRO</title>
            <meta http-equiv="refresh" content="30">
            <style>
                body {{ font-family: Arial, sans-serif; margin: 40px; background: #0f172a; color: #f1f5f9; }}
                .container {{ max-width: 1200px; margin: 0 auto; }}
                .header {{ background: linear-gradient(135deg, #1e40af, #7c3aed); padding: 25px; border-radius: 15px; margin-bottom: 25px; }}
                .card {{ background: #1e293b; padding: 20px; border-radius: 10px; margin-bottom: 15px; border-left: 4px solid #3b82f6; }}
                .grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 20px; }}
                .positive {{ color: #10b981; }}
                .negative {{ color: #ef4444; }}
                .stats {{ background: #334155; padding: 15px; border-radius: 8px; }}
                .btn {{ display: inline-block; padding: 10px 20px; margin: 5px; border-radius: 5px; text-decoration: none; font-weight: bold; }}
                .btn-primary {{ background: #3b82f6; color: white; }}
                .btn-success {{ background: #10b981; color: white; }}
                .btn-warning {{ background: #f59e0b; color: white; }}
                .btn-danger {{ background: #ef4444; color: white; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>🤖 AI PAIRS TRADING BOT PRO</h1>
                    <p><strong>⚡ Режим:</strong> АГРЕССИВНОЕ ТЕСТИРОВАНИЕ | SBER/VTBR Парный арбитраж</p>
                </div>
                
                <div class="grid">
                    <div class="card">
                        <h3>📊 ОСНОВНЫЕ МЕТРИКИ</h3>
                        <p><strong>🚀 Статус:</strong> {bot_status}</p>
                        <p><strong>⏰ Аптайм:</strong> {str(uptime).split('.')[0]}</p>
                        <p><strong>📈 Запросы:</strong> {request_count}</p>
                        <p><strong>🕒 Последняя торговля:</strong> {last_trading_time}</p>
                        <p><strong>🔢 Сессии:</strong> {session_count}</p>
                    </div>
                    
                    <div class="card">
                        <h3>💰 ПОРТФЕЛИ</h3>
                        <p><strong>💎 Реальный портфель:</strong> {real_portfolio_value:.2f} руб.</p>
                        <p><strong>🏦 Виртуальный портфель:</strong> {virtual_portfolio_value:.2f} руб.</p>
                        <p><strong>📈 Виртуальная доходность:</strong> 
                            <span class="{'positive' if total_virtual_return >= 0 else 'negative'}">
                                {total_virtual_return:+.2f}%
                            </span>
                        </p>
                        <p><strong>🎯 Общая прибыль:</strong> 
                            <span class="{'positive' if total_virtual_profit >= 0 else 'negative'}">
                                {total_virtual_profit:+.2f} руб.
                            </span>
                        </p>
                    </div>
                </div>
                
                <div class="card">
                    <h3>📊 СТАТИСТИКА ТОРГОВЛИ</h3>
                    <div class="grid">
                        <div class="stats">
                            <h4>🧮 Сделки</h4>
                            <p>Всего: {portfolio_stats.get('total_trades', 0)}</p>
                            <p>Успешных: {portfolio_stats.get('winning_trades', 0)}</p>
                            <p>Win Rate: <span class="{'positive' if portfolio_stats.get('win_rate', 0) > 50 else 'negative'}">
                                {portfolio_stats.get('win_rate', 0):.1f}%
                            </span></p>
                        </div>
                        
                        <div class="stats">
                            <h4>🧠 ИИ Аналитика</h4>
                            <p>Решений ИИ: {strategy_stats.get('ai_decisions', 0)}</p>
                            <p>Локальных: {strategy_stats.get('local_decisions', 0)}</p>
                            <p>Доля ИИ: {strategy_stats.get('ai_percentage', 0):.1f}%</p>
                        </div>
                        
                        <div class="stats">
                            <h4>🏦 Позиции</h4>
                            {f"""
                            <p><strong>Свободных средств:</strong> {portfolio_stats.get('cash', 0):.0f} руб.</p>
                            <p><strong>Активных позиций:</strong> {portfolio_stats.get('current_positions', 0)}</p>
                            """ if portfolio_stats else "<p>Нет данных о позициях</p>"}
                            {f"""
                            <p><strong>Позиции:</strong> {len(virtual_positions) if virtual_positions else 'Нет'}</p>
                            """ if virtual_positions else ""}
                        </div>
                    </div>
                </div>
                
                <div class="card">
                    <h3>⚡ БЫСТРЫЕ ДЕЙСТВИЯ</h3>
                    <p>
                        <a href="/status" class="btn btn-primary">📊 JSON Status</a>
                        <a href="/force" class="btn btn-success">🚀 Force Trade</a>
                        <a href="/trades" class="btn btn-warning">📋 Trade History</a>
                        <a href="/stats" class="btn btn-primary">📈 Detailed Stats</a>
                        <a href="/analyze" class="btn btn-danger">🧠 AI Analysis Only</a>
                    </p>
                </div>
                
                <p style="color: #94a3b8; text-align: center; margin-top: 30px;">
                    <em>🤖 Парный арбитраж SBER/VTBR | Агрессивный тестовый режим | ИИ-оптимизация PRO</em>
                </p>
            </div>
        </body>
    </html>
    """

@app.route('/status')
def status():
    portfolio_stats = virtual_portfolio.get_stats() if 'virtual_portfolio' in globals() else {}
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
        "portfolio_stats": portfolio_stats,
        "strategy_stats": strategy_stats,
        "timestamp": datetime.datetime.now().isoformat(),
        "strategy": "SBER/VTBR Pairs Trading with AI PRO",
        "trading_mode": os.getenv("TRADING_MODE", "AGGRESSIVE_TEST"),
        "check_interval": os.getenv("CHECK_INTERVAL_MINUTES", 15),
        "ai_enabled": strategy_stats.get('ai_enabled', False),
        "current_time": datetime.datetime.now().strftime("%H:%M:%S"),
        "server_time": datetime.datetime.now().isoformat()
    })

@app.route('/force')
def force_trade():
    run_trading_session(force_mode=True)
    return jsonify({
        "message": "🚀 ПРИНУДИТЕЛЬНЫЙ ЗАПУСК ТОРГОВЛИ (агрессивный режим)",
        "timestamp": datetime.datetime.now().isoformat(),
        "force_mode": True,
        "warning": "Временные ограничения отключены, ИИ анализирует всегда"
    })

@app.route('/trades')
def show_trades():
    portfolio_stats = virtual_portfolio.get_stats() if 'virtual_portfolio' in globals() else {}
    
    trades_html = ""
    for trade in trade_history[-20:]:
        if trade['action'] == 'BUY':
            color = "#10b981"
            icon = "🟢"
        else:
            if trade.get('profit', 0) > 0:
                color = "#10b981"
                icon = "💰"
            elif trade.get('profit', 0) < 0:
                color = "#ef4444"
                icon = "💸"
            else:
                color = "#6b7280"
                icon = "⚪"
        
        ai_badge = " 🧠" if trade.get('ai_generated') else ""
        profit_html = ""
        if trade.get('profit', 0) != 0:
            profit_class = "positive" if trade.get('profit', 0) > 0 else "negative"
            profit_html = f"<br><span class='{profit_class}'>💰 Прибыль: {trade.get('profit', 0):+.2f} руб. ({trade.get('profit_percent', 0):+.1f}%)</span>"
        
        confidence_html = f"<br>🎯 Confidence: {trade.get('confidence', 0):.2f}" if trade.get('confidence') else ""
        
        trades_html += f"""
        <div style="background: {color}20; border-left: 4px solid {color}; padding: 15px; margin: 10px 0; border-radius: 5px;">
            {icon}{ai_badge} {trade['timestamp']} | {trade['strategy']}
            <br><strong>{trade['action']} {trade['ticker']}</strong> x{trade['size']} по {trade['price']} руб.
            {profit_html}
            {confidence_html}
            <br><small>💡 {trade.get('reason', '')}</small>
        </div>
        """
    
    return f"""
    <html>
        <head><title>История Сделок</title>
        <style>
            body {{ font-family: Arial; margin: 40px; background: #0f172a; color: white; }}
            .positive {{ color: #10b981; }}
            .negative {{ color: #ef4444; }}
            .container {{ max-width: 800px; margin: 0 auto; }}
            .stats {{ background: #1e293b; padding: 20px; border-radius: 10px; margin: 20px 0; }}
        </style>
        </head>
        <body>
            <div class="container">
                <h1>📋 История Сделок</h1>
                
                <div class="stats">
                    <p><strong>Всего сделок:</strong> {len(trade_history)}</p>
                    <p><strong>Портфель:</strong> {virtual_portfolio_value:.2f} руб. (<span class="{{'positive' if total_virtual_return >= 0 else 'negative'}}">{total_virtual_return:+.2f}%</span>)</p>
                    <p><strong>Общая прибыль:</strong> <span class="{{'positive' if total_virtual_profit >= 0 else 'negative'}}">{total_virtual_profit:+.2f} руб.</span></p>
                    <p><strong>Win Rate:</strong> {portfolio_stats.get('win_rate', 0):.1f}% ({portfolio_stats.get('winning_trades', 0)}/{portfolio_stats.get('total_trades', 0)})</p>
                </div>
                
                {trades_html if trade_history else "<p>Сделок еще нет</p>"}
                
                <p style="margin-top: 30px;">
                    <a href="/" style="background: #3b82f6; color: white; padding: 10px 15px; text-decoration: none; border-radius: 5px;">← На главную</a>
                </p>
            </div>
        </body>
    </html>
    """

@app.route('/stats')
def detailed_stats():
    portfolio_stats = virtual_portfolio.get_stats() if 'virtual_portfolio' in globals() else {}
    
    ai_trades = [t for t in trade_history if t.get('ai_generated')]
    local_trades = [t for t in trade_history if not t.get('ai_generated')]
    
    ai_profits = [t.get('profit', 0) for t in ai_trades if t.get('profit')]
    local_profits = [t.get('profit', 0) for t in local_trades if t.get('profit')]
    
    ai_avg = sum(ai_profits)/len(ai_profits) if ai_profits else 0
    local_avg = sum(local_profits)/len(local_profits) if local_profits else 0
    
    return jsonify({
        "performance_summary": {
            "total_trades": len(trade_history),
            "ai_trades": len(ai_trades),
            "local_trades": len(local_trades),
            "win_rate": portfolio_stats.get('win_rate', 0),
            "total_profit": total_virtual_profit,
            "virtual_return": total_virtual_return,
            "portfolio_value": virtual_portfolio_value
        },
        "ai_performance": {
            "total_signals": strategy_stats.get('ai_decisions', 0),
            "executed_trades": len(ai_trades),
            "avg_profit_per_trade": ai_avg,
            "success_rate": (len([p for p in ai_profits if p > 0]) / len(ai_profits) * 100) if ai_profits else 0,
            "total_ai_profit": sum(ai_profits)
        },
        "local_performance": {
            "total_signals": strategy_stats.get('local_decisions', 0),
            "executed_trades": len(local_trades),
            "avg_profit_per_trade": local_avg,
            "success_rate": (len([p for p in local_profits if p > 0]) / len(local_profits) * 100) if local_profits else 0,
            "total_local_profit": sum(local_profits)
        },
        "current_market": {
            "real_portfolio": real_portfolio_value,
            "virtual_positions_count": len(virtual_positions),
            "available_cash": portfolio_stats.get('cash', 0),
            "session_count": session_count
        },
        "strategy_metrics": strategy_stats
    })

@app.route('/analyze')
def analyze_only():
    """Только анализ без торговли (для тестирования ИИ)"""
    async def analyze_async():
        token = os.getenv('TINKOFF_API_TOKEN')
        if not token:
            return {"error": "No TINKOFF_API_TOKEN"}
        
        with Client(token) as client:
            accounts = client.users.get_accounts()
            if not accounts.accounts:
                return {"error": "No accounts"}
            
            account_id = accounts.accounts[0].id
            strategy = PairsTradingStrategy(client, account_id)
            signals = await strategy.analyze(INSTRUMENTS, force_mode=True)
            
            return {
                "analysis_time": datetime.datetime.now().isoformat(),
                "signals_found": len(signals),
                "signals": signals,
                "strategy_stats": strategy.get_stats()
            }
    
    result = asyncio.run(analyze_async())
    return jsonify(result)

if __name__ == '__main__':
    schedule_tasks()
    scheduler_thread = threading.Thread(target=run_scheduler)
    scheduler_thread.daemon = True
    scheduler_thread.start()
    
    logger.info("=" * 60)
    logger.info("🚀 AI PAIRS TRADING BOT PRO STARTED!")
    logger.info("🎯 Стратегия: Агрессивный парный арбитраж SBER/VTBR")
    logger.info("🧠 ИИ включен: Да (OpenRouter API)")
    logger.info("💰 Стартовый капитал: 100,000 руб.")
    logger.info(f"⚡ Режим: {os.getenv('TRADING_MODE', 'AGGRESSIVE_TEST')}")
    logger.info(f"⏰ Проверки: каждые {os.getenv('CHECK_INTERVAL_MINUTES', 15)} минут")
    logger.info("📊 TP/SL: 3.0%/1.8% (агрессивный тест)")
    logger.info("🌐 Веб-интерфейс: http://0.0.0.0:10000")
    logger.info("=" * 60)
    
    app.run(host='0.0.0.0', port=10000, debug=False, use_reloader=False)
