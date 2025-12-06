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

# Импорт наших модулей
from news_fetcher import NewsFetcher
from nlp_engine import NlpEngine
from decision_engine import DecisionEngine
from tinkoff_executor import TinkoffExecutor
from virtual_portfolio import VirtualPortfolioPro
from simple_analyzer import SimpleAnalyzer

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

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
start_time = datetime.datetime.now()

# Инициализация модулей
news_fetcher = NewsFetcher()
nlp_engine = NlpEngine()
decision_engine = DecisionEngine()
tinkoff_executor = TinkoffExecutor()
virtual_portfolio = VirtualPortfolioPro(initial_capital=100000)
simple_analyzer = SimpleAnalyzer()

# HTML шаблон для светлого интерфейса
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>AI Новостной Трейдер</title>
    <meta http-equiv="refresh" content="30">
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        
        body {
            font-family: 'Arial', 'Helvetica', sans-serif;
            background: linear-gradient(135deg, #f8fafc 0%, #e2e8f0 100%);
            color: #334155;
            line-height: 1.6;
            min-height: 100vh;
            padding: 20px;
        }
        
        .container {
            max-width: 1400px;
            margin: 0 auto;
            padding: 20px;
        }
        
        /* Шапка */
        .header {
            background: linear-gradient(135deg, #3b82f6 0%, #1d4ed8 100%);
            color: white;
            padding: 25px 30px;
            border-radius: 16px;
            margin-bottom: 30px;
            box-shadow: 0 10px 25px rgba(59, 130, 246, 0.2);
            border: 1px solid rgba(255, 255, 255, 0.1);
        }
        
        .header h1 {
            font-size: 2.2rem;
            margin-bottom: 8px;
            display: flex;
            align-items: center;
            gap: 12px;
        }
        
        .header p {
            opacity: 0.9;
            font-size: 1.05rem;
        }
        
        /* Сетка карточек */
        .grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
            gap: 20px;
            margin-bottom: 25px;
        }
        
        /* Карточки */
        .card {
            background: white;
            border-radius: 14px;
            padding: 22px;
            box-shadow: 0 4px 20px rgba(0, 0, 0, 0.06);
            border: 1px solid #e2e8f0;
            transition: transform 0.3s ease, box-shadow 0.3s ease;
        }
        
        .card:hover {
            transform: translateY(-3px);
            box-shadow: 0 8px 25px rgba(0, 0, 0, 0.1);
        }
        
        .card h3 {
            color: #1e293b;
            margin-bottom: 18px;
            padding-bottom: 12px;
            border-bottom: 2px solid #e2e8f0;
            font-size: 1.3rem;
            display: flex;
            align-items: center;
            gap: 10px;
        }
        
        /* Статистика */
        .stats-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 15px;
            margin-top: 15px;
        }
        
        .stat-item {
            background: #f8fafc;
            padding: 14px;
            border-radius: 10px;
            text-align: center;
            border: 1px solid #e2e8f0;
        }
        
        .stat-value {
            font-size: 1.8rem;
            font-weight: bold;
            color: #1d4ed8;
            margin: 8px 0;
        }
        
        .stat-label {
            font-size: 0.9rem;
            color: #64748b;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }
        
        /* Цвета для прибыли/убытков */
        .positive {
            color: #10b981;
            font-weight: bold;
        }
        
        .negative {
            color: #ef4444;
            font-weight: bold;
        }
        
        /* Кнопки */
        .button-group {
            display: flex;
            flex-wrap: wrap;
            gap: 12px;
            margin-top: 20px;
        }
        
        .btn {
            display: inline-flex;
            align-items: center;
            gap: 8px;
            padding: 12px 22px;
            border-radius: 10px;
            text-decoration: none;
            font-weight: 600;
            font-size: 0.95rem;
            transition: all 0.2s ease;
            border: none;
            cursor: pointer;
        }
        
        .btn-primary {
            background: #3b82f6;
            color: white;
        }
        
        .btn-primary:hover {
            background: #2563eb;
            transform: translateY(-2px);
        }
        
        .btn-success {
            background: #10b981;
            color: white;
        }
        
        .btn-success:hover {
            background: #0da271;
        }
        
        .btn-warning {
            background: #f59e0b;
            color: white;
        }
        
        .btn-warning:hover {
            background: #d97706;
        }
        
        .btn-danger {
            background: #ef4444;
            color: white;
        }
        
        .btn-danger:hover {
            background: #dc2626;
        }
        
        /* Список сигналов */
        .signal-list {
            margin-top: 15px;
        }
        
        .signal-item {
            background: #f8fafc;
            border-left: 4px solid #3b82f6;
            padding: 15px;
            margin-bottom: 12px;
            border-radius: 8px;
            border: 1px solid #e2e8f0;
        }
        
        .signal-item.buy {
            border-left-color: #10b981;
        }
        
        .signal-item.sell {
            border-left-color: #ef4444;
        }
        
        .signal-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 8px;
        }
        
        .signal-ticker {
            font-weight: bold;
            font-size: 1.1rem;
        }
        
        .signal-confidence {
            background: #e0e7ff;
            color: #1d4ed8;
            padding: 4px 10px;
            border-radius: 20px;
            font-size: 0.85rem;
        }
        
        /* Футер */
        .footer {
            text-align: center;
            margin-top: 40px;
            padding-top: 20px;
            border-top: 1px solid #e2e8f0;
            color: #64748b;
            font-size: 0.9rem;
        }
        
        /* Адаптивность */
        @media (max-width: 768px) {
            .container { padding: 15px; }
            .header { padding: 20px; }
            .header h1 { font-size: 1.8rem; }
            .grid { grid-template-columns: 1fr; }
            .button-group { flex-direction: column; }
            .btn { justify-content: center; }
        }
        
        /* Иконки */
        .icon {
            font-size: 1.2em;
            vertical-align: middle;
        }
    </style>
</head>
<body>
    <div class="container">
        <!-- Шапка -->
        <div class="header">
            <h1>
                <span class="icon">🤖</span> 
                AI Новостной Трейдер "Sentiment Hunter"
            </h1>
            <p><strong>⚡ Режим:</strong> Агрессивное тестирование | Гибридный NLP-анализ</p>
            <p><strong>🎯 Провайдеры:</strong> GigaChat + OpenRouter + SimpleAnalyzer</p>
        </div>
        
        <!-- Основные метрики -->
        <div class="grid">
            <div class="card">
                <h3><span class="icon">📊</span> Состояние системы</h3>
                <div class="stats-grid">
                    <div class="stat-item">
                        <div class="stat-label">Статус</div>
                        <div class="stat-value" style="font-size: 1.2rem;">{{ bot_status }}</div>
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
                <p><strong>📈 Запросов к системе:</strong> {{ request_count }}</p>
            </div>
            
            <div class="card">
                <h3><span class="icon">💰</span> Финансовые показатели</h3>
                <div class="stats-grid">
                    <div class="stat-item">
                        <div class="stat-label">Портфель</div>
                        <div class="stat-value">{{ "%.2f"|format(virtual_portfolio_value) }} ₽</div>
                    </div>
                    <div class="stat-item">
                        <div class="stat-label">Доходность</div>
                        <div class="stat-value {% if total_virtual_return >= 0 %}positive{% else %}negative{% endif %}">
                            {{ "%+.2f"|format(total_virtual_return) }}%
                        </div>
                    </div>
                    <div class="stat-item">
                        <div class="stat-label">Прибыль</div>
                        <div class="stat-value {% if total_virtual_profit >= 0 %}positive{% else %}negative{% endif %}">
                            {{ "%+.2f"|format(total_virtual_profit) }} ₽
                        </div>
                    </div>
                </div>
            </div>
            
            <div class="card">
                <h3><span class="icon">📰</span> Анализ новостей</h3>
                <div class="stats-grid">
                    <div class="stat-item">
                        <div class="stat-label">Новостей</div>
                        <div class="stat-value">{{ last_news_count }}</div>
                    </div>
                    <div class="stat-item">
                        <div class="stat-label">Сигналов</div>
                        <div class="stat-value">{{ last_signals|length }}</div>
                    </div>
                    <div class="stat-item">
                        <div class="stat-label">Активных позиций</div>
                        <div class="stat-value">{{ virtual_positions|length }}</div>
                    </div>
                </div>
                <p><strong>🧠 Провайдер:</strong> {{ ai_provider }}</p>
                <p><strong>✅ Источники:</strong> {{ sources_status }}</p>
            </div>
        </div>
        
        <!-- Последние сигналы -->
        {% if last_signals %}
        <div class="card">
            <h3><span class="icon">🚨</span> Последние торговые сигналы</h3>
            <div class="signal-list">
                {% for signal in last_signals[:5] %}
                <div class="signal-item {{ signal.action|lower }}">
                    <div class="signal-header">
                        <div class="signal-ticker">
                            <span class="icon">
                                {% if signal.action == 'BUY' %}🟢{% else %}🔴{% endif %}
                            </span>
                            {{ signal.action }} {{ signal.ticker }}
                        </div>
                        <div class="signal-confidence">
                            Confidence: {{ "%.2f"|format(signal.confidence) }}
                        </div>
                    </div>
                    <p><strong>Событие:</strong> {{ signal.event_type }}</p>
                    <p><strong>Важность (Impact):</strong> {{ signal.impact_score }}/10</p>
                    <p><strong>Провайдер:</strong> {{ signal.ai_provider|default('simple') }}</p>
                    <p><strong>Причина:</strong> {{ signal.reason[:100] }}{% if signal.reason|length > 100 %}...{% endif %}</p>
                    <p><small><strong>Время:</strong> {{ signal.timestamp }}</small></p>
                </div>
                {% endfor %}
            </div>
        </div>
        {% endif %}
        
        <!-- Кнопки управления -->
        <div class="card">
            <h3><span class="icon">⚡</span> Управление системой</h3>
            <div class="button-group">
                <a href="/force" class="btn btn-success">
                    <span class="icon">🚀</span> Принудительный запуск
                </a>
                <a href="/trades" class="btn btn-warning">
                    <span class="icon">📋</span> История сделок
                </a>
                <a href="/status" class="btn btn-primary">
                    <span class="icon">📊</span> JSON статус
                </a>
                <a href="/analyze" class="btn btn-primary">
                    <span class="icon">🧠</span> Только анализ
                </a>
                <a href="/stats" class="btn btn-primary">
                    <span class="icon">📈</span> Детальная статистика
                </a>
                <a href="/test_providers" class="btn btn-warning">
                    <span class="icon">🔧</span> Тест провайдеров
                </a>
                <a href="/env" class="btn btn-danger">
                    <span class="icon">⚙️</span> Переменные окружения
                </a>
            </div>
        </div>
        
        <!-- Футер -->
        <div class="footer">
            <p><em>🤖 AI Новостной Трейдер "Sentiment Hunter" | Гибридный анализ: GigaChat + OpenRouter + SimpleAnalyzer</em></p>
            <p>Версия 3.0 | Система работает на базе нескольких ИИ-провайдеров</p>
        </div>
    </div>
</body>
</html>
"""

async def trading_session_async(force_mode=False):
    """Основная торговая сессия"""
    global last_trading_time, session_count, trade_history
    global total_virtual_profit, total_virtual_return, is_trading
    global bot_status, last_news_count, last_signals, system_stats
    
    if is_trading:
        logger.info("⏸️ Торговая сессия уже выполняется")
        return
    
    is_trading = True
    session_count += 1
    current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    last_trading_time = current_time
    
    mode_label = "🚀 ПРИНУДИТЕЛЬНАЯ" if force_mode else "🤖 РАСПИСАНИЕ"
    logger.info(f"{mode_label} ТОРГОВАЯ СЕССИЯ #{session_count} - {current_time}")
    
    try:
        # 1. Сбор новостей
        logger.info("📰 Сбор новостей из всех источников...")
        all_news = await news_fetcher.fetch_all_news()
        last_news_count = len(all_news)
        
        if not all_news:
            logger.warning("⚠️ Новостей не найдено")
            bot_status = f"🤖 Ожидание новостей | Сессия #{session_count}"
            is_trading = False
            return
        
        logger.info(f"✅ Получено {len(all_news)} новостей")
        
        # 2. NLP-анализ новостей (гибридный: GigaChat → OpenRouter → SimpleAnalyzer)
        logger.info("🧠 Гибридный анализ новостей...")
        analyzed_news = []
        
        for news_item in all_news[:8]:  # Ограничиваем для скорости
            # Пробуем сначала гибридный анализ (GigaChat + OpenRouter)
            analysis = await nlp_engine.analyze_news(news_item)
            
            if not analysis:
                # Если гибридный анализ не сработал, используем простой анализатор
                logger.info("🔄 Использую простой анализатор как fallback")
                simple_analysis = simple_analyzer.analyze_news(news_item)
                if simple_analysis:
                    # Добавляем метаданные
                    simple_analysis.update({
                        'news_id': news_item.get('id', ''),
                        'news_title': news_item.get('title', ''),
                        'news_source': news_item.get('source', ''),
                        'analysis_timestamp': datetime.datetime.now().isoformat(),
                        'ai_provider': 'simple',
                        'confidence': simple_analysis.get('confidence', 0.6)
                    })
                    analysis = simple_analysis
            
            if analysis:
                analyzed_news.append(analysis)
        
        logger.info(f"✅ Проанализировано {len(analyzed_news)} новостей")
        
        # 3. Принятие решений
        logger.info("🎯 Формирование торговых решений...")
        all_signals = []
        
        for news_analysis in analyzed_news:
            signals = decision_engine.generate_signals(news_analysis)
            if signals:
                all_signals.extend(signals)
        
        # Сохраняем последние сигналы для отображения
        last_signals = all_signals[:10]
        
        if not all_signals:
            logger.info("ℹ️ Нет торговых сигналов для выполнения")
            bot_status = f"🤖 Нет сигналов | Сессия #{session_count}"
            is_trading = False
            return
        
        logger.info(f"✅ Сформировано {len(all_signals)} сигналов")
        
        # 4. Получение текущих цен
        current_prices = {}
        tickers_to_check = list(set(signal['ticker'] for signal in all_signals))
        
        for ticker in tickers_to_check:
            price = await tinkoff_executor.get_current_price(ticker)
            if price:
                current_prices[ticker] = price
        
        if not current_prices:
            logger.error("❌ Не удалось получить цены")
            is_trading = False
            return
        
        # 5. Проверка условий выхода из позиций
        exit_signals = virtual_portfolio.check_exit_conditions(current_prices)
        
        # 6. Исполнение сделок (виртуальных)
        all_trades = all_signals + exit_signals
        executed_trades = []
        
        for signal in all_trades:
            ticker = signal['ticker']
            if ticker in current_prices:
                trade_result = virtual_portfolio.execute_trade(signal, current_prices[ticker])
                executed_trades.append(trade_result)
        
        # 7. Обновление статистики
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
            'total_signals_generated': len(all_signals),
            'total_trades_executed': len(executed_trades),
            'session_profit': session_profit,
            'nlp_stats': nlp_engine.get_stats(),
            'decision_engine_stats': decision_engine.get_stats(),
            'virtual_portfolio_stats': virtual_portfolio.get_stats()
        }
        
        # Обновление статуса
        current_provider = nlp_engine.get_current_provider()
        bot_status = f"🤖 AI Трейдер | {current_provider.upper()} | ROI: {total_virtual_return:+.1f}% | Сигналов: {len(all_signals)}"
        
        logger.info(f"💰 СЕССИЯ #{session_count} ЗАВЕРШЕНА")
        logger.info(f"💎 Портфель: {total_value:.2f} руб. ({total_virtual_return:+.2f}%)")
        logger.info(f"🎯 Прибыль за сессию: {session_profit:+.2f} руб.")
        
        if executed_trades:
            for trade in executed_trades:
                if trade['status'] == 'EXECUTED':
                    profit = trade.get('profit', 0)
                    symbol = '🟢' if profit >= 0 else '🔴'
                    logger.info(f"{symbol} {trade['action']} {trade['ticker']} x{trade['size']}: {profit:+.2f} руб.")
        
    except Exception as e:
        logger.error(f"❌ Ошибка в торговой сессии: {str(e)[:200]}")
        bot_status = f"🤖 Ошибка: {str(e)[:50]}..."
    finally:
        is_trading = False

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
        # Частые проверки в торговые часы
        for hour in range(10, 20):  # с 10:00 до 19:00
            schedule.every().day.at(f"{hour:02d}:00").do(lambda: run_trading_session(False))
            if check_interval <= 15:
                schedule.every().day.at(f"{hour:02d}:15").do(lambda: run_trading_session(False))
                schedule.every().day.at(f"{hour:02d}:30").do(lambda: run_trading_session(False))
                schedule.every().day.at(f"{hour:02d}:45").do(lambda: run_trading_session(False))
        logger.info(f"📅 Планировщик настроен: каждые 15 минут с 10:00 до 19:45")
    else:
        schedule.every(check_interval).minutes.do(lambda: run_trading_session(False))
        logger.info(f"📅 Планировщик настроен: каждые {check_interval} минут")

def run_scheduler():
    """Фоновая задача планировщика"""
    while True:
        schedule.run_pending()
        time.sleep(1)

@app.route('/')
def home():
    """Главная страница с интерфейсом"""
    global request_count
    request_count += 1
    
    # Расчет аптайма
    uptime = datetime.datetime.now() - start_time
    uptime_str = str(uptime).split('.')[0]
    
    # Получение данных о портфеле
    virtual_positions = virtual_portfolio.positions if 'virtual_portfolio' in globals() else {}
    virtual_portfolio_value = virtual_portfolio.get_total_value({}) if 'virtual_portfolio' in globals() else 100000
    
    # Получение текущего провайдера ИИ
    ai_provider = nlp_engine.get_current_provider() if 'nlp_engine' in globals() else "Не инициализирован"
    
    # Статус источников
    sources_status = "✅ NewsAPI, ✅ Zenserp, ⚠️ RSS MOEX"
    
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
        sources_status=sources_status
    )

@app.route('/force')
def force_trade():
    """Принудительный запуск торговой сессии"""
    run_trading_session(force_mode=True)
    return jsonify({
        "message": "🚀 Принудительный запуск торговой сессии (агрессивный режим)",
        "timestamp": datetime.datetime.now().isoformat(),
        "force_mode": True
    })

@app.route('/trades')
def show_trades():
    """История сделок"""
    portfolio_stats = virtual_portfolio.get_stats() if 'virtual_portfolio' in globals() else {}
    
    # HTML для истории сделок
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
        <div style="background: {color}20; border-left: 4px solid {color}; padding: 15px; margin: 10px 0; border-radius: 5px;">
            {icon}{ai_badge} {trade['timestamp']} | {trade.get('strategy', 'AI News Trading')}
            <br><strong>{trade['action']} {trade['ticker']}</strong> x{trade['size']} по {trade['price']} руб.
            {profit_html}
            <br><small>💡 {trade.get('reason', '')}</small>
        </div>
        """
    
    return f"""
    <html>
        <head>
            <title>История Сделок</title>
            <style>
                body {{ font-family: Arial; margin: 40px; background: #f8fafc; color: #334155; }}
                .positive {{ color: #10b981; }}
                .negative {{ color: #ef4444; }}
                .container {{ max-width: 800px; margin: 0 auto; background: white; padding: 30px; border-radius: 16px; box-shadow: 0 4px 20px rgba(0,0,0,0.08); }}
                .stats {{ background: #f1f5f9; padding: 20px; border-radius: 10px; margin: 20px 0; }}
            </style>
        </head>
        <body>
            <div class="container">
                <h1>📋 История Сделок</h1>
                
                <div class="stats">
                    <p><strong>Всего сделок:</strong> {len(trade_history)}</p>
                    <p><strong>Портфель:</strong> {virtual_portfolio.get_total_value({}):.2f} руб. 
                    (<span class="{{'positive' if total_virtual_return >= 0 else 'negative'}}">{total_virtual_return:+.2f}%</span>)</p>
                    <p><strong>Общая прибыль:</strong> <span class="{{'positive' if total_virtual_profit >= 0 else 'negative'}}">{total_virtual_profit:+.2f} руб.</span></p>
                    <p><strong>Win Rate:</strong> {portfolio_stats.get('win_rate', 0):.1f}%</p>
                </div>
                
                {trades_html if trade_history else "<p>Сделок еще нет</p>"}
                
                <p style="margin-top: 30px;">
                    <a href="/" style="background: #3b82f6; color: white; padding: 12px 20px; text-decoration: none; border-radius: 8px; display: inline-block;">← На главную</a>
                </p>
            </div>
        </body>
    </html>
    """

@app.route('/status')
def status():
    """JSON статус системы"""
    portfolio_stats = virtual_portfolio.get_stats() if 'virtual_portfolio' in globals() else {}
    uptime = datetime.datetime.now() - start_time
    
    nlp_stats = nlp_engine.get_stats() if 'nlp_engine' in globals() else {}
    
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
        "system_stats": system_stats,
        "last_news_count": last_news_count,
        "last_signals_count": len(last_signals) if last_signals else 0,
        "timestamp": datetime.datetime.now().isoformat(),
        "strategy": "News NLP Trading with AI",
        "trading_mode": os.getenv("TRADING_MODE", "AGGRESSIVE_TEST"),
        "check_interval": os.getenv("CHECK_INTERVAL_MINUTES", 15),
        "ai_provider": nlp_engine.get_current_provider() if 'nlp_engine' in globals() else "Unknown",
        "providers_configured": {
            "gigachat": bool(os.getenv("GIGACHATAPI")),
            "openrouter": bool(os.getenv("OPENROUTER_API_TOKEN"))
        }
    })

@app.route('/stats')
def detailed_stats():
    """Детальная статистика"""
    portfolio_stats = virtual_portfolio.get_stats() if 'virtual_portfolio' in globals() else {}
    
    # Разделение сделок по провайдерам
    ai_trades = [t for t in trade_history if t.get('ai_generated')]
    simple_trades = [t for t in trade_history if not t.get('ai_generated')]
    
    ai_profits = [t.get('profit', 0) for t in ai_trades if t.get('profit') is not None]
    simple_profits = [t.get('profit', 0) for t in simple_trades if t.get('profit') is not None]
    
    ai_avg = sum(ai_profits)/len(ai_profits) if ai_profits else 0
    simple_avg = sum(simple_profits)/len(simple_profits) if simple_profits else 0
    
    return jsonify({
        "performance_summary": {
            "total_trades": len(trade_history),
            "ai_trades": len(ai_trades),
            "simple_trades": len(simple_trades),
            "win_rate": portfolio_stats.get('win_rate', 0),
            "total_profit": total_virtual_profit,
            "virtual_return": total_virtual_return
        },
        "ai_performance": {
            "total_signals": system_stats.get('total_signals_generated', 0),
            "executed_trades": len(ai_trades),
            "avg_profit_per_trade": ai_avg,
            "success_rate": (len([p for p in ai_profits if p > 0]) / len(ai_profits) * 100) if ai_profits else 0
        },
        "simple_performance": {
            "executed_trades": len(simple_trades),
            "avg_profit_per_trade": simple_avg,
            "success_rate": (len([p for p in simple_profits if p > 0]) / len(simple_profits) * 100) if simple_profits else 0
        },
        "portfolio_status": {
            "current_value": virtual_portfolio.get_total_value({}),
            "positions_count": len(virtual_portfolio.positions),
            "available_cash": virtual_portfolio.cash
        }
    })

@app.route('/analyze')
def analyze_only():
    """Только анализ без торговли"""
    async def analyze_async():
        all_news = await news_fetcher.fetch_all_news()
        analyzed = []
        
        for news_item in all_news[:3]:
            # Гибридный анализ
            analysis = await nlp_engine.analyze_news(news_item)
            
            if not analysis:
                # Fallback на simple analyzer
                simple_result = simple_analyzer.analyze_news(news_item)
                if simple_result:
                    simple_result.update({
                        'news_id': news_item.get('id', ''),
                        'news_title': news_item.get('title', ''),
                        'analysis_timestamp': datetime.datetime.now().isoformat(),
                        'ai_provider': 'simple'
                    })
                    analysis = simple_result
            
            if analysis:
                analyzed.append(analysis)
        
        signals = []
        for analysis in analyzed:
            signals.extend(decision_engine.generate_signals(analysis))
        
        return {
            "analysis_time": datetime.datetime.now().isoformat(),
            "news_analyzed": len(analyzed),
            "signals_generated": len(signals),
            "sample_analysis": analyzed[0] if analyzed else None,
            "sample_signals": signals[:3] if signals else [],
            "nlp_stats": nlp_engine.get_stats()
        }
    
    result = asyncio.run(analyze_async())
    return jsonify(result)

@app.route('/test_providers')
def test_providers_page():
    """Страница тестирования провайдеров"""
    
    providers_info = {
        'gigachat': {
            'configured': bool(os.getenv('GIGACHATAPI')),
            'status': '✅ Настроен' if os.getenv('GIGACHATAPI') else '❌ Не настроен',
            'token_preview': os.getenv('GIGACHATAPI', '')[:10] + '...' if os.getenv('GIGACHATAPI') else 'Нет'
        },
        'openrouter': {
            'configured': bool(os.getenv('OPENROUTER_API_TOKEN')),
            'status': '✅ Настроен' if os.getenv('OPENROUTER_API_TOKEN') else '❌ Не настроен',
            'token_preview': os.getenv('OPENROUTER_API_TOKEN', '')[:10] + '...' if os.getenv('OPENROUTER_API_TOKEN') else 'Нет'
        }
    }
    
    return f"""
    <html>
        <head>
            <title>Тест ИИ-провайдеров</title>
            <style>
                body {{ font-family: Arial; margin: 40px; background: #f8fafc; color: #334155; }}
                .container {{ max-width: 800px; margin: 0 auto; background: white; padding: 30px; border-radius: 16px; box-shadow: 0 4px 20px rgba(0,0,0,0.08); }}
                .provider {{ padding: 20px; margin: 15px 0; border-radius: 10px; border-left: 4px solid #3b82f6; background: #f1f5f9; }}
                .btn {{ display: inline-block; padding: 12px 24px; margin: 10px 5px; border-radius: 8px; text-decoration: none; color: white; font-weight: bold; }}
                .btn-test {{ background: #10b981; }}
                .btn-test:hover {{ background: #0da271; }}
                .btn-back {{ background: #3b82f6; }}
                .btn-back:hover {{ background: #2563eb; }}
            </style>
        </head>
        <body>
            <div class="container">
                <h1>🔧 Тестирование ИИ-провайдеров</h1>
                <p>Проверка работы GigaChat и OpenRouter API</p>
                
                <div class="provider">
                    <h3>🏦 GigaChat API (Сбербанк)</h3>
                    <p><strong>Статус:</strong> {providers_info['gigachat']['status']}</p>
                    <p><strong>Токен:</strong> {providers_info['gigachat']['token_preview']}</p>
                    <p><strong>Scope:</strong> GIGACHAT_API_PERS</p>
                    <p><strong>Endpoint:</strong> https://gigachat.devices.sberbank.ru/api/v1/chat/completions</p>
                    <a href="/test_gigachat" class="btn btn-test">🧪 Тест GigaChat</a>
                </div>
                
                <div class="provider">
                    <h3>🌍 OpenRouter API</h3>
                    <p><strong>Статус:</strong> {providers_info['openrouter']['status']}</p>
                    <p><strong>Токен:</strong> {providers_info['openrouter']['token_preview']}</p>
                    <p><strong>Модели:</strong> Gemini, Mistral, DeepSeek</p>
                    <p><strong>Endpoint:</strong> https://openrouter.ai/api/v1/chat/completions</p>
                    <a href="/test_openrouter" class="btn btn-test">🧪 Тест OpenRouter</a>
                </div>
                
                <div style="margin-top: 30px;">
                    <a href="/" class="btn btn-back">← На главную</a>
                    <a href="/analyze" class="btn btn-test">📰 Тест полного анализа</a>
                </div>
            </div>
        </body>
    </html>
    """

@app.route('/test_gigachat')
async def test_gigachat():
    """Тестирование GigaChat API"""
    
    if not os.getenv('GIGACHATAPI'):
        return jsonify({"error": "GIGACHATAPI не настроен"})
    
    try:
        test_prompt = {
            "model": "GigaChat",
            "messages": [
                {
                    "role": "system",
                    "content": "Ты — помощник. Отвечай кратко."
                },
                {
                    "role": "user", 
                    "content": "Привет! Это тест API. Ответь '✅ GigaChat работает'"
                }
            ],
            "temperature": 0.1,
            "max_tokens": 50
        }
        
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(
                url="https://gigachat.devices.sberbank.ru/api/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {os.getenv('GIGACHATAPI')}",
                    "Content-Type": "application/json"
                },
                json=test_prompt
            )
        
        if response.status_code == 200:
            data = response.json()
            return jsonify({
                "status": "success",
                "provider": "gigachat",
                "response_code": response.status_code,
                "response": data.get("choices", [{}])[0].get("message", {}).get("content", "Пустой ответ"),
                "timestamp": datetime.datetime.now().isoformat()
            })
        else:
            return jsonify({
                "status": "error",
                "provider": "gigachat",
                "response_code": response.status_code,
                "error": response.text[:200],
                "timestamp": datetime.datetime.now().isoformat()
            })
            
    except Exception as e:
        return jsonify({
            "status": "exception",
            "provider": "gigachat",
            "error": str(e),
            "timestamp": datetime.datetime.now().isoformat()
        })

@app.route('/test_openrouter')
async def test_openrouter():
    """Тестирование OpenRouter API"""
    
    if not os.getenv('OPENROUTER_API_TOKEN'):
        return jsonify({"error": "OPENROUTER_API_TOKEN не настроен"})
    
    try:
        test_prompt = {
            "model": "google/gemini-2.0-flash-exp:free",
            "messages": [
                {
                    "role": "system",
                    "content": "You are a helpful assistant. Respond briefly."
                },
                {
                    "role": "user", 
                    "content": "Hello! This is an API test. Respond '✅ OpenRouter works'"
                }
            ],
            "temperature": 0.1,
            "max_tokens": 50
        }
        
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(
                url="https://openrouter.ai/api/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {os.getenv('OPENROUTER_API_TOKEN')}",
                    "Content-Type": "application/json",
                    "HTTP-Referer": "https://github.com"
                },
                json=test_prompt
            )
        
        if response.status_code == 200:
            data = response.json()
            return jsonify({
                "status": "success",
                "provider": "openrouter",
                "response_code": response.status_code,
                "response": data.get("choices", [{}])[0].get("message", {}).get("content", "Empty response"),
                "timestamp": datetime.datetime.now().isoformat()
            })
        else:
            return jsonify({
                "status": "error",
                "provider": "openrouter",
                "response_code": response.status_code,
                "error": response.text[:200],
                "timestamp": datetime.datetime.now().isoformat()
            })
            
    except Exception as e:
        return jsonify({
            "status": "exception",
            "provider": "openrouter",
            "error": str(e),
            "timestamp": datetime.datetime.now().isoformat()
        })

@app.route('/env')
def show_env():
    """Показать переменные окружения (безопасно)"""
    
    env_vars = {}
    for key, value in sorted(os.environ.items()):
        if any(word in key.upper() for word in ['API', 'TOKEN', 'KEY', 'SECRET']):
            # Маскируем чувствительные данные
            if value and len(value) > 8:
                masked = value[:4] + '*' * max(0, len(value)-8) + value[-4:]
                env_vars[key] = f"{masked} (длина: {len(value)})"
            else:
                env_vars[key] = "****"
        elif 'MODE' in key or 'INTERVAL' in key:
            env_vars[key] = value
    
    return jsonify({
        "environment_variables": env_vars,
        "total_vars": len(env_vars),
        "timestamp": datetime.datetime.now().isoformat()
    })

if __name__ == '__main__':
    # Запуск планировщика
    schedule_tasks()
    scheduler_thread = threading.Thread(target=run_scheduler)
    scheduler_thread.daemon = True
    scheduler_thread.start()
    
    # Инициализация системы
    logger.info("=" * 60)
    logger.info("🚀 AI НОВОСТНОЙ ТРЕЙДЕР 'SENTIMENT HUNTER' ЗАПУЩЕН!")
    logger.info("🎯 Архитектура: Гибридный NLP-анализ")
    logger.info("🏦 Основной провайдер: GigaChat API")
    logger.info("🌍 Резервный провайдер: OpenRouter API")
    logger.info("🧠 Fallback: SimpleAnalyzer")
    logger.info(f"⚡ Режим: {os.getenv('TRADING_MODE', 'AGGRESSIVE_TEST')}")
    logger.info(f"⏰ Проверки: каждые {os.getenv('CHECK_INTERVAL_MINUTES', 15)} минут")
    logger.info("📊 Портфель: 100,000 руб. (виртуальный)")
    logger.info("🌐 Веб-интерфейс: http://0.0.0.0:10000")
    logger.info("=" * 60)
    
    # Логируем конфигурацию провайдеров
    logger.info("🔧 Конфигурация провайдеров:")
    logger.info(f"   GigaChat: {'✅ Настроен' if os.getenv('GIGACHATAPI') else '❌ Не настроен'}")
    logger.info(f"   OpenRouter: {'✅ Настроен' if os.getenv('OPENROUTER_API_TOKEN') else '❌ Не настроен'}")
    
    # Запуск Flask приложения
    app.run(host='0.0.0.0', port=10000, debug=False, use_reloader=False)
