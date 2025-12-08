import logging
import json
import os
import asyncio
from datetime import datetime
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

class NlpEngine:
    """Гибридный ИИ-движок с поддержкой GigaChat и OpenRouter"""
    
    def __init__(self):
        logger.info("🔧 Инициализация гибридного NLP-движка...")
        
        # Инициализация провайдеров
        self.gigachat_auth = GigaChatAuth()  # Добавьте эту строку
        self.providers = {
            'gigachat': {
    'url': 'https://gigachat.devices.sberbank.ru/api/v1/chat/completions',
    'client_id': os.getenv('GIGACHAT_CLIENT_ID'),  # Используем Client ID вместо токена
    'scope': os.getenv('GIGACHAT_SCOPE', 'GIGACHAT_API_PERS'),
    'models': ['GigaChat', 'GigaChat-Pro'],
    'enabled': bool(os.getenv('GIGACHAT_CLIENT_ID')),  # Проверяем наличие Client ID
    'priority': 1,
    'auth': self.gigachat_auth  # Добавляем ссылку на auth объект
}
            'openrouter': {
                'url': 'https://openrouter.ai/api/v1/chat/completions',
                'token': os.getenv('OPENROUTER_API_TOKEN'),
                'models': [
                    'google/gemini-2.0-flash-exp:free',
                    'mistralai/mistral-7b-instruct:free'
                ],
                'headers': {
                    'Authorization': f'Bearer {os.getenv("OPENROUTER_API_TOKEN")}',
                    'Content-Type': 'application/json',
                    'HTTP-Referer': 'https://github.com',
                    'X-Title': 'News NLP Trading AI'
                },
                'enabled': bool(os.getenv('OPENROUTER_API_TOKEN')),
                'priority': 2  # Резервный
            }
        }
        
        # Сортируем провайдеры по приоритету
        self.provider_priority = sorted(
            [p for p in self.providers.keys() if self.providers[p]['enabled']],
            key=lambda x: self.providers[x]['priority']
        )
        
        if not self.provider_priority:
            logger.warning("⚠️ Ни один ИИ-провайдер не настроен (нужен GIGACHATAPI или OPENROUTER_API_TOKEN)")
            logger.warning("⚠️ Будет использоваться только SimpleAnalyzer")
        
        # Индексы для каждого провайдера
        self.model_indices = {provider: 0 for provider in self.provider_priority}
        
        # Кэш
        self.analysis_cache = {}
        self.cache_hits = 0
        self.cache_misses = 0
        
        # Статистика
        self.stats = {
            'total_requests': 0,
            'successful_requests': 0,
            'by_provider': {p: {'requests': 0, 'success': 0} for p in self.provider_priority},
            'cache_hits': 0,
            'cache_misses': 0
        }
        
        logger.info(f"🤖 Гибридный NLP-движок инициализирован")
        if self.provider_priority:
            logger.info(f"📊 Доступные провайдеры: {', '.join(self.provider_priority)}")
    
    def _create_cache_key(self, news_item: Dict) -> str:
        """Создание ключа для кэша"""
        title = news_item.get('title', '')[:50].replace(' ', '_').lower()
        source = news_item.get('source', '')[:20].replace(' ', '_').lower()
        content_hash = hash(news_item.get('content', '')[:200]) % 10000
        return f"{source}_{title}_{content_hash}"
    
    def _create_prompt_for_provider(self, news_item: Dict, provider: str) -> Dict:
        """Создание промпта в зависимости от провайдера"""
        
        title = news_item.get('title', '')
        description = news_item.get('description', '')
        content = news_item.get('content', '') or description
        source = news_item.get('source_name', news_item.get('source', 'Unknown'))
        
        if provider == 'gigachat':
            system_prompt = """Ты — финансовый аналитик Сбербанка. Анализируй новости российского рынка акций.
            
            ВАЖНЫЙ КОНТЕКСТ:
            1. Учитывай общие рыночные условия. Если рынок сегодня в сильном падении, даже позитивная новость может иметь ограниченный эффект.
            2. Обращай внимание на время публикации. Новости в нерабочие часы могут иметь запаздывающую реакцию.
            3. Различай факты и мнения/прогнозы.
            
            ИНСТРУКЦИИ ДЛЯ АНАЛИЗА:
            1. Найди все упоминания российских компаний и их тикеров (примеры: Сбербанк → SBER, Газпром → GAZP, Лукойл → LKOH)
            2. Определи тип события: earnings_report, dividend, merger_acquisition, regulatory, geopolitical, market_update, corporate_action, other
            3. Оцени важность (impact_score) для цены акции: 1-3=низкая, 4-6=средняя, 7-8=высокая, 9-10=критическая
            4. Оцени релевантность для трейдинга (relevance_score): 1-100
            5. Определи тональность: positive, negative, neutral, mixed
            6. Определи горизонт влияния: immediate (сегодня), short_term (несколько дней), medium_term (недели), long_term (месяцы+)
            7. Кратко объясни суть (2-3 предложения на русском)
            
            ВОЗВРАЩАЙ ТОЛЬКО JSON В СТРОГОМ ФОРМАТЕ:
            {
                "analysis": {
                    "tickers": ["TICKER1", "TICKER2"],
                    "event_type": "тип_события",
                    "impact_score": число,
                    "relevance_score": число,
                    "sentiment": "тональность",
                    "horizon": "горизонт",
                    "summary": "краткая суть на русском"
                }
            }
            
            ТОЛЬКО JSON, БЕЗ ДОПОЛНИТЕЛЬНОГО ТЕКСТА!"""
            
        else:  # openrouter и другие
            system_prompt = """You are a financial analyst AI. Analyze news and return strictly in JSON format.
            
            IMPORTANT CONTEXT:
            1. Consider overall market conditions. Even positive news may have limited effect in a bearish market.
            2. Note the publication time. News published outside market hours may have delayed reaction.
            3. Distinguish between facts and opinions/forecasts.
            
            ANALYSIS INSTRUCTIONS:
            1. Extract all company mentions and their tickers
            2. Determine event type: earnings_report, dividend, merger_acquisition, regulatory, geopolitical, market_update, corporate_action, other
            3. Rate importance (impact_score) for stock price: 1-10
            4. Rate relevance for trading (relevance_score): 1-100
            5. Determine sentiment: positive, negative, neutral, mixed
            6. Determine impact horizon: immediate (today), short_term (few days), medium_term (weeks), long_term (months+)
            7. Provide brief summary
            
            RETURN ONLY JSON IN THIS EXACT FORMAT:
            {
                "analysis": {
                    "tickers": ["TICKER1", "TICKER2"],
                    "event_type": "event_type",
                    "impact_score": number,
                    "relevance_score": number,
                    "sentiment": "sentiment",
                    "horizon": "horizon",
                    "summary": "brief summary"
                }
            }
            
            ONLY JSON, NO OTHER TEXT!"""
        
        # Выбираем модель для провайдера
        model_idx = self.model_indices[provider]
        models = self.providers[provider]['models']
        model = models[model_idx % len(models)]
        
        return {
            "model": model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"Источник: {source}\nЗаголовок: {title}\nТекст: {content[:1200]}"}
            ],
            "temperature": 0.1,
            "max_tokens": 600
        }
    
    def _switch_to_next_model(self, provider: str):
        """Переключение на следующую модель у провайдера"""
        models = self.providers[provider]['models']
        if len(models) > 1:
            old_idx = self.model_indices[provider]
            self.model_indices[provider] = (old_idx + 1) % len(models)
            old_model = models[old_idx]
            new_model = models[self.model_indices[provider]]
            logger.info(f"🔄 {provider}: смена модели {old_model} → {new_model}")
    
    async def analyze_news(self, news_item: Dict) -> Optional[Dict]:
        """Анализ новости с использованием доступных провайдеров"""
        
        self.stats['total_requests'] += 1
        
        # Проверка кэша
        cache_key = self._create_cache_key(news_item)
        if cache_key in self.analysis_cache:
            self.stats['cache_hits'] += 1
            self.cache_hits += 1
            logger.info(f"🔄 Использую кэшированный анализ (hits: {self.cache_hits})")
            return self.analysis_cache[cache_key]
        
        self.stats['cache_misses'] += 1
        self.cache_misses += 1
        news_title = news_item.get('title', '')[:50]
        logger.info(f"🧠 Анализ новости #{self.stats['total_requests']}: {news_title}...")
        
        # Если нет доступных провайдеров, возвращаем None
        if not self.provider_priority:
            logger.warning("⚠️ Нет доступных ИИ-провайдеров, пропускаем анализ")
            return None
        
        # Пробуем провайдеры по приоритету
        for provider in self.provider_priority:
            if not self.providers[provider]['enabled']:
                continue
            
            logger.info(f"📡 Пробую провайдер: {provider.upper()}")
            self.stats['by_provider'][provider]['requests'] += 1
            
            # Пробуем несколько раз с разными моделями провайдера
            max_retries = min(2, len(self.providers[provider]['models']))
            
            for attempt in range(max_retries):
                try:
                    logger.info(f"   📨 Попытка {attempt+1}/{max_retries}")
                    
                    # Создаем запрос для провайдера
                    prompt_data = self._create_prompt_for_provider(news_item, provider)
                    
                    # Импортируем httpx ТОЛЬКО ЗДЕСЬ, когда он действительно нужен
                    import httpx
                    
                    # ОСНОВНОЕ ИСПРАВЛЕНИЕ: отключаем SSL проверку ТОЛЬКО для GigaChat
                    if provider == 'gigachat':
                        # Отключаем проверку SSL для GigaChat из-за проблем с сертификатом
                        async with httpx.AsyncClient(timeout=30.0, verify=False) as client:
                            response = await client.post(
                                url=self.providers[provider]['url'],
                                headers=self.providers[provider]['headers'],
                                json=prompt_data
                            )
                    else:
                        # Для других провайдеров оставляем стандартную проверку SSL
                        async with httpx.AsyncClient(timeout=30.0) as client:
                            response = await client.post(
                                url=self.providers[provider]['url'],
                                headers=self.providers[provider]['headers'],
                                json=prompt_data
                            )
                    
                    logger.info(f"   📥 Ответ {provider}: статус {response.status_code}")
                    
                    if response.status_code == 200:
                        result = response.json()
                        ai_response = result.get("choices", [{}])[0].get("message", {}).get("content", "")
                        
                        if not ai_response:
                            logger.warning(f"   ⚠️ {provider}: пустой ответ")
                            continue
                        
                        # Парсинг JSON ответа
                        analysis_result = self._parse_ai_response(ai_response, news_item, provider)
                        
                        if analysis_result:
                            self.stats['successful_requests'] += 1
                            self.stats['by_provider'][provider]['success'] += 1
                            
                            # Кэшируем результат
                            self.analysis_cache[cache_key] = analysis_result
                            if len(self.analysis_cache) > 100:
                                oldest = next(iter(self.analysis_cache))
                                del self.analysis_cache[oldest]
                            
                            logger.info(f"   ✅ {provider}: успешный анализ")
                            return analysis_result
                        else:
                            logger.warning(f"   ⚠️ {provider}: не удалось распарсить ответ")
                    
                    elif response.status_code in [400, 404]:
                        error_data = response.json()
                        error_msg = error_data.get('error', {}).get('message', 'Unknown error')[:100]
                        logger.warning(f"   ⚠️ {provider}: ошибка модели - {error_msg}")
                        
                        if attempt < max_retries - 1:
                            self._switch_to_next_model(provider)
                            await asyncio.sleep(1)
                            continue
                    
                    elif response.status_code == 429:
                        logger.warning(f"   ⚠️ {provider}: rate limit")
                        break  # Переходим к следующему провайдеру
                    
                    elif response.status_code == 401:
                        logger.error(f"   ❌ {provider}: ошибка авторизации (неверный токен?)")
                        break
                    
                    else:
                        logger.warning(f"   ⚠️ {provider}: HTTP {response.status_code}")
                        break
                        
                except httpx.TimeoutException:
                    logger.error(f"   ⏰ {provider}: таймаут")
                    if attempt < max_retries - 1:
                        self._switch_to_next_model(provider)
                        await asyncio.sleep(2)
                        continue
                    break
                    
                except Exception as e:
                    logger.error(f"   ❌ {provider}: ошибка - {str(e)[:100]}")
                    break
            
            # Небольшая пауза перед следующим провайдером
            await asyncio.sleep(0.5)
        
        logger.error(f"❌ Все провайдеры недоступны для анализа новости")
        return None
    
    def _parse_ai_response(self, response: str, news_item: Dict, provider: str) -> Optional[Dict]:
        """Парсинг ответа ИИ"""
        try:
            # Очистка ответа
            response = response.strip()
            
            # Удаляем markdown кодовые блоки если есть
            if '```json' in response:
                response = response.split('```json')[1].split('```')[0].strip()
            elif '```' in response:
                response = response.split('```')[1].split('```')[0].strip()
            
            # Ищем JSON
            start_idx = response.find('{')
            end_idx = response.rfind('}') + 1
            
            if start_idx == -1 or end_idx == 0:
                logger.warning(f"   ⚠️ {provider}: не найден JSON в ответе")
                return None
            
            json_str = response[start_idx:end_idx]
            data = json.loads(json_str)
            
            analysis_data = data.get("analysis", {})
            
            # Валидация обязательных полей
            required_fields = ['tickers', 'event_type', 'impact_score', 'relevance_score']
            if not all(field in analysis_data for field in required_fields):
                logger.warning(f"   ⚠️ {provider}: отсутствуют обязательные поля")
                return None
            
            # Создаем результат анализа
            result = {
                'news_id': news_item.get('id', ''),
                'news_title': news_item.get('title', ''),
                'news_source': news_item.get('source', ''),
                'news_url': news_item.get('url', ''),
                'analysis_timestamp': datetime.now().isoformat(),
                
                # Анализ ИИ
                'tickers': analysis_data.get('tickers', []),
                'event_type': analysis_data.get('event_type', 'other'),
                'impact_score': int(analysis_data.get('impact_score', 1)),
                'relevance_score': int(analysis_data.get('relevance_score', 30)),
                'sentiment': analysis_data.get('sentiment', 'neutral'),
                'horizon': analysis_data.get('horizon', 'short_term'),
                'summary': analysis_data.get('summary', ''),
                
                # Метаданные
                'ai_provider': provider,
                'ai_model': self.providers[provider]['models'][self.model_indices[provider]],
                'confidence': min(1.0, analysis_data.get('relevance_score', 30) / 100.0)
            }
            
            # Логируем результат
            tickers_str = ', '.join(result['tickers']) if result['tickers'] else 'НЕТ ТИКЕРОВ'
            logger.info(f"   📊 {provider}: {tickers_str} | Impact: {result['impact_score']}/10")
            
            return result
            
        except json.JSONDecodeError as e:
            logger.error(f"   ❌ {provider}: невалидный JSON - {str(e)[:50]}")
            logger.debug(f"   💬 Ответ: {response[:200]}")
            return None
        except Exception as e:
            logger.error(f"   ❌ {provider}: ошибка парсинга - {str(e)[:50]}")
            return None
    
    def get_current_provider(self) -> str:
        """Получение текущего активного провайдера"""
        return self.provider_priority[0] if self.provider_priority else "simple"
    
    def get_stats(self) -> Dict:
        """Статистика работы NLP-движка"""
        success_rate = (self.stats['successful_requests'] / self.stats['total_requests'] * 100) if self.stats['total_requests'] > 0 else 0
        cache_hit_rate = (self.stats['cache_hits'] / (self.stats['cache_hits'] + self.stats['cache_misses']) * 100) if (self.stats['cache_hits'] + self.stats['cache_misses']) > 0 else 0
        
        # Статистика по провайдерам
        provider_stats = {}
        for provider in self.providers:
            req = self.stats['by_provider'].get(provider, {}).get('requests', 0)
            succ = self.stats['by_provider'].get(provider, {}).get('success', 0)
            rate = (succ / req * 100) if req > 0 else 0
            provider_stats[provider] = {
                'requests': req,
                'success': succ,
                'success_rate': round(rate, 1),
                'enabled': self.providers[provider]['enabled'],
                'models': len(self.providers[provider]['models'])
            }
        
        return {
            'total_requests': self.stats['total_requests'],
            'successful_requests': self.stats['successful_requests'],
            'success_rate': round(success_rate, 1),
            'cache_hits': self.stats['cache_hits'],
            'cache_misses': self.stats['cache_misses'],
            'cache_hit_rate': round(cache_hit_rate, 1),
            'current_provider': self.get_current_provider(),
            'providers': provider_stats
        }
