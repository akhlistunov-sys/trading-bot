# signal_pipeline.py - ПОСЛЕДОВАТЕЛЬНАЯ ОБРАБОТКА
import logging
import asyncio
from datetime import datetime
from typing import Dict, List, Optional
import json

logger = logging.getLogger(__name__)

class SignalPipeline:
    """Конвейер обработки новостей с последовательной обработкой GigaChat"""
    
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
        
        logger.info("🚀 SignalPipeline инициализирован с последовательной обработкой")
        logger.info("   Этапы: PreFilter → EnhancedAnalyzer → NLP (последовательно)")
    
    async def process_news_batch(self, news_list: List[Dict]) -> List[Dict]:
        """Пакетная обработка новостей ПОСЛЕДОВАТЕЛЬНО"""
        
        signals = []
        self.stats['total_news'] += len(news_list)
        
        logger.info(f"📊 Начало ПОСЛЕДОВАТЕЛЬНОЙ обработки {len(news_list)} новостей")
        
        # ПОСЛЕДОВАТЕЛЬНАЯ обработка (не параллельная!)
        processed_count = 0
        for news_item in news_list:
            try:
                signal = await self._process_single_news(news_item)
                if signal:
                    signals.append(signal)
                    logger.info(f"   ✅ Обработана новость {processed_count + 1}/{len(news_list)}: найдено {len(signals)} сигналов")
                else:
                    logger.debug(f"   ⏭️ Новость {processed_count + 1}/{len(news_list)} пропущена")
                
                processed_count += 1
                
                # Пауза между обработкой новостей для GigaChat
                if processed_count % 3 == 0:  # Каждые 3 новости
                    await asyncio.sleep(2)
                    
            except Exception as e:
                logger.error(f"❌ Ошибка обработки новости {processed_count + 1}: {str(e)[:100]}")
                continue
        
        self.stats['executed_signals'] += len(signals)
        
        logger.info(f"📊 Итоги ПОСЛЕДОВАТЕЛЬНОЙ обработки:")
        logger.info(f"   Новости: {self.stats['total_news']}")
        logger.info(f"   Отфильтровано: {self.stats['filtered_news']}")
        logger.info(f"   Проанализировано: {self.stats['analyzed_news']}")
        logger.info(f"   Сигналов: {len(signals)}")
        
        return signals
    
    async def _process_single_news(self, news_item: Dict) -> Optional[Dict]:
        """Обработка одной новости через все этапы"""
        
        # 1. Пре-фильтрация
        if not self.news_prefilter.is_tradable(news_item):
            self.stats['filtered_news'] += 1
            logger.debug(f"   ❌ PreFilter отсеял: {news_item.get('title', '')[:50]}")
            return None
        
        # 2. Быстрая проверка EnhancedAnalyzer (упрощенная)
        if not self.enhanced_analyzer.quick_filter(news_item):
            logger.debug(f"   ❌ EnhancedAnalyzer отсеял: {news_item.get('title', '')[:50]}")
            return None
        
        # 3. NLP анализ (GigaChat/OpenRouter) - ПОСЛЕДОВАТЕЛЬНО
        logger.debug(f"   📡 Отправляю в NLP: {news_item.get('title', '')[:60]}")
        nlp_analysis = await self.nlp_engine.analyze_news(news_item)
        
        # 4. Fallback: EnhancedAnalyzer если ИИ не сработал
        if not nlp_analysis:
            nlp_analysis = self.enhanced_analyzer.analyze_news(news_item)
            if nlp_analysis:
                nlp_analysis['ai_provider'] = 'enhanced_fallback'
                logger.debug(f"   🔧 Использую EnhancedAnalyzer fallback")
        
        if not nlp_analysis:
            logger.debug(f"   ❌ NLP не дал анализа")
            return None
        
        self.stats['analyzed_news'] += 1
        logger.debug(f"   ✅ NLP анализ получен от {nlp_analysis.get('ai_provider', 'unknown')}")
        
        # 5. Верификация через Finam
        verification = await self.finam_verifier.verify_signal(nlp_analysis)
        
        if not verification['valid']:
            logger.debug(f"   ❌ Finam верификация не прошла: {verification.get('reason', '')}")
            return None
        
        logger.debug(f"   ✅ Finam верификация пройдена")
        
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
                'pipeline_version': '2.1',
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
            'current_time': datetime.now().isoformat(),
            'processing_mode': 'sequential_gigachat'
        }
