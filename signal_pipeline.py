# signal_pipeline.py - УПРОЩЕННЫЙ ПАЙПЛАЙН С GIGACHAT
import logging
import asyncio
from datetime import datetime
from typing import Dict, List, Optional
import hashlib

logger = logging.getLogger(__name__)

class SignalPipeline:
    """Упрощенный конвейер обработки с GigaChat"""
    
    def __init__(self, nlp_engine, finam_verifier, risk_manager, enhanced_analyzer, news_prefilter):
        self.nlp_engine = nlp_engine
        self.finam_verifier = finam_verifier
        self.risk_manager = risk_manager
        self.enhanced_analyzer = enhanced_analyzer
        self.news_prefilter = news_prefilter
        
        # Кэш для предотвращения дублирования
        self.news_cache = {}
        self.cache_ttl = 300  # 5 минут
        
        self.stats = {
            'total_news': 0,
            'filtered_news': 0,
            'gigachat_requests': 0,
            'gigachat_success': 0,
            'verification_passed': 0,
            'signals_generated': 0,
            'pipeline_start': datetime.now().isoformat()
        }
        
        logger.info("🚀 SignalPipeline инициализирован (GigaChat-centric)")
        logger.info("   Этапы: PreFilter → GigaChat → Finam → RiskManager")
    
    async def process_news_batch(self, news_list: List[Dict]) -> List[Dict]:
        """Пакетная обработка новостей"""
        
        self.stats['total_news'] += len(news_list)
        
        logger.info(f"📊 Обработка {len(news_list)} новостей через GigaChat...")
        
        signals = []
        processed = 0
        
        # ПОСЛЕДОВАТЕЛЬНАЯ обработка для стабильности
        for news_item in news_list:
            try:
                signal = await self._process_single_news(news_item)
                if signal:
                    signals.append(signal)
                
                processed += 1
                
                # Пауза каждые 5 новостей
                if processed % 5 == 0:
                    await asyncio.sleep(1)
                    
            except Exception as e:
                logger.error(f"❌ Ошибка обработки новости: {str(e)[:100]}")
                continue
        
        self.stats['signals_generated'] += len(signals)
        
        logger.info(f"📊 Итоги: {len(signals)} сигналов из {len(news_list)} новостей")
        logger.info(f"   Эффективность: {(len(signals)/max(1, len(news_list))*100):.1f}%")
        
        return signals
    
    async def _process_single_news(self, news_item: Dict) -> Optional[Dict]:
        """Обработка одной новости"""
        
        # 1. КЭШИРОВАНИЕ (проверка дублей)
        news_hash = self._create_news_hash(news_item)
        if news_hash in self.news_cache:
            cache_time, cache_result = self.news_cache[news_hash]
            if (datetime.now().timestamp() - cache_time) < self.cache_ttl:
                if cache_result:
                    logger.debug(f"🔄 Кэш-попадание: {news_item.get('title', '')[:50]}")
                    return cache_result
                return None
        
        # 2. ПРЕ-ФИЛЬТРАЦИЯ
        if not self.news_prefilter.is_tradable(news_item):
            self.stats['filtered_news'] += 1
            logger.debug(f"   ❌ PreFilter: {news_item.get('title', '')[:50]}")
            # Сохраняем в кэш как "не торгуемый"
            self.news_cache[news_hash] = (datetime.now().timestamp(), None)
            return None
        
        # 3. GIGACHAT АНАЛИЗ
        self.stats['gigachat_requests'] += 1
        logger.debug(f"   📡 GigaChat: {news_item.get('title', '')[:60]}")
        
        nlp_analysis = await self.nlp_engine.analyze_news(news_item)
        
        if not nlp_analysis:
            logger.debug(f"   ❌ GigaChat не ответил")
            self.news_cache[news_hash] = (datetime.now().timestamp(), None)
            return None
        
        self.stats['gigachat_success'] += 1
        
        # Если GigaChat сказал "не торгуемый"
        if not nlp_analysis.get('is_tradable', True):
            logger.debug(f"   ⚠️ GigaChat: не торговый сигнал")
            self.news_cache[news_hash] = (datetime.now().timestamp(), None)
            return None
        
        # 4. ВЕРИФИКАЦИЯ ЧЕРЕЗ FINAM
        verification = await self.finam_verifier.verify_signal(nlp_analysis)
        
        if not verification['valid']:
            logger.debug(f"   ❌ Finam: {verification.get('reason', '')}")
            return None
        
        self.stats['verification_passed'] += 1
        
        # 5. ПОЛУЧЕНИЕ ЦЕН
        tickers = verification.get('tickers', [])
        current_prices = {}
        
        for ticker in tickers:
            price = await self.finam_verifier.get_current_prices([ticker])
            if ticker in price:
                current_prices[ticker] = price[ticker]
        
        if not current_prices:
            logger.debug(f"   ❌ Нет цен для тикеров")
            return None
        
        # 6. RISK MANAGER (подготовка сигнала)
        signal = self.risk_manager.prepare_signal(
            analysis=nlp_analysis,
            verification=verification,
            current_prices=current_prices
        )
        
        if signal:
            # Добавляем метаданные
            signal.update({
                'pipeline_version': 'gigachat_v1',
                'news_hash': news_hash,
                'processing_timestamp': datetime.now().isoformat(),
                'nlp_provider': 'gigachat',
                'verification_source': 'finam'
            })
            
            logger.info(f"✅ СИГНАЛ: {signal['action']} {signal['ticker']} (impact={signal['impact_score']})")
            
            # Сохраняем в кэш
            self.news_cache[news_hash] = (datetime.now().timestamp(), signal)
        
        return signal
    
    def _create_news_hash(self, news_item: Dict) -> str:
        """Создание хэша новости для кэширования"""
        title = news_item.get('title', '')
        content = news_item.get('content', '') or news_item.get('description', '')
        source = news_item.get('source', '')
        
        text = f"{title[:100]}|{content[:200]}|{source}"
        return hashlib.md5(text.encode()).hexdigest()[:16]
    
    def get_stats(self) -> Dict:
        """Получение статистики"""
        total = self.stats['total_news']
        gigachat_req = self.stats['gigachat_requests']
        gigachat_succ = self.stats['gigachat_success']
        signals = self.stats['signals_generated']
        
        if total > 0:
            filter_rate = (self.stats['filtered_news'] / total) * 100
            if gigachat_req > 0:
                gigachat_success_rate = (gigachat_succ / gigachat_req) * 100
            else:
                gigachat_success_rate = 0
            signal_rate = (signals / total) * 100
        else:
            filter_rate = gigachat_success_rate = signal_rate = 0
        
        return {
            **self.stats,
            'filter_rate_percent': round(filter_rate, 1),
            'gigachat_success_rate': round(gigachat_success_rate, 1),
            'signal_rate_percent': round(signal_rate, 1),
            'news_cache_size': len(self.news_cache),
            'current_time': datetime.now().isoformat(),
            'processing_mode': 'gigachat_sequential'
        }
