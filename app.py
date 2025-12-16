# app.py - NEUROTRADER PRO INTERFACE
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

# --- SYSTEM LOGS (Hidden on main page) ---
log_buffer = deque(maxlen=300)
class WebLogHandler(logging.Handler):
    def emit(self, record):
        try:
            msg = self.format(record)
            color = "#8b949e"
            if "BUY" in msg: color = "#2ea043"
            elif "SELL" in msg: color = "#da3633"
            elif "ERROR" in msg: color = "#f85149"
            elif "GigaChat" in msg: color = "#238636"
            
            time_str = datetime.now().strftime("%H:%M:%S")
            html = f'<div style="color:{color};border-bottom:1px solid #21262d;padding:2px 0;">' \
                   f'<span style="opacity:0.5;margin-right:10px;">{time_str}</span>{msg}</div>'
            log_buffer.append(html)
        except: pass

logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger()
logger.handlers.clear()
logger.addHandler(logging.StreamHandler())
logger.addHandler(WebLogHandler())

# --- MODULES ---
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
    logger.critical(f"Import Error: {e}")

app = Flask(__name__)
bot_status = "ONLINE"

# --- INIT ---
finam_client = FinamClient()
news_fetcher = NewsFetcher()
nlp_engine = NlpEngine()
risk_manager = RiskManager(initial_capital=100000)
virtual_portfolio = VirtualPortfolioPro(initial_capital=100000)
news_prefilter = NewsPreFilter()
technical_strategy = TechnicalStrategy(finam_client)

class FinamAdapter:
    def __init__(self, c): self.c = c
    async def get_current_prices(self, t):
        p = {}
        for x in t: 
            val = await self.c.get_current_price(x)
            if val: p[x] = val
        return p

verifier = FinamAdapter(finam_client)
pipeline = SignalPipeline(nlp_engine, verifier, risk_manager, EnhancedAnalyzer(), news_prefilter, technical_strategy)

# --- WORKER ---
async def trading_task():
    global bot_status
    if bot_status == "SCANNING": return
    bot_status = "SCANNING"
    
    try:
        news = await news_fetcher.fetch_all_news()
        signals = await pipeline.process_news_batch(news)
        
        # Portfolio Update
        all_tickers = set([s['ticker'] for s in signals] + list(virtual_portfolio.positions.keys()))
        prices = await verifier.get_current_prices(list(all_tickers))
        
        # Exits
        for exit_sig in virtual_portfolio.check_exit_conditions(prices):
            virtual_portfolio.execute_trade(exit_sig, prices.get(exit_sig['ticker']))
            
        # Entries
        for sig in signals:
            if sig['ticker'] in prices and sig['action'] == 'BUY':
                virtual_portfolio.execute_trade(sig, prices[sig['ticker']])
                
    except Exception as e:
        logger.error(f"Task Error: {e}")
    finally:
        bot_status = "ONLINE"

def run_worker():
    threading.Thread(target=lambda: asyncio.run(trading_task())).start()

# --- WEB UI ---
NAV_HTML = """
<div style="background:#161b22; border-bottom:1px solid #30363d; padding:0 20px;">
    <div style="max-width:1200px; margin:0 auto; display:flex; height:60px; align-items:center; justify-content:space-between;">
        <div style="font-weight:700; font-size:18px; color:#f0f6fc; display:flex; align-items:center; gap:10px;">
            <i class="fas fa-chart-line" style="color:#238636;"></i> NeuroTrader Pro
        </div>
        <div style="display:flex; gap:20px;">
            <a href="/" class="nav-link {{ 'active' if page == 'dash' }}">Dashboard</a>
            <a href="/analysis" class="nav-link {{ 'active' if page == 'analysis' }}">AI Analysis</a>
            <a href="/system" class="nav-link {{ 'active' if page == 'system' }}">System</a>
        </div>
        <div style="font-size:12px; color:#8b949e; display:flex; align-items:center; gap:10px;">
            <span>{{ status }}</span>
            <a href="/force" style="color:#f0f6fc; text-decoration:none; background:#238636; padding:4px 10px; border-radius:4px;">Scan</a>
        </div>
    </div>
</div>
"""

BASE_HTML = """
<!DOCTYPE html>
<html>
<head>
    <title>NeuroTrader</title>
    <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css" rel="stylesheet">
    <style>
        body { background:#0d1117; color:#c9d1d9; font-family:'Segoe UI', sans-serif; margin:0; }
        .nav-link { color:#8b949e; text-decoration:none; font-weight:600; font-size:14px; padding:18px 0; border-bottom:2px solid transparent; }
        .nav-link:hover { color:#f0f6fc; }
        .nav-link.active { color:#f0f6fc; border-bottom-color:#f78166; }
        .container { max-width:1200px; margin:20px auto; padding:0 20px; }
        .card { background:#161b22; border:1px solid #30363d; border-radius:6px; padding:20px; margin-bottom:20px; }
        .grid { display:grid; grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); gap:20px; }
        table { width:100%; border-collapse:collapse; font-size:13px; }
        th { text-align:left; color:#8b949e; padding-bottom:10px; border-bottom:1px solid #30363d; }
        td { padding:12px 0; border-bottom:1px solid #21262d; }
        .val-up { color:#238636; } .val-down { color:#da3633; }
        .ticker { background:#21262d; padding:2px 6px; border-radius:4px; font-family:monospace; font-weight:700; color:#f0f6fc; }
        .status-badge { padding:2px 8px; border-radius:10px; font-size:11px; font-weight:600; }
        .s-SIGNAL { background:rgba(35,134,54,0.2); color:#3fb950; }
        .s-FILTER { background:rgba(110,118,129,0.2); color:#8b949e; }
        .s-SKIP { background:rgba(210,153,34,0.2); color:#d29922; }
    </style>
</head>
<body>
    {{ nav|safe }}
    <div class="container">
        {{ content|safe }}
    </div>
</body>
</html>
"""

@app.route('/')
def dashboard():
    stats = virtual_portfolio.get_stats()
    
    # KPI HTML
    kpi = f"""
    <div class="grid">
        <div class="card">
            <div style="color:#8b949e; font-size:12px;">TOTAL EQUITY</div>
            <div style="font-size:24px; font-weight:300; color:#f0f6fc;">{stats['current_value']:,.0f} ₽</div>
        </div>
        <div class="card">
            <div style="color:#8b949e; font-size:12px;">CASH AVAILABLE</div>
            <div style="font-size:24px; font-weight:300;">{stats['cash']:,.0f} ₽</div>
        </div>
        <div class="card">
            <div style="color:#8b949e; font-size:12px;">TOTAL P&L</div>
            <div style="font-size:24px; font-weight:300;" class="{'val-up' if stats['total_profit'] >=0 else 'val-down'}">
                {stats['total_profit']:+,.0f} ₽
            </div>
        </div>
    </div>
    """
    
    # POSITIONS HTML
    pos_rows = ""
    for t, p in virtual_portfolio.positions.items():
        pos_rows += f"<tr><td><span class='ticker'>{t}</span></td><td>{p['size']}</td><td>{p['avg_price']:.1f}</td><td>-</td></tr>"
    
    pos_table = f"""
    <div class="card">
        <h3 style="margin-top:0; font-size:16px;">Active Positions</h3>
        <table><thead><tr><th>Asset</th><th>Size</th><th>Entry</th><th>P&L</th></tr></thead>
        <tbody>{pos_rows if pos_rows else '<tr><td colspan="4" style="text-align:center; padding:20px; color:#8b949e;">No active positions</td></tr>'}</tbody></table>
    </div>
    """
    
    # RECENT TRADES
    trade_rows = ""
    for tr in stats['trade_history'][:5]:
        color = "val-up" if tr['action'] == "BUY" else "val-down"
        trade_rows += f"<tr><td>{tr['timestamp']}</td><td class='{color}'>{tr['action']}</td><td><span class='ticker'>{tr['ticker']}</span></td><td>{tr['price']:.1f}</td></tr>"
    
    trade_table = f"""
    <div class="card">
        <h3 style="margin-top:0; font-size:16px;">Recent Executions</h3>
        <table><thead><tr><th>Time</th><th>Side</th><th>Asset</th><th>Price</th></tr></thead>
        <tbody>{trade_rows if trade_rows else '<tr><td colspan="4" style="text-align:center; color:#8b949e;">No trades yet</td></tr>'}</tbody></table>
    </div>
    """
    
    return render_template_string(BASE_HTML, nav=render_template_string(NAV_HTML, page='dash', status=bot_status), content=kpi + pos_table + trade_table)

@app.route('/analysis')
def analysis():
    history = pipeline.get_ai_history()
    
    rows = ""
    for item in history:
        badge = f"<span class='status-badge s-{item['status']}'>{item['status']}</span>"
        rows += f"""
        <tr>
            <td>{item['time']}</td>
            <td>{item['source']}</td>
            <td>{item['title']}</td>
            <td>{badge}</td>
            <td><span class='ticker'>{item['result']}</span></td>
            <td style="color:#8b949e;">{item['reason']}</td>
            <td>{item['provider']}</td>
        </tr>
        """
        
    table = f"""
    <div class="card">
        <h3 style="margin-top:0; font-size:16px;">AI Decision Feed</h3>
        <table>
            <thead><tr><th>Time</th><th>Source</th><th>News Header</th><th>Verdict</th><th>Target</th><th>Reasoning</th><th>AI Model</th></tr></thead>
            <tbody>{rows}</tbody>
        </table>
    </div>
    """
    return render_template_string(BASE_HTML, nav=render_template_string(NAV_HTML, page='analysis', status=bot_status), content=table)

@app.route('/system')
def system():
    logs = "".join(list(log_buffer))
    content = f"""
    <div class="card">
        <h3 style="margin-top:0; font-size:16px;">System Logs (Live)</h3>
        <div style="background:#000; padding:10px; border-radius:4px; font-family:monospace; height:500px; overflow-y:auto; font-size:12px;">
            {logs}
        </div>
    </div>
    """
    return render_template_string(BASE_HTML, nav=render_template_string(NAV_HTML, page='system', status=bot_status), content=content)

@app.route('/force')
def force():
    run_worker()
    return redirect(url_for('analysis'))

if __name__ == '__main__':
    schedule.every(10).minutes.do(run_worker)
    threading.Thread(target=lambda: asyncio.run(trading_task())).start()
    
    def sched():
        while True: schedule.run_pending(); time.sleep(1)
    threading.Thread(target=sched, daemon=True).start()
    
    app.run(host='0.0.0.0', port=10000)
