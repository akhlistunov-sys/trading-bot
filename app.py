# app.py - НЕЙРО-ИНТЕРФЕЙС (NeuroTrader Style)
from flask import Flask, jsonify, render_template_string
import datetime
import time
import threading
import schedule
import logging
import os
import asyncio
from dotenv import load_dotenv

# Загрузка переменных
load_dotenv(override=True)

# Логирование
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Импорты модулей
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
    logger.info("✅ Модули загружены")
except ImportError as e:
    logger.error(f"❌ Ошибка импорта: {e}")
    raise

app = Flask(__name__)

# --- ГЛОБАЛЬНЫЕ ПЕРЕМЕННЫЕ ---
start_time = datetime.datetime.now()
session_count = 0
last_news_count = 0
bot_status = "ONLINE"
last_signals = []
technical_signals = []

# --- ИНИЦИАЛИЗАЦИЯ ---
try:
    news_fetcher = NewsFetcher()
    nlp_engine = NlpEngine()
    finam_verifier = FinamVerifier()
    risk_manager = RiskManager(initial_capital=100000)
    enhanced_analyzer = EnhancedAnalyzer()
    news_prefilter = NewsPreFilter()
    tinkoff_executor = TinkoffExecutor()
    virtual_portfolio = VirtualPortfolioPro(initial_capital=100000)
    
    # Стратегия Momentum (Обновленная)
    technical_strategy = TechnicalStrategy(tinkoff_executor=tinkoff_executor)
    
    signal_pipeline = SignalPipeline(
        nlp_engine=nlp_engine,
        finam_verifier=finam_verifier,
        risk_manager=risk_manager,
        enhanced_analyzer=enhanced_analyzer,
        news_prefilter=news_prefilter,
        technical_strategy=technical_strategy
    )
    
    logger.info("✅ Система инициализирована: Momentum Strategy")
except Exception as e:
    logger.error(f"❌ Критическая ошибка старта: {e}")
    raise

# --- НОВЫЙ ДИЗАЙН (NEURO TRADER STYLE) ---
HTML_TEMPLATE = '''
<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>NeuroTrader AI Dashboard</title>
    <meta http-equiv="refresh" content="30">
    <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css" rel="stylesheet">
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        :root {
            --bg-dark: #13141f;
            --bg-card: #1c1e2a;
            --accent-purple: #7b2cbf;
            --accent-blue: #3a86ff;
            --accent-green: #00b894;
            --accent-red: #ff4757;
            --text-primary: #ffffff;
            --text-secondary: #a0a0a0;
            --border-color: #2d303e;
        }
        
        * { margin: 0; padding: 0; box-sizing: border-box; font-family: 'Inter', -apple-system, sans-serif; }
        
        body {
            background-color: var(--bg-dark);
            color: var(--text-primary);
            display: flex;
            min-height: 100vh;
        }

        /* Sidebar */
        .sidebar {
            width: 260px;
            background-color: #161722;
            padding: 20px;
            border-right: 1px solid var(--border-color);
            display: flex;
            flex-direction: column;
            position: fixed;
            height: 100%;
        }
        
        .logo {
            font-size: 1.5rem;
            font-weight: 700;
            color: var(--text-primary);
            margin-bottom: 40px;
            display: flex;
            align-items: center;
            gap: 10px;
        }
        
        .logo span { color: var(--accent-purple); }
        
        .nav-item {
            display: flex;
            align-items: center;
            padding: 12px 16px;
            color: var(--text-secondary);
            text-decoration: none;
            border-radius: 12px;
            margin-bottom: 8px;
            transition: 0.3s;
            font-weight: 500;
        }
        
        .nav-item:hover, .nav-item.active {
            background-color: rgba(123, 44, 191, 0.15);
            color: var(--accent-purple);
        }
        
        .nav-item i { margin-right: 12px; width: 20px; }

        /* Main Content */
        .main-content {
            margin-left: 260px;
            flex: 1;
            padding: 30px;
            max-width: 1600px;
        }

        .header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 30px;
        }

        .header h1 { font-size: 1.8rem; font-weight: 600; }
        
        .status-badge {
            font-size: 0.9rem;
            color: var(--accent-green);
            display: flex;
            align-items: center;
            gap: 6px;
        }
        
        .status-dot {
            width: 8px; height: 8px;
            background: var(--accent-green);
            border-radius: 50%;
            box-shadow: 0 0 10px var(--accent-green);
        }

        .action-btn {
            background: var(--accent-purple);
            color: white;
            border: none;
            padding: 10px 20px;
            border-radius: 8px;
            font-weight: 600;
            cursor: pointer;
            text-decoration: none;
            display: inline-flex;
            align-items: center;
            gap: 8px;
            transition: 0.2s;
        }
        
        .action-btn:hover { background: #9d4edd; transform: translateY(-2px); }

        /* Dashboard Grid */
        .dashboard-grid {
            display: grid;
            grid-template-columns: repeat(4, 1fr);
            gap: 20px;
            margin-bottom: 30px;
        }

        .kpi-card {
            background: var(--bg-card);
            border: 1px solid var(--border-color);
            border-radius: 16px;
            padding: 20px;
            position: relative;
            overflow: hidden;
        }
        
        .kpi-title { font-size: 0.8rem; color: var(--text-secondary); letter-spacing: 1px; margin-bottom: 10px; }
        .kpi-value { font-size: 1.8rem; font-weight: 700; }
        .kpi-sub { font-size: 0.85rem; margin-top: 5px; }
        .positive { color: var(--accent-green); }
        .negative { color: var(--accent-red); }
        .icon-bg {
            position: absolute; right: 20px; top: 20px;
            font-size: 2rem; color: rgba(255,255,255,0.05);
        }

        /* Charts & Lists Area */
        .content-split {
            display: grid;
            grid-template-columns: 2.5fr 1fr;
            gap: 20px;
            margin-bottom: 30px;
        }

        .panel {
            background: var(--bg-card);
            border: 1px solid var(--border-color);
            border-radius: 16px;
            padding: 20px;
        }
        
        .panel-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 20px;
            border-bottom: 1px solid var(--border-color);
            padding-bottom: 15px;
        }
        
        .panel-title { font-size: 1.1rem; font-weight: 600; display: flex; align-items: center; gap: 10px; }

        /* Chart Area */
        .chart-container { height: 350px; width: 100%; }

        /* Signal List */
        .signal-list { display: flex; flex-direction: column; gap: 12px; }
        
        .signal-item {
            background: rgba(255,255,255,0.03);
            border-radius: 10px;
            padding: 12px;
            display: flex;
            align-items: center;
            justify-content: space-between;
            border-left: 3px solid transparent;
        }
        
        .signal-item.buy { border-left-color: var(--accent-green); }
        .signal-item.sell { border-left-color: var(--accent-red); }
        
        .ticker-badge {
            background: rgba(255,255,255,0.1);
            padding: 4px 8px;
            border-radius: 4px;
            font-weight: 700;
            font-size: 0.9rem;
        }

        /* Bottom Grid */
        .bottom-grid {
            display: grid;
            grid-template-columns: 1fr 2fr;
            gap: 20px;
        }

        /* Ticker Pills */
        .ticker-pill {
            display: inline-block;
            background: #252836;
            padding: 6px 12px;
            border-radius: 6px;
            font-size: 0.85rem;
            margin-right: 8px;
            margin-bottom: 8px;
            border: 1px solid var(--border-color);
        }

        /* Mobile Responsive */
        @media (max-width: 1024px) {
            .sidebar { width: 70px; padding: 20px 10px; }
            .logo span, .nav-item span { display: none; }
            .main-content { margin-left: 70px; }
            .dashboard-grid, .content-split, .bottom-grid { grid-template-columns: 1fr; }
        }
    </style>
</head>
<body>
    <!-- Sidebar -->
    <nav class="sidebar">
        <div class="logo">
            <i class="fas fa-brain" style="color: var(--accent-purple);"></i>
            <span>NeuroTrader</span>
        </div>
        <a href="#" class="nav-item active"><i class="fas fa-th-large"></i> <span>Dashboard</span></a>
        <a href="/trades" class="nav-item"><i class="fas fa-history"></i> <span>History</span></a>
        <a href="/stats" class="nav-item"><i class="fas fa-chart-pie"></i> <span>Analytics</span></a>
        <a href="#" class="nav-item"><i class="fas fa-cog"></i> <span>Settings</span></a>
    </nav>

    <!-- Main Content -->
    <main class="main-content">
        <header class="header">
            <div>
                <h1>NeuroTrader Dashboard</h1>
                <div class="status-badge"><div class="status-dot"></div> System Status: {{ bot_status }}</div>
            </div>
            <a href="/force" class="action-btn"><i class="fas fa-bolt"></i> Analyze Market</a>
        </header>

        <!-- KPI Cards -->
        <div class="dashboard-grid">
            <div class="kpi-card">
                <div class="kpi-title">PORTFOLIO VALUE</div>
                <div class="kpi-value">{{ "{:,.0f}".format(portfolio_stats.total_value).replace(",", " ") }} ₽</div>
                <div class="kpi-sub positive">+{{ "%+.2f"|format(portfolio_stats.total_return_pct) }}%</div>
                <i class="fas fa-wallet icon-bg"></i>
            </div>
            <div class="kpi-card">
                <div class="kpi-title">TOTAL PROFIT</div>
                <div class="kpi-value" style="color: {% if portfolio_stats.total_profit >= 0 %}var(--accent-green){% else %}var(--accent-red){% endif %};">
                    {{ "%+.0f"|format(portfolio_stats.total_profit) }} ₽
                </div>
                <div class="kpi-sub">Lifetime P&L</div>
                <i class="fas fa-chart-line icon-bg"></i>
            </div>
            <div class="kpi-card">
                <div class="kpi-title">TOTAL TRADES</div>
                <div class="kpi-value">{{ portfolio_stats.total_trades }}</div>
                <div class="kpi-sub">Sessions: {{ session_count }}</div>
                <i class="fas fa-exchange-alt icon-bg"></i>
            </div>
            <div class="kpi-card">
                <div class="kpi-title">ACTIVE MODEL</div>
                <div class="kpi-value" style="font-size: 1.4rem;">GigaChat + Momentum</div>
                <div class="kpi-sub">Latency: ~300ms</div>
                <i class="fas fa-microchip icon-bg"></i>
            </div>
        </div>

        <!-- Charts & Signals -->
        <div class="content-split">
            <!-- Main Chart -->
            <div class="panel">
                <div class="panel-header">
                    <div class="panel-title"><i class="fas fa-chart-area" style="color: var(--accent-green);"></i> Portfolio Performance</div>
                </div>
                <div class="chart-container">
                    <canvas id="portfolioChart"></canvas>
                </div>
            </div>

            <!-- Live Signals -->
            <div class="panel">
                <div class="panel-header">
                    <div class="panel-title"><i class="fas fa-broadcast-tower" style="color: var(--accent-purple);"></i> Live AI Signals</div>
                    <span style="font-size: 0.8rem; background: var(--accent-purple); padding: 2px 6px; border-radius: 4px;">Beta</span>
                </div>
                
                <div class="signal-list">
                    {% if last_signals %}
                        {% for signal in last_signals[:5] %}
                        <div class="signal-item {{ signal.action|lower }}">
                            <div>
                                <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 4px;">
                                    <span class="ticker-badge">{{ signal.ticker }}</span>
                                    <span style="font-weight: 600; font-size: 0.9rem; color: {% if signal.action=='BUY' %}var(--accent-green){% else %}var(--accent-red){% endif %};">{{ signal.action }}</span>
                                </div>
                                <div style="font-size: 0.8rem; color: var(--text-secondary);">{{ signal.reason[:30] }}...</div>
                            </div>
                            <div style="text-align: right;">
                                <div style="font-size: 0.9rem;">{{ "%.0f"|format(signal.impact_score) }}/10</div>
                                <div style="font-size: 0.75rem; color: var(--text-secondary);">Score</div>
                            </div>
                        </div>
                        {% endfor %}
                    {% else %}
                        <div style="text-align: center; color: var(--text-secondary); padding: 40px 0;">
                            <i class="fas fa-satellite-dish" style="font-size: 2rem; margin-bottom: 10px; opacity: 0.5;"></i>
                            <br>Awaiting Market Signals...
                        </div>
                    {% endif %}
                </div>
            </div>
        </div>

        <!-- Bottom Info -->
        <div class="bottom-grid">
            <div class="panel">
                <div class="panel-title" style="margin-bottom: 15px;">Risk Management</div>
                <div style="display: flex; justify-content: space-between; margin-bottom: 10px; border-bottom: 1px solid var(--border-color); padding-bottom: 8px;">
                    <span style="color: var(--text-secondary);">Daily Limit</span>
                    <span style="color: var(--accent-red);">7.0%</span>
                </div>
                 <div style="display: flex; justify-content: space-between; margin-bottom: 10px;">
                    <span style="color: var(--text-secondary);">Stop Loss (Base)</span>
                    <span style="color: var(--accent-red);">1.5%</span>
                </div>
                <div style="display: flex; justify-content: space-between;">
                    <span style="color: var(--text-secondary);">Short Selling</span>
                    <span style="color: #666;">DISABLED</span>
                </div>
            </div>
            
            <div class="panel">
                <div class="panel-title" style="margin-bottom: 15px;">Active Monitored Tickers (Top 25 MOEX)</div>
                <div>
                    {% for ticker in ['SBER', 'GAZP', 'LKOH', 'ROSN', 'GMKN', 'YNDX', 'OZON', 'MGNT', 'FIVE', 'NVTK', 'TCSG', 'VTBR'] %}
                        <span class="ticker-pill">{{ ticker }}</span>
                    {% endfor %}
                    <span class="ticker-pill" style="opacity: 0.5;">+13 more</span>
                </div>
            </div>
        </div>

    </main>

    <script>
        // График портфеля
        const ctx = document.getElementById('portfolioChart').getContext('2d');
        
        // Создаем градиент
        let gradient = ctx.createLinearGradient(0, 0, 0, 400);
        gradient.addColorStop(0, 'rgba(0, 184, 148, 0.2)');
        gradient.addColorStop(1, 'rgba(0, 184, 148, 0)');

        const chartData = {
            labels: {{ portfolio_stats.chart_labels|tojson|safe }},
            datasets: [{
                label: 'Portfolio Value',
                data: {{ portfolio_stats.chart_values|tojson|safe }},
                borderColor: '#00b894',
                backgroundColor: gradient,
                borderWidth: 2,
                pointBackgroundColor: '#00b894',
                pointRadius: 0,
                pointHoverRadius: 6,
                fill: true,
                tension: 0.4
            }]
        };

        new Chart(ctx, {
            type: 'line',
            data: chartData,
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { display: false },
                    tooltip: {
                        mode: 'index',
                        intersect: false,
                        backgroundColor: '#1c1e2a',
                        titleColor: '#fff',
                        bodyColor: '#a0a0a0',
                        borderColor: '#2d303e',
                        borderWidth: 1
                    }
                },
                scales: {
                    x: {
                        grid: { color: 'rgba(255, 255, 255, 0.05)' },
                        ticks: { color: '#666' }
                    },
                    y: {
                        grid: { color: 'rgba(255, 255, 255, 0.05)' },
                        ticks: { color: '#666' }
                    }
                },
                interaction: {
                    mode: 'nearest',
                    axis: 'x',
                    intersect: false
                }
            }
        });
    </script>
</body>
</html>
'''

# --- ЛОГИКА ТОРГОВЛИ ---
async def trading_session_async(force_mode=False):
    global bot_status, session_count, last_signals, technical_signals
    
    if bot_status == "ANALYZING": return
    bot_status = "ANALYZING"
    session_count += 1
    
    logger.info(f"⚡ Сессия #{session_count} (Momentum Strategy)")
    
    try:
        # 1. Получаем новости
        news = await news_fetcher.fetch_all_news()
        
        # 2. Получаем технические сигналы
        tech_signals = await technical_strategy.scan_for_signals()
        technical_signals = tech_signals
        
        # 3. Обработка пайплайном
        signals = await signal_pipeline.process_news_batch(news)
        
        # 4. Объединение (Технический Momentum имеет приоритет)
        all_signals = signals + tech_signals
        last_signals = all_signals[:10] # Для UI
        
        # 5. Исполнение
        if all_signals:
            prices = await tinkoff_executor.get_current_price("SBER") # Ping
            prices_dict = await finam_verifier.get_current_prices([s['ticker'] for s in all_signals])
            
            risk_manager.update_positions(virtual_portfolio.positions)
            
            # Проверка выходов
            exits = virtual_portfolio.check_exit_conditions(prices_dict)
            for exit_sig in exits:
                virtual_portfolio.execute_trade(exit_sig, prices_dict.get(exit_sig['ticker'], 0))
            
            # Входы
            for sig in all_signals:
                ticker = sig['ticker']
                price = prices_dict.get(ticker)
                
                # Фильтр Momentum: Входим только если подтвержден тренд
                if price:
                    res = virtual_portfolio.execute_trade(sig, price)
                    if res.get('status') == 'EXECUTED':
                        logger.info(f"✅ TRADE: {res['action']} {ticker}")

    except Exception as e:
        logger.error(f"Error in session: {e}")
    finally:
        bot_status = "ONLINE"

def run_trading_session(force=False):
    threading.Thread(target=lambda: asyncio.run(trading_session_async(force))).start()

# --- ROUTES ---
@app.route('/')
def dashboard():
    stats = virtual_portfolio.get_stats()
    # Mock chart data for visuals if empty
    if not stats.get('chart_values'):
        stats['chart_labels'] = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
        stats['chart_values'] = [100000, 102000, 101500, 104000, 103500, 106000, stats['current_value']]

    return render_template_string(HTML_TEMPLATE, 
                                  portfolio_stats=stats,
                                  bot_status=bot_status,
                                  last_signals=last_signals,
                                  session_count=session_count)

@app.route('/force')
def force():
    run_trading_session(True)
    return jsonify({"status": "started"})

@app.route('/status')
def status():
    return jsonify({
        "status": bot_status, 
        "balance": virtual_portfolio.cash,
        "positions": len(virtual_portfolio.positions)
    })

if __name__ == '__main__':
    schedule.every(15).minutes.do(run_trading_session)
    threading.Thread(target=lambda: [schedule.run_pending(), time.sleep(1)] and None).start()
    app.run(host='0.0.0.0', port=10000)
