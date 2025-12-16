# signal_pipeline.py - DEBUG VERSION
import logging
import asyncio
import time
import hashlib
from datetime import datetime
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

class SignalPipeline:
    """Конвейер обработки сигналов"""
    
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
            'total_news': 0,
            'technical_signals': 0,
            'signals_generated': 0,
            'pipeline_start': datetime.now().isoformat()
        }
        
        logger.info("🚀 SignalPipeline Ready (Real Data Mode)")
    
    async def process_news_batch(self, news_items):
        fresh_news = []
        
        # Фильтрация дублей (Кэш на 4 часа)
        for news in news_items:
            title = news.get('title', '')
            news_id = news.get('id') or hashlib.md5(title.encode()).hexdigest()
            
            if news_id in self.processed_news_cache:
                if time.time() - self.processed_news_cache[news_id] < 14400:
                    continue
            
            fresh_news.append(news)
            self.processed_news_cache[news_id] = time.time()
            
            # Ограничиваем очередь на обработку, чтобы не ждать вечность с GigaChat
            if len(fresh_news) >= 5: 
                break 
        
        # Чистка кэша
        current_time = time.time()
        self.processed_news_cache = {k:v for k,v in self.processed_news_cache.items() 
                                   if current_time - v < 14400}
        
        # 1. Сбор технических сигналов
        verified_signals = []
        if self.technical_strategy:
            try:
                technical_signals = await self.technical_strategy.scan_for_signals()
                if technical_signals:
                    logger.info(f"📈 Технический анализ: {len(technical_signals)} сигналов")
                    verified_signals.extend(self._verify_batch(technical_signals))
            except Exception as e:
                logger.error(f"❌ Ошибка Tech Strategy: {e}")
        
        # 2. Анализ новостей
        if fresh_news:
            logger.info(f"🧠 AI Анализ {len(fresh_news)} новостей (GigaChat)...")
            
            for news_item in fresh_news:
                try:
                    # Поштучная обработка (важно для GigaChat)
                    signal = await self._process_single_news(news_item)
                    if signal:
                        verified = await self._verify_single(signal)
                        if verified:
                            verified_signals.append(verified)
                    else:
                        # ЛОГИРУЕМ ПОЧЕМУ НЕТ СИГНАЛА
                        pass 
                except Exception as e:
                    logger.error(f"❌ Ошибка в цикле новостей: {e}")

        if verified_signals:
            logger.info(f"⚡ ГОТОВЫЕ ОРДЕРА: {len(verified_signals)}")
        
        self.stats['signals_generated'] += len(verified_signals)
        return verified_signals

    async def _process_single_news(self, news_item):
        # 1. Префильтр (Regex)
        if not self.news_prefilter.is_tradable(news_item):
            # logger.debug(f"Skipped (PreFilter): {news_item['title'][:30]}")
            return None
            
        # 2. AI Анализ
        analysis = await self.nlp_engine.analyze_news(news_item)
        
        if not analysis:
            logger.debug(f"Skipped (AI Null): {news_item['title'][:30]}")
            return None
            
        if not analysis.get('is_tradable'):
            logger.debug(f"Skipped (AI Not Tradable): {news_item['title'][:30]}")
            return None
            
        if not analysis.get('ticker'):
            logger.debug(f"Skipped (No Ticker): {news_item['title'][:30]}")
            return None
            
        # Успешный сигнал
        return {
            'ticker': analysis['ticker'],
            'action': 'BUY' if analysis['sentiment'] == 'positive' else 'SELL',
            'confidence': analysis['confidence'],
            'impact_score': analysis['impact_score'],
            'reason': analysis['reason'],
            'ai_provider': analysis['ai_provider'],
            'sentiment': analysis['sentiment']
        }

    # Вспомогательные методы для верификации (чтобы не дублировать код)
    def _verify_batch(self, signals):
        # Здесь мы можем получить цены пакетно, но пока для простоты оставим пустым
        # т.к. тех анализ уже идет с ценой, а RiskManager проверит снова
        # В реальной реализации здесь нужен FinamVerifier
        return signals # Пока пропускаем как есть, RiskManager отфильтрует

    async def _verify_single(self, signal):
        # Получаем цену
        ticker = signal['ticker']
        prices = await self.finam_verifier.get_current_prices([ticker])
        
        if not prices.get(ticker):
            logger.warning(f"❌ Цена не найдена: {ticker}")
            return None
            
        # Проверяем через RiskManager
        risk_signal = self.risk_manager.prepare_signal(
            analysis=signal,
            verification={'valid': True, 'primary_ticker': ticker},
            current_prices=prices
        )
        return risk_signal

    def get_stats(self):
        return self.stats
