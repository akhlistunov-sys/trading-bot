# signal_pipeline.py
import logging
import asyncio
from datetime import datetime
from typing import Dict, List, Optional
import json

logger = logging.getLogger(__name__)

class SignalPipeline:
    """Конвейер обработки новостей в торговые сигналы"""
    
    def __init__(self, nlp_engine, finam_verifier, risk_manager, enhanced_analyzer, news_prefilter):
        self.nlp_engine = nlp_engine
        self.finam_verifier = finam_verifier
        self.risk_manager = risk_manager
        self.enhanced_analyzer = enhanced_analyzer
        self.news_prefilter = news_prefilter
        
        self.stats = {
            'total_news': 0,
            'filtered_news': 0,
            'analyzed_news': 0,
            'verified_signals': 0,
            'executed_signals': 0,
            'pipeline_start': datetime.now().isoformat()
        }
        
        logger.info("🚀 SignalPipeline инициализирован")
        logger.info("   Этапы: PreFilter → NLP → Finam → RiskManager")
    
    async def process_news_batch(self, news_list: List[Dict]) -> List[Dict]:
        """Пакетная обработка новостей"""
        
        signals = []
        self.stats['total_news'] += len(news_list)
        
        logger.info(f"📊 Начало обработки {len(news_list)} новостей")
        
        # Параллельная обработка (но с лимитом)
        batch_size = min(10, len(news_list))
        
        for i in range(0, len(news_list), batch_size):
            batch = news_list[i:i+batch_size]
            
            batch_signals = await self._process_batch(batch)
            signals.extend(batch_signals)
            
            # Пауза между батчами
            if i + batch_size < len(news_list):
                await asyncio.sleep(1)
        
        self.stats['executed_signals'] += len(signals)
        
        logger.info(f"📊 Итоги обработки:")
        logger.info(f"   Новости: {self.stats['total_news']}")
        logger.info(f"   Отфильтровано: {self.stats['filtered_news']}")
        logger.info(f"   Проанализировано: {self.stats['analyzed_news']}")
        logger.info(f"   Сигналов: {len(signals)}")
        
        return signals
    
    async def _process_batch(self, news_batch: List[Dict]) -> List[Dict]:
        """Обработка батча новостей"""
        batch_signals = []
        
        # Параллельная обработка каждой новости
        tasks = []
        for news_item in news_batch:
            task = self._process_single_news(news_item)
            tasks.append(task)
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        for result in results:
            if isinstance(result, Exception):
                logger.error(f"❌ Ошибка обработки новости: {result}")
                continue
            
            if result:
                batch_signals.append(result)
        
        return batch_signals
    
    async def _process_single_news(self, news_item: Dict) -> Optional[Dict]:
        """Обработка одной новости через все этапы"""
        
        # 1. Пре-фильтрация
        if not self.news_prefilter.is_tradable(news_item):
            self.stats['filtered_news'] += 1
            return None
        
        # 2. Быстрая проверка EnhancedAnalyzer
        if not self.enhanced_analyzer.quick_filter(news_item):
            return None
        
        # 3. NLP анализ (GigaChat/OpenRouter)
        nlp_analysis = await self.nlp_engine.analyze_news(news_item)
        
        # 4. Fallback: EnhancedAnalyzer если ИИ не сработал
        if not nlp_analysis:
            nlp_analysis = self.enhanced_analyzer.analyze_news(news_item)
            if nlp_analysis:
                nlp_analysis['ai_provider'] = 'enhanced_fallback'
        
        if not nlp_analysis:
            return None
        
        self.stats['analyzed_news'] += 1
        
        # 5. Верификация через Finam
        verification = await self.finam_verifier.verify_signal(nlp_analysis)
        
        if not verification['valid']:
            return None
        
        # 6. Получение текущих цен
        tickers = verification.get('tickers', [])
        if not tickers:
            return None
        
        current_prices = await self.finam_verifier.get_current_prices(tickers)
        
        # 7. Risk Manager подготовка сигнала
        signal = self.risk_manager.prepare_signal(
            analysis=nlp_analysis,
            verification=verification,
            current_prices=current_prices
        )
        
        if signal:
            self.stats['verified_signals'] += 1
            
            # Добавляем метаданные
            signal.update({
                'pipeline_version': '2.0',
                'processing_timestamp': datetime.now().isoformat(),
                'verification_details': verification.get('details', {}),
                'nlp_analysis': {
                    'provider': nlp_analysis.get('ai_provider'),
                    'event_type': nlp_analysis.get('event_type'),
                    'sentiment': nlp_analysis.get('sentiment'),
                    'confidence': nlp_analysis.get('confidence')
                }
            })
            
            logger.info(f"✅ СИГНАЛ сформирован: {signal['action']} {signal['ticker']}")
        
        return signal
    
    def get_stats(self) -> Dict:
        """Получение статистики конвейера"""
        total_processed = self.stats['total_news']
        
        if total_processed > 0:
            filter_rate = (self.stats['filtered_news'] / total_processed) * 100
            analysis_rate = (self.stats['analyzed_news'] / total_processed) * 100
            signal_rate = (self.stats['verified_signals'] / total_processed) * 100
        else:
            filter_rate = analysis_rate = signal_rate = 0
        
        return {
            **self.stats,
            'filter_rate_percent': round(filter_rate, 1),
            'analysis_rate_percent': round(analysis_rate, 1),
            'signal_rate_percent': round(signal_rate, 1),
            'efficiency': round((self.stats['verified_signals'] / max(1, self.stats['analyzed_news'])) * 100, 1),
            'current_time': datetime.now().isoformat()
        }
