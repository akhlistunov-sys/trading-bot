# app.py - NEUROTRADER: GIGACHAT EDITION
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

# Загрузка переменных окружения
load_dotenv(override=True)

# --- БУФЕР ЛОГОВ ДЛЯ ВЕБ-ИНТЕРФЕЙСА ---
log_buffer = deque(maxlen=200)

class WebLogHandler(logging.Handler):
    def emit(self, record):
        try:
            msg = self.format(record)
            # Цветовая схема (Dark Mode)
            color = "#a0a1a7" # Серый (Info)
            
            if "BUY" in msg: color = "#2ecc71"    # Зеленый
            elif "SELL" in msg: color = "#e74c3c"  # Красный
            elif "ERROR" in msg or "❌" in msg: color = "#ff6b6b" # Ярко-красный
            elif "WARNING" in msg or "⚠️" in msg: color = "#f1c40f" # Желтый
            elif "GigaChat" in msg: color = "#27ae60" # Сбер-зеленый
            elif "Gemini" in msg: color = "#9b59b6"   # Фиолетовый
            elif "Finam" in msg: color = "#3498db"    # Голубой
            
            time_str = datetime.now().strftime("%H:%M:%S")
            html_log = f'<div style="color: {color}; font-family: \'JetBrains Mono\', monospace; margin-bottom: 6px; font-size: 12px; border-bottom: 1px solid #2d3446; padding-bottom: 2px;"><span style="opacity:0.5; margin-right: 8px;">[{time_str}]</span>{msg}</div>'
            log_buffer.append(html_log)
        except: pass

# Настройка логгера
logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger()
if logger.hasHandlers(): logger.handlers.clear()
logger.addHandler(logging.StreamHandler())
logger.addHandler(WebLogHandler())

# --- ИМПОРТЫ МОДУЛЕЙ ---
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

# --- ИНИЦИАЛИЗАЦИЯ СИСТЕМЫ ---
try:
    logger.info("🚀 SYSTEM BOOT: Starting NeuroTrader AI...")
    
    # 1. Данные и Новости
    finam_client = FinamClient()
    news_fetcher = NewsFetcher()
    
    # 2. Мозг (AI)
    nlp_engine = NlpEngine()
    if nlp_engine.gigachat_available:
        logger.info("🧠 AI Core: GigaChat Connected")
    elif nlp_engine.gemini_available:
        logger.info("🧠 AI Core: Gemini Connected (Backup Mode)")
    else:
        logger.warning("⚠️ AI Core: NO CONNECTION (Using Algo Fallback)")

    # 3. Стратегия и Риски
    risk_manager = RiskManager(initial_capital=100000)
    enhanced_analyzer = EnhancedAnalyzer()
    news_prefilter = NewsPreFilter()
    technical_strategy = TechnicalStrategy(finam_client=finam_client)
    
    # 4. Портфель (Виртуальный)
    virtual_portfolio = VirtualPortfolioPro(initial_capital=100000)

    # 5. Адаптер (Связывает Pipeline с FinamClient)
    class FinamAdapterVerifier:
        def __init__(self, client):
            self.client = client
            
        async def get_current_prices(self, tickers):
            """Получает цены списком"""
            prices = {}
            for t in tickers:
                p = await self.client.get_current_price(t)
                if p: prices[t] = p
            return prices
            
        async def verify_signal(self, analysis):
            """Базовая верификация"""
            tickers = analysis.get('tickers', [])
            if not tickers: return {'valid': False}
            
            # Проверяем цену главного тикера
            ticker = tickers[0]
            price = await self.client.get_current_price(ticker)
            
            return {
                'valid': bool(price and price > 0),
                'primary_ticker': ticker,
                'primary_price': price,
                'reason': 'Price check passed' if price else 'No price data'
            }

    finam_verifier = FinamAdapterVerifier(finam_client)

    # 6. Сборка Пайплайна
    signal_pipeline = SignalPipeline(
        nlp_engine, finam_verifier, risk_manager, 
        enhanced_analyzer, news_prefilter, technical_strategy
    )
    
    logger.info("✅ Core Systems: OPERATIONAL")

except Exception as e:
    logger.critical(f"❌ CRITICAL INIT FAILURE: {e}")
    raise e

# --- ТОРГОВЫЙ ЦИКЛ (ASYNC) ---
async def trading_loop_async():
    global bot_status, session_count
    if bot_status == "ANALYZING": return
    
    bot_status = "ANALYZING"
    session_count += 1
    logger.info(f"⚡ Session #{session_count}: Scanning Market...")
    
    try:
        # 1. Получение новостей
        news = await news_fetcher.fetch_all_news()
        
        # 2. Обработка пайплайном (AI + Tech)
        # Здесь происходит магия: GigaChat анализирует новости, TechStrategy смотрит RSI
        signals = await signal_pipeline.process_news_batch(news)
        
        # 3. Работа с позициями
        tickers_of_interest = set()
        if signals:
            tickers_of_interest.update([s['ticker'] for s in signals])
        tickers_of_interest.update(virtual_portfolio.positions.keys())
        
        # Получаем актуальные цены для всего списка
        current_prices = await finam_verifier.get_current_prices(list(tickers_of_interest))
        
        # 3.1 Проверка выходов (Stop Loss / Take Profit)
        exits = virtual_portfolio.check_exit_conditions(current_prices)
        for exit_sig in exits:
            res = virtual_portfolio.execute_trade(exit_sig, current_prices.get(exit_sig['ticker']))
            # Озвучиваем результат
            if res['profit'] > 0:
                logger.info(f"💰 PROFIT: {exit_sig['ticker']} +{res['profit']:.2f} RUB")
        
        # 3.2 Проверка входов (Новые сигналы)
        for sig in signals:
            t = sig['ticker']
            price = current_prices.get(t)
            
            if price and sig['action'] == 'BUY':
                # Исполняем в виртуальном портфеле
                res = virtual_portfolio.execute_trade(sig, price)
                
                if res['status'] == 'EXECUTED':
                    provider = sig.get('ai_provider', 'Algo').upper()
                    logger.info(f"🚀 ORDER EXECUTED: BUY {t} | Src: {provider}")

    except Exception as e:
        logger.error(f"❌ Session Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        bot_status = "ONLINE"
        logger.info("💤 Session Complete. Waiting next cycle.")

# Обретка для запуска асинхронного цикла в потоке
def run_trading_session():
    threading.Thread(target=lambda: asyncio.run(trading_loop_async())).start()

# --- WEB UI (FLASK) ---
HTML_TEMPLATE = '''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>NeuroTrader: GigaChat Edition</title>
    <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css" rel="stylesheet">
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;600&family=JetBrains+Mono:wght@400&display=swap" rel="stylesheet">
    <style>
        :root { --bg: #0d1117; --panel: #161b22; --border: #30363d; --accent: #238636; --text: #c9d1d9; }
        body { background: var(--bg); color: var(--text); font-family: 'Inter', sans-serif; margin: 0; padding: 20px; }
        .container { max-width: 1200px; margin: 0 auto; display: grid; grid-template-columns: 300px 1fr; gap: 20px; }
        .card { background: var(--panel); border: 1px solid var(--border); border-radius: 6px; padding: 20px; }
        .header { grid-column: 1 / -1; display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; }
        .btn { background: var(--accent); color: white; padding: 8px 16px; border-radius: 6px; text-decoration: none; font-weight: 600; font-size: 14px; }
        .btn:hover { opacity: 0.9; }
        
        .kpi-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; margin-bottom: 20px; }
        .kpi-box { background: #21262d; padding: 10px; border-radius: 6px; }
        .kpi-label { font-size: 12px; color: #8b949e; }
        .kpi-val { font-size: 18px; font-weight: 600; color: #f0f6fc; }
        
        table { width: 100%; border-collapse: collapse; }
        th { text-align: left; color: #8b949e; font-size: 12px; padding-bottom: 10px; border-bottom: 1px solid var(--border); }
        td { padding: 10px 0; border-bottom: 1px solid var(--border); font-size: 14px; }
        
        .log-box { height: 500px; overflow-y: auto; font-family: 'JetBrains Mono', monospace; background: #000; padding: 15px; border-radius: 6px; border: 1px solid var(--border); }
        
        .status-dot { height: 8px; width: 8px; background-color: #238636; border-radius: 50%; display: inline-block; margin-right: 5px; }
        .status-dot.analyzing { background-color: #d29922; animation: pulse 1s infinite; }
        @keyframes pulse { 0% { opacity: 1; } 50% { opacity: 0.5; } 100% { opacity: 1; } }
    </style>
</head>
<body>
    <div class="header">
        <div style="font-weight: 600; font-size: 20px; display: flex; align-items: center;">
            <i class="fas fa-robot" style="margin-right: 10px; color: #58a6ff;"></i> NeuroTrader AI
        </div>
        <div>
            <span style="margin-right: 15px; font-size: 14px; color: #8b949e;">
                <span class="status-dot {% if status == 'ANALYZING' %}analyzing{% endif %}"></span> {{ status }}
            </span>
            <a href="/force" class="btn"><i class="fas fa-bolt"></i> Force Run</a>
        </div>
    </div>

    <div class="container">
        <!-- SIDEBAR -->
        <div>
            <div class="card">
                <div style="font-weight: 600; margin-bottom: 15px; color: #58a6ff;">Portfolio</div>
                <div class="kpi-grid">
                    <div class="kpi-box">
                        <div class="kpi-label">Total Value</div>
                        <div class="kpi-val">{{ "{:,.0f}".format(stats.current_value) }} ₽</div>
                    </div>
                    <div class="kpi-box">
                        <div class="kpi-label">Cash</div>
                        <div class="kpi-val">{{ "{:,.0f}".format(stats.cash) }} ₽</div>
                    </div>
                    <div class="kpi-box">
                        <div class="kpi-label">Profit</div>
                        <div class="kpi-val" style="color: {% if stats.total_profit >= 0 %}#238636{% else %}#da3633{% endif %};">
                            {{ "{:+,.0f}".format(stats.total_profit) }} ₽
                        </div>
                    </div>
                    <div class="kpi-box">
                        <div class="kpi-label">Trades</div>
                        <div class="kpi-val">{{ stats.total_trades }}</div>
                    </div>
                </div>
                
                <div style="font-weight: 600; margin-bottom: 10px; margin-top: 20px;">Active Positions</div>
                {% if positions %}
                    <table style="font-size: 12px;">
                        {% for t, p in positions.items() %}
                        <tr>
                            <td><b>{{ t }}</b></td>
                            <td>{{ p.size }}</td>
                            <td>{{ "{:.1f}".format(p.avg_price) }}</td>
                        </tr>
                        {% endfor %}
                    </table>
                {% else %}
                    <div style="color: #8b949e; font-size: 13px;">No positions</div>
                {% endif %}
            </div>
            
            <div class="card" style="margin-top: 20px;">
                <div style="font-weight: 600; margin-bottom: 10px; color: #a371f7;">AI Core Status</div>
                <div style="font-size: 13px;">
                    <div style="display:flex; justify-content:space-between; margin-bottom:5px;">
                        <span>Primary (GigaChat)</span>
                        <span style="color: #238636;">Active</span>
                    </div>
                    <div style="display:flex; justify-content:space-between; margin-bottom:5px;">
                        <span>Backup (Gemini)</span>
                        <span style="color: #8b949e;">Standby</span>
                    </div>
                    <div style="margin-top: 10px; font-size: 11px; color: #8b949e;">
                        Session #{{ session }}
                    </div>
                </div>
            </div>
        </div>

        <!-- LOGS -->
        <div class="card">
            <div style="font-weight: 600; margin-bottom: 10px;">Live System Logs</div>
            <div class="log-box" id="logBox">
                {% for log in logs %}
                    {{ log|safe }}
                {% endfor %}
            </div>
        </div>
    </div>

    <script>
        const logBox = document.getElementById("logBox");
        logBox.scrollTop = logBox.scrollHeight;
        setTimeout(() => location.reload(), 5000); // Auto-refresh 5s
    </script>
</body>
</html>
'''

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

# --- ЗАПУСК СЕРВЕРА ---
if __name__ == '__main__':
    # Планировщик: каждые 15 минут
    schedule.every(15).minutes.do(run_trading_session)
    
    # Поток планировщика
    def schedule_loop():
        while True:
            schedule.run_pending()
            time.sleep(1)
    
    threading.Thread(target=schedule_loop, daemon=True).start()
    
    # Запуск Flask
    port = int(os.environ.get("PORT", 10000))
    # Запускаем первую сессию анализа сразу при старте (в фоне)
    run_trading_session()
    
    app.run(host='0.0.0.0', port=port)
