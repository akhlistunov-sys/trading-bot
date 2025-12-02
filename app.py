# app.py - ПОЛНАЯ ВЕРСИЯ С AI-TRADING CORE
from flask import Flask, jsonify
import datetime
import time
import threading
import schedule
import logging
import os
import asyncio
import json
from tinkoff.invest import Client
from ai_core import AITradingCore, MarketState  # Новый AI модуль

# Настройка логирования
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Глобальные переменные
request_count = 0
last_trading_time = "Not started yet"
bot_status = "⚡ AI TRADING BOT - VIRTUAL MODE"
session_count = 0
trade_history = []
real_portfolio_value = 0
virtual_portfolio_value = 100000  # Стартовый виртуальный капитал
virtual_positions = {}
total_virtual_profit = 0
ai_core = None  # AI ядро будет инициализировано при старте

# Инструменты для торговли (обновленные FIGI)
INSTRUMENTS = {
    "SBER": "BBG004730N88",
    "GAZP": "BBG004730RP0", 
    "VTBR": "BBG004730ZJ9",
    "LKOH": "BBG004731032",
    "ROSN": "BBG004731354",
    "YNDX": "BBG006L8G4H1",
    "GMKN": "BBG004731489",
    "ALRS": "BBG004S681W4",
    "NLMK": "BBG004S683W7",
    "MOEX": "BBG0047315D0"
}

class VirtualPortfolio:
    """Управление виртуальным портфелем с реальным P&L"""
    
    def __init__(self, initial_capital=100000):
        self.cash = initial_capital
        self.positions = {}  # {ticker: {"quantity": X, "avg_price": Y}}
        self.trade_history = []
        self.commission_rate = 0.0005  # 0.05% комиссия
        
    def execute_trade(self, signal, current_price):
        """Исполнение виртуальной сделки с реальным P&L"""
        ticker = signal['ticker']
        action = signal['action']
        size = signal['size']
        
        trade_cost = current_price * size
        commission = trade_cost * self.commission_rate
        total_cost = trade_cost + commission
        
        trade_result = {
            'timestamp': datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            'strategy': signal.get('strategy', 'AI Core'),
            'action': action,
            'ticker': ticker,
            'price': current_price,
            'size': size,
            'virtual': True,
            'commission': commission,
            'reason': signal.get('reason', ''),
            'confidence': signal.get('confidence', 0.5),
            'ai_meta': signal.get('meta', {})
        }
        
        if action == 'BUY':
            if total_cost <= self.cash:
                # Покупка
                self.cash -= total_cost
                
                # Обновляем позицию
                if ticker not in self.positions:
                    self.positions[ticker] = {"quantity": 0, "avg_price": 0, "total_cost": 0}
                
                pos = self.positions[ticker]
                total_quantity = pos["quantity"] + size
                total_invested = pos["total_cost"] + total_cost
                
                self.positions[ticker] = {
                    "quantity": total_quantity,
                    "avg_price": total_invested / total_quantity if total_quantity > 0 else 0,
                    "total_cost": total_invested
                }
                
                trade_result.update({
                    'status': "EXECUTED",
                    'profit': 0,
                    'position_after': self.positions[ticker]['quantity'],
                    'cash_after': self.cash
                })
                
                logger.info(f"✅ ВИРТУАЛЬНАЯ ПОКУПКА: {ticker} {size} лотов по {current_price:.2f}")
                
            else:
                trade_result.update({
                    'status': "INSUFFICIENT_FUNDS",
                    'profit': 0,
                    'position_after': self.positions.get(ticker, {}).get('quantity', 0),
                    'cash_after': self.cash
                })
                logger.warning(f"⚠️ НЕДОСТАТОЧНО СРЕДСТВ: {ticker} {size} лотов")
                
        else:  # SELL
            if ticker in self.positions and self.positions[ticker]["quantity"] >= size:
                # Продажа с расчетом реальной прибыли
                pos = self.positions[ticker]
                buy_cost = pos["avg_price"] * size
                sell_revenue = trade_cost - commission
                
                # Реальная прибыль/убыток
                profit = sell_revenue - (buy_cost + (buy_cost * self.commission_rate))
                
                self.cash += sell_revenue
                
                # Обновляем позицию
                new_quantity = pos["quantity"] - size
                if new_quantity > 0:
                    # Частичная продажа - avg_price не меняется
                    self.positions[ticker]["quantity"] = new_quantity
                    self.positions[ticker]["total_cost"] = pos["avg_price"] * new_quantity
                else:
                    # Полная продажа - удаляем позицию
                    del self.positions[ticker]
                
                trade_result.update({
                    'status': "EXECUTED",
                    'profit': profit,
                    'position_after': new_quantity if new_quantity > 0 else 0,
                    'cash_after': self.cash,
                    'buy_price': pos["avg_price"]
                })
                
                logger.info(f"✅ ВИРТУАЛЬНАЯ ПРОДАЖА: {ticker} {size} лотов по {current_price:.2f}, Прибыль: {profit:.2f}")
                
            else:
                trade_result.update({
                    'status': "NO_POSITION",
                    'profit': 0,
                    'position_after': self.positions.get(ticker, {}).get('quantity', 0),
                    'cash_after': self.cash
                })
                logger.warning(f"⚠️ НЕТ ПОЗИЦИИ: {ticker} {size} лотов")
        
        self.trade_history.append(trade_result)
        return trade_result
    
    def get_portfolio_value(self, current_prices):
        """Расчет текущей стоимости портфеля"""
        positions_value = 0
        for ticker, pos in self.positions.items():
            if ticker in current_prices:
                positions_value += current_prices[ticker] * pos["quantity"]
        return self.cash + positions_value

async def trading_session_async():
    """Асинхронная торговая сессия с AI-ядром"""
    global last_trading_time, session_count, trade_history, real_portfolio_value
    global virtual_portfolio_value, total_virtual_profit, virtual_positions, ai_core
    
    session_count += 1
    current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    last_trading_time = current_time
    
    logger.info(f"🚀 AI ТОРГОВАЯ СЕССИЯ #{session_count} - {current_time}")
    
    token = os.getenv('TINKOFF_API_TOKEN')
    if not token:
        logger.error("❌ TINKOFF_API_TOKEN не найден")
        return
    
    try:
        with Client(token) as client:
            # 1. Инициализируем AI ядро если ещё не инициализировано
            if ai_core is None:
                try:
                    ai_core = AITradingCore()
                    logger.info("✅ AI ядро инициализировано")
                except Exception as e:
                    logger.error(f"❌ Ошибка инициализации AI ядра: {e}")
                    return
            
            # 2. Получаем реальные цены
            real_prices = {}
            for ticker, figi in INSTRUMENTS.items():
                try:
                    last_price = client.market_data.get_last_prices(figi=[figi])
                    if last_price.last_prices:
                        price_obj = last_price.last_prices[0].price
                        price = price_obj.units + price_obj.nano / 1e9
                        real_prices[ticker] = price
                        logger.debug(f"📊 РЕАЛЬНАЯ ЦЕНА {ticker}: {price} руб.")
                except Exception as e:
                    logger.error(f"❌ Ошибка получения цены {ticker}: {e}")
                    real_prices[ticker] = 0.0
            
            # 3. Получаем реальный портфель (для информации)
            try:
                accounts = client.users.get_accounts()
                if accounts.accounts:
                    account_id = accounts.accounts[0].id
                    portfolio = client.operations.get_portfolio(account_id=account_id)
                    real_portfolio_value = portfolio.total_amount_portfolio.units + portfolio.total_amount_portfolio.nano/1e9
                    logger.info(f"💰 РЕАЛЬНЫЙ ПОРТФЕЛЬ: {real_portfolio_value:.2f} руб.")
            except Exception as e:
                logger.warning(f"⚠️ Не удалось получить реальный портфель: {e}")
                real_portfolio_value = 0
            
            # 4. Инициализируем виртуальный портфель
            virtual_portfolio = VirtualPortfolio(100000)
            
            # 5. Собираем данные рынка для AI
            market_state = ai_core.collect_market_data(client, INSTRUMENTS)
            
            # 6. Обновляем рыночные данные текущими ценами
            market_state.prices = real_prices
            
            # 7. Получаем решения от AI
            logger.info("🧠 Запрашиваю решения у AI...")
            ai_decisions = await ai_core.get_ai_decisions(market_state)
            
            # 8. Исполняем сигналы от AI
            signals = ai_decisions.get("signals", [])
            executed_trades = []
            
            if signals:
                logger.info(f"📈 AI сгенерировал {len(signals)} сигналов")
                
                for signal in signals:
                    ticker = signal.get('ticker')
                    confidence = signal.get('confidence', 0)
                    
                    if confidence > 0.6 and ticker in real_prices:
                        current_price = real_prices[ticker]
                        
                        # Проверяем, что цена в сигнале реалистична
                        price_diff = abs(signal.get('price', current_price) - current_price) / current_price
                        if price_diff < 0.05:  # Разница не более 5%
                            trade_result = virtual_portfolio.execute_trade(signal, current_price)
                            executed_trades.append(trade_result)
                        else:
                            logger.warning(f"⚠️ Цена в сигнале {ticker} отклоняется на {price_diff*100:.1f}%, пропускаю")
                    else:
                        logger.debug(f"📉 Сигнал {ticker} пропущен: уверенность {confidence:.2f}")
            else:
                logger.info("📊 AI не нашел торговых возможностей")
            
            # 9. Обновляем глобальные переменные
            trade_history.extend(executed_trades)
            virtual_positions = {ticker: pos["quantity"] for ticker, pos in virtual_portfolio.positions.items()}
            virtual_portfolio_value = virtual_portfolio.get_portfolio_value(real_prices)
            
            # Считаем прибыль за сессию
            session_profit = sum(trade.get('profit', 0) for trade in executed_trades)
            total_virtual_profit += session_profit
            
            # 10. Логируем результат
            market_regime = ai_decisions.get('market_regime', 'unknown')
            risk_level = ai_decisions.get('risk_level', 'medium')
            
            logger.info(f"✅ СЕССИЯ #{session_count} ЗАВЕРШЕНА")
            logger.info(f"🎯 Режим рынка: {market_regime.upper()} (риск: {risk_level.upper()})")
            logger.info(f"💎 ВИРТУАЛЬНЫЙ ПОРТФЕЛЬ: {virtual_portfolio_value:.2f} руб.")
            logger.info(f"📈 ПРИБЫЛЬ ЗА СЕССИЮ: {session_profit:.2f} руб.")
            logger.info(f"🏦 ПОЗИЦИИ: {virtual_positions}")
            
            # Сохраняем логи AI решений
            if signals:
                decision_log = {
                    'timestamp': current_time,
                    'session': session_count,
                    'market_regime': market_regime,
                    'risk_level': risk_level,
                    'signals_count': len(signals),
                    'executed_trades': len(executed_trades),
                    'session_profit': session_profit,
                    'signals': signals[:3]  # Первые 3 сигнала для примера
                }
                logger.info(f"🧠 AI ЛОГ: {json.dumps(decision_log, ensure_ascii=False)}")
            
    except Exception as e:
        logger.error(f"❌ Ошибка торговой сессии: {e}")
        import traceback
        logger.error(traceback.format_exc())

def trading_session():
    """Запуск асинхронной торговой сессии"""
    asyncio.run(trading_session_async())

def run_trading_session():
    """Запуск торговой сессии в отдельном потоке"""
    thread = threading.Thread(target=trading_session)
    thread.daemon = True
    thread.start()

def schedule_tasks():
    """Настройка расписания - AI трейдинг"""
    # Торговая сессия каждые 30 минут
    schedule.every(30).minutes.do(run_trading_session)
    
    # Экстренная сессия при сильных движениях (ежечасно)
    schedule.every(1).hour.do(run_trading_session)
    
    logger.info("📅 AI планировщик настроен - трейдинг каждые 30 минут!")

def run_scheduler():
    """Запуск планировщика в фоновом режиме"""
    while True:
        schedule.run_pending()
        time.sleep(1)

# Flask роуты
@app.route('/')
def home():
    global request_count
    request_count += 1
    uptime = datetime.datetime.now() - start_time
    
    # Расчет доходности
    initial_capital = 100000
    current_virtual_value = virtual_portfolio_value
    
    # Добавляем стоимость открытых позиций
    if virtual_positions:
        # Для упрощения берем последние цены из последней сессии
        # В реальности нужно получать текущие цены
        estimated_value = sum(virtual_positions[ticker] * 300 for ticker in virtual_positions)  # Примерная оценка
        current_virtual_value += estimated_value
    
    virtual_return = ((current_virtual_value - initial_capital) / initial_capital) * 100
    
    # Статус AI
    ai_status = "✅ Активно" if ai_core else "❌ Не инициализирован"
    
    return f"""
    <html>
        <head>
            <title>AI Trading Bot</title>
            <meta http-equiv="refresh" content="30">
            <style>
                body {{ font-family: Arial, sans-serif; margin: 40px; background: #0f172a; color: #f1f5f9; }}
                .container {{ background: #1e293b; padding: 30px; border-radius: 15px; box-shadow: 0 10px 25px rgba(0,0,0,0.3); }}
                h1 {{ color: #60a5fa; border-bottom: 2px solid #3b82f6; padding-bottom: 10px; }}
                .status-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 20px; margin: 20px 0; }}
                .card {{ background: #334155; padding: 20px; border-radius: 10px; border-left: 4px solid #3b82f6; }}
                .card h3 {{ color: #94a3b8; margin-top: 0; }}
                .metric {{ font-size: 24px; font-weight: bold; color: #60a5fa; }}
                .positive {{ color: #10b981; }}
                .negative {{ color: #ef4444; }}
                .buttons {{ margin-top: 30px; display: flex; gap: 15px; flex-wrap: wrap; }}
                .btn {{ background: #3b82f6; color: white; padding: 12px 24px; text-decoration: none; border-radius: 8px; transition: all 0.3s; }}
                .btn:hover {{ background: #2563eb; transform: translateY(-2px); }}
                .btn-danger {{ background: #ef4444; }}
                .btn-success {{ background: #10b981; }}
                .btn-warning {{ background: #f59e0b; }}
                .ai-badge {{ background: linear-gradient(90deg, #8b5cf6, #3b82f6); color: white; padding: 5px 15px; border-radius: 20px; font-size: 14px; display: inline-block; margin-left: 10px; }}
            </style>
        </head>
        <body>
            <div class="container">
                <h1>⚡ AI Trading Bot <span class="ai-badge">DeepSeek R1T Chimera</span></h1>
                
                <div class="status-grid">
                    <div class="card">
                        <h3>🚀 Статус системы</h3>
                        <p><strong>Статус:</strong> {bot_status}</p>
                        <p><strong>AI Ядро:</strong> {ai_status}</p>
                        <p><strong>⏰ Время работы:</strong> {str(uptime).split('.')[0]}</p>
                        <p><strong>📊 Запросы:</strong> {request_count}</p>
                    </div>
                    
                    <div class="card">
                        <h3>📈 Торговля</h3>
                        <p><strong>🕒 Последняя сессия:</strong> {last_trading_time}</p>
                        <p><strong>🔢 Сессии:</strong> {session_count}</p>
                        <p><strong>💰 Виртуальных сделок:</strong> {len(trade_history)}</p>
                        <p><strong>🎯 Следующая сессия:</strong> Через {30 - (datetime.datetime.now().minute % 30)} мин</p>
                    </div>
                    
                    <div class="card">
                        <h3>💎 Финансы</h3>
                        <p><strong>🏦 Реальный портфель:</strong> <span class="metric">{real_portfolio_value:.2f}</span> руб.</p>
                        <p><strong>🤖 Виртуальный портфель:</strong> <span class="metric">{virtual_portfolio_value:.2f}</span> руб.</p>
                        <p><strong>📈 Виртуальная доходность:</strong> 
                            <span class="metric {'positive' if virtual_return >= 0 else 'negative'}">{virtual_return:.2f}%</span>
                        </p>
                        <p><strong>📊 Общая виртуальная прибыль:</strong> 
                            <span class="metric {'positive' if total_virtual_profit >= 0 else 'negative'}">{total_virtual_profit:.2f}</span> руб.
                        </p>
                    </div>
                    
                    <div class="card">
                        <h3>📊 Позиции</h3>
                        {"".join(f'<p><strong>{ticker}:</strong> {qty} лотов</p>' for ticker, qty in virtual_positions.items()) if virtual_positions else '<p>Нет открытых позиций</p>'}
                        <p><strong>🎯 Стратегии:</strong> AI Core, Арбитраж, Моментум</p>
                        <p><strong>⏰ Частота:</strong> Каждые 30 минут</p>
                    </div>
                </div>
                
                <div class="buttons">
                    <a href="/status" class="btn">📊 JSON Статус</a>
                    <a href="/force" class="btn btn-success">🚀 Принудительный запуск</a>
                    <a href="/trades" class="btn btn-warning">📋 История сделок</a>
                    <a href="/ai_decisions" class="btn">🧠 Решения AI</a>
                    <a href="/portfolio" class="btn">💼 Детали портфеля</a>
                </div>
                
                <p style="margin-top: 30px; color: #94a3b8; font-size: 14px;">
                    <em>🤖 Автономный AI-трейдинг на реальных данных | DeepSeek R1T Chimera | Каждые 30 минут</em>
                </p>
            </div>
        </body>
    </html>
    """

@app.route('/status')
def status():
    uptime = datetime.datetime.now() - start_time
    
    initial_capital = 100000
    current_virtual_value = virtual_portfolio_value
    
    virtual_return = ((current_virtual_value - initial_capital) / initial_capital) * 100
    
    return jsonify({
        "status": bot_status,
        "ai_initialized": ai_core is not None,
        "uptime_seconds": int(uptime.total_seconds()),
        "requests_served": request_count,
        "trading_sessions": session_count,
        "virtual_trades": len(trade_history),
        "real_portfolio": real_portfolio_value,
        "virtual_portfolio": virtual_portfolio_value,
        "virtual_return_percentage": virtual_return,
        "total_virtual_profit": total_virtual_profit,
        "virtual_positions": virtual_positions,
        "last_trading_time": last_trading_time,
        "next_session_in_minutes": 30 - (datetime.datetime.now().minute % 30),
        "timestamp": datetime.datetime.now().isoformat(),
        "mode": "AI_AUTONOMOUS_TRADING",
        "strategies": ["AI Core", "Arbitrage", "Momentum"],
        "ai_model": "DeepSeek R1T Chimera",
        "trading_interval_minutes": 30
    })

@app.route('/force')
def force_trade():
    """Принудительный запуск торговой сессии"""
    run_trading_session()
    return jsonify({
        "message": "🚀 ПРИНУДИТЕЛЬНЫЙ ЗАПУСК AI-ТОРГОВЛИ",
        "timestamp": datetime.datetime.now().isoformat(),
        "session_number": session_count + 1
    })

@app.route('/trades')
def show_trades():
    trades_html = ""
    for trade in trade_history[-20:]:
        color = "#10b981" if trade['action'] == 'BUY' else "#ef4444"
        status_color = "#10b981" if trade.get('profit', 0) > 0 else "#ef4444"
        
        trades_html += f"""
        <div style="background: {color}15; border-left: 4px solid {color}; padding: 15px; margin: 10px 0; border-radius: 5px;">
            <div style="display: flex; justify-content: space-between;">
                <div>
                    <strong>{'🟢 ПОКУПКА' if trade['action'] == 'BUY' else '🔴 ПРОДАЖА'}</strong> | 
                    {trade['timestamp']} | {trade['strategy']}
                    <br><strong>{trade['ticker']}</strong> ×{trade['size']} по {trade['price']:.2f} руб.
                    <br><small>💡 {trade.get('reason', '')}</small>
                </div>
                <div style="text-align: right;">
                    <div style="color: {status_color}; font-weight: bold;">
                        {f"+{trade.get('profit', 0):.2f} руб." if trade.get('profit') else ''}
                    </div>
                    <small>Уверенность: {trade.get('confidence', 0)*100:.0f}%</small>
                </div>
            </div>
        </div>
        """
    
    return f"""
    <html>
        <head>
            <title>История сделок</title>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 40px; background: #0f172a; color: #f1f5f9; }}
                .container {{ background: #1e293b; padding: 30px; border-radius: 15px; }}
                h1 {{ color: #60a5fa; }}
                .back-btn {{ background: #3b82f6; color: white; padding: 10px 20px; text-decoration: none; border-radius: 8px; display: inline-block; margin-top: 20px; }}
            </style>
        </head>
        <body>
            <div class="container">
                <h1>📋 История виртуальных сделок</h1>
                <p><strong>Всего сделок:</strong> {len(trade_history)}</p>
                <p><strong>Виртуальный портфель:</strong> {virtual_portfolio_value:.2f} руб.</p>
                <p><strong>Общая прибыль:</strong> <span style="color: {'#10b981' if total_virtual_profit >= 0 else '#ef4444'}">{total_virtual_profit:.2f}</span> руб.</p>
                
                {trades_html if trade_history else "<p>Сделок пока нет</p>"}
                
                <a href="/" class="back-btn">← На главную</a>
            </div>
        </body>
    </html>
    """

@app.route('/ai_decisions')
def ai_decisions():
    """Последние решения AI"""
    recent_trades = trade_history[-10:]
    decisions = []
    
    for trade in recent_trades:
        if 'ai_meta' in trade:
            decisions.append({
                'time': trade['timestamp'],
                'ticker': trade['ticker'],
                'action': trade['action'],
                'reason': trade.get('reason', ''),
                'confidence': trade.get('confidence', 0),
                'meta': trade['ai_meta']
            })
    
    return jsonify({
        "recent_ai_decisions": decisions,
        "total_ai_trades": len([t for t in trade_history if 'ai_meta' in t]),
        "ai_model": "DeepSeek R1T Chimera"
    })

@app.route('/portfolio')
def portfolio_details():
    """Детальная информация о портфеле"""
    portfolio_value = virtual_portfolio_value
    positions_details = []
    
    # Здесь нужно получить текущие цены для расчета
    # Для упрощения используем последние цены из истории
    
    return jsonify({
        "portfolio_value": portfolio_value,
        "cash": 100000,  # Заглушка - нужно обновить
        "positions": virtual_positions,
        "performance": {
            "total_profit": total_virtual_profit,
            "total_trades": len(trade_history),
            "win_rate": len([t for t in trade_history if t.get('profit', 0) > 0]) / len(trade_history) if trade_history else 0
        }
    })

# Инициализация
start_time = datetime.datetime.now()

if __name__ == '__main__':
    # Запускаем планировщик
    schedule_tasks()
    scheduler_thread = threading.Thread(target=run_scheduler)
    scheduler_thread.daemon = True
    scheduler_thread.start()
    
    # Запускаем первую сессию через 10 секунд после старта
    def initial_session():
        time.sleep(10)
        run_trading_session()
    
    init_thread = threading.Thread(target=initial_session)
    init_thread.daemon = True
    init_thread.start()
    
    logger.info("🚀 AI TRADING BOT STARTED!")
    logger.info(f"🧠 AI Модель: DeepSeek R1T Chimera")
    logger.info("⚡ Режим: Полностью автономный AI-трейдинг")
    logger.info("💰 Стартовый капитал: 100,000 руб.")
    logger.info("🎯 Частота сессий: Каждые 30 минут")
    logger.info("🌐 Веб-интерфейс: http://localhost:10000")
    
    app.run(host='0.0.0.0', port=10000, debug=False)
