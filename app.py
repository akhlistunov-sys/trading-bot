# app.py - ПОЛНАЯ РАБОЧАЯ ВЕРСИЯ С ИСПРАВЛЕНИЯМИ
from flask import Flask, jsonify, render_template_string
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

# Логируем ЗАГРУЖЕННЫЕ значения для отладки
loaded_confidence = os.getenv("MIN_CONFIDENCE", "NOT_FOUND")
loaded_impact = os.getenv("MIN_IMPACT_SCORE", "NOT_FOUND")
loaded_position = os.getenv("BASE_POSITION_SIZE", "NOT_FOUND")
loaded_stop = os.getenv("BASE_STOP_LOSS", "NOT_FOUND")
loaded_risk = os.getenv("RISK_PER_TRADE", "NOT_FOUND")

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
logger.info(f"   • RISK_PER_TRADE: {loaded_risk}")
logger.info(f"   • MIN_CONFIDENCE: {loaded_confidence}")
logger.info(f"   • MIN_IMPACT_SCORE: {loaded_impact}")
logger.info(f"   • BASE_POSITION_SIZE: {loaded_position}")
logger.info(f"   • BASE_STOP_LOSS: {loaded_stop}")
logger.info("=" * 60)
# ===== КОНЕЦ ИСПРАВЛЕНИЯ =====

# ТЕПЕРЬ импортируем наши модули
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

app = Flask(__name__)

# Глобальные переменные состояния
request_count = 0
last_trading_time = "Еще не запускалась"
bot_status = "🤖 AI Новостной Трейдер - Ожидание запуска"
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

# Инициализация всех модулей
logger.info("🔧 Инициализация всех модулей...")

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

# HTML шаблон для светлого интерфейса (АДАПТИВНЫЙ ДЛЯ ТЕЛЕФОНА)
HTML_TEMPLATE = '''
<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>AI Трейдер v3.0</title>
    <meta http-equiv="refresh" content="30">
    <style>
        * { 
            margin: 0; 
            padding: 0; 
            box-sizing: border-box; 
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
        }
        
        body {
            background: #f8fafc;
            color: #334155;
            line-height: 1.5;
            padding: 10px;
            font-size: 14px;
        }
        
        .container {
            max-width: 100%;
            margin: 0 auto;
        }
        
        /* Шапка - компактная */
        .header {
            background: linear-gradient(135deg, #3b82f6 0%, #1d4ed8 100%);
            color: white;
            padding: 15px;
            border-radius: 12px;
            margin-bottom: 15px;
            box-shadow: 0 4px 12px rgba(59, 130, 246, 0.2);
        }
        
        .header h1 {
            font-size: 1.4rem;
            margin-bottom: 6px;
            display: flex;
            align-items: center;
            gap: 8px;
        }
        
        .header p {
            opacity: 0.9;
            font-size: 0.9rem;
            margin: 3px 0;
        }
        
        /* Карточки - адаптивные */
        .card {
            background: white;
            border-radius: 12px;
            padding: 15px;
            margin-bottom: 12px;
            box-shadow: 0 2px 8px rgba(0, 0, 0, 0.06);
            border: 1px solid #e2e8f0;
        }
        
        .card h3 {
            color: #1e293b;
            margin-bottom: 12px;
            padding-bottom: 8px;
            border-bottom: 2px solid #e2e8f0;
            font-size: 1.1rem;
            display: flex;
            align-items: center;
            gap: 8px;
        }
        
        /* Статистика в строку */
        .stats-row {
            display: flex;
            flex-wrap: wrap;
            gap: 10px;
            margin-bottom: 10px;
        }
        
        .stat-item {
            flex: 1;
            min-width: 120px;
            background: #f8fafc;
            padding: 10px;
            border-radius: 8px;
            text-align: center;
            border: 1px solid #e2e8f0;
        }
        
        .stat-value {
            font-size: 1.4rem;
            font-weight: bold;
            color: #1d4ed8;
            margin: 5px 0;
        }
        
        .stat-label {
            font-size: 0.75rem;
            color: #64748b;
            text-transform: uppercase;
            letter-spacing: 0.3px;
        }
        
        /* Цвета для прибыли/убытков */
        .positive { color: #10b981; font-weight: bold; }
        .negative { color: #ef4444; font-weight: bold; }
        
        /* Кнопки управления - адаптивные */
        .button-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
            gap: 8px;
            margin-top: 15px;
        }
        
        .btn {
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 6px;
            padding: 10px;
            border-radius: 8px;
            text-decoration: none;
            font-weight: 600;
            font-size: 0.85rem;
            transition: all 0.2s;
            border: none;
            cursor: pointer;
            text-align: center;
        }
        
        .btn-primary { background: #3b82f6; color: white; }
        .btn-primary:hover { background: #2563eb; }
        
        .btn-success { background: #10b981; color: white; }
        .btn-success:hover { background: #0da271; }
        
        .btn-warning { background: #f59e0b; color: white; }
        .btn-warning:hover { background: #d97706; }
        
        .btn-danger { background: #ef4444; color: white; }
        .btn-danger:hover { background: #dc2626; }
        
        /* Сигналы */
        .signal-item {
            background: #f8fafc;
            border-left: 4px solid #3b82f6;
            padding: 12px;
            margin-bottom: 10px;
            border-radius: 8px;
            border: 1px solid #e2e8f0;
        }
        
        .signal-item.buy { border-left-color: #10b981; }
        .signal-item.sell { border-left-color: #ef4444; }
        
        .signal-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 6px;
        }
        
        .signal-ticker {
            font-weight: bold;
            font-size: 1.05rem;
        }
        
        .signal-confidence {
            background: #e0e7ff;
            color: #1d4ed8;
            padding: 3px 8px;
            border-radius: 12px;
            font-size: 0.8rem;
        }
        
        /* Pipeline статистика */
        .pipeline-row {
            display: flex;
            flex-wrap: wrap;
            gap: 8px;
            margin-top: 10px;
        }
        
        .pipeline-stat {
            flex: 1;
            min-width: 70px;
            background: #e0e7ff;
            padding: 8px;
            border-radius: 6px;
            text-align: center;
            font-size: 0.8rem;
        }
        
        .pipeline-label {
            font-size: 0.7rem;
            color: #4f46e5;
        }
        
        .pipeline-value {
            font-weight: bold;
            font-size: 0.95rem;
            color: #1e40af;
        }
        
        /* Футер */
        .footer {
            text-align: center;
            margin-top: 20px;
            padding-top: 15px;
            border-top: 1px solid #e2e8f0;
            color: #64748b;
            font-size: 0.8rem;
        }
        
        /* Улучшения для мобильных */
        @media (max-width: 480px) {
            body { padding: 8px; }
            .header { padding: 12px; }
            .header h1 { font-size: 1.2rem; }
            .card { padding: 12px; }
            .stat-item { min-width: 100px; }
            .button-grid { grid-template-columns: repeat(2, 1fr); }
            .btn { font-size: 0.8rem; padding: 8px; }
        }
        
        /* Иконки */
        .icon { font-size: 1.1em; }
    </style>
</head>
<body>
    <div class="container">
        <!-- Шапка -->
        <div class="header">
            <h1><span class="icon">🤖</span> AI Трейдер "Sentiment Hunter"</h1>
            <p><strong>⚡ Режим:</strong> Агрессивное тестирование</p>
            <p><strong>🏦 Архитектура:</strong> GigaChat + Risk Management</p>
        </div>
        
        <!-- Состояние системы -->
        <div class="card">
            <h3><span class="icon">📊</span> Состояние системы</h3>
            <div class="stats-row">
                <div class="stat-item">
                    <div class="stat-label">Статус</div>
                    <div class="stat-value" style="font-size: 1rem;">{{ bot_status }}</div>
                </div>
                <div class="stat-item">
                    <div class="stat-label">Аптайм</div>
                    <div class="stat-value">{{ uptime }}</div>
                </div>
                <div class="stat-item">
                    <div class="stat-label">Сессии</div>
                    <div class="stat-value">{{ session_count }}</div>
                </div>
            </div>
            <p><strong>🕒 Последняя торговля:</strong> {{ last_trading_time }}</p>
            <p><strong>📈 Запросов:</strong> {{ request_count }}</p>
            <p><strong>🧠 Pipeline:</strong> {{ pipeline_efficiency }}% эффективность</p>
        </div>
        
        <!-- Финансы -->
        <div class="card">
            <h3><span class="icon">💰</span> Финансы</h3>
            <div class="stats-row">
                <div class="stat-item">
                    <div class="stat-label">Портфель</div>
                    <div class="stat-value">{{ "%.0f"|format(virtual_portfolio_value) }}₽</div>
                </div>
                <div class="stat-item">
                    <div class="stat-label">Доходность</div>
                    <div class="stat-value {% if total_virtual_return >= 0 %}positive{% else %}negative{% endif %}">
                        {{ "%+.1f"|format(total_virtual_return) }}%
                    </div>
                </div>
                <div class="stat-item">
                    <div class="stat-label">Прибыль</div>
                    <div class="stat-value {% if total_virtual_profit >= 0 %}positive{% else %}negative{% endif %}">
                        {{ "%+.0f"|format(total_virtual_profit) }}₽
                    </div>
                </div>
            </div>
            <div class="pipeline-row">
                <div class="pipeline-stat">
                    <div class="pipeline-label">Риск/сделку</div>
                    <div class="pipeline-value">{{ risk_per_trade }}%</div>
                </div>
                <div class="pipeline-stat">
                    <div class="pipeline-label">Стоп-лосс</div>
                    <div class="pipeline-value">{{ stop_loss }}%</div>
                </div>
                <div class="pipeline-stat">
                    <div class="pipeline-label">Тейк-профит</div>
                    <div class="pipeline-value">{{ take_profit }}%</div>
                </div>
            </div>
        </div>
        
        <!-- Анализ новостей -->
        <div class="card">
            <h3><span class="icon">📰</span> Анализ новостей</h3>
            <div class="stats-row">
                <div class="stat-item">
                    <div class="stat-label">Новостей</div>
                    <div class="stat-value">{{ last_news_count }}</div>
                </div>
                <div class="stat-item">
                    <div class="stat-label">Сигналов</div>
                    <div class="stat-value">{{ last_signals|length }}</div>
                </div>
                <div class="stat-item">
                    <div class="stat-label">Позиций</div>
                    <div class="stat-value">{{ virtual_positions|length }}</div>
                </div>
            </div>
            <p><strong>🧠 Провайдер:</strong> {{ ai_provider|upper }}</p>
            <p><strong>🔧 Finam:</strong> {{ finam_status }}</p>
            <p><strong>🎯 Отфильтровано:</strong> {{ filtered_percent }}% новостей</p>
        </div>
        
        <!-- Pipeline статистика -->
        {% if pipeline_stats %}
        <div class="card">
            <h3><span class="icon">⚙️</span> Pipeline</h3>
            <div class="pipeline-row">
                <div class="pipeline-stat">
                    <div class="pipeline-label">Новостей</div>
                    <div class="pipeline-value">{{ pipeline_stats.total_news }}</div>
                </div>
                <div class="pipeline-stat">
                    <div class="pipeline-label">Отфильтровано</div>
                    <div class="pipeline-value">{{ pipeline_stats.filtered_news }}</div>
                </div>
                <div class="pipeline-stat">
                    <div class="pipeline-label">Проанализировано</div>
                    <div class="pipeline-value">{{ pipeline_stats.analyzed_news }}</div>
                </div>
                <div class="pipeline-stat">
                    <div class="pipeline-label">Сигналов</div>
                    <div class="pipeline-value">{{ pipeline_stats.verified_signals }}</div>
                </div>
            </div>
        </div>
        {% endif %}
        
        <!-- Последние сигналы -->
        {% if last_signals %}
        <div class="card">
            <h3><span class="icon">🚨</span> Последние сигналы</h3>
            {% for signal in last_signals[:3] %}
            <div class="signal-item {{ signal.action|lower }}">
                <div class="signal-header">
                    <div class="signal-ticker">
                        <span class="icon">
                            {% if signal.action == 'BUY' %}🟢{% else %}🔴{% endif %}
                        </span>
                        {{ signal.action }} {{ signal.ticker }}
                        <span style="font-size: 0.8rem; color: #64748b; margin-left: 8px;">
                            x{{ signal.position_size }}
                        </span>
                    </div>
                    <div class="signal-confidence">
                        {{ "%.2f"|format(signal.confidence) }}
                    </div>
                </div>
                <p><strong>Событие:</strong> {{ signal.event_type|capitalize }}</p>
                <p><strong>Тональность:</strong> {{ signal.sentiment }} (Impact: {{ signal.impact_score }})</p>
                <p><strong>💰 Стоимость:</strong> {{ "%.0f"|format(signal.position_value) }} руб.</p>
                <p style="font-size: 0.8rem;"><strong>Время:</strong> {{ signal.timestamp[11:19] }}</p>
            </div>
            {% endfor %}
        </div>
        {% endif %}
        
        <!-- Управление -->
        <div class="card">
            <h3><span class="icon">⚡</span> Управление</h3>
            <div class="button-grid">
                <a href="/force" class="btn btn-success">
                    <span class="icon">🚀</span> Запуск
                </a>
                <a href="/trades" class="btn btn-warning">
                    <span class="icon">📋</span> Сделки
                </a>
                <a href="/status" class="btn btn-primary">
                    <span class="icon">📊</span> Статус
                </a>
                <a href="/analyze" class="btn btn-primary">
                    <span class="icon">🧠</span> Анализ
                </a>
                <a href="/test_providers" class="btn btn-warning">
                    <span class="icon">🔧</span> Тесты
                </a>
                <a href="/test_pipeline" class="btn btn-success">
                    <span class="icon">⚙️</span> Pipeline
                </a>
                <a href="/env" class="btn btn-danger">
                    <span class="icon">⚙️</span> Переменные
                </a>
            </div>
        </div>
        
        <!-- Футер -->
        <div class="footer">
            <p><em>🤖 AI Трейдер "Sentiment Hunter" v3.0 | Signal Pipeline</em></p>
            <p>Риск-менеджмент: {{ risk_per_trade }}% на сделку</p>
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
            bot_status = f"🤖 Ожидание новостей | Сессия #{session_count}"
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
            bot_status = f"🤖 Нет сигналов | Сессия #{session_count}"
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
        current_provider = nlp_engine.get_current_provider()
        risk_stats = risk_manager.get_risk_stats()
        
        bot_status = (f"🤖 AI Трейдер v3.0 | {current_provider.upper()} | "
                     f"ROI: {total_virtual_return:+.1f}% | "
                     f"Сигналов: {len(signals)} | "
                     f"Риск: {risk_stats['risk_per_trade']}%")
        
        logger.info(f"💰 СЕССИЯ #{session_count} ЗАВЕРШЕНА")
        logger.info(f"💎 Портфель: {total_value:.2f} руб. ({total_virtual_return:+.2f}%)")
        logger.info(f"🎯 Прибыль за сессию: {session_profit:+.2f} руб.")
        logger.info(f"📊 Pipeline: {pipeline_stats.get('efficiency', 0):.1f}% эффективность")
        
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
        bot_status = f"🤖 Ошибка: {str(e)[:50]}..."
        
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
    check_interval = int(os.getenv("CHECK_INTERVAL_MINUTES", "15"))
    
    if check_interval <= 15:
        # Частые проверки в торговые часы (10:00-18:45 МСК)
        for hour in range(10, 19):  # с 10:00 до 18:00
            schedule.every().day.at(f"{hour:02d}:00").do(lambda: run_trading_session(False))
            if check_interval <= 15:
                schedule.every().day.at(f"{hour:02d}:15").do(lambda: run_trading_session(False))
                schedule.every().day.at(f"{hour:02d}:30").do(lambda: run_trading_session(False))
                schedule.every().day.at(f"{hour:02d}:45").do(lambda: run_trading_session(False))
        logger.info(f"📅 Планировщик настроен: каждые 15 минут с 10:00 до 18:45")
    else:
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
            "gigachat_configured": nlp_engine.providers['gigachat']['enabled'],
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
    """Главная страница с интерфейсом"""
    global request_count
    request_count += 1
    
    # Расчет аптайма
    uptime = datetime.datetime.now() - start_time
    uptime_str = str(uptime).split('.')[0]
    
    # Получение данных о портфеле
    virtual_positions = virtual_portfolio.positions
    virtual_portfolio_value = virtual_portfolio.get_total_value({})
    
    # Получение текущего провайдера ИИ
    ai_provider = nlp_engine.provider_priority[0] if nlp_engine.provider_priority else "none"
    
    # Статус источников
    finam_status = "✅" if finam_verifier.api_token else "❌"
    
    # Pipeline статистика
    pipeline_efficiency = pipeline_stats.get('efficiency', 0) if pipeline_stats else 0
    filtered_percent = pipeline_stats.get('filter_rate_percent', 0) if pipeline_stats else 0
    
    # Risk parameters
    risk_stats = risk_manager.get_risk_stats()
    risk_per_trade = risk_stats.get('risk_per_trade', 1.5)
    stop_loss = risk_stats['parameters']['stop_loss_pct']
    take_profit = risk_stats['parameters']['take_profit_pct']
    
    # Рендеринг HTML
    return render_template_string(
        HTML_TEMPLATE,
        bot_status=bot_status,
        uptime=uptime_str,
        session_count=session_count,
        last_trading_time=last_trading_time,
        request_count=request_count,
        virtual_portfolio_value=virtual_portfolio_value,
        total_virtual_return=total_virtual_return,
        total_virtual_profit=total_virtual_profit,
        last_news_count=last_news_count,
        last_signals=last_signals[:5] if last_signals else [],
        virtual_positions=virtual_positions,
        ai_provider=ai_provider,
        finam_status=finam_status,
        pipeline_stats=pipeline_stats,
        pipeline_efficiency=round(pipeline_efficiency, 1),
        filtered_percent=round(filtered_percent, 1),
        risk_per_trade=risk_per_trade,
        stop_loss=stop_loss,
        take_profit=take_profit
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
                body {{ font-family: Arial; margin: 20px; background: #f8fafc; color: #334155; font-size: 14px; }}
                .positive {{ color: #10b981; }}
                .negative {{ color: #ef4444; }}
                .container {{ max-width: 100%; margin: 0 auto; background: white; padding: 20px; border-radius: 12px; box-shadow: 0 2px 8px rgba(0,0,0,0.06); }}
                .stats {{ background: #f1f5f9; padding: 15px; border-radius: 8px; margin: 15px 0; }}
                .risk-params {{ background: #e0e7ff; padding: 12px; border-radius: 6px; margin: 8px 0; }}
                .back-btn {{ background: #3b82f6; color: white; padding: 10px 16px; text-decoration: none; border-radius: 6px; display: inline-block; margin-top: 15px; }}
            </style>
        </head>
        <body>
            <div class="container">
                <h2>📋 История Сделок</h2>
                
                <div class="stats">
                    <h4>📊 Статистика</h4>
                    <p><strong>Всего сделок:</strong> {len(trade_history)}</p>
                    <p><strong>Портфель:</strong> {virtual_portfolio.get_total_value({}):.0f} руб. 
                    (<span class="{{'positive' if total_virtual_return >= 0 else 'negative'}}">{total_virtual_return:+.1f}%</span>)</p>
                    <p><strong>Общая прибыль:</strong> <span class="{{'positive' if total_virtual_profit >= 0 else 'negative'}}">{total_virtual_profit:+.0f} руб.</span></p>
                </div>
                
                <div class="risk-params">
                    <h4>🎯 Риски</h4>
                    <p><strong>Риск на сделку:</strong> {risk_stats.get('risk_per_trade', 1.5)}%</p>
                    <p><strong>Стоп-лосс:</strong> {risk_stats['parameters']['stop_loss_pct']}%</p>
                    <p><strong>Тейк-профит:</strong> {risk_stats['parameters']['take_profit_pct']}%</p>
                </div>
                
                {trades_html if trade_history else "<p>Сделок еще нет</p>"}
                
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
        "strategy": "Signal Pipeline News Trading",
        "trading_mode": os.getenv("TRADING_MODE", "AGGRESSIVE_TEST"),
        "check_interval": os.getenv("CHECK_INTERVAL_MINUTES", 15),
        "ai_provider": nlp_engine.get_current_provider(),
        "providers_configured": {
            "gigachat": nlp_engine.providers['gigachat']['enabled'],
            "openrouter": nlp_engine.providers['openrouter']['enabled'],
            "finam": bool(finam_verifier.api_token),
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
    
    pipeline_efficiency = pipeline_stats.get('efficiency', 0) if pipeline_stats else 0
    
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
            "risk_per_trade": risk_stats.get('risk_per_trade', 1.5),
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
            'configured': nlp_engine.providers['gigachat']['enabled'],
            'status': '✅ Настроен' if nlp_engine.providers['gigachat']['enabled'] else '❌ Не настроен',
            'client_id_preview': os.getenv('GIGACHAT_CLIENT_ID', '')[:10] + '...' if os.getenv('GIGACHAT_CLIENT_ID') else 'Нет',
            'client_secret_preview': '****' + os.getenv('GIGACHAT_CLIENT_SECRET', '')[-4:] if os.getenv('GIGACHAT_CLIENT_SECRET') else 'Нет'
        },
        'openrouter': {
            'configured': nlp_engine.providers['openrouter']['enabled'],
            'status': '✅ Настроен' if nlp_engine.providers['openrouter']['enabled'] else '❌ Не настроен',
            'token_preview': os.getenv('OPENROUTER_API_TOKEN', '')[:10] + '...' if os.getenv('OPENROUTER_API_TOKEN') else 'Нет',
            'models_count': len(nlp_engine.openrouter_models)
        },
        'finam': {
            'configured': bool(finam_verifier.api_token),
            'status': '✅ Настроен' if finam_verifier.api_token else '❌ Не настроен',
            'token_preview': finam_verifier.api_token[:8] + '...' if finam_verifier.api_token else 'Нет',
            'liquid_tickers': len(finam_verifier.liquid_tickers)
        }
    }
    
    return f'''
    <html>
        <head>
            <title>Тест провайдеров</title>
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <style>
                body {{ font-family: Arial; margin: 20px; background: #f8fafc; color: #334155; font-size: 14px; }}
                .container {{ max-width: 100%; margin: 0 auto; background: white; padding: 20px; border-radius: 12px; box-shadow: 0 2px 8px rgba(0,0,0,0.06); }}
                .provider {{ padding: 15px; margin: 12px 0; border-radius: 8px; border-left: 4px solid #3b82f6; background: #f1f5f9; }}
                .btn {{ display: inline-block; padding: 10px 16px; margin: 6px 4px; border-radius: 6px; text-decoration: none; color: white; font-weight: 600; font-size: 0.9rem; }}
                .btn-test {{ background: #10b981; }}
                .btn-back {{ background: #3b82f6; }}
                .btn-pipeline {{ background: #8b5cf6; }}
            </style>
        </head>
        <body>
            <div class="container">
                <h2>🔧 Тестирование провайдеров</h2>
                
                <div class="provider">
                    <h4>🏦 GigaChat API</h4>
                    <p><strong>Статус:</strong> {providers_info['gigachat']['status']}</p>
                    <p><strong>Client ID:</strong> {providers_info['gigachat']['client_id_preview']}</p>
                    <p><strong>Scope:</strong> GIGACHAT_API_PERS</p>
                    <a href="/test_gigachat_fixed" class="btn btn-test">🧪 Тест GigaChat</a>
                </div>
                
                <div class="provider">
                    <h4>🌍 OpenRouter</h4>
                    <p><strong>Статус:</strong> {providers_info['openrouter']['status']}</p>
                    <p><strong>Модели:</strong> {providers_info['openrouter']['models_count']} бесплатных</p>
                </div>
                
                <div class="provider">
                    <h4>🏦 Finam API</h4>
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

@app.route('/debug_prefilter')
def debug_prefilter():
    """Отладка префильтра"""
    async def _debug():
        all_news = await news_fetcher.fetch_all_news()
        
        debug_results = []
        for i, news in enumerate(all_news[:5]):
            is_tradable = news_prefilter.is_tradable(news)
            
            title = news.get('title', '')[:100]
            content = news.get('content', '')[:200] or news.get('description', '')[:200]
            text = f"{title} {content}".lower()
            
            accept_count = sum(1 for kw in news_prefilter.accept_keywords if kw in text)
            reject_count = sum(1 for kw in news_prefilter.reject_keywords if kw in text)
            
            debug_results.append({
                'index': i,
                'title': title,
                'is_tradable': is_tradable,
                'accept_keywords': accept_count,
                'reject_keywords': reject_count,
                'text_preview': text[:150]
            })
        
        return debug_results
    
    try:
        results = asyncio.run(_debug())
        return jsonify({
            "debug": results,
            "prefilter_stats": news_prefilter.get_filter_stats(all_news[:10])
        })
    except Exception as e:
        return jsonify({"error": str(e)})

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

@app.route('/check_secret')
def check_secret():
    """Проверка формата GigaChat secret"""
    import base64
    
    secret = os.getenv('GIGACHAT_CLIENT_SECRET', '')
    client_id = os.getenv('GIGACHAT_CLIENT_ID', '')
    
    try:
        decoded = base64.b64decode(secret).decode('utf-8')
        is_base64 = True
        parts = decoded.split(':')
        
        return jsonify({
            "is_base64": is_base64,
            "original_length": len(secret),
            "decoded": decoded[:50] + "..." if len(decoded) > 50 else decoded,
            "parts_count": len(parts),
            "client_id_match": parts[0] == client_id if len(parts) > 0 else False,
            "has_secret": len(parts) > 1,
            "secret_preview": parts[1][:10] + "..." if len(parts) > 1 and len(parts[1]) > 10 else parts[1] if len(parts) > 1 else None
        })
    except:
        return jsonify({
            "is_base64": False,
            "original_length": len(secret),
            "client_id": client_id[:20] + "..." if len(client_id) > 20 else client_id
        })

if __name__ == '__main__':
    # Запуск планировщика
    schedule_tasks()
    scheduler_thread = threading.Thread(target=run_scheduler)
    scheduler_thread.daemon = True
    scheduler_thread.start()
    
    # Инициализация системы
    logger.info("=" * 60)
    logger.info("🚀 AI НОВОСТНОЙ ТРЕЙДЕР 'SENTIMENT HUNTER' v3.0 ЗАПУЩЕН!")
    logger.info(f"🏦 Основной провайдер: GigaChat API {'✅' if nlp_engine.providers['gigachat']['enabled'] else '❌'}")
    logger.info(f"🌍 Резервный провайдер: OpenRouter API {'✅' if nlp_engine.providers['openrouter']['enabled'] else '❌'}")
    logger.info(f"🏦 Finam API: {'✅' if finam_verifier.finam_client else '❌'}")
    logger.info(f"🧠 EnhancedAnalyzer: ✅ ({len(enhanced_analyzer.TICKER_MAP)} тикеров)")
    logger.info(f"⚡ Режим: {os.getenv('TRADING_MODE', 'AGGRESSIVE_TEST')}")
    logger.info(f"⏰ Проверки: каждые {os.getenv('CHECK_INTERVAL_MINUTES', 15)} минут")
    logger.info(f"📊 Портфель: 100,000 руб. (виртуальный)")
    logger.info("🎯 Параметры стратегии:")
    logger.info(f"   • Риск на сделку: {risk_manager.risk_per_trade}%")
    logger.info(f"   • Стоп-лосс: {risk_manager.stop_loss_pct}%")
    logger.info(f"   • Тейк-профит: {risk_manager.take_profit_pct}%")
    logger.info(f"   • Макс. на тикер: {risk_manager.max_risk_per_ticker}%")
    logger.info(f"   • Макс. на сектор: {risk_manager.max_risk_per_sector}%")
    logger.info("🌐 Веб-интерфейс: http://0.0.0.0:10000")
    logger.info("=" * 60)
    
    # Запуск Flask приложения
    app.run(host='0.0.0.0', port=10000, debug=False, use_reloader=False)
