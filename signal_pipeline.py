# signal_pipeline.py - ГИБРИДНЫЙ ПАЙПЛАЙН С GIGACHAT И ТЕХНИЧЕСКИМ АНАЛИЗОМ
import logging
import asyncio
from datetime import datetime
from typing import Dict, List, Optional
import hashlib

logger = logging.getLogger(__name__)

class SignalPipeline:
    """Гибридный конвейер обработки с GigaChat и Техническим анализом"""
    
    def __init__(self, nlp_engine, finam_verifier, risk_manager, 
                 enhanced_analyzer, news_prefilter, technical_strategy=None):
        self.nlp_engine = nlp_engine
        self.finam_verifier = finam_verifier
        self.risk_manager = risk_manager
        self.enhanced_analyzer = enhanced_analyzer
        self.news_prefilter = news_prefilter
        self.technical_strategy = technical_strategy
        
        # Кэш для предотвращения дублирования
        self.news_cache = {}
        self.technical_cache = {}
        self.cache_ttl = 300  # 5 минут
        
        self.stats = {
            'total_news': 0,
            'total_technical_scans': 0,
            'filtered_news': 0,
            'gigachat_requests': 0,
            'gigachat_success': 0,
            'technical_signals': 0,
            'verification_passed': 0,
            'signals_generated': 0,
            'hybrid_signals': 0,
            'pipeline_start': datetime.now().isoformat()
        }
        
        logger.info("🚀 Гибридный SignalPipeline инициализирован")
        logger.info("   Этапы: PreFilter → GigaChat/Technical → Finam → RiskManager")
        logger.info(f"   Тех. анализ: {'✅' if technical_strategy else '❌'}")
    
    async def process_news_batch(self, news_items):
        fresh_news = []
        for news in news_items:
            news_id = news.get('id') or hash(news.get('title', ''))
            
            # Пропускаем если уже обрабатывали в последние 4 часа
            if news_id in self.processed_news_cache:
                if time.time() - self.processed_news_cache[news_id] < 14400:  # 4 часа
                    continue
            
            fresh_news.append(news)
            self.processed_news_cache[news_id] = time.time()
        
        logger.info(f"📊 Гибридная обработка {len(news_list)} новостей...")
        
        signals = []
        
        # 1. ПАРАЛЛЕЛЬНО: Технический анализ (если доступен)
        technical_signals = []
        if self.technical_strategy:
            try:
                self.stats['total_technical_scans'] += 1
                tech_signals = await self.technical_strategy.scan_for_signals()
                self.stats['technical_signals'] += len(tech_signals)
                technical_signals = tech_signals
                logger.info(f"📈 Тех. анализ: {len(tech_signals)} сигналов")
            except Exception as e:
                logger.error(f"❌ Ошибка технического анализа: {str(e)[:100]}")
        
        # 2. ПОСЛЕДОВАТЕЛЬНАЯ обработка новостей для стабильности
        news_signals = []
        processed = 0
        
        for news_item in news_list:
            try:
                signal = await self._process_single_news(news_item)
                if signal:
                    news_signals.append(signal)
                
                processed += 1
                
                # Пауза каждые 5 новостей
                if processed % 5 == 0:
                    await asyncio.sleep(1)
                    
            except Exception as e:
                logger.error(f"❌ Ошибка обработки новости: {str(e)[:100]}")
                continue
        
        # 3. ОБЪЕДИНЕНИЕ сигналов из двух источников
        all_signals = news_signals + technical_signals
        self.stats['hybrid_signals'] = len(all_signals)
        
        # 4. ВЕРИФИКАЦИЯ и подготовка через RiskManager
        verified_signals = []
        current_prices = {}
        
        # Собираем все тикеры для запроса цен
        all_tickers = list(set(signal.get('ticker') for signal in all_signals if signal.get('ticker')))
        
        if all_tickers:
            logger.info(f"💰 Получение цен для {len(all_tickers)} тикеров...")
            current_prices = await self.finam_verifier.get_current_prices(all_tickers)
        
        # Обработка каждого сигнала через RiskManager
        for signal in all_signals:
            try:
                ticker = signal.get('ticker')
                if not ticker:
                    continue
                    
                # Получаем цену для тикера
                if ticker not in current_prices:
                    # Пытаемся получить цену отдельно
                    price = await self.finam_verifier._get_price_from_finam(ticker)
                    if price:
                        current_prices[ticker] = price
                    else:
                        logger.warning(f"⚠️ Нет цены для {ticker}, пропускаем сигнал")
                        continue
                
                # Для новостных сигналов нужна верификация
                if signal.get('ai_provider') in ['gigachat', 'enhanced']:
                    # Создаём упрощённый анализ для верификации
                    analysis_for_verification = {
                        'tickers': [ticker],
                        'sentiment': signal.get('sentiment', 'neutral'),
                        'impact_score': signal.get('impact_score', 5),
                        'confidence': signal.get('confidence', 0.5),
                        'event_type': signal.get('event_type', 'ai_analyzed'),
                        'ai_provider': signal.get('ai_provider', 'gigachat')
                    }
                    
                    verification = await self.finam_verifier.verify_signal(analysis_for_verification)
                    
                    if not verification.get('valid'):
                        logger.debug(f"   ❌ Finam верификация не пройдена для {ticker}")
                        continue
                    
                    self.stats['verification_passed'] += 1
                    
                    # Подготовка сигнала через RiskManager
                    risk_signal = self.risk_manager.prepare_signal(
                        analysis=analysis_for_verification,
                        verification=verification,
                        current_prices={ticker: current_prices[ticker]}
                    )
                    
                    if risk_signal:
                        # Добавляем метаданные из оригинального сигнала
                        risk_signal.update({
                            'original_reason': signal.get('reason'),
                            'pipeline_version': 'hybrid_v2',
                            'news_hash': signal.get('news_hash') if 'news_hash' in signal else self._create_news_hash(signal),
                            'processing_timestamp': datetime.now().isoformat(),
                            'nlp_provider': signal.get('ai_provider', 'unknown'),
                            'verification_source': 'finam'
                        })
                        verified_signals.append(risk_signal)
                        logger.info(f"✅ Верифицирован: {risk_signal['action']} {ticker}")
                
                # Для технических сигналов упрощённая обработка
                elif signal.get('ai_provider') == 'technical':
                    # Технические сигналы уже содержат action и логику
                    analysis_for_risk = {
                        'tickers': [ticker],
                        'sentiment': signal.get('sentiment', 'neutral'),
                        'impact_score': signal.get('impact_score', 5),
                        'confidence': signal.get('confidence', 0.5),
                        'event_type': signal.get('event_type', 'technical'),
                        'ai_provider': 'technical',
                        'action': signal.get('action'),  # Важно: передаём уже определённое действие
                        'summary': signal.get('reason', 'Технический сигнал')
                    }
                    
                    # Создаём упрощённую верификацию
                    verification = {
                        'valid': True,
                        'reason': 'Технический сигнал',
                        'tickers': [ticker],
                        'primary_ticker': ticker,
                        'primary_price': current_prices[ticker]
                    }
                    
                    risk_signal = self.risk_manager.prepare_signal(
                        analysis=analysis_for_risk,
                        verification=verification,
                        current_prices={ticker: current_prices[ticker]}
                    )
                    
                    if risk_signal:
                        verified_signals.append(risk_signal)
                        logger.info(f"📈 Тех. сигнал принят: {risk_signal['action']} {ticker}")
                        
            except Exception as e:
                logger.error(f"❌ Ошибка обработки сигнала {signal.get('ticker', 'unknown')}: {str(e)[:100]}")
                continue
        
        self.stats['signals_generated'] += len(verified_signals)
        
        logger.info(f"📊 Итоги гибридной обработки:")
        logger.info(f"   📰 Новостных сигналов: {len(news_signals)}")
        logger.info(f"   📈 Технических сигналов: {len(technical_signals)}")
        logger.info(f"   ✅ Верифицировано: {len(verified_signals)}")
        logger.info(f"   💰 Получено цен: {len(current_prices)}")
        
        return verified_signals
    
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
        
        # 3. УСИЛЕННЫЙ АНАЛИЗ (если GigaChat не доступен)
        enhanced_analysis = None
        if not self.nlp_engine.enabled:
            logger.debug(f"   🔧 EnhancedAnalyzer: {news_item.get('title', '')[:50]}")
            enhanced_analysis = self.enhanced_analyzer.analyze_news(news_item)
            
            if not enhanced_analysis or not enhanced_analysis.get('tickers'):
                logger.debug(f"   ❌ Enhanced: не найдены тикеры")
                self.news_cache[news_hash] = (datetime.now().timestamp(), None)
                return None
            
            # Создаём сигнал на основе enhanced анализа
            signal = {
                'news_hash': news_hash,
                'ticker': enhanced_analysis['tickers'][0] if enhanced_analysis['tickers'] else None,
                'tickers': enhanced_analysis['tickers'],
                'sentiment': enhanced_analysis['sentiment'],
                'impact_score': enhanced_analysis['impact_score'],
                'confidence': enhanced_analysis['confidence'],
                'event_type': enhanced_analysis['event_type'],
                'reason': enhanced_analysis['summary'],
                'ai_provider': 'enhanced',
                'news_id': news_item.get('id', ''),
                'news_title': news_item.get('title', '')[:100],
                'timestamp': datetime.now().isoformat()
            }
            
            if signal['ticker']:
                self.news_cache[news_hash] = (datetime.now().timestamp(), signal)
                logger.debug(f"✅ Enhanced сигнал: {signal['ticker']} ({signal['sentiment']})")
                return signal
            return None
        
        # 4. GIGACHAT АНАЛИЗ (основной)
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
        
        # Проверяем, есть ли тикеры
        if not nlp_analysis.get('tickers'):
            logger.debug(f"   ⚠️ GigaChat: нет тикеров в ответе")
            self.news_cache[news_hash] = (datetime.now().timestamp(), None)
            return None
        
        # Создаём сигнал на основе анализа GigaChat
        signal = {
            'news_hash': news_hash,
            'ticker': nlp_analysis['tickers'][0] if nlp_analysis['tickers'] else None,
            'tickers': nlp_analysis['tickers'],
            'sentiment': nlp_analysis['sentiment'],
            'impact_score': nlp_analysis['impact_score'],
            'confidence': nlp_analysis['confidence'],
            'event_type': nlp_analysis.get('event_type', 'ai_analyzed'),
            'reason': nlp_analysis.get('summary', 'Анализ GigaChat'),
            'ai_provider': 'gigachat',
            'news_id': news_item.get('id', ''),
            'news_title': nlp_analysis.get('news_title', '')[:100],
            'timestamp': datetime.now().isoformat()
        }
        
        if signal['ticker']:
            self.news_cache[news_hash] = (datetime.now().timestamp(), signal)
            logger.debug(f"✅ GigaChat сигнал: {signal['ticker']} (impact={signal['impact_score']})")
            return signal
        
        return None
    
    def _create_news_hash(self, news_item: Dict) -> str:
        """Создание хэша новости для кэширования"""
        title = news_item.get('title', '')
        content = news_item.get('content', '') or news_item.get('description', '')
        source = news_item.get('source', '')
        
        text = f"{title[:100]}|{content[:200]}|{source}"
        return hashlib.md5(text.encode()).hexdigest()[:16]
    
    def get_stats(self) -> Dict:
        """Получение статистики гибридного пайплайна"""
        total_news = self.stats['total_news']
        gigachat_req = self.stats['gigachat_requests']
        gigachat_succ = self.stats['gigachat_success']
        tech_signals = self.stats['technical_signals']
        signals = self.stats['signals_generated']
        hybrid = self.stats['hybrid_signals']
        
        if total_news > 0:
            filter_rate = (self.stats['filtered_news'] / total_news) * 100
            if gigachat_req > 0:
                gigachat_success_rate = (gigachat_succ / gigachat_req) * 100
            else:
                gigachat_success_rate = 0
            signal_rate = (signals / total_news) * 100 if total_news > 0 else 0
            hybrid_rate = (hybrid / max(1, total_news + self.stats['total_technical_scans'])) * 100
        else:
            filter_rate = gigachat_success_rate = signal_rate = hybrid_rate = 0
        
        return {
            **self.stats,
            'filter_rate_percent': round(filter_rate, 1),
            'gigachat_success_rate': round(gigachat_success_rate, 1),
            'signal_rate_percent': round(signal_rate, 1),
            'hybrid_rate_percent': round(hybrid_rate, 1),
            'news_cache_size': len(self.news_cache),
            'technical_cache_size': len(self.technical_cache),
            'current_time': datetime.now().isoformat(),
            'processing_mode': 'hybrid_parallel' if self.technical_strategy else 'gigachat_sequential',
            'has_technical': bool(self.technical_strategy)
        }
    
    async def run_continuous_hybrid_scan(self, news_interval: int = 300, tech_interval: int = 60):
        """Непрерывное гибридное сканирование в фоновом режиме"""
        logger.info(f"🔄 Запуск непрерывного гибридного сканирования...")
        logger.info(f"   Новости: каждые {news_interval} сек, Тех. анализ: каждые {tech_interval} сек")
        
        async def news_scan():
            while True:
                try:
                    logger.debug("📰 Запуск сканирования новостей...")
                    news = await self.nlp_engine.news_fetcher.fetch_all_news() if hasattr(self.nlp_engine, 'news_fetcher') else []
                    if news:
                        signals = await self.process_news_batch(news[:10])  # Ограничиваем для теста
                        if signals:
                            logger.info(f"📊 Новостной сканинг: {len(signals)} сигналов")
                    await asyncio.sleep(news_interval)
                except Exception as e:
                    logger.error(f"❌ Ошибка новостного сканирования: {str(e)[:100]}")
                    await asyncio.sleep(news_interval)
        
        async def technical_scan():
            while True:
                try:
                    if self.technical_strategy:
                        logger.debug("📈 Запуск технического сканирования...")
                        signals = await self.technical_strategy.scan_for_signals()
                        if signals:
                            logger.info(f"📊 Тех. сканинг: {len(signals)} сигналов")
                    await asyncio.sleep(tech_interval)
                except Exception as e:
                    logger.error(f"❌ Ошибка технического сканирования: {str(e)[:100]}")
                    await asyncio.sleep(tech_interval)
        
        # Запускаем оба сканирования параллельно
        await asyncio.gather(
            news_scan(),
            technical_scan()
        )
