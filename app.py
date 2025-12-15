# app.py - С ЛОГАМИ, МЕНЮ И ПЕРСИСТЕНТНОСТЬЮ
from flask import Flask, jsonify, render_template_string, request, redirect, url_for
import datetime
import time
import threading
import schedule
import logging
import os
import asyncio
from collections import deque
from dotenv import load_dotenv

load_dotenv(override=True)

# БУФЕР ЛОГОВ (Для вывода на сайт)
log_buffer = deque(maxlen=100)

class WebLogHandler(logging.Handler):
    def emit(self, record):
        try:
            msg = self.format(record)
            color = "#a0a0a0" # серый
            if "BUY" in msg or "TRADE" in msg: color = "#00b894" # зеленый
            elif "SELL" in msg: color = "#ff4757" # красный
            elif "GigaChat" in msg: color = "#0984e3" # синий
            elif "WARNING" in msg: color = "#fdcb6e" # желтый
            elif "ERROR" in msg: color = "#d63031" # темно-красный
            
            html_log = f'<div style="color: {color}; font-family: monospace; margin-bottom: 4px;">{msg}</div>'
            log_buffer.append(html_log)
        except: pass

# Настройка логгера
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger()
logger.addHandler(WebLogHandler())

# Импорты
try:
    from news_fetcher import NewsFetcher
    from nlp_engine import NlpEngine
    from decision_engine import DecisionEngine
    from tinkoff_executor import TinkoffExecutor
    from virtual_portfolio import VirtualPortfolioPro
    from enhanced_analyzer import EnhancedAnalyzer
    from news_prefilter import NewsPreFilter
    from finam_verifier import FinamVerifier
    from risk_manager import RiskManager
    from signal_pipeline import SignalPipeline
    from technical_strategy import TechnicalStrategy
except ImportError as e:
    logger.error(f"Import Error: {e}")
    raise

app = Flask(__name__)

# Глобальные объекты
bot_status = "ONLINE"
session_count = 0
last_signals = []

# Инициализация
news_fetcher = NewsFetcher()
nlp_engine = NlpEngine()
finam_verifier = FinamVerifier()
risk_manager = RiskManager()
enhanced_analyzer = EnhancedAnalyzer()
news_prefilter = NewsPreFilter()
tinkoff_executor = TinkoffExecutor()
virtual_portfolio = VirtualPortfolioPro(initial_capital=100000)
technical_strategy = TechnicalStrategy(tinkoff_executor=tinkoff_executor)

signal_pipeline = SignalPipeline(
    nlp_engine, finam_verifier, risk_manager, 
    enhanced_analyzer, news_prefilter, technical_strategy
)

# --- HTML TEMPLATE ---
HTML_TEMPLATE = '''
<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>NeuroTrader Pro</title>
    <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css" rel="stylesheet">
    <style>
        :root { --bg: #13141f; --card: #1c1e2a; --accent: #7b2cbf; --text: #fff; }
        body { background: var(--bg); color: var(--text); font-family: sans-serif; margin: 0; display: flex; }
        .sidebar { width: 250px; background: #161722; padding: 20px; height: 100vh; position: fixed; }
        .main { margin-left: 250px; padding: 30px; width: 100%; }
        .nav-item { display: block; padding: 12px; color: #a0a0a0; text-decoration: none; border-radius: 8px; margin-bottom: 5px; }
        .nav-item:hover, .nav-item.active { background: rgba(123, 44, 191, 0.2); color: var(--accent); }
        .card { background: var(--card); padding: 20px; border-radius: 12px; margin-bottom: 20px; }
        .log-console { background: #000; padding: 15px; border-radius: 8px; height: 400px; overflow-y: auto; font-size: 13px; border: 1px solid #333; }
        .kpi-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 20px; margin-bottom: 30px; }
        .btn { background: var(--accent); color: white; padding: 10px 20px; border: none; border-radius: 6px; cursor: pointer; text-decoration: none; }
        table { width: 100%; border-collapse: collapse; }
        th, td { padding: 12px; text-align: left; border-bottom: 1px solid #333; }
    </style>
</head>
<body>
    <div class="sidebar">
        <h2 style="color: var(--accent); margin-bottom: 30px;"><i class="fas fa-brain"></i> NeuroTrader</h2>
        <a href="/" class="nav-item {% if page=='dashboard' %}active{% endif %}"><i class="fas fa-th-large"></i> Dashboard</a>
        <a href="/trades" class="nav-item {% if page=='trades' %}active{% endif %}"><i class="fas fa-history"></i> Trades</a>
        <a href="/logs" class="nav-item {% if page=='logs' %}active{% endif %}"><i class="fas fa-terminal"></i> Live Logs</a>
    </div>

    <div class="main">
        {% block content %}{% endblock %}
    </div>
</body>
</html>
'''

DASHBOARD_CONTENT = '''
{% extends "base" %}
{% block content %}
    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 30px;">
        <h1>Dashboard</h1>
        <a href="/force" class="btn"><i class="fas fa-bolt"></i> Run Analysis</a>
    </div>

    <div class="kpi-grid">
        <div class="card">
            <div style="color: #a0a0a0; font-size: 0.9em;">PORTFOLIO VALUE</div>
            <div style="font-size: 1.8em; font-weight: bold;">{{ "{:,.0f}".format(stats.current_value|default(0)).replace(",", " ") }} ₽</div>
            <div style="color: {% if stats.portfolio_return >= 0 %}#00b894{% else %}#ff4757{% endif %}">
                {{ "%+.2f"|format(stats.portfolio_return|default(0)) }}%
            </div>
        </div>
        <div class="card">
            <div style="color: #a0a0a0; font-size: 0.9em;">CASH BALANCE</div>
            <div style="font-size: 1.8em; font-weight: bold;">{{ "{:,.0f}".format(stats.cash|default(0)).replace(",", " ") }} ₽</div>
        </div>
        <div class="card">
            <div style="color: #a0a0a0; font-size: 0.9em;">ACTIVE POSITIONS</div>
            <div style="font-size: 1.8em; font-weight: bold;">{{ stats.positions_count|default(0) }}</div>
        </div>
        <div class="card">
            <div style="color: #a0a0a0; font-size: 0.9em;">TOTAL PROFIT</div>
            <div style="font-size: 1.8em; font-weight: bold; color: {% if stats.total_profit >= 0 %}#00b894{% else %}#ff4757{% endif %}">
                {{ "%+.0f"|format(stats.total_profit|default(0)) }} ₽
            </div>
        </div>
    </div>

    <div class="card">
        <h3><i class="fas fa-layer-group"></i> Active Positions</h3>
        {% if positions %}
        <table>
            <thead><tr><th>Ticker</th><th>Size</th><th>Avg Price</th><th>Value</th></tr></thead>
            <tbody>
            {% for ticker, pos in positions.items() %}
                <tr>
                    <td><b>{{ ticker }}</b></td>
                    <td>{{ pos.size }}</td>
                    <td>{{ "{:.2f}".format(pos.avg_price) }}</td>
                    <td>{{ "{:.0f}".format(pos.size * pos.avg_price) }} ₽</td>
                </tr>
            {% endfor %}
            </tbody>
        </table>
        {% else %}
            <p style="color: #666; text-align: center;">No active positions</p>
        {% endif %}
    </div>
{% endblock %}
'''

LOGS_CONTENT = '''
{% extends "base" %}
{% block content %}
    <h1><i class="fas fa-terminal"></i> System Logs</h1>
    <p style="color: #a0a0a0;">Real-time execution logs from GigaChat, Finam, and RiskManager.</p>
    <div class="log-console" id="console">
        {% for log in logs %}
            {{ log|safe }}
        {% endfor %}
    </div>
    <script>
        // Auto-scroll to bottom
        var objDiv = document.getElementById("console");
        objDiv.scrollTop = objDiv.scrollHeight;
        
        // Auto-refresh every 5 sec
        setTimeout(function(){ location.reload(); }, 5000);
    </script>
{% endblock %}
'''

TRADES_CONTENT = '''
{% extends "base" %}
{% block content %}
    <h1>Trade History</h1>
    <div class="card">
        <table>
            <thead><tr><th>Time</th><th>Action</th><th>Ticker</th><th>Price</th><th>Size</th><th>Result</th></tr></thead>
            <tbody>
            {% for trade in history|reverse %}
                <tr>
                    <td>{{ trade.timestamp[:16].replace('T', ' ') }}</td>
                    <td style="color: {% if trade.action=='BUY' %}#00b894{% else %}#ff4757{% endif %}; font-weight: bold;">{{ trade.action }}</td>
                    <td>{{ trade.ticker }}</td>
                    <td>{{ trade.price }}</td>
                    <td>{{ trade.size }}</td>
                    <td>
                        {% if trade.profit is defined %}
                            <span style="color: {% if trade.profit > 0 %}#00b894{% else %}#ff4757{% endif %}">{{ "%+.0f"|format(trade.profit) }}</span>
                        {% else %}
                            -
                        {% endif %}
                    </td>
                </tr>
            {% endfor %}
            </tbody>
        </table>
    </div>
{% endblock %}
'''

# --- ЛОГИКА ТОРГОВЛИ ---
async def trading_session_async():
    global bot_status, session_count
    if bot_status == "BUSY": return
    bot_status = "BUSY"
    session_count += 1
    logger.info(f"🏁 Запуск торговой сессии #{session_count}")
    
    try:
        # 1. Новости
        news = await news_fetcher.fetch_all_news()
        
        # 2. Технический анализ
        tech_signals = await technical_strategy.scan_for_signals()
        
        # 3. Обработка
        signals = await signal_pipeline.process_news_batch(news)
        all_signals = signals + tech_signals
        
        # 4. Исполнение
        if all_signals:
            # Получаем реальные цены
            tickers = [s['ticker'] for s in all_signals]
            prices = {}
            for t in tickers:
                p = await tinkoff_executor.get_current_price(t)
                if p: prices[t] = p
            
            # Проверка выходов
            exits = virtual_portfolio.check_exit_conditions(prices)
            for exit_sig in exits:
                virtual_portfolio.execute_trade(exit_sig, prices.get(exit_sig['ticker'], 0))
            
            # Проверка входов
            for sig in all_signals:
                t = sig['ticker']
                if t in prices:
                    virtual_portfolio.execute_trade(sig, prices[t])
                    
    except Exception as e:
        logger.error(f"Session Error: {e}")
    finally:
        bot_status = "ONLINE"
        logger.info("🏁 Сессия завершена")

def run_trading_session():
    threading.Thread(target=lambda: asyncio.run(trading_session_async())).start()

# --- МАРШРУТЫ ---
@app.route('/')
def dashboard():
    # Собираем шаблон
    full_html = HTML_TEMPLATE.replace('{% block content %}{% endblock %}', DASHBOARD_CONTENT)
    # Удаляем наследование из подшаблона, так как мы склеили вручную
    full_html = full_html.replace('{% extends "base" %}', '')
    
    return render_template_string(full_html, 
                                  page='dashboard',
                                  stats=virtual_portfolio.get_stats(),
                                  positions=virtual_portfolio.positions)

@app.route('/logs')
def logs():
    full_html = HTML_TEMPLATE.replace('{% block content %}{% endblock %}', LOGS_CONTENT)
    full_html = full_html.replace('{% extends "base" %}', '')
    return render_template_string(full_html, page='logs', logs=list(log_buffer))

@app.route('/trades')
def trades():
    full_html = HTML_TEMPLATE.replace('{% block content %}{% endblock %}', TRADES_CONTENT)
    full_html = full_html.replace('{% extends "base" %}', '')
    return render_template_string(full_html, page='trades', history=virtual_portfolio.trade_history)

@app.route('/force')
def force():
    run_trading_session()
    return redirect('/logs')

if __name__ == '__main__':
    schedule.every(20).minutes.do(run_trading_session)
    threading.Thread(target=lambda: [schedule.run_pending(), time.sleep(1)] and None).start()
    app.run(host='0.0.0.0', port=10000)
