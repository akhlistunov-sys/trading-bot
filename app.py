# app.py - ИСПРАВЛЕННАЯ ВЕРСИЯ С ПРОВЕРКОЙ ОШИБОК
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

# Принудительно загружаем переменные окружения из Render Dashboard
load_dotenv(override=True)

# Инициализируем логирование сразу после загрузки переменных
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

# Логируем факт загрузки переменных
logger.info("=" * 60)
logger.info("🔧 ПЕРЕМЕННЫЕ ОКРУЖЕНИЯ ЗАГРУЖЕНЫ:")
logger.info("=" * 60)

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
start_time = datetime.datetime.now()

# Инициализация всех модулей с обработкой ошибок
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
    
    # Создаём SignalPipeline
    signal_pipeline = SignalPipeline(
        nlp_engine=nlp_engine,
        finam_verifier=finam_verifier,
        risk_manager=risk_manager,
        enhanced_analyzer=enhanced_analyzer,
        news_prefilter=news_prefilter
    )
    
    # DecisionEngine с интеграцией RiskManager
    decision_engine = DecisionEngine(risk_manager=risk_manager)
    
    logger.info("✅ Все модули инициализированы")
except Exception as e:
    logger.error(f"❌ Критическая ошибка инициализации: {e}")
    raise

# ============================================
# ИСПРАВЛЕННЫЙ HTML ШАБЛОН - БЕЗ ОШИБОК
# ============================================
HTML_TEMPLATE = '''
<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=5.0, user-scalable=yes">
    <title>🏦 Кабинет Управляющего | AI Трейдер</title>
    <meta http-equiv="refresh" content="45">
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
    <style>
        /* ===== СБРОС И БАЗА ===== */
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
            -webkit-tap-highlight-color: transparent;
        }

        :root {
            --primary-dark: #0f172a;
            --primary-light: #1e293b;
            --accent-blue: #3b82f6;
            --accent-green: #10b981;
            --accent-red: #ef4444;
            --accent-amber: #f59e0b;
            --accent-purple: #8b5cf6;
            --text-primary: #f1f5f9;
            --text-secondary: #94a3b8;
            --border-color: #334155;
        }

        body {
            background: var(--primary-dark);
            color: var(--text-primary);
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, sans-serif;
            line-height: 1.5;
            font-size: 15px;
            padding-bottom: 80px;
            min-height: 100vh;
        }

        .container {
            max-width: 100%;
            margin: 0 auto;
            padding: 12px;
        }

        /* ===== ШАПКА - КАПИТАЛ И СТАТУС ===== */
        .header {
            background: linear-gradient(135deg, var(--primary-light) 0%, #1e293b 100%);
            border-radius: 16px;
            padding: 20px;
            margin-bottom: 16px;
            border: 1px solid var(--border-color);
            box-shadow: 0 8px 32px rgba(0, 0, 0, 0.3);
        }

        .capital-display {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 16px;
        }

        .capital-amount {
            font-size: 2.2rem;
            font-weight: 700;
            letter-spacing: -0.5px;
        }

        .capital-change {
            font-size: 1.1rem;
            font-weight: 600;
            padding: 6px 12px;
            border-radius: 20px;
        }

        .capital-change.positive {
            background: rgba(16, 185, 129, 0.15);
            color: var(--accent-green);
        }

        .capital-change.negative {
            background: rgba(239, 68, 68, 0.15);
            color: var(--accent-red);
        }

        .status-bar {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding-top: 12px;
            border-top: 1px solid var(--border-color);
        }

        .status-badge {
            display: inline-flex;
            align-items: center;
            gap: 6px;
            padding: 6px 12px;
            border-radius: 20px;
            font-size: 0.85rem;
            font-weight: 600;
        }

        .status-badge.active {
            background: rgba(16, 185, 129, 0.15);
            color: var(--accent-green);
        }

        .status-badge.paused {
            background: rgba(245, 158, 11, 0.15);
            color: var(--accent-amber);
        }

        /* ===== БЫСТРЫЕ ДЕЙСТВИЯ ===== */
        .quick-actions {
            display: grid;
            grid-template-columns: repeat(4, 1fr);
            gap: 10px;
            margin-bottom: 20px;
        }

        .action-btn {
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            padding: 14px 8px;
            background: var(--primary-light);
            border: 1px solid var(--border-color);
            border-radius: 12px;
            color: var(--text-primary);
            text-decoration: none;
            transition: all 0.2s;
            font-size: 0.8rem;
            font-weight: 600;
        }

        .action-btn:hover {
            transform: translateY(-2px);
            border-color: var(--accent-blue);
        }

        .action-btn i {
            font-size: 1.4rem;
            margin-bottom: 6px;
        }

        .action-btn.primary {
            background: linear-gradient(135deg, var(--accent-blue) 0%, #2563eb 100%);
            color: white;
            border: none;
        }

        .action-btn.danger {
            background: linear-gradient(135deg, var(--accent-red) 0%, #dc2626 100%);
            color: white;
            border: none;
        }

        .action-btn.success {
            background: linear-gradient(135deg, var(--accent-green) 0%, #0da271 100%);
            color: white;
            border: none;
        }

        /* ===== КЛЮЧЕВЫЕ МЕТРИКИ ===== */
        .metrics-grid {
            display: grid;
            grid-template-columns: repeat(2, 1fr);
            gap: 12px;
            margin-bottom: 20px;
        }

        .metric-card {
            background: var(--primary-light);
            border: 1px solid var(--border-color);
            border-radius: 12px;
            padding: 16px;
            position: relative;
            overflow: hidden;
        }

        .metric-card::before {
            content: '';
            position: absolute;
            top: 0;
            left: 0;
            width: 4px;
            height: 100%;
            background: var(--accent-blue);
        }

        .metric-card.success::before {
            background: var(--accent-green);
        }

        .metric-card.warning::before {
            background: var(--accent-amber);
        }

        .metric-card.danger::before {
            background: var(--accent-red);
        }

        .metric-label {
            font-size: 0.8rem;
            color: var(--text-secondary);
            text-transform: uppercase;
            letter-spacing: 0.5px;
            margin-bottom: 6px;
        }

        .metric-value {
            font-size: 1.6rem;
            font-weight: 700;
            margin-bottom: 4px;
        }

        .metric-subtext {
            font-size: 0.8rem;
            color: var(--text-secondary);
        }

        /* ===== ЛЕНТА СИГНАЛОВ GIGACHAT ===== */
        .signals-section {
            margin-bottom: 20px;
        }

        .section-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 16px;
        }

        .section-title {
            font-size: 1.1rem;
            font-weight: 600;
            display: flex;
            align-items: center;
            gap: 8px;
        }

        .signal-list {
            display: flex;
            flex-direction: column;
            gap: 10px;
        }

        .signal-card {
            background: var(--primary-light);
            border: 1px solid var(--border-color);
            border-radius: 12px;
            padding: 16px;
            transition: all 0.2s;
        }

        .signal-card:hover {
            border-color: var(--accent-blue);
            transform: translateX(2px);
        }

        .signal-card.buy {
            border-left: 4px solid var(--accent-green);
        }

        .signal-card.sell {
            border-left: 4px solid var(--accent-red);
        }

        .signal-header {
            display: flex;
            justify-content: space-between;
            align-items: flex-start;
            margin-bottom: 10px;
        }

        .signal-ticker {
            font-size: 1.2rem;
            font-weight: 700;
            display: flex;
            align-items: center;
            gap: 8px;
        }

        .signal-confidence {
            background: rgba(59, 130, 246, 0.15);
            color: var(--accent-blue);
            padding: 4px 10px;
            border-radius: 12px;
            font-size: 0.8rem;
            font-weight: 600;
        }

        .signal-meta {
            display: flex;
            gap: 12px;
            margin-bottom: 8px;
            font-size: 0.85rem;
            color: var(--text-secondary);
        }

        .signal-reason {
            font-size: 0.9rem;
            color: var(--text-primary);
            line-height: 1.4;
        }

        .impact-badge {
            display: inline-block;
            padding: 2px 8px;
            border-radius: 10px;
            font-size: 0.75rem;
            font-weight: 600;
            margin-top: 8px;
        }

        .impact-high {
            background: rgba(16, 185, 129, 0.15);
            color: var(--accent-green);
        }

        .impact-medium {
            background: rgba(245, 158, 11, 0.15);
            color: var(--accent-amber);
        }

        .impact-low {
            background: rgba(148, 163, 184, 0.15);
            color: var(--text-secondary);
        }

        /* ===== ФИКСИРОВАННАЯ ПАНЕЛЬ УПРАВЛЕНИЯ ===== */
        .control-bar {
            position: fixed;
            bottom: 0;
            left: 0;
            right: 0;
            background: rgba(15, 23, 42, 0.95);
            backdrop-filter: blur(10px);
            border-top: 1px solid var(--border-color);
            padding: 12px;
            z-index: 1000;
        }

        .control-grid {
            display: grid;
            grid-template-columns: repeat(5, 1fr);
            gap: 8px;
        }

        .control-btn {
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            padding: 10px 6px;
            background: var(--primary-light);
            border: 1px solid var(--border-color);
            border-radius: 10px;
            color: var(--text-primary);
            text-decoration: none;
            font-size: 0.75rem;
            transition: all 0.2s;
        }

        .control-btn i {
            font-size: 1.2rem;
            margin-bottom: 4px;
        }

        .control-btn.active {
            background: var(--accent-blue);
            color: white;
            border-color: var(--accent-blue);
        }

        /* ===== АДАПТИВНОСТЬ ===== */
        @media (max-width: 480px) {
            .capital-amount {
                font-size: 1.8rem;
            }
            
            .quick-actions {
                grid-template-columns: repeat(2, 1fr);
                gap: 8px;
            }
            
            .metrics-grid {
                grid-template-columns: 1fr;
            }
            
            .control-grid {
                grid-template-columns: repeat(5, 1fr);
            }
            
            .control-btn span {
                font-size: 0.7rem;
            }
        }

        @media (min-width: 768px) {
            .container {
                max-width: 720px;
                padding: 20px;
            }
            
            .quick-actions {
                grid-template-columns: repeat(8, 1fr);
            }
            
            .metrics-grid {
                grid-template-columns: repeat(4, 1fr);
            }
        }

        /* ===== УТИЛИТЫ ===== */
        .positive { color: var(--accent-green); }
        .negative { color: var(--accent-red); }
        .neutral { color: var(--text-secondary); }
        
        .text-sm { font-size: 0.85rem; }
        .text-xs { font-size: 0.75rem; }
        
        .mb-2 { margin-bottom: 8px; }
        .mb-3 { margin-bottom: 12px; }
        .mb-4 { margin-bottom: 16px; }
        
        .refresh-note {
            text-align: center;
            color: var(--text-secondary);
            font-size: 0.8rem;
            padding: 12px;
            border-top: 1px solid var(--border-color);
            margin-top: 20px;
        }
        
        .error-message {
            background: rgba(239, 68, 68, 0.15);
            border: 1px solid var(--accent-red);
            border-radius: 12px;
            padding: 16px;
            margin: 16px 0;
            color: var(--accent-red);
        }
    </style>
</head>
<body>
    <div class="container">
        <!-- ШАПКА - КАПИТАЛ И СТАТУС -->
        <div class="header">
            <div class="capital-display">
                <div class="capital-amount">
                    {{ "{:,.0f}".format(virtual_portfolio_value).replace(",", " ") }} ₽
                </div>
                <div class="capital-change {% if total_virtual_return >= 0 %}positive{% else %}negative{% endif %}">
                    {% if total_virtual_return >= 0 %}+{% endif %}{{ "%.2f"|format(total_virtual_return) }}%
                </div>
            </div>
            <div class="status-bar">
                <div class="status-badge {% if bot_status.startswith('▶️') or bot_status.startswith('🚀') %}active{% else %}paused{% endif %}">
                    <i class="fas fa-robot"></i>
                    <span>{{ bot_status }}</span>
                </div>
                <div class="text-sm">
                    <i class="fas fa-history"></i> Сессий: {{ session_count }}
                </div>
            </div>
        </div>

        <!-- БЫСТРЫЕ ДЕЙСТВИЯ -->
        <div class="quick-actions">
            <a href="/force" class="action-btn primary">
                <i class="fas fa-play"></i>
                <span>Запуск</span>
            </a>
            <a href="/analyze" class="action-btn">
                <i class="fas fa-brain"></i>
                <span>Анализ</span>
            </a>
            <a href="/test_pipeline" class="action-btn">
                <i class="fas fa-code-branch"></i>
                <span>Тест</span>
            </a>
            <a href="/trades" class="action-btn success">
                <i class="fas fa-chart-line"></i>
                <span>Сделки</span>
            </a>
            <a href="/test_gigachat_fixed" class="action-btn">
                <i class="fas fa-comment-dots"></i>
                <span>GigaChat</span>
            </a>
            <a href="/test_finam" class="action-btn">
                <i class="fas fa-ruble-sign"></i>
                <span>Finam</span>
            </a>
            <a href="/stats" class="action-btn">
                <i class="fas fa-chart-bar"></i>
                <span>Статистика</span>
            </a>
            <a href="/env" class="action-btn danger">
                <i class="fas fa-cog"></i>
                <span>Настройки</span>
            </a>
        </div>

        <!-- КЛЮЧЕВЫЕ МЕТРИКИ -->
        <div class="metrics-grid">
            <div class="metric-card success">
                <div class="metric-label">Прибыль</div>
                <div class="metric-value {% if total_virtual_profit >= 0 %}positive{% else %}negative{% endif %}">
                    {{ "%+.0f"|format(total_virtual_profit) }} ₽
                </div>
                <div class="metric-subtext">Всего</div>
            </div>
            
            <div class="metric-card">
                <div class="metric-label">Сделок</div>
                <div class="metric-value">{{ trade_history|length if trade_history else 0 }}</div>
                <div class="metric-subtext">Всего исполнено</div>
            </div>
            
            <div class="metric-card warning">
                <div class="metric-label">Новостей</div>
                <div class="metric-value">{{ last_news_count }}</div>
                <div class="metric-subtext">Последняя проверка</div>
            </div>
            
            <div class="metric-card">
                <div class="metric-label">Эффективность</div>
                <div class="metric-value">
                    {% if pipeline_stats %}
                        {{ "%.1f"|format(pipeline_stats.get('gigachat_success_rate', 0)) }}%
                    {% else %}
                        0%
                    {% endif %}
                </div>
                <div class="metric-subtext">GigaChat</div>
            </div>
        </div>

        <!-- ЛЕНТА СИГНАЛОВ GIGACHAT -->
        {% if last_signals and last_signals|length > 0 %}
        <div class="signals-section">
            <div class="section-header">
                <h2 class="section-title">
                    <i class="fas fa-bolt"></i>
                    Последние сигналы GigaChat
                </h2>
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
                        <div class="signal-confidence">
                            {{ "%.2f"|format(signal.confidence) if signal.confidence else "0.00" }}
                        </div>
                    </div>
                    
                    <div class="signal-meta">
                        <span><i class="fas fa-project-diagram"></i> {{ signal.event_type|replace('_', ' ')|title if signal.event_type else 'N/A' }}</span>
                        <span><i class="fas fa-wave-square"></i> Impact: {{ signal.impact_score if signal.impact_score else 0 }}/10</span>
                        <span><i class="fas fa-clock"></i> {{ signal.timestamp[11:19] if signal.timestamp else 'N/A' }}</span>
                    </div>
                    
                    <div class="signal-reason mb-2">
                        {{ signal.reason[:80] if signal.reason else 'Нет описания' }}{% if signal.reason and signal.reason|length > 80 %}...{% endif %}
                    </div>
                    
                    <div class="impact-badge {% if signal.impact_score and signal.impact_score >= 7 %}impact-high{% elif signal.impact_score and signal.impact_score >= 4 %}impact-medium{% else %}impact-low{% endif %}">
                        Сила сигнала: {{ signal.impact_score if signal.impact_score else 0 }}/10
                    </div>
                </div>
                {% endfor %}
            </div>
        </div>
        {% endif %}

        <!-- АКТИВНЫЕ ПОЗИЦИИ -->
        {% if portfolio_positions and portfolio_positions|length > 0 %}
        <div class="signals-section">
            <div class="section-header">
                <h2 class="section-title">
                    <i class="fas fa-chart-line"></i>
                    Активные позиции
                </h2>
                <span class="text-sm">{{ portfolio_positions|length }} открыто</span>
            </div>
            
            <div class="signal-list">
                {% for ticker, pos in portfolio_positions.items() %}
                <div class="signal-card">
                    <div class="signal-header">
                        <div class="signal-ticker">
                            <i class="fas fa-coins positive"></i>
                            {{ ticker }}
                            <span class="text-sm neutral">×{{ pos.size if pos.size else 0 }}</span>
                        </div>
                        <div class="signal-confidence">
                            {{ "%.0f"|format(pos.avg_price) if pos.avg_price else "0" }} ₽
                        </div>
                    </div>
                    
                    <div class="signal-meta">
                        <span><i class="fas fa-sign-in-alt"></i> Вход: {{ pos.entry_time[11:16] if pos.entry_time else 'N/A' }}</span>
                        <span><i class="fas fa-robot"></i> {{ pos.get('ai_provider', 'unknown') }}</span>
                    </div>
                    
                    <div class="signal-reason">
                        Стоп: {{ "%.2f"|format(pos.stop_loss) if pos.stop_loss else "0.00" }} ₽ 
                        (-{{ pos.stop_loss_percent if pos.stop_loss_percent else "0.0" }}%)
                    </div>
                </div>
                {% endfor %}
            </div>
        </div>
        {% endif %}

        <!-- СИСТЕМНАЯ ИНФОРМАЦИЯ -->
        <div class="metric-card">
            <div class="metric-label">Системная информация</div>
            <div class="text-sm mb-2">
                <i class="fas fa-microchip"></i> Аптайм: {{ uptime_str }}
            </div>
            <div class="text-sm mb-2">
                <i class="fas fa-calendar"></i> Последняя торговля: {{ last_trading_time }}
            </div>
            <div class="text-sm">
                <i class="fas fa-sync-alt"></i> Автообновление: каждые 45 сек
            </div>
        </div>

        <div class="refresh-note">
            <i class="fas fa-sync"></i> Страница обновляется автоматически
        </div>
    </div>

    <!-- ФИКСИРОВАННАЯ ПАНЕЛЬ УПРАВЛЕНИЯ ДЛЯ ТЕЛЕФОНА -->
    <div class="control-bar">
        <div class="control-grid">
            <a href="/" class="control-btn active">
                <i class="fas fa-home"></i>
                <span>Главная</span>
            </a>
            <a href="/force" class="control-btn">
                <i class="fas fa-play"></i>
                <span>Старт</span>
            </a>
            <a href="/trades" class="control-btn">
                <i class="fas fa-history"></i>
                <span>Сделки</span>
            </a>
            <a href="/status" class="control-btn">
                <i class="fas fa-heartbeat"></i>
                <span>Статус</span>
            </a>
            <a href="/test_gigachat_fixed" class="control-btn">
                <i class="fas fa-robot"></i>
                <span>ИИ</span>
            </a>
        </div>
    </div>
</body>
</html>
'''

async def trading_session_async(force_mode=False):
    """Основная торговая сессия с SignalPipeline"""
    global last_trading_time, session_count, trade_history
    global total_virtual_profit, total_virtual_return, is_trading
    global bot_status, last_news_count, last_signals, system_stats, pipeline_stats
    
    if is_trading:
        logger.info("⏸️ Торговая сессия уже выполняется")
        return
    
    is_trading = True
    session_count += 1
    current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    last_trading_time = current_time
    
    mode_label = "🚀 ПРИНУДИТЕЛЬНАЯ" if force_mode else "🤖 РАСПИСАНИЕ"
    logger.info(f"{mode_label} ТОРГОВАЯ СЕССИЯ #{session_count} - {current_time}")
    logger.info("=" * 60)
    
    try:
        # 1. Сбор новостей
        logger.info("📰 Сбор новостей из всех источников...")
        all_news = await news_fetcher.fetch_all_news()
        last_news_count = len(all_news)
        
        if not all_news:
            logger.warning("⚠️ Новостей не найдено")
            bot_status = f"⏸️ Ожидание новостей | Сессия #{session_count}"
            return
        
        logger.info(f"✅ Получено {len(all_news)} новостей")
        
        # 2. Обработка через SignalPipeline
        logger.info("⚙️ Обработка через SignalPipeline...")
        signals = await signal_pipeline.process_news_batch(all_news)
        
        # Сохраняем статистику pipeline
        pipeline_stats = signal_pipeline.get_stats()
        
        # Сохраняем последние сигналы для отображения
        last_signals = signals[:10]
        
        if not signals:
            logger.info("ℹ️ Нет торговых сигналов для выполнения")
            bot_status = f"⏸️ Нет сигналов | Сессия #{session_count}"
            return
        
        logger.info(f"✅ Сформировано {len(signals)} сигналов")
        
        # 3. Получение текущих цен
        logger.info("💰 Получение текущих цен...")
        current_prices = {}
        tickers_to_check = list(set(signal['ticker'] for signal in signals))
        
        for ticker in tickers_to_check:
            try:
                price = await tinkoff_executor.get_current_price(ticker)
                if price:
                    current_prices[ticker] = price
                else:
                    logger.warning(f"⚠️ Не удалось получить цену для {ticker}")
            except Exception as e:
                logger.error(f"❌ Ошибка получения цены {ticker}: {str(e)[:50]}")
        
        if not current_prices:
            logger.error("❌ Не удалось получить цены ни для одного тикера")
            # Используем fallback цены для продолжения тестирования
            for signal in signals:
                ticker = signal['ticker']
                if ticker in tinkoff_executor.fallback_prices:
                    current_prices[ticker] = tinkoff_executor.fallback_prices[ticker]
                    logger.info(f"📊 Использую fallback цену для {ticker}")
            
            if not current_prices:
                logger.error("❌ Нет даже fallback цен")
                return
        
        # 4. Обновление позиций в RiskManager
        risk_manager.update_positions(virtual_portfolio.positions)
        
        # 5. Проверка условий выхода из позиций
        exit_signals = virtual_portfolio.check_exit_conditions(current_prices)
        
        # 6. Исполнение сделок (виртуальных)
        all_trades = signals + exit_signals
        executed_trades = []
        
        for signal in all_trades:
            try:
                ticker = signal['ticker']
                if ticker in current_prices:
                    trade_result = virtual_portfolio.execute_trade(signal, current_prices[ticker])
                    if trade_result:
                        executed_trades.append(trade_result)
                else:
                    logger.warning(f"⚠️ Нет цены для исполнения сигнала {ticker}")
            except Exception as e:
                logger.error(f"❌ Ошибка исполнения сигнала {signal.get('ticker', 'unknown')}: {str(e)[:50]}")
        
        # 7. Обновление истории и статистики
        trade_history.extend(executed_trades)
        
        # Расчет прибыли
        session_profit = sum(trade.get('profit', 0) for trade in executed_trades)
        total_virtual_profit += session_profit
        
        # Расчет общей стоимости портфеля
        total_value = virtual_portfolio.get_total_value(current_prices)
        total_virtual_return = ((total_value - 100000) / 100000) * 100
        
        # Обновление статистики системы
        system_stats = {
            'total_news_processed': last_news_count,
            'total_signals_generated': len(signals),
            'total_trades_executed': len(executed_trades),
            'session_profit': session_profit,
            'nlp_stats': nlp_engine.get_stats(),
            'decision_engine_stats': decision_engine.get_stats(),
            'virtual_portfolio_stats': virtual_portfolio.get_stats(),
            'pipeline_stats': pipeline_stats,
            'finam_verifier_stats': {
                'liquid_tickers_count': len(finam_verifier.liquid_tickers)
            }
        }
        
        # Обновление статуса
        if len(signals) > 0:
            bot_status = f"▶️ Анализ | Сессия #{session_count}"
        else:
            bot_status = f"⏸️ Нет сигналов | Сессия #{session_count}"
        
        logger.info(f"💰 СЕССИЯ #{session_count} ЗАВЕРШЕНА")
        logger.info(f"💎 Портфель: {total_value:.2f} руб. ({total_virtual_return:+.2f}%)")
        logger.info(f"🎯 Прибыль за сессию: {session_profit:+.2f} руб.")
        logger.info(f"📊 Pipeline: {pipeline_stats.get('gigachat_success_rate', 0):.1f}% эффективность")
        
        if executed_trades:
            for trade in executed_trades:
                if trade.get('status') == 'EXECUTED':
                    profit = trade.get('profit', 0)
                    symbol = '🟢' if profit >= 0 else '🔴'
                    logger.info(f"{symbol} {trade.get('action', '')} {trade.get('ticker', '')} x{trade.get('size', 0)}: {profit:+.2f} руб.")
        
    except Exception as e:
        logger.error(f"❌ КРИТИЧЕСКАЯ ошибка в торговой сессии: {str(e)}")
        import traceback
        logger.error(f"Трейсбек: {traceback.format_exc()[:500]}")
        bot_status = f"⚠️ Ошибка: {str(e)[:30]}..."
        
    finally:
        # ГАРАНТИРОВАННО сбрасываем флаг даже при ошибке
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
    
    # Настройка интервала из переменных окружения
    check_interval = int(os.getenv("CHECK_INTERVAL_MINUTES", "30"))
    
    schedule.every(check_interval).minutes.do(lambda: run_trading_session(False))
    logger.info(f"📅 Планировщик настроен: каждые {check_interval} минут")

def run_scheduler():
    """Фоновая задача планировщика"""
    while True:
        schedule.run_pending()
        time.sleep(1)

# ==================== СИНХРОННЫЕ ВРАППЕРЫ ДЛЯ ASYNC ФУНКЦИЙ ====================

@app.route('/test_pipeline')
def test_pipeline():
    """Тест SignalPipeline"""
    async def _test():
        test_news = {
            'id': 'test_001',
            'title': 'Сбербанк рекомендовал увеличение дивидендов на 20%',
            'description': 'Совет директоров Сбербанка рекомендовал увеличение дивидендов',
            'content': 'Сбербанк увеличивает дивиденды, что положительно скажется на котировках',
            'source': 'test',
            'published_at': datetime.datetime.now().isoformat()
        }
        
        signal = await signal_pipeline._process_single_news(test_news)
        
        return jsonify({
            'pipeline_test': 'success' if signal else 'no_signal',
            'test_news': test_news['title'],
            'signal': signal,
            'pipeline_stats': signal_pipeline.get_stats(),
            'timestamp': datetime.datetime.now().isoformat()
        })
    
    try:
        return asyncio.run(_test())
    except Exception as e:
        return jsonify({
            'pipeline_test': 'error',
            'error': str(e),
            'timestamp': datetime.datetime.now().isoformat()
        })

@app.route('/test_finam')
def test_finam():
    """Тест Finam API"""
    async def _test():
        test_ticker = 'SBER'
        
        price = await tinkoff_executor.get_price_from_finam(test_ticker)
        
        test_analysis = {
            'tickers': [test_ticker],
            'event_type': 'dividend',
            'sentiment': 'positive',
            'impact_score': 7
        }
        
        verification = await finam_verifier.verify_signal(test_analysis)
        
        return jsonify({
            'finam_test': 'success',
            'test_ticker': test_ticker,
            'price_from_finam': price,
            'verification_result': verification,
            'liquid_tickers_count': len(finam_verifier.liquid_tickers),
            'timestamp': datetime.datetime.now().isoformat()
        })
    
    try:
        return asyncio.run(_test())
    except Exception as e:
        return jsonify({
            'finam_test': 'error',
            'error': str(e),
            'timestamp': datetime.datetime.now().isoformat()
        })

@app.route('/test_gigachat_fixed')
def test_gigachat_fixed():
    """Тест исправленного GigaChat API"""
    
    async def _test():
        if not os.getenv('GIGACHAT_CLIENT_ID') or not os.getenv('GIGACHAT_CLIENT_SECRET'):
            return jsonify({
                "error": "Требуются GIGACHAT_CLIENT_ID и GIGACHAT_CLIENT_SECRET",
                "status": "configuration_error"
            })
        
        test_news = {
            'id': 'giga_test',
            'title': 'Тест GigaChat API',
            'description': 'Тестирование работы GigaChat'
        }
        
        analysis = await nlp_engine.analyze_news(test_news)
        
        return jsonify({
            "status": "success" if analysis else "no_analysis",
            "gigachat_configured": nlp_engine.enabled,
            "analysis_result": analysis,
            "nlp_stats": nlp_engine.get_stats(),
            "timestamp": datetime.datetime.now().isoformat()
        })
    
    try:
        return asyncio.run(_test())
    except Exception as e:
        return jsonify({
            "status": "exception",
            "error": str(e),
            "timestamp": datetime.datetime.now().isoformat()
        })

# ==================== ОСНОВНЫЕ РОУТЫ ====================

@app.route('/')
def home():
    """Главная страница с новым интерфейсом"""
    global request_count
    request_count += 1
    
    # Расчет аптайма
    uptime = datetime.datetime.now() - start_time
    uptime_str = str(uptime).split('.')[0]
    
    # Получение данных о портфеле
    try:
        virtual_portfolio_value = virtual_portfolio.get_total_value({})
        portfolio_positions = virtual_portfolio.positions
    except Exception as e:
        logger.error(f"❌ Ошибка получения данных портфеля: {e}")
        virtual_portfolio_value = 100000
        portfolio_positions = {}
    
    # Рендеринг нового HTML
    return render_template_string(
        HTML_TEMPLATE,
        bot_status=bot_status,
        uptime_str=uptime_str,
        session_count=session_count,
        last_trading_time=last_trading_time,
        request_count=request_count,
        virtual_portfolio_value=virtual_portfolio_value,
        total_virtual_return=total_virtual_return,
        total_virtual_profit=total_virtual_profit,
        last_news_count=last_news_count,
        last_signals=last_signals[:5] if last_signals else [],
        portfolio_positions=portfolio_positions,  # Переименовано для ясности
        pipeline_stats=pipeline_stats,
        trade_history=trade_history
    )

@app.route('/force')
def force_trade():
    """Принудительный запуск торговой сессии"""
    run_trading_session(force_mode=True)
    return jsonify({
        "message": "🚀 Принудительный запуск торговой сессии (Signal Pipeline)",
        "timestamp": datetime.datetime.now().isoformat(),
        "force_mode": True,
        "session_number": session_count + 1
    })

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
            {icon}{ai_badge} {trade['timestamp'][11:19]} | {trade.get('strategy', 'AI Trading')}
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
                .risk-params {{ background: rgba(59, 130, 246, 0.15); padding: 12px; border-radius: 10px; margin: 8px 0; border: 1px solid #3b82f6; }}
                .back-btn {{ background: #3b82f6; color: white; padding: 10px 16px; text-decoration: none; border-radius: 10px; display: inline-block; margin-top: 15px; font-weight: 600; }}
            </style>
        </head>
        <body>
            <div class="container">
                <h2 style="color: #f1f5f9; margin-bottom: 20px;">📋 История Сделок</h2>
                
                <div class="stats">
                    <h4 style="color: #94a3b8; margin-bottom: 10px;">📊 Статистика</h4>
                    <p><strong>Всего сделок:</strong> {len(trade_history)}</p>
                    <p><strong>Портфель:</strong> {virtual_portfolio.get_total_value({}):.0f} руб. 
                    (<span class="{{'positive' if total_virtual_return >= 0 else 'negative'}}">{total_virtual_return:+.1f}%</span>)</p>
                    <p><strong>Общая прибыль:</strong> <span class="{{'positive' if total_virtual_profit >= 0 else 'negative'}}">{total_virtual_profit:+.0f} руб.</span></p>
                </div>
                
                <div class="risk-params">
                    <h4 style="color: #94a3b8; margin-bottom: 10px;">🎯 Риски</h4>
                    <p><strong>Риск на сделку:</strong> {risk_stats.get('risk_per_trade', 1.5)}%</p>
                    <p><strong>Стоп-лосс:</strong> {risk_stats['parameters']['stop_loss_pct']}%</p>
                    <p><strong>Тейк-профит:</strong> {risk_stats['parameters']['take_profit_pct']}%</p>
                </div>
                
                {trades_html if trade_history else "<p style='text-align: center; color: #94a3b8;'>Сделок еще нет</p>"}
                
                <p style="margin-top: 20px;">
                    <a href="/" class="back-btn">← На главную</a>
                </p>
            </div>
        </body>
    </html>
    """

@app.route('/status')
def status():
    """JSON статус системы"""
    portfolio_stats = virtual_portfolio.get_stats()
    uptime = datetime.datetime.now() - start_time
    
    nlp_stats = nlp_engine.get_stats()
    risk_stats = risk_manager.get_risk_stats()
    
    return jsonify({
        "status": bot_status,
        "uptime_seconds": int(uptime.total_seconds()),
        "requests_served": request_count,
        "trading_sessions": session_count,
        "total_trades": len(trade_history),
        "virtual_portfolio_value": virtual_portfolio.get_total_value({}),
        "virtual_return_percentage": total_virtual_return,
        "total_profit": total_virtual_profit,
        "last_trading_time": last_trading_time,
        "portfolio_stats": portfolio_stats,
        "nlp_stats": nlp_stats,
        "risk_stats": risk_stats,
        "pipeline_stats": pipeline_stats,
        "system_stats": system_stats,
        "last_news_count": last_news_count,
        "last_signals_count": len(last_signals) if last_signals else 0,
        "timestamp": datetime.datetime.now().isoformat(),
        "strategy": "GigaChat Dynamic Risk",
        "trading_mode": os.getenv("TRADING_MODE", "AGGRESSIVE_TEST"),
        "check_interval": os.getenv("CHECK_INTERVAL_MINUTES", 30),
        "ai_provider": "gigachat",
        "providers_configured": {
            "gigachat": nlp_engine.enabled,
            "enhanced_analyzer": True
        }
    })

@app.route('/stats')
def detailed_stats():
    """Детальная статистика"""
    portfolio_stats = virtual_portfolio.get_stats()
    risk_stats = risk_manager.get_risk_stats()
    
    ai_trades = [t for t in trade_history if t.get('ai_generated')]
    simple_trades = [t for t in trade_history if not t.get('ai_generated')]
    
    ai_profits = [t.get('profit', 0) for t in ai_trades if t.get('profit') is not None]
    simple_profits = [t.get('profit', 0) for t in simple_trades if t.get('profit') is not None]
    
    ai_avg = sum(ai_profits)/len(ai_profits) if ai_profits else 0
    simple_avg = sum(simple_profits)/len(simple_profits) if simple_profits else 0
    
    pipeline_efficiency = pipeline_stats.get('gigachat_success_rate', 0) if pipeline_stats else 0
    
    return jsonify({
        "performance_summary": {
            "total_trades": len(trade_history),
            "ai_trades": len(ai_trades),
            "simple_trades": len(simple_trades),
            "win_rate": portfolio_stats.get('win_rate', 0),
            "total_profit": total_virtual_profit,
            "virtual_return": total_virtual_return,
            "pipeline_efficiency": round(pipeline_efficiency, 1)
        },
        "ai_performance": {
            "total_signals": system_stats.get('total_signals_generated', 0),
            "executed_trades": len(ai_trades),
            "avg_profit_per_trade": ai_avg,
            "success_rate": (len([p for p in ai_profits if p > 0]) / len(ai_profits) * 100) if ai_profits else 0
        },
        "risk_management": {
            "current_capital": risk_stats.get('current_capital', 100000),
            "risk_per_trade": risk_stats.get('risk_per_trade', 2.5),
            "sector_risks": risk_stats.get('sector_risks', {}),
            "open_positions": len(virtual_portfolio.positions),
            "max_drawdown": portfolio_stats.get('max_drawdown', 0)
        },
        "pipeline_performance": pipeline_stats,
        "portfolio_status": {
            "current_value": virtual_portfolio.get_total_value({}),
            "positions_count": len(virtual_portfolio.positions),
            "available_cash": virtual_portfolio.cash,
            "positions": list(virtual_portfolio.positions.keys())
        }
    })

@app.route('/test_moex')
def test_moex():
    """Тест MOEX API"""
    async def _test():
        result = await tinkoff_executor.test_connections()
        return jsonify(result)
    
    try:
        return asyncio.run(_test())
    except Exception as e:
        return jsonify({"error": str(e)})

@app.route('/analyze')
def analyze_only():
    """Только анализ без торговли"""
    async def _analyze():
        all_news = await news_fetcher.fetch_all_news()
        
        # Обработка через pipeline
        signals = await signal_pipeline.process_news_batch(all_news[:5])
        
        return {
            "analysis_time": datetime.datetime.now().isoformat(),
            "total_news": len(all_news),
            "signals_generated": len(signals),
            "sample_signals": signals[:3] if signals else [],
            "pipeline_stats": signal_pipeline.get_stats(),
            "nlp_stats": nlp_engine.get_stats(),
            "prefilter_stats": news_prefilter.get_filter_stats(all_news[:10])
        }
    
    try:
        result = asyncio.run(_analyze())
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)})

@app.route('/test_providers')
def test_providers_page():
    """Страница тестирования провайдеров"""
    
    providers_info = {
        'gigachat': {
            'configured': nlp_engine.enabled,
            'status': '✅ Настроен' if nlp_engine.enabled else '❌ Не настроен',
            'client_id_preview': os.getenv('GIGACHAT_CLIENT_ID', '')[:10] + '...' if os.getenv('GIGACHAT_CLIENT_ID') else 'Нет',
            'client_secret_preview': '****' + os.getenv('GIGACHAT_CLIENT_SECRET', '')[-4:] if os.getenv('GIGACHAT_CLIENT_SECRET') else 'Нет'
        },
        'finam': {
            'configured': bool(finam_verifier.finam_client),
            'status': '✅ Настроен' if finam_verifier.finam_client else '❌ Не настроен',
            'token_preview': finam_verifier.jwt_token[:8] + '...' if finam_verifier.jwt_token else 'Нет',
            'liquid_tickers': len(finam_verifier.liquid_tickers)
        }
    }
    
    return f'''
    <html>
        <head>
            <title>Тест провайдеров</title>
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <style>
                body {{ font-family: Arial; margin: 20px; background: #0f172a; color: #e2e8f0; font-size: 14px; }}
                .container {{ max-width: 100%; margin: 0 auto; background: #1e293b; padding: 20px; border-radius: 16px; box-shadow: 0 8px 32px rgba(0,0,0,0.3); border: 1px solid #334155; }}
                .provider {{ padding: 15px; margin: 12px 0; border-radius: 12px; border-left: 4px solid #3b82f6; background: rgba(30, 41, 59, 0.8); border: 1px solid #334155; }}
                .btn {{ display: inline-block; padding: 10px 16px; margin: 6px 4px; border-radius: 10px; text-decoration: none; color: white; font-weight: 600; font-size: 0.9rem; border: none; }}
                .btn-test {{ background: #10b981; }}
                .btn-back {{ background: #3b82f6; }}
                .btn-pipeline {{ background: #8b5cf6; }}
            </style>
        </head>
        <body>
            <div class="container">
                <h2 style="color: #f1f5f9; margin-bottom: 20px;">🔧 Тестирование провайдеров</h2>
                
                <div class="provider">
                    <h4 style="color: #94a3b8; margin-bottom: 10px;">🏦 GigaChat API</h4>
                    <p><strong>Статус:</strong> {providers_info['gigachat']['status']}</p>
                    <p><strong>Client ID:</strong> {providers_info['gigachat']['client_id_preview']}</p>
                    <p><strong>Scope:</strong> GIGACHAT_API_PERS</p>
                    <a href="/test_gigachat_fixed" class="btn btn-test">🧪 Тест GigaChat</a>
                </div>
                
                <div class="provider">
                    <h4 style="color: #94a3b8; margin-bottom: 10px;">🏦 Finam API</h4>
                    <p><strong>Статус:</strong> {providers_info['finam']['status']}</p>
                    <p><strong>Тикеров:</strong> {providers_info['finam']['liquid_tickers']}</p>
                    <a href="/test_finam" class="btn btn-test">🧪 Тест Finam</a>
                </div>
                
                <div style="margin-top: 20px;">
                    <a href="/" class="btn btn-back">← На главную</a>
                    <a href="/test_pipeline" class="btn btn-pipeline">⚙️ Pipeline</a>
                    <a href="/analyze" class="btn btn-test">📰 Анализ</a>
                    <a href="/force" class="btn btn-test">🚀 Торговля</a>
                </div>
            </div>
        </body>
    </html>
    '''

@app.route('/env')
def show_env():
    """Показать переменные окружения (безопасно)"""
    
    env_vars = {}
    for key, value in sorted(os.environ.items()):
        if any(word in key.upper() for word in ['API', 'TOKEN', 'KEY', 'SECRET']):
            if value and len(value) > 8:
                masked = value[:4] + '*' * max(0, len(value)-8) + value[-4:]
                env_vars[key] = f"{masked} (длина: {len(value)})"
            else:
                env_vars[key] = "****"
        elif 'MODE' in key or 'INTERVAL' in key or 'CONFIDENCE' in key or 'SCORE' in key or 'SIZE' in key or 'LOSS' in key or 'RISK' in key:
            env_vars[key] = value
    
    return jsonify({
        "environment_variables": env_vars,
        "total_vars": len(env_vars),
        "timestamp": datetime.datetime.now().isoformat()
    })

@app.route('/check_gigachat')
def check_gigachat():
    """Проверка настроек GigaChat"""
    import base64
    
    client_id = os.getenv('GIGACHAT_CLIENT_ID')
    client_secret = os.getenv('GIGACHAT_CLIENT_SECRET')
    scope = os.getenv('GIGACHAT_SCOPE', 'GIGACHAT_API_PERS')
    
    result = {
        'client_id_exists': bool(client_id),
        'client_id_length': len(client_id) if client_id else 0,
        'client_secret_exists': bool(client_secret),
        'client_secret_length': len(client_secret) if client_secret else 0,
        'scope': scope,
        'problem': None
    }
    
    if not client_id or not client_secret:
        result['problem'] = 'Missing client_id or client_secret'
    elif len(client_id) < 5 or len(client_secret) < 5:
        result['problem'] = 'client_id or client_secret too short'
    elif 'GIGACHAT_API_PERS' not in scope:
        result['problem'] = f'Wrong scope: {scope}, should be GIGACHAT_API_PERS'
    else:
        try:
            auth_string = f"{client_id}:{client_secret}"
            auth_base64 = base64.b64encode(auth_string.encode()).decode()
            result['base64_first_30'] = auth_base64[:30]
            result['base64_length'] = len(auth_base64)
            result['problem'] = 'Credentials seem valid'
        except Exception as e:
            result['problem'] = f'Base64 error: {str(e)}'
    
    return jsonify(result)

@app.route('/test_openrouter')
def test_openrouter():
    """Тест OpenRouter API"""
    async def _test():
        import httpx
        
        headers = {
            "Authorization": f"Bearer {os.getenv('OPENROUTER_API_TOKEN')}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://github.com"
        }
        
        data = {
            "model": "google/gemini-2.0-flash:free",
            "messages": [{"role": "user", "content": "Hello"}],
            "max_tokens": 10,
            "temperature": 0.1
        }
        
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers=headers,
                json=data
            )
            
            return jsonify({
                "status": response.status_code,
                "success": response.status_code == 200,
                "response": response.text[:200] if response.status_code != 200 else "OK"
            })
    
    try:
        return asyncio.run(_test())
    except Exception as e:
        return jsonify({"error": str(e)})

if __name__ == '__main__':
    # Запуск планировщика
    schedule_tasks()
    scheduler_thread = threading.Thread(target=run_scheduler)
    scheduler_thread.daemon = True
    scheduler_thread.start()
    
    # Инициализация системы
    logger.info("=" * 60)
    logger.info("🚀 AI НОВОСТНОЙ ТРЕЙДЕР 'SENTIMENT HUNTER' v4.1 ЗАПУЩЕН!")
    logger.info(f"🏦 ИИ-ПРОВАЙДЕР: GigaChat API {'✅' if nlp_engine.enabled else '❌ ВЫКЛ (проверь ключи!)'}")
    
    # Статистика GigaChat
    if nlp_engine.enabled:
        giga_stats = nlp_engine.get_stats()
        logger.info(f"   • Токен активен: {'✅' if nlp_engine.gigachat_auth and nlp_engine.gigachat_auth.access_token else '❌'}")
        logger.info(f"   • Семафор: {giga_stats.get('semaphore_queue', 1)} одновременных запроса")
    else:
        logger.warning("   ⚠️ GigaChat отключен! Система будет работать без ИИ-анализа")
    
    # RiskManager информация
    risk_stats = risk_manager.get_risk_stats()
    logger.info(f"🎯 РИСК-МЕНЕДЖМЕНТ: АГРЕССИВНЫЙ ТЕСТ (динамический)")
    logger.info(f"   • Базовый риск: {risk_manager.risk_per_trade}% капитала")
    logger.info(f"   • Диапазон риска: {risk_manager.impact_multipliers[1]*100:.0f}%-{risk_manager.impact_multipliers[10]*100:.0f}% от базового")
    logger.info(f"   • Стоп-лосс: {risk_manager.stop_loss_pct}% (динамический)")
    logger.info(f"   • Тейк-профит: {risk_manager.take_profit_pct}% (динамический)")
    logger.info(f"   • Мин. confidence: {risk_manager.min_confidence}")
    logger.info(f"   • Мин. impact_score: {risk_manager.min_impact_score}")
    
    # Портфельные лимиты
    logger.info(f"💰 УПРАВЛЕНИЕ КАПИТАЛОМ:")
    logger.info(f"   • Макс. позиция: {risk_manager.portfolio_limits['max_position_value']*100:.0f}% портфеля")
    logger.info(f"   • STOP ALL при: {risk_manager.portfolio_limits['max_daily_loss']*100:.0f}% дневной просадки")
    logger.info(f"   • Капитал: {risk_manager.current_capital:.0f} руб. (виртуальный)")
    
    # Источники данных
    logger.info(f"📊 ДАННЫЕ И ИСТОЧНИКИ:")
    logger.info(f"   • Finam API: {'✅' if finam_verifier.finam_client else '❌'}")
    logger.info(f"   • MOEX источники: {len(news_fetcher.rss_feeds)} RSS")
    logger.info(f"   • NewsAPI: {'✅' if news_fetcher.newsapi_key else '❌'}")
    logger.info(f"   • EnhancedAnalyzer: ✅ ({len(enhanced_analyzer.TICKER_MAP)} тикеров)")
    
    # Конвейер
    pipeline_stats = signal_pipeline.get_stats()
    logger.info(f"⚙️ КОНВЕЙЕР ОБРАБОТКИ:")
    logger.info(f"   • Режим: {pipeline_stats.get('processing_mode', 'gigachat_sequential')}")
    logger.info(f"   • Кэш новостей: {pipeline_stats.get('news_cache_size', 0)} записей")
    logger.info(f"   • TTL кэша: {signal_pipeline.cache_ttl} сек.")
    
    # Режим работы
    logger.info(f"⚡ РЕЖИМ РАБОТЫ:")
    logger.info(f"   • Торговый режим: {os.getenv('TRADING_MODE', 'AGGRESSIVE_TEST')}")
    logger.info(f"   • Проверка каждые: {os.getenv('CHECK_INTERVAL_MINUTES', 30)} минут")
    logger.info(f"   • Фильтр новостей: УСИЛЕННЫЙ (PreFilter)")
    
    # Доступные эндпоинты
    logger.info(f"🌐 ВЕБ-ИНТЕРФЕЙС И API:")
    logger.info(f"   • Веб-интерфейс: http://0.0.0.0:10000")
    logger.info(f"   • Статус системы: /status")
    logger.info(f"   • Тест GigaChat: /test_gigachat_fixed")
    logger.info(f"   • Тест пайплайна: /test_pipeline")
    logger.info(f"   • История сделок: /trades")
    
    # Предупреждения
    if not nlp_engine.enabled:
        logger.warning("⚠️  ВНИМАНИЕ: GigaChat отключен! Система будет работать только на EnhancedAnalyzer")
        logger.warning("   Настрой GIGACHAT_CLIENT_ID и GIGACHAT_CLIENT_SECRET в переменных окружения")
    
    if not finam_verifier.finam_client:
        logger.warning("⚠️  ВНИМАНИЕ: Finam API недоступен! Будут использоваться fallback цены")
        logger.warning("   Настрой FINAM_API_TOKEN для получения реальных цен")
    
    # Итоговая информация
    logger.info("=" * 60)
    logger.info("🎯 СТРАТЕГИЯ: GigaChat Dynamic Risk")
    logger.info("   • Все сигналы проходят через GigaChat")
    logger.info("   • Риск адаптируется под impact_score (1-10)")
    logger.info("   • Сильные сигналы → больше капитала, ужеще стопы")
    logger.info("   • Слабые сигналы → меньше капитала, шире стопы")
    logger.info("=" * 60)
    
    # Запуск Flask приложения
    try:
        app.run(host='0.0.0.0', port=10000, debug=False, use_reloader=False)
    except Exception as e:
        logger.error(f"❌ Ошибка запуска Flask: {e}")
        raise
