from flask import Flask, jsonify
import datetime
import time
import threading
import schedule
import logging
import os
import requests
import feedparser
from tinkoff.invest import Client, OrderDirection, OrderType
import re
from collections import deque

# Настройка логирования
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Глобальные переменные
request_count = 0
last_trading_time = "Not started yet"
bot_status = "NEWS TRADING BOT - ACTIVE"
session_count = 0
trade_history = []
portfolio_value = 0
total_profit = 0
news_history = deque(maxlen=100)

# Новостные источники
NEWS_SOURCES = {
    "rbc": "https://rssexport.rbc.ru/rbcnews/news/30/full.rss",
    "moex": "https://www.moex.com/export/news.aspx",
    "interfax": "https://www.interfax.ru/rss.asp"
}

# Торговые правила для новостей
TRADING_RULES = {
    "дивиденд": {"action": "BUY", "confidence": 0.8, "sectors": ["finance", "oil", "mining"]},
    "выкуп акций": {"action": "STRONG_BUY", "confidence": 0.9, "sectors": ["all"]},
    "рекордная прибыль": {"action": "BUY", "confidence": 0.85, "sectors": ["all"]},
    "повышение дивидендов": {"action": "BUY", "confidence": 0.8, "sectors": ["all"]},
    "ставки цб": {"action": "SELL", "confidence": 0.7, "sectors": ["finance"]},
    "санкции": {"action": "STOP_LOSS", "confidence": 0.9, "sectors": ["all"]},
    "лицензия": {"action": "BUY", "confidence": 0.75, "sectors": ["oil", "mining"]},
    "контракт": {"action": "BUY", "confidence": 0.7, "sectors": ["all"]},
    "отчетность": {"action": "BUY", "confidence": 0.6, "sectors": ["all"]}
}

# Сектора экономики
SECTORS = {
    "SBER": "finance",
    "VTBR": "finance", 
    "GAZP": "oil",
    "LKOH": "oil",
    "ROSN": "oil",
    "NVTK": "oil",
    "GMKN": "mining",
    "NLMK": "mining",
    "PLZL": "mining"
}

class NewsTradingBot:
    def __init__(self, client, account_id):
        self.client = client
        self.account_id = account_id
        self.news_cache = set()
        self.last_news_check = datetime.datetime.now()
        
    def fetch_news(self):
        """Получение новостей из различных источников"""
        all_news = []
        
        try:
            # RBC News
            rbc_feed = feedparser.parse(NEWS_SOURCES["rbc"])
            for entry in rbc_feed.entries[:10]:
                news_item = {
                    'source': 'RBC',
                    'title': entry.title,
                    'summary': entry.summary,
                    'published': entry.published,
                    'link': entry.link,
                    'timestamp': datetime.datetime.now()
                }
                all_news.append(news_item)
                
        except Exception as e:
            logger.error(f"❌ Ошибка получения новостей RBC: {e}")
            
        return all_news
    
    def analyze_news_sentiment(self, news_item):
        """Анализ тональности новости и извлечение тикеров"""
        title = news_item['title'].lower()
        summary = news_item['summary'].lower()
        
        # Поиск тикеров в тексте
        found_tickers = []
        for ticker in SECTORS.keys():
            if ticker.lower() in title or ticker.lower() in summary:
                found_tickers.append(ticker)
        
        # Анализ тональности и поиск триггеров
        signals = []
        for pattern, rule in TRADING_RULES.items():
            if pattern in title or pattern in summary:
                for ticker in found_tickers:
                    if rule["sectors"] == ["all"] or SECTORS.get(ticker) in rule["sectors"]:
                        signals.append({
                            'ticker': ticker,
                            'action': rule['action'],
                            'confidence': rule['confidence'],
                            'reason': f"Новость: {pattern}",
                            'news_title': news_item['title'],
                            'source': news_item['source']
                        })
                        
        return signals
    
    def execute_news_trade(self, signal):
        """Исполнение торговой операции на основе новости"""
        try:
            ticker = signal['ticker']
            figi = self.get_figi_by_ticker(ticker)
            if not figi:
                return None
            
            # Получаем текущую цену
            last_price = self.client.market_data.get_last_prices(figi=[figi])
            if not last_price.last_prices:
                return None
                
            current_price = last_price.last_prices[0].price.units + last_price.last_prices[0].price.nano/1e9
            
            # Определяем направление и размер позиции
            if signal['action'] in ['BUY', 'STRONG_BUY']:
                direction = OrderDirection.ORDER_DIRECTION_BUY
                size = 10 if signal['action'] == 'STRONG_BUY' else 5
            elif signal['action'] == 'SELL':
                direction = OrderDirection.ORDER_DIRECTION_SELL
                size = 5
            else:
                return None
            
            # Размещаем ордер
            response = self.client.orders.post_order(
                figi=figi,
                quantity=size,
                direction=direction,
                account_id=self.account_id,
                order_type=OrderType.ORDER_TYPE_MARKET
            )
            
            trade_result = {
                'timestamp': datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                'action': signal['action'],
                'ticker': ticker,
                'price': current_price,
                'size': size,
                'order_id': response.order_id,
                'confidence': signal['confidence'],
                'reason': signal['reason'],
                'news_source': signal['source'],
                'news_title': signal['news_title']
            }
            
            logger.info(f"🎯 НОВОСТНАЯ ТОРГОВЛЯ: {signal['action']} {ticker} x{size} по {current_price} руб.")
            logger.info(f"📰 Новость: {signal['news_title']}")
            
            return trade_result
            
        except Exception as e:
            logger.error(f"❌ Ошибка исполнения новостной сделки: {e}")
            return None
    
    def get_figi_by_ticker(self, ticker):
        """Получение FIGI по тикеру"""
        ticker_to_figi = {
            "SBER": "BBG004730N88",
            "GAZP": "BBG004730RP0",
            "VTBR": "BBG004730ZJ9",
            "LKOH": "BBG004731032",
            "ROSN": "BBG004731354",
            "GMKN": "BBG00475K2X9",
            "NLMK": "BBG004S68614",
            "PLZL": "BBG000R7GJQ6"
        }
        return ticker_to_figi.get(ticker)

def news_monitoring_loop():
    """Бесконечный цикл мониторинга новостей"""
    logger.info("📰 ЗАПУСК НОВОСТНОГО МОНИТОРИНГА 24/7")
    
    while True:
        try:
            token = os.getenv('TINKOFF_API_TOKEN')
            if not token:
                time.sleep(60)
                continue
                
            with Client(token) as client:
                accounts = client.users.get_accounts()
                if not accounts.accounts:
                    time.sleep(60)
                    continue
                    
                account_id = accounts.accounts[0].id
                bot = NewsTradingBot(client, account_id)
                
                # Проверяем новости
                fresh_news = bot.fetch_news()
                
                for news_item in fresh_news:
                    news_hash = hash(news_item['title'] + news_item['published'])
                    if news_hash not in bot.news_cache:
                        bot.news_cache.add(news_hash)
                        news_history.append(news_item)
                        
                        # Анализируем новость
                        signals = bot.analyze_news_sentiment(news_item)
                        
                        # Исполняем торговые сигналы
                        for signal in signals:
                            if signal['confidence'] > 0.7:  # Только высоковероятные сигналы
                                trade_result = bot.execute_news_trade(signal)
                                if trade_result:
                                    trade_history.append(trade_result)
                                    logger.info(f"✅ НОВОСТНАЯ СДЕЛКА ИСПОЛНЕНА: {signal['ticker']}")
                
                # Обновляем статистику портфеля
                try:
                    portfolio = client.operations.get_portfolio(account_id=account_id)
                    global portfolio_value
                    portfolio_value = portfolio.total_amount_portfolio.units + portfolio.total_amount_portfolio.nano/1e9
                except:
                    pass
                    
        except Exception as e:
            logger.error(f"❌ Ошибка в цикле новостного мониторинга: {e}")
        
        # Пауза между проверками (1 минута)
        time.sleep(60)

def trading_session():
    """Регулярная торговая сессия (дополнительная аналитика)"""
    global last_trading_time, session_count
    session_count += 1
    last_trading_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    logger.info(f"🔍 ДОПОЛНИТЕЛЬНАЯ АНАЛИТИКА СЕССИЯ #{session_count}")

def run_trading_session():
    thread = threading.Thread(target=trading_session)
    thread.daemon = True
    thread.start()

def schedule_tasks():
    schedule.every(30).minutes.do(run_trading_session)
    logger.info("📅 Планировщик дополнительной аналитики настроен")

def run_scheduler():
    while True:
        schedule.run_pending()
        time.sleep(1)

@app.route('/')
def home():
    global request_count
    request_count += 1
    uptime = datetime.datetime.now() - start_time
    
    return f"""
    <html>
        <head><title>News Trading Bot</title><meta http-equiv="refresh" content="30"></head>
        <body style="font-family: Arial, sans-serif; margin: 40px; background: #0f0f23;">
            <h1 style="color: #00ff00;">📰 NEWS TRADING BOT</h1>
            <div style="background: #1a1a2e; color: #00ff00; padding: 25px; border-radius: 10px; border: 1px solid #00ff00;">
                <p><strong>⚡ Status:</strong> {bot_status}</p>
                <p><strong>⏰ Uptime:</strong> {str(uptime).split('.')[0]}</p>
                <p><strong>📊 Requests:</strong> {request_count}</p>
                <p><strong>🕒 Last Trading:</strong> {last_trading_time}</p>
                <p><strong>🔢 Sessions:</strong> {session_count}</p>
                <p><strong>💰 News Trades:</strong> {len(trade_history)}</p>
                <p><strong>💎 Real Portfolio:</strong> {portfolio_value:.2f} руб.</p>
                <p><strong>📰 News Monitored:</strong> {len(news_history)}</p>
            </div>
            <p style="margin-top: 20px;">
                <a href="/status" style="margin-right: 15px; background: #00ff00; color: black; padding: 10px 15px; text-decoration: none; border-radius: 5px; font-weight: bold;">JSON Status</a>
                <a href="/news" style="margin-right: 15px; background: #ff00ff; color: black; padding: 10px 15px; text-decoration: none; border-radius: 5px; font-weight: bold;">📰 News Feed</a>
                <a href="/trades" style="background: #ffff00; color: black; padding: 10px 15px; text-decoration: none; border-radius: 5px; font-weight: bold;">📋 Trade History</a>
            </p>
            <p style="color: #00ff00;"><em>🤖 24/7 News Monitoring & Auto-Trading | Live RSS Feeds</em></p>
        </body>
    </html>
    """

@app.route('/status')
def status():
    uptime = datetime.datetime.now() - start_time
    return jsonify({
        "status": bot_status,
        "uptime_seconds": int(uptime.total_seconds()),
        "requests_served": request_count,
        "trading_sessions": session_count,
        "news_trades": len(trade_history),
        "real_portfolio": portfolio_value,
        "news_monitored": len(news_history),
        "last_trading_time": last_trading_time,
        "timestamp": datetime.datetime.now().isoformat(),
        "mode": "24_7_NEWS_TRADING"
    })

@app.route('/news')
def show_news():
    news_html = ""
    for news in list(news_history)[-10:]:
        news_html += f"""
        <div style="background: #1a1a2e; color: #00ff00; padding: 15px; margin: 10px 0; border-radius: 5px; border: 1px solid #00ff00;">
            <strong>{news['source']}</strong> - {news['published']}
            <br><strong>{news['title']}</strong>
            <br><small>{news['summary'][:200]}...</small>
        </div>
        """
    
    return f"""
    <html>
        <body style="font-family: Arial, sans-serif; margin: 40px; background: #0f0f23; color: #00ff00;">
            <h1>📰 Live News Feed</h1>
            <p><strong>Total News Monitored:</strong> {len(news_history)}</p>
            {news_html if news_history else "<p>No news yet</p>"}
            <p><a href="/" style="background: #00ff00; color: black; padding: 10px 15px; text-decoration: none; border-radius: 5px; font-weight: bold;">← Back to Main</a></p>
        </body>
    </html>
    """

@app.route('/trades')
def show_trades():
    trades_html = ""
    for trade in trade_history[-15:]:
        color = "#00ff00" if trade['action'] in ['BUY', 'STRONG_BUY'] else "#ff0000"
        trades_html += f"""
        <div style="background: #1a1a2e; color: {color}; padding: 15px; margin: 10px 0; border-radius: 5px; border: 1px solid {color};">
            <strong>🎯 {trade['action']} {trade['ticker']} x{trade['size']} по {trade['price']} руб.</strong>
            <br>📰 {trade['news_source']}: {trade['news_title']}
            <br>📊 Уверенность: {trade['confidence']:.0%} | Причина: {trade['reason']}
            <br>⏰ {trade['timestamp']}
        </div>
        """
    
    return f"""
    <html>
        <body style="font-family: Arial, sans-serif; margin: 40px; background: #0f0f23; color: #00ff00;">
            <h1>📋 News Trade History</h1>
            <p><strong>Total Trades:</strong> {len(trade_history)}</p>
            {trades_html if trade_history else "<p>No trades yet</p>"}
            <p><a href="/" style="background: #00ff00; color: black; padding: 10px 15px; text-decoration: none; border-radius: 5px; font-weight: bold;">← Back to Main</a></p>
        </body>
    </html>
    """

start_time = datetime.datetime.now()

if __name__ == '__main__':
    # Запускаем новостной мониторинг в отдельном потоке
    news_thread = threading.Thread(target=news_monitoring_loop)
    news_thread.daemon = True
    news_thread.start()
    
    # Запускаем планировщик дополнительной аналитики
    schedule_tasks()
    scheduler_thread = threading.Thread(target=run_scheduler)
    scheduler_thread.daemon = True
    scheduler_thread.start()
    
    logger.info("🚀 NEWS TRADING BOT STARTED!")
    logger.info("📰 Режим: 24/7 Новостной мониторинг и авто-трейдинг")
    logger.info("⚡ Источники: RBC, MOEX, Интерфакс")
    logger.info("🎯 Стратегия: Торговля на корпоративных новостях")
    
    app.run(host='0.0.0.0', port=10000, debug=False)
