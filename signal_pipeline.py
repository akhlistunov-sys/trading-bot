# signal_pipeline.py - ПОЛНЫЙ ФАЙЛ (ИСПРАВЛЕН ВЫЛЕТ)
import logging
import asyncio
import time
from datetime import datetime
from typing import Dict, List, Optional
import hashlib

logger = logging.getLogger(__name__)

class SignalPipeline:
    """Гибридный конвейер: Новости + Тех.Анализ"""
    
    def __init__(self, nlp_engine, finam_verifier, risk_manager, 
                 enhanced_analyzer, news_prefilter, technical_strategy=None):
        self.nlp_engine = nlp_engine
        self.finam_verifier = finam_verifier
        self.risk_manager = risk_manager
        self.enhanced_analyzer = enhanced_analyzer
        self.news_prefilter = news_prefilter
        self.technical_strategy = technical_strategy
        
        # Кэширование (ВАЖНО: Инициализация здесь!)
        self.news_cache = {}
        self.processed_news_cache = {} 
        self.cache_ttl = 300
        
        self.stats = {
            'total_news': 0,
            'technical_signals': 0,
            'signals_generated': 0,
            'hybrid_signals': 0,
            'pipeline_start': datetime.now().isoformat()
        }
        
        logger.info("🚀 SignalPipeline инициализирован (Кэш исправлен)")
    
    async def process_news_batch(self, news_items):
        """Основной метод обработки"""
        fresh_news = []
        
        # Фильтрация дублей новостей
        for news in news_items:
            # Генерируем ID если нет
            title = news.get('title', '')
            news_id = news.get('id') or hashlib.md5(title.encode()).hexdigest()
            
            # Проверяем, обрабатывали ли мы эту новость за последние 4 часа
            if news_id in self.processed_news_cache:
                if time.time() - self.processed_news_cache[news_id] < 14400:
                    continue
            
            fresh_news.append(news)
            self.processed_news_cache[news_id] = time.time()
        
        # Чистка старого кэша
        current_time = time.time()
        self.processed_news_cache = {k:v for k,v in self.processed_news_cache.items() 
                                   if current_time - v < 14400}
        
        if fresh_news:
            logger.info(f"📊 Обработка {len(fresh_news)} свежих новостей...")
        
        # 1. Сбор технических сигналов
        technical_signals = []
        if self.technical_strategy:
            try:
                technical_signals = await self.technical_strategy.scan_for_signals()
                self.stats['technical_signals'] += len(technical_signals)
            except Exception as e:
                logger.error(f"❌ Ошибка тех. анализа: {e}")
        
        # 2. Сбор новостных сигналов
        news_signals = []
        for news_item in fresh_news:
            try:
                signal = await self._process_single_news(news_item)
                if signal:
                    news_signals.append(signal)
            except Exception as e:
                logger.error(f"❌ Ошибка новости: {e}")
                
        # 3. Объединение всех сигналов
        all_signals = news_signals + technical_signals
        self.stats['hybrid_signals'] = len(all_signals)
        
        verified_signals = []
        
        # 4. Верификация и Риск-менеджмент
        if all_signals:
            # Получаем цены для всех тикеров сразу
            tickers = list(set(s['ticker'] for s in all_signals if s.get('ticker')))
            prices = await self.finam_verifier.get_current_prices(tickers)
            
            for signal in all_signals:
                ticker = signal.get('ticker')
                
                # Если цены нет, пропускаем (риск-менеджер не сможет посчитать объем)
                if not ticker or ticker not in prices:
                    continue
                
                # Для технических сигналов упрощенная верификация
                if signal.get('ai_provider') == 'technical':
                    verification = {
                        'valid': True,
                        'primary_ticker': ticker,
                        'primary_price': prices[ticker],
                        'reason': 'Technical Signal'
                    }
                    analysis_data = signal # Используем сам сигнал как данные анализа
                
                # Для новостных - полная проверка
                else:
                    analysis_data = {
                        'tickers': [ticker],
                        'sentiment': signal.get('sentiment'),
                        'impact_score': signal.get('impact_score'),
                        'confidence': signal.get('confidence'),
                        'ai_provider': signal.get('ai_provider')
                    }
                    verification = await self.finam_verifier.verify_signal(analysis_data)
                
                # Если верификация пройдена - отправляем в Риск Менеджер
                if verification.get('valid'):
                    risk_signal = self.risk_manager.prepare_signal(
                        analysis=analysis_data,
                        verification=verification,
                        current_prices=prices
                    )
                    
                    if risk_signal:
                        # Для тех. сигналов сохраняем оригинальный action (BUY/SELL)
                        if signal.get('ai_provider') == 'technical':
                            risk_signal['action'] = signal['action']
                            
                        verified_signals.append(risk_signal)

        self.stats['signals_generated'] += len(verified_signals)
        return verified_signals

    async def _process_single_news(self, news_item):
        """Анализ одной новости"""
        try:
            # Сначала быстрый фильтр
            if not self.news_prefilter.is_tradable(news_item):
                return None
            
            # Если GigaChat работает
            if self.nlp_engine.enabled:
                analysis = await self.nlp_engine.analyze_news(news_item)
                
                if analysis and analysis.get('is_tradable') and analysis.get('tickers'):
                    return {
                        'ticker': analysis['tickers'][0],
                        'action': 'BUY' if analysis['sentiment'] == 'positive' else 'SELL',
                        'confidence': analysis['confidence'],
                        'impact_score': analysis['impact_score'],
                        'reason': analysis['summary'],
                        'ai_provider': 'gigachat',
                        'sentiment': analysis['sentiment'],
                        'event_type': analysis['event_type']
                    }
        except Exception:
            return None
        return None

    def get_stats(self):
        return self.stats
