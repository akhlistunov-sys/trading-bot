# signal_pipeline.py - VERBOSE DEBUG MODE
import logging
import asyncio
import time
import hashlib
from datetime import datetime
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

class SignalPipeline:
    """Конвейер с подробным логированием отказов"""
    
    def __init__(self, nlp_engine, finam_verifier, risk_manager, 
                 enhanced_analyzer, news_prefilter, technical_strategy=None):
        self.nlp_engine = nlp_engine
        self.finam_verifier = finam_verifier
        self.risk_manager = risk_manager
        self.enhanced_analyzer = enhanced_analyzer
        self.news_prefilter = news_prefilter
        self.technical_strategy = technical_strategy
        
        self.processed_news_cache = {} 
        self.stats = {
            'signals_generated': 0,
            'pipeline_start': datetime.now().isoformat()
        }
        
        logger.info("🚀 SignalPipeline: VERBOSE DEBUG MODE (Видим всё)")
    
    async def process_news_batch(self, news_items):
        fresh_news = []
        
        # Фильтрация дублей
        for news in news_items:
            title = news.get('title', '')
            news_id = news.get('id') or hashlib.md5(title.encode()).hexdigest()
            
            if news_id in self.processed_news_cache:
                if time.time() - self.processed_news_cache[news_id] < 14400:
                    continue
            
            fresh_news.append(news)
            self.processed_news_cache[news_id] = time.time()
            
            # Лимит 5 новостей за раз для GigaChat (чтобы не ждать вечность)
            if len(fresh_news) >= 5: 
                break 
        
        # 1. Технический анализ
        verified_signals = []
        if self.technical_strategy:
            try:
                tech_signals = await self.technical_strategy.scan_for_signals()
                if tech_signals:
                    logger.info(f"📈 TECH SIGNAL: Найдено {len(tech_signals)} шт.")
                    # Сразу добавляем, тех. анализ надежен
                    verified_signals.extend(tech_signals)
            except Exception as e:
                logger.error(f"❌ Tech Error: {e}")

        # 2. Анализ новостей
        if fresh_news:
            logger.info(f"📨 Отправка {len(fresh_news)} новостей в AI...")
            
            for news_item in fresh_news:
                # Пауза между запросами к GigaChat (защита от бана)
                await asyncio.sleep(1.1) 
                
                signal = await self._process_single_news(news_item)
                
                if signal:
                    # Верификация цены
                    ticker = signal['ticker']
                    prices = await self.finam_verifier.get_current_prices([ticker])
                    
                    if prices.get(ticker):
                        # Риск-менеджмент
                        risk_signal = self.risk_manager.prepare_signal(
                            analysis=signal,
                            verification={'valid': True, 'primary_ticker': ticker},
                            current_prices=prices
                        )
                        if risk_signal:
                            verified_signals.append(risk_signal)
                        else:
                            logger.info(f"🛡️ RISK REJECT [{ticker}]: Шорт запрещен или нет денег")
                    else:
                        logger.info(f"❌ PRICE ERROR [{ticker}]: Нет данных в Finam")

        return verified_signals

    async def _process_single_news(self, news_item):
        title = news_item.get('title', '')[:40]
        
        # 1. Префильтр
        if not self.news_prefilter.is_tradable(news_item):
            logger.info(f"🗑️ FILTER: {title}... (Нет ключевых слов)")
            return None
            
        # 2. AI Анализ
        # Передаем в NLP движок
        analysis = await self.nlp_engine.analyze_news(news_item)
        
        if not analysis:
            logger.info(f"🤖 AI NULL: {title}... (Сбой API)")
            return None
            
        if not analysis.get('is_tradable'):
            logger.info(f"📉 AI SKIP: {title}... (Не для торговли. Ticker: {analysis.get('tickers')})")
            return None
            
        if not analysis.get('ticker'):
            logger.info(f"❓ AI NO TICKER: {title}...")
            return None
        
        # Успех
        logger.info(f"✨ AI SIGNAL: {analysis['ticker']} {analysis['sentiment'].upper()} (Conf: {analysis['confidence']})")
        return {
            'ticker': analysis['ticker'],
            'action': 'BUY' if analysis['sentiment'] == 'positive' else 'SELL',
            'confidence': analysis['confidence'],
            'impact_score': analysis['impact_score'],
            'reason': analysis['reason'], # Это описание пойдет в историю сделок
            'ai_provider': analysis['ai_provider'],
            'sentiment': analysis['sentiment']
        }

    def get_stats(self):
        return self.stats
