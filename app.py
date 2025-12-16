# app.py - NEUROTRADER: WITH TRADE HISTORY CABINET
from flask import Flask, render_template_string, redirect, url_for
import time
import threading
import schedule
import logging
import asyncio
import os
from collections import deque
from datetime import datetime
from dotenv import load_dotenv

load_dotenv(override=True)

# --- БУФЕР ЛОГОВ ---
log_buffer = deque(maxlen=200)

class WebLogHandler(logging.Handler):
    def emit(self, record):
        try:
            msg = self.format(record)
            color = "#a0a1a7"
            if "BUY" in msg: color = "#2ecc71"
            elif "SELL" in msg: color = "#e74c3c"
            elif "AI SIGNAL" in msg: color = "#9b59b6" # Фиолетовый для сигналов
            elif "FILTER" in msg: color = "#565c64" # Темный для фильтра
            elif "RISK" in msg: color = "#d29922"
            
            time_str = datetime.now().strftime("%H:%M:%S")
            html_log = f'<div style="color: {color}; font-family: \'JetBrains Mono\', monospace; margin-bottom: 4px; font-size: 12px; border-bottom: 1px solid #21262d; padding-bottom: 2px;"><span style="opacity:0.5; margin-right: 8px;">{time_str}</span>{msg}</div>'
            log_buffer.append(html_log)
        except: pass

logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger()
if logger.hasHandlers(): logger.handlers.clear()
logger.addHandler(logging.StreamHandler())
logger.addHandler(WebLogHandler())

# --- ИМПОРТЫ ---
try:
    from news_fetcher import NewsFetcher
    from nlp_engine import NlpEngine
    from finam_client import FinamClient
    from virtual_portfolio import VirtualPortfolioPro
    from enhanced_analyzer import EnhancedAnalyzer
    from news_prefilter import NewsPreFilter
    from risk_manager import RiskManager
    from signal_pipeline import SignalPipeline
    from technical_strategy import TechnicalStrategy
except ImportError as e:
    logger.critical(f"❌ IMPORT ERROR: {e}")
    exit(1)

app = Flask(__name__)
bot_status = "ONLINE"
session_count = 0

# --- INIT ---
try:
    finam_client = FinamClient()
    news_fetcher = NewsFetcher()
    nlp_engine = NlpEngine()
    risk_manager = RiskManager(initial_capital=100000)
    enhanced_analyzer = EnhancedAnalyzer()
    news_prefilter = NewsPreFilter()
    technical_strategy = TechnicalStrategy(finam_client=finam_client)
    virtual_portfolio = VirtualPortfolioPro(initial_capital=100000)

    class FinamAdapterVerifier:
        def __init__(self, client): self.client = client
        async def get_current_prices(self, tickers):
            prices = {}
            for t in tickers:
                p = await self.client.get_current_price(t)
                if p: prices[t] = p
            return prices

    finam_verifier = FinamAdapterVerifier(finam_client)

    signal_pipeline = SignalPipeline(
        nlp_engine, finam_verifier, risk_manager, 
        enhanced_analyzer, news_prefilter, technical_strategy
    )
    logger.info("✅ NeuroTrader Active with Trade History")

except Exception as e:
    logger.critical(f"INIT FAIL: {e}")

# --- LOOP ---
async def trading_loop_async():
    global bot_status, session_count
    if bot_status == "ANALYZING": return
    bot_status = "ANALYZING"
    session_count += 1
    
    try:
        # 1. Новости
        news = await news_fetcher.fetch_all_news()
        
        # 2. Пайплайн (Теперь болтливый)
        signals = await signal_pipeline.process_news_batch(news)
        
        # 3. Цены и Исполнение
        tickers_check = set([s['ticker'] for s in signals])
        tickers_check.update(virtual_portfolio.positions.keys())
        prices = await finam_verifier.get_current_prices(list(tickers_check))
        
        # Выходы
        exits = virtual_portfolio.check_exit_conditions(prices)
        for exit_sig in exits:
            res = virtual_portfolio.execute_trade(exit_sig, prices.get(exit_sig['ticker']))
            if res['status'] == 'EXECUTED':
                logger.info(f"💰 PROFIT TAKING: {exit_sig['ticker']} ({res['profit']:.2f} rub)")
        
        # Входы
        for sig in signals:
            t = sig['ticker']
            if t in prices and sig['action'] == 'BUY':
                res = virtual_portfolio.execute_trade(sig, prices[t])
                if res['status'] == 'EXECUTED':
                    logger.info(f"🚀 ORDER: BUY {t} | News: {sig['reason'][:30]}...")

    except Exception as e:
        logger.error(f"Loop Error: {e}")
    finally:
        bot_status = "ONLINE"
        # Выводим статус портфеля в лог для контроля
        stats = virtual_portfolio.get_stats()
        logger.info(f"💼 Portfolio: {stats['current_value']:,.0f} RUB | Positions: {len(virtual_portfolio.positions)}")

def run_trading_session():
    threading.Thread(target=lambda: asyncio.run(trading_loop_async())).start()

# --- UI TEMPLATE ---
HTML_TEMPLATE = '''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>NeuroTrader Dashboard</title>
    <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css" rel="stylesheet">
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600&family=JetBrains+Mono:wght@400&display=swap" rel="stylesheet">
    <style>
        :root { --bg: #0d1117; --panel: #161b22; --border: #30363d; --text: #c9d1d9; --green: #238636; --red: #da3633; }
        body { background: var(--bg); color: var(--text); font-family: 'Inter', sans-serif; margin: 0; padding: 20px; }
        .grid { display: grid; grid-template-columns: 320px 1fr; gap: 20px; max-width: 1400px; margin: 0 auto; }
        .card { background: var(--panel); border: 1px solid var(--border); border-radius: 8px; padding: 20px; margin-bottom: 20px; }
        .btn { background: var(--green); color: white; padding: 8px 16px; border-radius: 6px; text-decoration: none; display: inline-block; font-weight: 600; }
        
        table { width: 100%; border-collapse: collapse; font-size: 13px; }
        th { text-align: left; color: #8b949e; padding: 8px 0; border-bottom: 1px solid var(--border); }
        td { padding: 10px 0; border-bottom: 1px solid #21262d; }
        
        .ticker { font-family: 'JetBrains Mono', monospace; font-weight: 600; background: #21262d; padding: 2px 6px; border-radius: 4px; }
        .tag-buy { color: var(--green); font-weight: 600; }
        .tag-sell { color: var(--red); font-weight: 600; }
        
        .log-container { height: 400px; overflow-y: auto; background: #000; padding: 10px; border-radius: 6px; border: 1px solid var(--border); font-family: 'JetBrains Mono', monospace; }
    </style>
</head>
<body>
    <div style="max-width: 1400px; margin: 0 auto 20px; display: flex; justify-content: space-between; align-items: center;">
        <h2 style="margin: 0;"><i class="fas fa-brain" style="color: #58a6ff;"></i> NeuroTrader AI</h2>
        <div>
            <span style="margin-right: 15px; color: #8b949e;">Status: <span style="color: var(--green);">{{ status }}</span></span>
            <a href="/force" class="btn">Force Scan</a>
        </div>
    </div>

    <div class="grid">
        <!-- LEFT COLUMN -->
        <div>
            <!-- STATS -->
            <div class="card">
                <div style="font-size: 12px; color: #8b949e; margin-bottom: 5px;">TOTAL EQUITY</div>
                <div style="font-size: 28px; font-weight: 600; margin-bottom: 20px;">{{ "{:,.0f}".format(stats.current_value) }} ₽</div>
                
                <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 10px;">
                    <div>
                        <div style="font-size: 11px; color: #8b949e;">CASH</div>
                        <div style="font-size: 16px;">{{ "{:,.0f}".format(stats.cash) }}</div>
                    </div>
                    <div>
                        <div style="font-size: 11px; color: #8b949e;">PROFIT</div>
                        <div style="font-size: 16px; color: {% if stats.total_profit >= 0 %}var(--green){% else %}var(--red){% endif %};">
                            {{ "{:+,.0f}".format(stats.total_profit) }}
                        </div>
                    </div>
                </div>
            </div>

            <!-- ACTIVE POSITIONS -->
            <div class="card">
                <h3 style="margin-top: 0; font-size: 16px;">Active Positions</h3>
                {% if positions %}
                    <table>
                        <thead><tr><th>Asset</th><th>Size</th><th>Avg</th></tr></thead>
                        <tbody>
                            {% for t, p in positions.items() %}
                            <tr>
                                <td><span class="ticker">{{ t }}</span></td>
                                <td>{{ p.size }}</td>
                                <td>{{ "{:.1f}".format(p.avg_price) }}</td>
                            </tr>
                            {% endfor %}
                        </tbody>
                    </table>
                {% else %}
                    <div style="color: #8b949e; padding: 20px 0; text-align: center;">No active positions</div>
                {% endif %}
            </div>
        </div>

        <!-- RIGHT COLUMN -->
        <div>
            <!-- TRADE HISTORY CABINET -->
            <div class="card">
                <h3 style="margin-top: 0; font-size: 16px;"><i class="fas fa-history"></i> Trade History</h3>
                <div style="max-height: 250px; overflow-y: auto;">
                    {% if stats.trade_history %}
                    <table>
                        <thead>
                            <tr>
                                <th>Time</th>
                                <th>Type</th>
                                <th>Asset</th>
                                <th>Price</th>
                                <th>Reason / News</th>
                                <th>P&L</th>
                            </tr>
                        </thead>
                        <tbody>
                            {% for trade in stats.trade_history %}
                            <tr>
                                <td style="color: #8b949e; font-size: 11px;">{{ trade.timestamp.split(' ')[1] }}</td>
                                <td class="{% if trade.action == 'BUY' %}tag-buy{% else %}tag-sell{% endif %}">{{ trade.action }}</td>
                                <td><span class="ticker">{{ trade.ticker }}</span></td>
                                <td>{{ "{:.1f}".format(trade.price) }}</td>
                                <td style="color: #a0a1a7; max-width: 200px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">
                                    {{ trade.reason }}
                                </td>
                                <td>
                                    {% if trade.profit != 0 %}
                                        <span style="color: {% if trade.profit > 0 %}var(--green){% else %}var(--red){% endif %};">
                                            {{ "{:+.0f}".format(trade.profit) }}
                                        </span>
                                    {% else %}
                                        -
                                    {% endif %}
                                </td>
                            </tr>
                            {% endfor %}
                        </tbody>
                    </table>
                    {% else %}
                        <div style="color: #8b949e; padding: 10px; text-align: center;">No trades yet</div>
                    {% endif %}
                </div>
            </div>

            <!-- SYSTEM LOGS -->
            <div class="card">
                <h3 style="margin-top: 0; font-size: 16px;">System Logs</h3>
                <div class="log-container" id="logBox">
                    {% for log in logs %}
                        {{ log|safe }}
                    {% endfor %}
                </div>
            </div>
        </div>
    </div>

    <script>
        const logBox = document.getElementById("logBox");
        logBox.scrollTop = logBox.scrollHeight;
        setTimeout(() => location.reload(), 8000);
    </script>
</body>
</html>
'''

@app.route('/')
def dashboard():
    return render_template_string(
        HTML_TEMPLATE, 
        stats=virtual_portfolio.get_stats(),
        positions=virtual_portfolio.positions,
        logs=list(log_buffer),
        status=bot_status
    )

@app.route('/force')
def force():
    run_trading_session()
    return redirect(url_for('dashboard'))

if __name__ == '__main__':
    schedule.every(10).minutes.do(run_trading_session)
    threading.Thread(target=lambda: asyncio.run(trading_loop_async())).start() # Start one immediately
    
    def schedule_loop():
        while True: schedule.run_pending(); time.sleep(1)
    threading.Thread(target=schedule_loop, daemon=True).start()
    
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 10000)))
