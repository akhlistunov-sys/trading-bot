# app.py - NEUROTRADER DARK UI + FINAM CORE
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

# --- БУФЕР ЛОГОВ ДЛЯ ВЕБ-ИНТЕРФЕЙСА ---
log_buffer = deque(maxlen=100)

class WebLogHandler(logging.Handler):
    def emit(self, record):
        try:
            msg = self.format(record)
            # Цветовая схема под темную тему
            color = "#a0a1a7" # серый по умолчанию
            if "BUY" in msg: color = "#2ecc71" # зеленый
            elif "SELL" in msg: color = "#e74c3c" # красный
            elif "ERROR" in msg: color = "#ff6b6b" # светло-красный
            elif "WARNING" in msg: color = "#f1c40f" # желтый
            elif "Finam" in msg: color = "#3498db" # голубой
            elif "Gemini" in msg: color = "#9b59b6" # фиолетовый
            
            # Форматирование времени
            time_str = datetime.now().strftime("%H:%M:%S")
            html_log = f'<div style="color: {color}; font-family: \'JetBrains Mono\', monospace; margin-bottom: 6px; font-size: 12px; border-bottom: 1px solid #2d3446; padding-bottom: 2px;"><span style="opacity:0.5; margin-right: 8px;">[{time_str}]</span>{msg}</div>'
            log_buffer.append(html_log)
        except: pass

# Настройка логгера
logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger()
# Удаляем старые хендлеры, чтобы не дублировать
if logger.hasHandlers():
    logger.handlers.clear()
logger.addHandler(logging.StreamHandler()) # В консоль
logger.addHandler(WebLogHandler())     # В веб

# --- ИМПОРТЫ МОДУЛЕЙ ---
try:
    from news_fetcher import NewsFetcher
    from nlp_engine import NlpEngine
    from finam_client import FinamClient # <-- НОВЫЙ КЛИЕНТ
    from virtual_portfolio import VirtualPortfolioPro
    from enhanced_analyzer import EnhancedAnalyzer
    from news_prefilter import NewsPreFilter
    from risk_manager import RiskManager
    from signal_pipeline import SignalPipeline
    from technical_strategy import TechnicalStrategy
except ImportError as e:
    logger.error(f"CRITICAL IMPORT ERROR: {e}")

app = Flask(__name__)
bot_status = "ONLINE"
session_count = 0

# --- ИНИЦИАЛИЗАЦИЯ ---
try:
    logger.info("🚀 System Boot: NeuroTrader AI")
    
    news_fetcher = NewsFetcher()
    nlp_engine = NlpEngine()
    finam_client = FinamClient() # Используем Finam
    
    risk_manager = RiskManager()
    enhanced_analyzer = EnhancedAnalyzer()
    news_prefilter = NewsPreFilter()
    
    # Виртуальный портфель (хранит состояние)
    virtual_portfolio = VirtualPortfolioPro(initial_capital=1250000) 
    
    # Техническая стратегия на данных Finam
    technical_strategy = TechnicalStrategy(finam_client=finam_client)

    # Адаптер для верификации (связывает FinamClient с Pipeline)
    class FinamAdapterVerifier:
        async def get_current_prices(self, tickers):
            prices = {}
            for t in tickers:
                p = await finam_client.get_current_price(t)
                if p: prices[t] = p
            return prices
        async def verify_signal(self, analysis):
            # В упрощенном режиме считаем сигнал валидным, если есть тикер
            tickers = analysis.get('tickers', [])
            return {
                'valid': bool(tickers), 
                'primary_ticker': tickers[0] if tickers else None,
                'reason': 'Finam Checked'
            }

    finam_verifier = FinamAdapterVerifier()

    signal_pipeline = SignalPipeline(
        nlp_engine, finam_verifier, risk_manager, 
        enhanced_analyzer, news_prefilter, technical_strategy
    )
    logger.info("✅ Core Systems: OPERATIONAL")

except Exception as e:
    logger.error(f"❌ System Init Failed: {e}")

# --- ТОРГОВАЯ ЛОГИКА ---
async def trading_loop_async():
    global bot_status, session_count
    if bot_status == "ANALYZING": return
    
    bot_status = "ANALYZING"
    session_count += 1
    logger.info(f"⚡ Session #{session_count}: Market Scan Started")
    
    try:
        # 1. Получение новостей
        news = await news_fetcher.fetch_all_news()
        
        # 2. Генерация сигналов (News + Tech)
        signals = await signal_pipeline.process_news_batch(news)
        
        # 3. Работа с ценами и ордерами
        if signals:
            tickers = list(set([s['ticker'] for s in signals if s.get('ticker')]))
            prices = await finam_verifier.get_current_prices(tickers)
            
            # 3.1 Проверка выходов (Stop Loss / Take Profit)
            # Получаем цены для имеющихся позиций
            portfolio_tickers = list(virtual_portfolio.positions.keys())
            portfolio_prices = await finam_verifier.get_current_prices(portfolio_tickers)
            prices.update(portfolio_prices) # Объединяем цены
            
            exits = virtual_portfolio.check_exit_conditions(prices)
            
            for exit_sig in exits:
                t = exit_sig['ticker']
                size = int(exit_sig['position_size'])
                # Исполнение в Finam
                res = await finam_client.execute_order(t, 'SELL', size)
                if res['status'] == 'EXECUTED':
                    virtual_portfolio.execute_trade(exit_sig, prices.get(t, 0))
            
            # 3.2 Проверка входов
            for sig in signals:
                t = sig['ticker']
                if t in prices and sig['action'] == 'BUY':
                    size = int(sig.get('position_size', 1))
                    # Исполнение в Finam
                    order = await finam_client.execute_order(t, 'BUY', size)
                    
                    if order['status'] == 'EXECUTED':
                        # Фиксация в портфеле
                        res = virtual_portfolio.execute_trade(sig, prices[t])
                        if res['status'] == 'EXECUTED':
                            logger.info(f"✅ CONFIRMED: BUY {size} {t} @ {prices[t]:.2f}")

    except Exception as e:
        logger.error(f"❌ Session Error: {e}")
    finally:
        bot_status = "ONLINE"
        logger.info("💤 Session Complete. Standing by.")

def run_trading_session():
    threading.Thread(target=lambda: asyncio.run(trading_loop_async())).start()

# --- WEB UI (NEUROTRADER DARK THEME) ---
HTML_TEMPLATE = '''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>NeuroTrader AI Dashboard</title>
    <!-- Icons & Fonts -->
    <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css" rel="stylesheet">
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400&display=swap" rel="stylesheet">
    
    <style>
        :root {
            --bg-dark: #13141f;
            --sidebar-bg: #161722;
            --panel-bg: #1c1e2a;
            --border-col: #2d3446;
            --accent: #7b2cbf;
            --accent-hover: #9b51e0;
            --success: #00b894;
            --danger: #ff4757;
            --text-main: #ffffff;
            --text-muted: #8b9bb4;
        }
        
        * { box-sizing: border-box; }

        body { 
            background-color: var(--bg-dark); 
            color: var(--text-main); 
            font-family: 'Inter', sans-serif; 
            margin: 0; 
            display: flex;
            height: 100vh;
            overflow: hidden;
        }

        /* SIDEBAR */
        .sidebar {
            width: 260px;
            background-color: var(--sidebar-bg);
            border-right: 1px solid var(--border-col);
            display: flex;
            flex-direction: column;
            padding: 24px;
        }
        
        .brand {
            font-size: 20px;
            font-weight: 700;
            color: white;
            display: flex;
            align-items: center;
            gap: 12px;
            margin-bottom: 40px;
        }
        .brand i { color: var(--accent); font-size: 24px; }

        .nav-item {
            display: flex;
            align-items: center;
            padding: 12px 16px;
            color: var(--text-muted);
            text-decoration: none;
            border-radius: 10px;
            margin-bottom: 8px;
            transition: 0.2s;
            font-weight: 500;
        }
        .nav-item i { width: 24px; margin-right: 8px; }
        .nav-item:hover, .nav-item.active {
            background: rgba(123, 44, 191, 0.1);
            color: var(--accent);
        }

        /* MAIN AREA */
        .main {
            flex: 1;
            padding: 32px;
            overflow-y: auto;
        }

        .header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 32px;
        }

        .page-title h1 { margin: 0; font-size: 24px; }
        .status-badge {
            font-size: 12px;
            background: rgba(0, 184, 148, 0.15);
            color: var(--success);
            padding: 6px 12px;
            border-radius: 20px;
            font-weight: 600;
            display: inline-flex;
            align-items: center;
            gap: 6px;
        }

        .analyze-btn {
            background: linear-gradient(135deg, var(--accent) 0%, var(--accent-hover) 100%);
            color: white;
            border: none;
            padding: 12px 24px;
            border-radius: 8px;
            font-weight: 600;
            cursor: pointer;
            text-decoration: none;
            display: inline-flex;
            align-items: center;
            gap: 8px;
            box-shadow: 0 4px 12px rgba(123, 44, 191, 0.3);
            transition: transform 0.2s;
        }
        .analyze-btn:hover { transform: translateY(-2px); }

        /* KPI CARDS */
        .grid-kpi {
            display: grid;
            grid-template-columns: repeat(4, 1fr);
            gap: 24px;
            margin-bottom: 32px;
        }

        .card {
            background: var(--panel-bg);
            border-radius: 16px;
            padding: 24px;
            border: 1px solid var(--border-col);
            position: relative;
            overflow: hidden;
        }

        .kpi-label { color: var(--text-muted); font-size: 12px; font-weight: 600; letter-spacing: 0.5px; text-transform: uppercase; margin-bottom: 8px; }
        .kpi-value { font-size: 28px; font-weight: 700; color: white; margin-bottom: 4px; }
        .kpi-sub { font-size: 13px; font-weight: 500; }
        .text-up { color: var(--success); }
        .text-down { color: var(--danger); }
        
        .card-icon {
            position: absolute;
            top: 24px; right: 24px;
            font-size: 24px;
            color: var(--text-muted);
            opacity: 0.2;
        }

        /* CONTENT GRID */
        .grid-content {
            display: grid;
            grid-template-columns: 2fr 1fr;
            gap: 24px;
            height: 500px;
        }

        .panel-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 20px;
        }
        .panel-title { font-size: 16px; font-weight: 600; }

        /* TABLE */
        table { width: 100%; border-collapse: collapse; }
        th { text-align: left; color: var(--text-muted); font-size: 12px; font-weight: 600; padding-bottom: 12px; border-bottom: 1px solid var(--border-col); }
        td { padding: 16px 0; border-bottom: 1px solid rgba(255,255,255,0.05); font-size: 14px; }
        .ticker-badge { background: rgba(255,255,255,0.05); padding: 4px 8px; border-radius: 4px; font-weight: 600; font-family: 'JetBrains Mono', monospace; }

        /* LOGS */
        .log-container {
            background: #0f1016;
            border-radius: 12px;
            padding: 16px;
            height: 420px;
            overflow-y: auto;
            border: 1px solid var(--border-col);
        }
        
        /* SCROLLBAR */
        ::-webkit-scrollbar { width: 6px; }
        ::-webkit-scrollbar-track { background: transparent; }
        ::-webkit-scrollbar-thumb { background: #3c4050; border-radius: 3px; }

    </style>
</head>
<body>

    <!-- SIDEBAR -->
    <div class="sidebar">
        <div class="brand">
            <i class="fas fa-brain"></i>
            <span>NeuroTrader</span>
        </div>
        
        <a href="/" class="nav-item active"><i class="fas fa-th-large"></i> Dashboard</a>
        <a href="/trades" class="nav-item"><i class="fas fa-history"></i> Trade History</a>
        <a href="/settings" class="nav-item"><i class="fas fa-cog"></i> Settings</a>
        
        <div style="margin-top: auto; padding-top: 20px; border-top: 1px solid var(--border-col);">
            <div style="color: var(--text-muted); font-size: 12px;">Server Status</div>
            <div style="display:flex; align-items:center; gap:6px; margin-top:6px; font-size:13px;">
                <div style="width:8px; height:8px; background:var(--success); border-radius:50%; box-shadow: 0 0 8px var(--success);"></div>
                Connected (Finam)
            </div>
        </div>
    </div>

    <!-- MAIN -->
    <div class="main">
        
        <!-- HEADER -->
        <div class="header">
            <div class="page-title">
                <h1>AI Market Dashboard</h1>
                <div class="status-badge">
                    <i class="fas fa-circle" style="font-size: 6px;"></i> {{ status }}
                </div>
            </div>
            <a href="/force" class="analyze-btn">
                <i class="fas fa-bolt"></i> Analyze Market
            </a>
        </div>

        <!-- KPI GRID -->
        <div class="grid-kpi">
            <div class="card">
                <div class="kpi-label">Portfolio Value</div>
                <div class="kpi-value">{{ "{:,.0f}".format(stats.current_value).replace(',', ' ') }} ₽</div>
                <div class="kpi-sub {% if stats.portfolio_return >= 0 %}text-up{% else %}text-down{% endif %}">
                    <i class="fas fa-chart-line"></i> {{ "{:+.2f}".format(stats.portfolio_return) }}%
                </div>
                <i class="fas fa-wallet card-icon"></i>
            </div>
            
            <div class="card">
                <div class="kpi-label">Total Profit</div>
                <div class="kpi-value {% if stats.total_profit >= 0 %}text-up{% else %}text-down{% endif %}">
                    {{ "{:+,.0f}".format(stats.total_profit).replace(',', ' ') }} ₽
                </div>
                <div class="kpi-sub" style="color: var(--text-muted);">All time</div>
                <i class="fas fa-coins card-icon"></i>
            </div>
            
            <div class="card">
                <div class="kpi-label">Total Trades</div>
                <div class="kpi-value">{{ stats.total_trades|default(0) }}</div>
                <div class="kpi-sub" style="color: var(--text-muted);">Session #{{ session }}</div>
                <i class="fas fa-exchange-alt card-icon"></i>
            </div>

            <div class="card">
                <div class="kpi-label">Active Model</div>
                <div class="kpi-value" style="font-size: 20px;">Gemini 1.5</div>
                <div class="kpi-sub" style="color: var(--accent);">Latency: 120ms</div>
                <i class="fas fa-microchip card-icon"></i>
            </div>
        </div>

        <!-- MAIN GRID -->
        <div class="grid-content">
            
            <!-- LEFT: POSITIONS -->
            <div class="card">
                <div class="panel-header">
                    <div class="panel-title">Active Positions</div>
                    <div style="font-size: 12px; color: var(--text-muted);">{{ positions|length }} Active</div>
                </div>
                
                {% if positions %}
                <table>
                    <thead>
                        <tr>
                            <th>ASSET</th>
                            <th>SIZE</th>
                            <th>ENTRY</th>
                            <th>VALUE</th>
                        </tr>
                    </thead>
                    <tbody>
                        {% for t, p in positions.items() %}
                        <tr>
                            <td><span class="ticker-badge">{{ t }}</span></td>
                            <td style="font-weight:600;">{{ p.size }}</td>
                            <td style="color:var(--text-muted);">{{ "{:.2f}".format(p.avg_price) }}</td>
                            <td style="color:var(--text-main);">{{ "{:,.0f}".format(p.size * p.avg_price).replace(',', ' ') }} ₽</td>
                        </tr>
                        {% endfor %}
                    </tbody>
                </table>
                {% else %}
                <div style="display:flex; flex-direction:column; align-items:center; justify-content:center; height:200px; color:var(--text-muted);">
                    <i class="fas fa-box-open" style="font-size:32px; margin-bottom:12px; opacity:0.3;"></i>
                    No active positions
                </div>
                {% endif %}
            </div>

            <!-- RIGHT: LOGS -->
            <div class="card">
                <div class="panel-header">
                    <div class="panel-title">Live AI Signals</div>
                    <div class="status-badge" style="background:rgba(123, 44, 191, 0.1); color:var(--accent);">Live</div>
                </div>
                <div class="log-container" id="logBox">
                    {% for log in logs %}
                        {{ log|safe }}
                    {% endfor %}
                </div>
            </div>
            
        </div>
    </div>

    <script>
        // Auto-scroll logs
        var logBox = document.getElementById("logBox");
        logBox.scrollTop = logBox.scrollHeight;
        
        // Auto-refresh logic (only if not scrolling manually)
        setTimeout(function(){ 
            location.reload(); 
        }, 10000); // 10 seconds refresh
    </script>
</body>
</html>
'''

# --- МАРШРУТЫ ---
@app.route('/')
def dashboard():
    stats = virtual_portfolio.get_stats()
    return render_template_string(
        HTML_TEMPLATE, 
        stats=stats, 
        positions=virtual_portfolio.positions,
        logs=list(log_buffer),
        status=bot_status,
        session=session_count
    )

@app.route('/force')
def force():
    run_trading_session()
    return redirect(url_for('dashboard'))

# --- ЗАПУСК ---
if __name__ == '__main__':
    # Планировщик (каждые 15 минут)
    schedule.every(15).minutes.do(run_trading_session)
    
    # Фоновый поток для планировщика
    def schedule_loop():
        while True:
            schedule.run_pending()
            time.sleep(1)
    
    threading.Thread(target=schedule_loop, daemon=True).start()
    
    # Запуск сервера
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
