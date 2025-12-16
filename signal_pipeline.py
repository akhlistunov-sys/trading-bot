# signal_pipeline.py - WITH ANALYSIS HISTORY
import logging
import asyncio
import time
import hashlib
from datetime import datetime
from collections import deque

logger = logging.getLogger(__name__)

class SignalPipeline:
    def __init__(self, nlp_engine, finam_verifier, risk_manager, 
                 enhanced_analyzer, news_prefilter, technical_strategy=None):
        self.nlp_engine = nlp_engine
        self.finam_verifier = finam_verifier
        self.risk_manager = risk_manager
        self.news_prefilter = news_prefilter
        self.technical_strategy = technical_strategy
        
        self.processed_news_cache = {} 
        # Буфер для хранения последних 50 решений AI (для UI)
        self.ai_history = deque(maxlen=50) 
        
        logger.info("🚀 SignalPipeline: Init Complete")
    
    async def process_news_batch(self, news_items):
        fresh_news = []
        
        # Фильтр дублей
        for news in news_items:
            title = news.get('title', '')
            news_id = news.get('id') or hashlib.md5(title.encode()).hexdigest()
            if news_id in self.processed_news_cache:
                if time.time() - self.processed_news_cache[news_id] < 14400: continue
            fresh_news.append(news)
            self.processed_news_cache[news_id] = time.time()
            if len(fresh_news) >= 5: break 
        
        verified_signals = []
        
        # 1. Tech Analysis
        if self.technical_strategy:
            try:
                tech = await self.technical_strategy.scan_for_signals()
                if tech: verified_signals.extend(tech)
            except: pass

        # 2. News Analysis
        if fresh_news:
            logger.info(f"📨 AI Scanning {len(fresh_news)} news...")
            for item in fresh_news:
                await asyncio.sleep(1.0) # Rate limit
                
                # --- PREFILTER LOGIC ---
                if not self.news_prefilter.is_tradable(item):
                    self._add_to_history(item, "FILTER", "Skipped", "No keywords")
                    continue
                
                # --- AI ANALYSIS ---
                analysis = await self.nlp_engine.analyze_news(item)
                
                if not analysis:
                    self._add_to_history(item, "ERROR", "Fail", "AI connection failed")
                    continue
                
                if not analysis['is_tradable'] or not analysis['ticker']:
                    self._add_to_history(item, "SKIP", "Neutral", analysis['reason'], analysis['ai_provider'])
                    continue
                
                # --- SIGNAL FOUND ---
                self._add_to_history(item, "SIGNAL", analysis['ticker'], analysis['reason'], analysis['ai_provider'])
                
                # Verification
                ticker = analysis['ticker']
                prices = await self.finam_verifier.get_current_prices([ticker])
                
                if prices.get(ticker):
                    risk_sig = self.risk_manager.prepare_signal(
                        analysis=analysis,
                        verification={'valid': True, 'primary_ticker': ticker},
                        current_prices=prices
                    )
                    if risk_sig:
                        verified_signals.append(risk_sig)
                        
        return verified_signals

    def _add_to_history(self, news_item, status, result, reason, provider="System"):
        """Добавляет запись в историю для UI"""
        record = {
            'time': datetime.now().strftime("%H:%M:%S"),
            'source': news_item.get('source_name', 'RSS')[:10],
            'title': news_item.get('title', '')[:60] + "...",
            'status': status,   # FILTER, ERROR, SKIP, SIGNAL
            'result': result,   # Ticker or verdict
            'reason': reason[:50],
            'provider': provider
        }
        self.ai_history.appendleft(record)

    def get_ai_history(self):
        return list(self.ai_history)
