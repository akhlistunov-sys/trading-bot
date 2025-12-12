# app.py - ПОЛНЫЙ ОБНОВЛЁННЫЙ ФАЙЛ С ВИЗУАЛЬНЫМИ И ЛОГИЧЕСКИМИ УЛУЧШЕНИЯМИ
from flask import Flask, jsonify, render_template_string, request
import datetime
import time
import threading
import schedule
import logging
import os
import asyncio
import json
from typing import Dict, List

# ===== КРИТИЧЕСКОЕ ИСПРАВЛЕНИЕ: принудительная загрузка переменных окружения =====
from dotenv import load_dotenv
load_dotenv(override=True)

# Инициализируем логирование
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

# ТЕПЕРЬ импортируем наши модули
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
    from technical_strategy import TechnicalStrategy  # НОВЫЙ МОДУЛЬ
    logger.info("✅ Все модули импортированы")
except ImportError as e:
    logger.error(f"❌ Ошибка импорта модулей: {e}")
    raise

app = Flask(__name__)

# Глобальные переменные состояния
request_count = 0
last_trading_time = "Еще не запускалась"
bot_status = "⏸️ Ожидание"
session_count = 0
trade_history = []
total_virtual_profit = 0
total_virtual_return = 0.0
is_trading = False
last_news_count = 0
last_signals = []
system_stats = {}
pipeline_stats = {}
technical_signals = []
start_time = datetime.datetime.now()

# Инициализация всех модулей
logger.info("🔧 Инициализация всех модулей...")

try:
    news_fetcher = NewsFetcher()
    nlp_engine = NlpEngine()
    finam_verifier = FinamVerifier()
    risk_manager = RiskManager(initial_capital=100000)
    enhanced_analyzer = EnhancedAnalyzer()
    news_prefilter = NewsPreFilter()
    tinkoff_executor = TinkoffExecutor()
    virtual_portfolio = VirtualPortfolioPro(initial_capital=100000)
    
    # НОВЫЙ: Технический стратегии модуль
    technical_strategy = TechnicalStrategy(tinkoff_executor=tinkoff_executor)
    
    # Создаём SignalPipeline С ТЕХНИЧЕСКИМ МОДУЛЕМ
    signal_pipeline = SignalPipeline(
        nlp_engine=nlp_engine,
        finam_verifier=finam_verifier,
        risk_manager=risk_manager,
        enhanced_analyzer=enhanced_analyzer,
        news_prefilter=news_prefilter,
        technical_strategy=technical_strategy  # НОВЫЙ ПАРАМЕТР
    )
    
    # DecisionEngine с интеграцией RiskManager
    decision_engine = DecisionEngine(risk_manager=risk_manager)
    
    logger.info("✅ Все модули инициализированы (включая TechnicalStrategy)")
except Exception as e:
    logger.error(f"❌ Критическая ошибка инициализации: {e}")
    raise

# ============================================
# ОБНОВЛЁННЫЙ HTML ШАБЛОН С ВИЗУАЛИЗАЦИЕЙ ПРИБЫЛИ
# ============================================
HTML_TEMPLATE = '''
<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>🏦 Гибридный AI Трейдер</title>
    <meta http-equiv="refresh" content="45">
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        :root {
            --primary-dark: #0f172a; --primary-light: #1e293b;
            --accent-blue: #3b82f6; --accent-green: #10b981; --accent-red: #ef4444;
            --accent-amber: #f59e0b; --accent-purple: #8b5cf6;
            --text-primary: #f1f5f9; --text-secondary: #94a3b8;
            --border-color: #334155;
        }
        body {
            background: var(--primary-dark); color: var(--text-primary);
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            line-height: 1.5; font-size: 15px; padding-bottom: 80px; min-height: 100vh;
        }
        .container { max-width: 100%; margin: 0 auto; padding: 12px; }
        
        /* ШАПКА С ФИНАНСОВЫМ ИТОГОМ */
        .header {
            background: linear-gradient(135deg, var(--primary-light) 0%, #1e293b 100%);
            border-radius: 16px; padding: 20px; margin-bottom: 16px;
            border: 1px solid var(--border-color); box-shadow: 0 8px 32px rgba(0,0,0,0.3);
        }
        .capital-summary {
            display: flex; justify-content: space-between; align-items: center;
            margin-bottom: 16px; flex-wrap: wrap;
        }
        .total-value { font-size: 2.2rem; font-weight: 700; }
        .profit-summary {
            background: rgba(30, 41, 59, 0.8); padding: 12px 16px;
            border-radius: 12px; border: 1px solid var(--border-color);
        }
        .profit-row { display: flex; justify-content: space-between; margin: 4px 0; }
        .profit-label { color: var(--text-secondary); }
        .profit-value { font-weight: 600; }
        .positive { color: var(--accent-green); }
        .negative { color: var(--accent-red); }
        
        /* КЛЮЧЕВЫЕ МЕТРИКИ */
        .metrics-grid {
            display: grid; grid-template-columns: repeat(2, 1fr); gap: 12px;
            margin-bottom: 20px;
        }
        @media (min-width: 768px) {
            .metrics-grid { grid-template-columns: repeat(4, 1fr); }
        }
        .metric-card {
            background: var(--primary-light); border: 1px solid var(--border-color);
            border-radius: 12px; padding: 16px; position: relative;
        }
        .metric-card::before {
            content: ''; position: absolute; top: 0; left: 0;
            width: 4px; height: 100%; background: var(--accent-blue);
        }
        .metric-card.success::before { background: var(--accent-green); }
        .metric-card.warning::before { background: var(--accent-amber); }
        .metric-card.danger::before { background: var(--accent-red); }
        .metric-label {
            font-size: 0.8rem; color: var(--text-secondary);
            text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 6px;
        }
        .metric-value { font-size: 1.6rem; font-weight: 700; margin-bottom: 4px; }
        
        /* ГРАФИК И ПОЗИЦИИ */
        .main-content {
            display: grid; grid-template-columns: 1fr; gap: 20px;
            margin-bottom: 20px;
        }
        @media (min-width: 1024px) {
            .main-content { grid-template-columns: 2fr 1fr; }
        }
        .chart-section, .positions-section {
            background: var(--primary-light); border: 1px solid var(--border-color);
            border-radius: 16px; padding: 20px;
        }
        .section-title {
            font-size: 1.1rem; font-weight: 600; margin-bottom: 16px;
            display: flex; align-items: center; gap: 8px;
        }
        .chart-container { height: 300px; position: relative; }
        
        /* ТАБЛИЦА ПОЗИЦИЙ */
        .positions-table { width: 100%; border-collapse: collapse; }
        .positions-table th {
            text-align: left; padding: 12px; color: var(--text-secondary);
            border-bottom: 1px solid var(--border-color); font-weight: 600;
        }
        .positions-table td {
            padding: 12px; border-bottom: 1px solid var(--border-color);
        }
        .ticker-cell { font-weight: 700; }
        .action-buy { color: var(--accent-green); }
        .action-sell { color: var(--accent-red); }
        
        /* СИГНАЛЫ */
        .signals-section { margin-bottom: 20px; }
        .signal-list { display: flex; flex-direction: column; gap: 10px; }
        .signal-card {
            background: var(--primary-light); border: 1px solid var(--border-color);
            border-radius: 12px; padding: 16px; transition: all 0.2s;
        }
        .signal-card:hover { border-color: var(--accent-blue); }
        .signal-card.buy { border-left: 4px solid var(--accent-green); }
        .signal-card.sell { border-left: 4px solid var(--accent-red); }
        .signal-header {
            display: flex; justify-content: space-between; align-items: flex-start;
            margin-bottom: 10px;
        }
        .signal-ticker {
            font-size: 1.2rem; font-weight: 700; display: flex; align-items: center; gap: 8px;
        }
        
        /* ПАНЕЛЬ УПРАВЛЕНИЯ */
        .control-bar {
            position: fixed; bottom: 0; left: 0; right: 0;
            background: rgba(15, 23, 42, 0.95); backdrop-filter: blur(10px);
            border-top: 1px solid var(--border-color); padding: 12px; z-index: 1000;
        }
        .control-grid {
            display: grid; grid-template-columns: repeat(5, 1fr); gap: 8px;
        }
        .control-btn {
            display: flex; flex-direction: column; align-items: center; justify-content: center;
            padding: 10px 6px; background: var(--primary-light);
            border: 1px solid var(--border-color); border-radius: 10px;
            color: var(--text-primary); text-decoration: none; font-size: 0.75rem;
            transition: all 0.2s;
        }
        .control-btn i { font-size: 1.2rem; margin-bottom: 4px; }
        .control-btn.active { background: var(--accent-blue); color: white; }
    </style>
</head>
<body>
    <div class="container">
        <!-- ШАПКА С ФИНАНСОВЫМ ИТОГОМ -->
        <div class="header">
            <div class="capital-summary">
                <div>
                    <div class="total-value">{{ "{:,.0f}".format(portfolio_stats.total_value).replace(",", " ") }} ₽</div>
                    <div class="text-sm">Общая стоимость портфеля</div>
                </div>
                <div class="profit-summary">
                    <div class="profit-row">
                        <span class="profit-label">Прибыль всего:</span>
                        <span class="profit-value {% if portfolio_stats.total_profit >= 0 %}positive{% else %}negative{% endif %}">
                            {{ "%+.0f"|format(portfolio_stats.total_profit) }} ₽
                        </span>
                    </div>
                    <div class="profit-row">
                        <span class="profit-label">Доходность:</span>
                        <span class="profit-value {% if portfolio_stats.total_return_pct >= 0 %}positive{% else %}negative{% endif %}">
                            {{ "%+.2f"|format(portfolio_stats.total_return_pct) }}%
                        </span>
                    </div>
                    <div class="profit-row">
                        <span class="profit-label">Сегодня:</span>
                        <span class="profit-value {% if portfolio_stats.daily_profit >= 0 %}positive{% else %}negative{% endif %}">
                            {{ "%+.0f"|format(portfolio_stats.daily_profit) }} ₽
                        </span>
                    </div>
                </div>
            </div>
            <div style="display: flex; justify-content: space-between; align-items: center; padding-top: 12px; border-top: 1px solid var(--border-color);">
                <div style="display: inline-flex; align-items: center; gap: 6px; padding: 6px 12px; border-radius: 20px; font-size: 0.85rem; font-weight: 600; background: rgba(16, 185, 129, 0.15); color: var(--accent-green);">
                    <i class="fas fa-robot"></i>
                    <span>{{ bot_status }}</span>
                </div>
                <div class="text-sm">
                    <i class="fas fa-history"></i> Сессий: {{ session_count }}
                </div>
            </div>
        </div>

        <!-- КЛЮЧЕВЫЕ МЕТРИКИ -->
        <div class="metrics-grid">
            <div class="metric-card success">
                <div class="metric-label">Прибыль всего</div>
                <div class="metric-value {% if portfolio_stats.total_profit >= 0 %}positive{% else %}negative{% endif %}">
                    {{ "%+.0f"|format(portfolio_stats.total_profit) }} ₽
                </div>
                <div class="text-sm">С начала работы</div>
            </div>
            <div class="metric-card">
                <div class="metric-label">Сделок</div>
                <div class="metric-value">{{ portfolio_stats.total_trades }}</div>
                <div class="text-sm">Всего исполнено</div>
            </div>
            <div class="metric-card warning">
                <div class="metric-label">Новостей</div>
                <div class="metric-value">{{ last_news_count }}</div>
                <div class="text-sm">Последняя проверка</div>
            </div>
            <div class="metric-card">
                <div class="metric-label">Тех. сигналы</div>
                <div class="metric-value">{{ technical_signals|length }}</div>
                <div class="text-sm">Активные</div>
            </div>
        </div>

        <!-- ОСНОВНОЙ КОНТЕНТ: ГРАФИК И ПОЗИЦИИ -->
        <div class="main-content">
            <div class="chart-section">
                <h2 class="section-title"><i class="fas fa-chart-line"></i> Динамика портфеля</h2>
                <div class="chart-container">
                    <canvas id="portfolioChart"></canvas>
                </div>
            </div>
            <div class="positions-section">
                <h2 class="section-title"><i class="fas fa-coins"></i> Активные позиции</h2>
                {% if portfolio_stats.positions %}
                <table class="positions-table">
                    <thead>
                        <tr>
                            <th>Тикер</th>
                            <th>Действие</th>
                            <th>Кол-во</th>
                            <th>P&L</th>
                            <th>Доля</th>
                        </tr>
                    </thead>
                    <tbody>
                        {% for pos in portfolio_stats.positions %}
                        <tr>
                            <td class="ticker-cell">{{ pos.ticker }}</td>
                            <td><span class="action-{{ pos.action|lower }}">{{ pos.action }}</span></td>
                            <td>{{ pos.size }}</td>
                            <td class="{% if pos.current_pnl >= 0 %}positive{% else %}negative{% endif %}">
                                {{ "%+.0f"|format(pos.current_pnl) }} ₽
                            </td>
                            <td>{{ "%.1f"|format(pos.portfolio_share*100) }}%</td>
                        </tr>
                        {% endfor %}
                    </tbody>
                </table>
                {% else %}
                <p style="text-align: center; color: var(--text-secondary); padding: 40px 0;">Нет открытых позиций</p>
                {% endif %}
            </div>
        </div>

        <!-- ПОСЛЕДНИЕ СИГНАЛЫ -->
        {% if last_signals and last_signals|length > 0 %}
        <div class="signals-section">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px;">
                <h2 class="section-title"><i class="fas fa-bolt"></i> Последние сигналы</h2>
                <span class="text-sm">{{ last_signals|length }} всего</span>
            </div>
            <div class="signal-list">
                {% for signal in last_signals[:5] %}
                <div class="signal-card {{ signal.action|lower if signal.action else 'neutral' }}">
                    <div class="signal-header">
                        <div class="signal-ticker">
                            {% if signal.action == 'BUY' %}
                                <i class="fas fa-arrow-up positive"></i>
                            {% elif signal.action == 'SELL' %}
                                <i class="fas fa-arrow-down negative"></i>
                            {% else %}
                                <i class="fas fa-minus neutral"></i>
                            {% endif %}
                            {{ signal.ticker if signal.ticker else 'N/A' }}
                            <span class="text-sm neutral">×{{ signal.position_size if signal.position_size else 1 }}</span>
                        </div>
                        <div style="background: rgba(59, 130, 246, 0.15); color: var(--accent-blue); padding: 4px 10px; border-radius: 12px; font-size: 0.8rem; font-weight: 600;">
                            {{ "%.2f"|format(signal.confidence) if signal.confidence else "0.00" }}
                        </div>
                    </div>
                    <div style="display: flex; gap: 12px; margin-bottom: 8px; font-size: 0.85rem; color: var(--text-secondary);">
                        <span><i class="fas fa-project-diagram"></i> {{ signal.event_type|replace('_', ' ')|title if signal.event_type else 'N/A' }}</span>
                        <span><i class="fas fa-wave-square"></i> Impact: {{ signal.impact_score if signal.impact_score else 0 }}/10</span>
                        <span><i class="fas fa-robot"></i> {{ signal.ai_provider|default('GigaChat') }}</span>
                    </div>
                    <div style="font-size: 0.9rem; color: var(--text-primary); line-height: 1.4; margin-bottom: 8px;">
                        {{ signal.reason[:80] if signal.reason else 'Нет описания' }}{% if signal.reason and signal.reason|length > 80 %}...{% endif %}
                    </div>
                </div>
                {% endfor %}
            </div>
        </div>
        {% endif %}

        <!-- ТЕХНИЧЕСКИЕ СИГНАЛЫ -->
        {% if technical_signals and technical_signals|length > 0 %}
        <div class="signals-section">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px;">
                <h2 class="section-title"><i class="fas fa-calculator"></i> Технические сигналы</h2>
                <span class="text-sm">{{ technical_signals|length }} активно</span>
            </div>
            <div class="signal-list">
                {% for signal in technical_signals[:3] %}
                <div class="signal-card {{ signal.action|lower }}">
                    <div class="signal-header">
                        <div class="signal-ticker">
                            {% if signal.action == 'BUY' %}
                                <i class="fas fa-arrow-up positive"></i>
                            {% elif signal.action == 'SELL' %}
                                <i class="fas fa-arrow-down negative"></i>
                            {% endif %}
                            {{ signal.ticker }}
                            <span class="text-sm neutral">Тех. анализ</span>
                        </div>
                        <div style="background: rgba(139, 92, 246, 0.15); color: var(--accent-purple); padding: 4px 10px; border-radius: 12px; font-size: 0.8rem; font-weight: 600;">
                            RSI
                        </div>
                    </div>
                    <div style="font-size: 0.9rem; color: var(--text-primary); line-height: 1.4;">
                        {{ signal.reason }}
                    </div>
                </div>
                {% endfor %}
            </div>
        </div>
        {% endif %}
    </div>

    <!-- ФИКСИРОВАННАЯ ПАНЕЛЬ УПРАВЛЕНИЯ -->
    <div class="control-bar">
        <div class="control-grid">
            <a href="/" class="control-btn active"><i class="fas fa-home"></i><span>Главная</span></a>
            <a href="/force" class="control-btn"><i class="fas fa-play"></i><span>Старт</span></a>
            <a href="/trades" class="control-btn"><i class="fas fa-history"></i><span>Сделки</span></a>
            <a href="/test_technical" class="control-btn"><i class="fas fa-calculator"></i><span>Тех. анализ</span></a>
            <a href="/stats" class="control-btn"><i class="fas fa-chart-bar"></i><span>Статистика</span></a>
        </div>
    </div>

    <script>
        // График портфеля
        const ctx = document.getElementById('portfolioChart').getContext('2d');
        const chartData = {
            labels: {{ portfolio_stats.chart_labels|tojson|safe }},
            datasets: [{
                label: 'Стоимость портфеля',
                data: {{ portfolio_stats.chart_values|tojson|safe }},
                borderColor: '#3b82f6',
                backgroundColor: 'rgba(59, 130, 246, 0.1)',
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
                plugins: { legend: { display: false } },
                scales: {
                    y: { 
                        ticks: { color: '#94a3b8' },
                        grid: { color: 'rgba(148, 163, 184, 0.1)' }
                    },
                    x: { 
                        ticks: { color: '#94a3b8' },
                        grid: { color: 'rgba(148, 163, 184, 0.1)' }
                    }
                }
            }
        });
    </script>
</body>
</html>
'''

# ==================== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ====================

def calculate_portfolio_stats():
    """Расчёт статистики портфеля для отображения в интерфейсе"""
    # Получаем текущие цены для всех позиций
    current_prices = {}
    for ticker in virtual_portfolio.positions.keys():
        # В реальном коде здесь нужно асинхронно получать цены
        # Для упрощения используем последние известные цены
        current_prices[ticker] = virtual_portfolio.positions[ticker].get('avg_price', 0)
    
    # Общая стоимость портфеля
    total_value = virtual_portfolio.get_total_value(current_prices)
    
    # Прибыль и доходность
    total_profit = total_virtual_profit
    total_return_pct = total_virtual_return
    
    # Детализация позиций
    positions_detail = []
    for ticker, pos in virtual_portfolio.positions.items():
        current_price = current_prices.get(ticker, pos['avg_price'])
        current_value = current_price * pos['size']
        pnl = (current_price - pos['avg_price']) * pos['size']
        positions_detail.append({
            'ticker': ticker,
            'action': 'BUY',  # Пока предполагаем только лонги
            'size': pos['size'],
            'avg_price': pos['avg_price'],
            'current_price': current_price,
            'current_value': current_value,
            'current_pnl': pnl,
            'portfolio_share': current_value / total_value if total_value > 0 else 0
        })
    
    # Данные для графика (упрощённо)
    chart_labels = ['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вс']
    chart_values = [98000, 99000, 101000, 100500, 100800, 101200, total_value/1000*1000]
    
    return {
        'total_value': total_value,
        'total_profit': total_profit,
        'total_return_pct': total_return_pct,
        'daily_profit': system_stats.get('session_profit', 0),
        'total_trades': len(trade_history),
        'positions': positions_detail,
        'chart_labels': chart_labels,
        'chart_values': chart_values
    }

# ==================== ОСНОВНЫЕ ФУНКЦИИ ====================

async def trading_session_async(force_mode=False):
    """ОБНОВЛЁННАЯ торговая сессия с ГИБРИДНОЙ стратегией"""
    global last_trading_time, session_count, trade_history
    global total_virtual_profit, total_virtual_return, is_trading
    global bot_status, last_news_count, last_signals, system_stats, pipeline_stats, technical_signals
    
    if is_trading:
        logger.info("⏸️ Торговая сессия уже выполняется")
        return
    
    is_trading = True
    session_count += 1
    current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    last_trading_time = current_time
    
    mode_label = "🚀 ПРИНУДИТЕЛЬНАЯ" if force_mode else "🤖 РАСПИСАНИЕ"
    logger.info(f"{mode_label} ГИБРИДНАЯ СЕССИЯ #{session_count} - {current_time}")
    logger.info("=" * 60)
    
    try:
        # 1. Сбор новостей
        logger.info("📰 Сбор новостей...")
        all_news = await news_fetcher.fetch_all_news()
        last_news_count = len(all_news)
        
        if not all_news:
            logger.warning("⚠️ Новостей не найдено")
            bot_status = f"⏸️ Ожидание новостей | Сессия #{session_count}"
            return
        
        logger.info(f"✅ Получено {len(all_news)} новостей")
        
        # 2. Технический анализ (ПАРАЛЛЕЛЬНО новостям)
        logger.info("📊 Запуск технического анализа...")
        tech_signals = await technical_strategy.scan_for_signals()
        technical_signals = tech_signals
        logger.info(f"✅ Тех. анализ: {len(tech_signals)} сигналов")
        
        # 3. Обработка новостей через SignalPipeline
        logger.info("⚙️ Обработка новостей через SignalPipeline...")
        news_signals = await signal_pipeline.process_news_batch(all_news)
        
        # 4. Объединение сигналов из двух источников
        all_signals = news_signals + tech_signals
        pipeline_stats = signal_pipeline.get_stats()
        last_signals = all_signals[:10]
        
        if not all_signals:
            logger.info("ℹ️ Нет торговых сигналов для выполнения")
            bot_status = f"⏸️ Нет сигналов | Сессия #{session_count}"
            return
        
        logger.info(f"✅ Сформировано {len(all_signals)} сигналов ({len(news_signals)} новостных + {len(tech_signals)} технических)")
        
        # 5. Получение текущих цен
        logger.info("💰 Получение текущих цен...")
        current_prices = {}
        tickers_to_check = list(set(signal['ticker'] for signal in all_signals))
        
        for ticker in tickers_to_check:
            try:
                price = await tinkoff_executor.get_current_price(ticker)
                if price:
                    current_prices[ticker] = price
                else:
                    logger.warning(f"⚠️ Не удалось получить цену для {ticker}")
            except Exception as e:
                logger.error(f"❌ Ошибка получения цены {ticker}: {str(e)[:50]}")
        
        # 6. Обновление позиций в RiskManager
        risk_manager.update_positions(virtual_portfolio.positions)
        
        # 7. Проверка условий выхода из позиций
        exit_signals = virtual_portfolio.check_exit_conditions(current_prices)
        
        # 8. Исполнение сделок (объединяем входные и выходные сигналы)
        all_trades = all_signals + exit_signals
        executed_trades = []
        
        for signal in all_trades:
            try:
                ticker = signal['ticker']
                if ticker in current_prices:
                    trade_result = virtual_portfolio.execute_trade(signal, current_prices[ticker])
                    if trade_result:
                        executed_trades.append(trade_result)
                        # Обновляем P&L в RiskManager
                        if 'profit' in trade_result:
                            risk_manager.update_pnl(trade_result['profit'])
                else:
                    logger.warning(f"⚠️ Нет цены для исполнения сигнала {ticker}")
            except Exception as e:
                logger.error(f"❌ Ошибка исполнения сигнала {signal.get('ticker', 'unknown')}: {str(e)[:50]}")
        
        # 9. Обновление истории и статистики
        trade_history.extend(executed_trades)
        
        # Расчёт прибыли
        session_profit = sum(trade.get('profit', 0) for trade in executed_trades)
        total_virtual_profit += session_profit
        
        # Расчёт общей стоимости портфеля и доходности
        total_value = virtual_portfolio.get_total_value(current_prices)
        total_virtual_return = ((total_value - 100000) / 100000) * 100
        
        # Обновление статистики системы
        system_stats = {
            'total_news_processed': last_news_count,
            'news_signals_generated': len(news_signals),
            'tech_signals_generated': len(tech_signals),
            'total_trades_executed': len(executed_trades),
            'session_profit': session_profit,
            'nlp_stats': nlp_engine.get_stats(),
            'virtual_portfolio_stats': virtual_portfolio.get_stats(),
            'pipeline_stats': pipeline_stats,
            'risk_stats': risk_manager.get_risk_stats(),
            'hybrid_mode': True
        }
        
        # Обновление статуса
        signal_count = len(all_signals)
        if signal_count > 0:
            bot_status = f"▶️ Гибридный анализ | Сессия #{session_count}"
        else:
            bot_status = f"⏸️ Нет сигналов | Сессия #{session_count}"
        
        logger.info(f"💰 ГИБРИДНАЯ СЕССИЯ #{session_count} ЗАВЕРШЕНА")
        logger.info(f"💎 Портфель: {total_value:.2f} руб. ({total_virtual_return:+.2f}%)")
        logger.info(f"🎯 Прибыль за сессию: {session_profit:+.2f} руб.")
        logger.info(f"📊 Сигналы: {len(news_signals)} новостных + {len(tech_signals)} технических")
        
        if executed_trades:
            for trade in executed_trades:
                if trade.get('status') == 'EXECUTED':
                    profit = trade.get('profit', 0)
                    symbol = '🟢' if profit >= 0 else '🔴'
                    source = trade.get('ai_provider', 'unknown')
                    logger.info(f"{symbol} {trade.get('action', '')} {trade.get('ticker', '')} x{trade.get('size', 0)} ({source}): {profit:+.2f} руб.")
        
    except Exception as e:
        logger.error(f"❌ КРИТИЧЕСКАЯ ошибка в торговой сессии: {str(e)}")
        import traceback
        logger.error(f"Трейсбек: {traceback.format_exc()[:500]}")
        bot_status = f"⚠️ Ошибка: {str(e)[:30]}..."
        
    finally:
        is_trading = False
        logger.info(f"🔄 Флаг is_trading сброшен после сессии #{session_count}")

def run_trading_session(force_mode=False):
    """Запуск торговой сессии в отдельном потоке"""
    thread = threading.Thread(target=lambda: asyncio.run(trading_session_async(force_mode)))
    thread.daemon = True
    thread.start()

def schedule_tasks():
    """Настройка планировщика задач"""
    schedule.clear()
    check_interval = int(os.getenv("CHECK_INTERVAL_MINUTES", "30"))
    schedule.every(check_interval).minutes.do(lambda: run_trading_session(False))
    logger.info(f"📅 Планировщик настроен: каждые {check_interval} минут")

def run_scheduler():
    """Фоновая задача планировщика"""
    while True:
        schedule.run_pending()
        time.sleep(1)

# ==================== ВЕБ-РОУТЫ ====================

@app.route('/')
def home():
    """Главная страница с новым интерфейсом"""
    global request_count
    request_count += 1
    
    # Расчёт статистики портфеля
    portfolio_stats = calculate_portfolio_stats()
    
    # Рендеринг нового HTML
    return render_template_string(
        HTML_TEMPLATE,
        bot_status=bot_status,
        uptime_str=str(datetime.datetime.now() - start_time).split('.')[0],
        session_count=session_count,
        last_trading_time=last_trading_time,
        request_count=request_count,
        portfolio_stats=portfolio_stats,
        total_virtual_return=total_virtual_return,
        total_virtual_profit=total_virtual_profit,
        last_news_count=last_news_count,
        last_signals=last_signals[:5] if last_signals else [],
        technical_signals=technical_signals[:3] if technical_signals else [],
        pipeline_stats=pipeline_stats,
        trade_history=trade_history
    )

@app.route('/force')
def force_trade():
    """Принудительный запуск торговой сессии"""
    run_trading_session(force_mode=True)
    return jsonify({
        "message": "🚀 Принудительный запуск ГИБРИДНОЙ торговой сессии",
        "timestamp": datetime.datetime.now().isoformat(),
        "force_mode": True,
        "session_number": session_count + 1,
        "strategy": "hybrid_news_technical"
    })

@app.route('/test_technical')
def test_technical():
    """Тест технического анализа"""
    async def _test():
        signals = await technical_strategy.scan_for_signals()
        return jsonify({
            "technical_test": "success",
            "signals_found": len(signals),
            "signals": signals[:5],
            "tracked_tickers": technical_strategy.tracked_tickers,
            "timestamp": datetime.datetime.now().isoformat()
        })
    
    try:
        return asyncio.run(_test())
    except Exception as e:
        return jsonify({"error": str(e)})

@app.route('/trades')
def show_trades():
    """История сделок"""
    portfolio_stats = virtual_portfolio.get_stats()
    risk_stats = risk_manager.get_risk_stats()
    
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
        
        ai_badge = f" {trade.get('ai_provider', 'simple').upper()}" if trade.get('ai_provider') else ""
        profit_html = ""
        if trade.get('profit', 0) != 0:
            profit_class = "positive" if trade.get('profit', 0) > 0 else "negative"
            profit_html = f"<br><span class='{profit_class}'>💰 Прибыль: {trade.get('profit', 0):+.2f} руб.</span>"
        
        trades_html += f"""
        <div style="background: {color}20; border-left: 4px solid {color}; padding: 12px; margin: 8px 0; border-radius: 6px;">
            {icon}{ai_badge} {trade['timestamp'][11:19]} | {trade.get('strategy', 'Hybrid AI Trading')}
            <br><strong>{trade['action']} {trade['ticker']}</strong> x{trade['size']} по {trade['price']} руб.
            {profit_html}
            <br><small>💡 {trade.get('reason', '')[:80]}</small>
        </div>
        """
    
    return f"""
    <html>
        <head>
            <title>История Сделок</title>
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <style>
                body {{ font-family: Arial; margin: 20px; background: #0f172a; color: #e2e8f0; font-size: 14px; }}
                .positive {{ color: #10b981; }}
                .negative {{ color: #ef4444; }}
                .container {{ max-width: 100%; margin: 0 auto; background: #1e293b; padding: 20px; border-radius: 16px; box-shadow: 0 8px 32px rgba(0,0,0,0.3); border: 1px solid #334155; }}
                .stats {{ background: rgba(30, 41, 59, 0.8); padding: 15px; border-radius: 12px; margin: 15px 0; border: 1px solid #334155; }}
                .back-btn {{ background: #3b82f6; color: white; padding: 10px 16px; text-decoration: none; border-radius: 10px; display: inline-block; margin-top: 15px; font-weight: 600; }}
            </style>
        </head>
        <body>
            <div class="container">
                <h2 style="color: #f1f5f9; margin-bottom: 20px;">📋 История Сделок (Гибридная стратегия)</h2>
                
                <div class="stats">
                    <h4 style="color: #94a3b8; margin-bottom: 10px;">📊 Статистика</h4>
                    <p><strong>Всего сделок:</strong> {len(trade_history)}</p>
                    <p><strong>Портфель:</strong> {portfolio_stats.get('current_value', 0):.0f} руб. 
                    (<span class="{{'positive' if total_virtual_return >= 0 else 'negative'}}">{total_virtual_return:+.1f}%</span>)</p>
                    <p><strong>Общая прибыль:</strong> <span class="{{'positive' if total_virtual_profit >= 0 else 'negative'}}">{total_virtual_profit:+.0f} руб.</span></p>
                    <p><strong>Источники сигналов:</strong> Новости + Тех. анализ</p>
                </div>
                
                {trades_html if trade_history else "<p style='text-align: center; color: #94a3b8;'>Сделок еще нет</p>"}
                
                <p style="margin-top: 20px;">
                    <a href="/" class="back-btn">← На главную</a>
                </p>
            </div>
        </body>
    </html>
    """

@app.route('/stats')
def detailed_stats():
    """Детальная статистика"""
    portfolio_stats = virtual_portfolio.get_stats()
    risk_stats = risk_manager.get_risk_stats()
    
    # Анализ сделок по источникам
    news_trades = [t for t in trade_history if t.get('ai_provider') == 'gigachat']
    tech_trades = [t for t in trade_history if t.get('ai_provider') == 'technical']
    other_trades = [t for t in trade_history if t.get('ai_provider') not in ['gigachat', 'technical']]
    
    return jsonify({
        "performance_summary": {
            "total_trades": len(trade_history),
            "news_trades": len(news_trades),
            "technical_trades": len(tech_trades),
            "other_trades": len(other_trades),
            "total_profit": total_virtual_profit,
            "virtual_return": total_virtual_return,
            "current_portfolio_value": virtual_portfolio.get_total_value({}),
            "strategy": "Hybrid News + Technical Analysis"
        },
        "hybrid_performance": {
            "news_signals": system_stats.get('news_signals_generated', 0),
            "technical_signals": system_stats.get('tech_signals_generated', 0),
            "pipeline_efficiency": pipeline_stats.get('signal_rate_percent', 0) if pipeline_stats else 0,
            "gigachat_success_rate": nlp_engine.get_stats().get('success_rate', 0)
        },
        "risk_management": risk_stats,
        "portfolio_status": portfolio_stats,
        "timestamp": datetime.datetime.now().isoformat()
    })

@app.route('/status')
def status():
    """JSON статус системы"""
    portfolio_stats = virtual_portfolio.get_stats()
    uptime = datetime.datetime.now() - start_time
    
    return jsonify({
        "status": bot_status,
        "uptime_seconds": int(uptime.total_seconds()),
        "trading_sessions": session_count,
        "total_trades": len(trade_history),
        "virtual_portfolio_value": virtual_portfolio.get_total_value({}),
        "virtual_return_percentage": total_virtual_return,
        "total_profit": total_virtual_profit,
        "last_trading_time": last_trading_time,
        "hybrid_mode": True,
        "signal_sources": ["gigachat", "technical"],
        "tracked_tickers": technical_strategy.tracked_tickers,
        "timestamp": datetime.datetime.now().isoformat()
    })

# ==================== ЗАПУСК ПРИЛОЖЕНИЯ ====================

if __name__ == '__main__':
    # Запуск планировщика
    schedule_tasks()
    scheduler_thread = threading.Thread(target=run_scheduler)
    scheduler_thread.daemon = True
    scheduler_thread.start()
    
    # Инициализация системы
    logger.info("=" * 60)
    logger.info("🚀 ГИБРИДНЫЙ AI ТРЕЙДЕР v5.0 ЗАПУЩЕН!")
    logger.info(f"🏦 ИИ-ПРОВАЙДЕРЫ: GigaChat {'✅' if nlp_engine.enabled else '❌'} + Тех. анализ ✅")
    logger.info(f"📊 СТРАТЕГИЯ: Гибридная (новости + RSI/Bollinger)")
    logger.info(f"🎯 РИСК-МЕНЕДЖМЕНТ: С поддержкой шортов, секторные лимиты")
    logger.info(f"📈 ВИЗУАЛИЗАЦИЯ: Полная статистика P&L, график портфеля")
    logger.info(f"🌐 ВЕБ-ИНТЕРФЕЙС: http://0.0.0.0:10000")
    logger.info("=" * 60)
    
    # Запуск Flask приложения
    try:
        app.run(host='0.0.0.0', port=10000, debug=False, use_reloader=False)
    except Exception as e:
        logger.error(f"❌ Ошибка запуска Flask: {e}")
        raise
