# signal_pipeline.py - PROFIT HUNTER ENTRY FILTER
import logging
import asyncio
import time
import hashlib
from datetime import datetime
from collections import deque

logger = logging.getLogger(__name__)

class SignalPipeline:
    def __init__(self, nlp_engine, finam_verifier, risk_manager, 
                 enhanced_analyzer, news_prefilter, technical_strategy):
        self.nlp = nlp_engine
        self.verifier = finam_verifier
        self.risk = risk_manager
        self.prefilter = news_prefilter
        self.tech = technical_strategy
        self.cache = {} 
        self.history = deque(maxlen=50)
        logger.info("🚀 Pipeline: Profit Hunter Mode (RSI Filter Active)")
    
    async def process_news_batch(self, news):
        fresh = []
        for n in news:
            nid = n.get('id') or hashlib.md5(n.get('title','').encode()).hexdigest()
            if nid in self.cache and time.time() - self.cache[nid] < 14400: continue
            fresh.append(n)
            self.cache[nid] = time.time()
            if len(fresh) >= 5: break
            
        verified = []
        
        # 1. Tech Signals
        try:
            ts = await self.tech.scan_for_signals()
            verified.extend(ts)
        except: pass

        # 2. AI Signals
        if fresh:
            logger.info(f"📨 Scanning {len(fresh)} news...")
            for item in fresh:
                await asyncio.sleep(1.0)
                
                if not self.prefilter.is_tradable(item):
                    self._log(item, "FILTER", "Skip", "No keywords")
                    continue
                
                analysis = await self.nlp.analyze_news(item)
                if not analysis or not analysis['is_tradable']:
                    self._log(item, "SKIP", "Neutral", "No signal")
                    continue
                
                ticker = analysis['ticker']
                
                # --- PROFIT HUNTER FILTER ---
                # Если RSI > 75 (перекуплен) -> Отменяем покупку
                rsi = self.tech.get_rsi(ticker)
                if rsi and rsi > 75 and analysis['sentiment'] == 'positive':
                    self._log(item, "REJECT", ticker, f"RSI Overbought ({rsi:.0f})")
                    continue
                # ----------------------------

                # Проверка цены
                prices = await self.verifier.get_current_prices([ticker])
                if not prices.get(ticker):
                    self._log(item, "ERROR", ticker, "No Price Data")
                    continue
                    
                risk_sig = self.risk.prepare_signal(
                    analysis=analysis,
                    verification={'valid': True, 'primary_ticker': ticker},
                    current_prices=prices
                )
                
                if risk_sig:
                    self._log(item, "SIGNAL", ticker, analysis['reason'], "GigaChat")
                    verified.append(risk_sig)
                else:
                    self._log(item, "RISK", ticker, "Risk Reject")
                    
        return verified

    def _log(self, item, status, res, reason, prov="System"):
        self.history.appendleft({
            'time': datetime.now().strftime("%H:%M:%S"),
            'source': item.get('source_name', 'RSS')[:10],
            'title': item.get('title', '')[:50],
            'status': status, 'result': res, 'reason': reason, 'provider': prov
        })

    def get_ai_history(self): return list(self.history)
