import logging
import json
import os
import asyncio
import httpx
import time
import re
import uuid
from datetime import datetime
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

# ==================== GIGACHAT OAUTH 2.0 КЛАСС (ИСПРАВЛЕННЫЙ) ====================
class GigaChatAuth:
    """Класс для авторизации в GigaChat API через OAuth 2.0 (Client Credentials)"""
    
    def __init__(self, client_id: str, client_secret: str, scope: str = "GIGACHAT_API_PERS"):
        self.client_id = client_id
        self.client_secret = client_secret  # Важно: теперь нужен и секрет!
        self.scope = scope
        self.access_token = None
        self.token_expiry = 0
        
    async def get_access_token(self) -> Optional[str]:
        """Получение access token через OAuth 2.0 Client Credentials flow"""
        # Если токен ещё действителен (с запасом 60 секунд)
        if self.access_token and time.time() < self.token_expiry - 60:
            return self.access_token
        
        url = "https://ngw.devices.sberbank.ru:9443/api/v2/oauth"
        
        # Правильные заголовки для OAuth 2.0
        headers = {
            'Content-Type': 'application/x-www-form-urlencoded',
            'Accept': 'application/json',
            'RqUID': str(uuid.uuid4()),  # Уникальный ID для каждого запроса
        }
        
        # ПРАВИЛЬНЫЕ данные для OAuth 2.0 Client Credentials
        payload = {
            'scope': self.scope,
            'grant_type': 'client_credentials',
            'client_id': self.client_id,
            'client_secret': self.client_secret
        }
        
        try:
            logger.info("🔑 Запрашиваю новый токен GigaChat...")
            
            # ВАЖНО: отключаем SSL проверку для этого endpoint
            async with httpx.AsyncClient(timeout=30.0, verify=False) as client:
                response = await client.post(url, headers=headers, data=payload)
                
                if response.status_code == 200:
                    data = response.json()
                    self.access_token = data.get('access_token')
                    expires_in = data.get('expires_in', 1800)  # 30 минут по умолчанию
                    
                    self.token_expiry = time.time() + expires_in
                    
                    logger.info(f"✅ GigaChat: получен новый access token (действует {expires_in//60} мин)")
                    return self.access_token
                else:
                    error_msg = response.text[:200]
                    logger.error(f"❌ GigaChat auth ошибка {response.status_code}: {error_msg}")
                    
                    # Детальный лог для отладки
                    logger.debug(f"   Request URL: {url}")
                    logger.debug(f"   Client ID: {self.client_id[:8]}...")
                    logger.debug(f"   Client Secret: {'*' * len(self.client_secret) if self.client_secret else 'NOT SET'}")
                    logger.debug(f"   Full response: {response.text}")
                    return None
                    
        except httpx.TimeoutException:
            logger.error("❌ GigaChat auth: таймаут запроса")
            return None
        except Exception as e:
            logger.error(f"❌ Ошибка получения токена GigaChat: {str(e)[:100]}")
            return None

# ==================== ОСНОВНОЙ NLP КЛАСС ====================
class NlpEngine:
    """Гибридный ИИ-движок с поддержкой GigaChat и OpenRouter"""
    
    def __init__(self):
        logger.info("🔧 Инициализация гибридного NLP-движка...")
        
        # ========== ИНИЦИАЛИЗАЦИЯ GIGACHAT OAUTH (ИСПРАВЛЕННО) ==========
        gigachat_client_id = os.getenv('GIGACHAT_CLIENT_ID')
        gigachat_client_secret = os.getenv('GIGACHAT_CLIENT_SECRET')  # Теперь нужен и секрет!
        gigachat_scope = os.getenv('GIGACHAT_SCOPE', 'GIGACHAT_API_PERS')
        
        # Инициализируем только если есть Client ID И Client Secret
        self.gigachat_auth = None
        if gigachat_client_id and gigachat_client_secret:
            self.gigachat_auth = GigaChatAuth(gigachat_client_id, gigachat_client_secret, gigachat_scope)
            logger.info(f"🔑 GigaChat OAuth настроен (Client ID: {gigachat_client_id[:8]}...)")
        else:
            missing = []
            if not gigachat_client_id:
                missing.append("GIGACHAT_CLIENT_ID")
            if not gigachat_client_secret:
                missing.append("GIGACHAT_CLIENT_SECRET")
            logger.warning(f"⚠️ GigaChat отключен: отсутствуют {', '.join(missing)}")
        
        # ========== КОНФИГУРАЦИЯ ПРОВАЙДЕРОВ ==========
        self.providers = {
            'gigachat': {
                'url': 'https://gigachat.devices.sberbank.ru/api/v1/chat/completions',
                'client_id': gigachat_client_id,
                'client_secret': gigachat_client_secret,
                'scope': gigachat_scope,
                'models': ['GigaChat', 'GigaChat-Pro'],
                'headers': {},  # Заполняются динамически с токеном
                'enabled': bool(gigachat_client_id and gigachat_client_secret),
                'priority': 1,  # Высший приоритет
                'auth': self.gigachat_auth  # Ссылка на объект авторизации
            },
            'openrouter': {
                'url': 'https://openrouter.ai/api/v1/chat/completions',
                'token': os.getenv('OPENROUTER_API_TOKEN'),
                'models': [
                    'google/gemini-2.0-flash-exp:free',
                    'mistralai/mistral-7b-instruct:free',
                    'deepseek/deepseek-chat:free'
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
        
        # Сортируем провайдеры по приоритету (только включенные)
        self.provider_priority = sorted(
            [p for p in self.providers.keys() if self.providers[p]['enabled']],
            key=lambda x: self.providers[x]['priority']
        )
        
        if not self.provider_priority:
            logger.warning("⚠️ Ни один ИИ-провайдер не настроен, будет использоваться только SimpleAnalyzer")
        
        # Индексы для переключения моделей
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
        logger.info(f"📊 Доступные провайдеры: {', '.join(self.provider_priority) if self.provider_priority else 'НЕТ (только SimpleAnalyzer)'}")
    
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
            system_prompt = """Ты — финансовый аналитик. Анализируй новости российского рынка акций.
            ВОЗВРАЩАЙ ТОЛЬКО JSON БЕЗ ЛЮБЫХ ДОПОЛНИТЕЛЬНЫХ ТЕКСТОВ, КОММЕНТАРИЕВ ИЛИ ОБЪЯСНЕНИЙ!
            
            Требуемый JSON формат:
            {
                "analysis": {
                    "tickers": ["SBER", "GAZP"],
                    "event_type": "earnings_report|dividend|merger_acquisition|regulatory|geopolitical|market_update|corporate_action|other",
                    "impact_score": 1-10,
                    "relevance_score": 1-100,
                    "sentiment": "positive|negative|neutral|mixed",
                    "horizon": "immediate|short_term|medium_term|long_term",
                    "summary": "краткая суть на русском (2-3 предложения)"
                }
            }
            
            Пример правильного ответа:
            {"analysis": {"tickers": ["SBER"], "event_type": "market_update", "impact_score": 5, "relevance_score": 60, "sentiment": "neutral", "horizon": "short_term", "summary": "Новость о банковском секторе"}}
            
            ТОЛЬКО JSON, НИЧЕГО БОЛЬШЕ!"""
            
        else:  # openrouter - УСИЛЕННЫЙ ПРОМПТ
            system_prompt = """You are a financial analysis AI. You MUST return ONLY valid JSON, no other text.

            CRITICAL INSTRUCTIONS:
            1. You MUST output ONLY valid JSON
            2. No explanations, no markdown, no code blocks
            3. If you can't analyze, return: {"analysis": {"tickers": [], "error": "no_analysis"}}
            
            REQUIRED JSON STRUCTURE:
            {
                "analysis": {
                    "tickers": ["SBER", "GAZP"],
                    "event_type": "earnings_report|dividend|merger_acquisition|regulatory|geopolitical|market_update|corporate_action|other",
                    "impact_score": 1-10,
                    "relevance_score": 1-100,
                    "sentiment": "positive|negative|neutral|mixed",
                    "horizon": "immediate|short_term|medium_term|long_term",
                    "summary": "brief summary in Russian"
                }
            }
            
            EXAMPLE CORRECT RESPONSE:
            {"analysis": {"tickers": ["SBER"], "event_type": "market_update", "impact_score": 5, "relevance_score": 60, "sentiment": "neutral", "horizon": "short_term", "summary": "Новость о банковском секторе"}}
            
            ONLY JSON OUTPUT! NO OTHER TEXT!"""
        
        # Выбираем модель
        model_idx = self.model_indices[provider]
        models = self.providers[provider]['models']
        model = models[model_idx % len(models)]
        
        prompt_data = {
            "model": model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"Источник: {source}\nЗаголовок: {title}\nТекст: {content[:1200]}"}
            ],
            "temperature": 0.1,
            "max_tokens": 600
        }
        
        # Добавляем response_format для OpenAI-совместимых API
        if provider == 'openrouter':
            prompt_data["response_format"] = {"type": "json_object"}
        
        return prompt_data
    
    def _switch_to_next_model(self, provider: str):
        """Переключение на следующую модель у провайдера"""
        models = self.providers[provider]['models']
        if len(models) > 1:
            old_idx = self.model_indices[provider]
            self.model_indices[provider] = (old_idx + 1) % len(models)
            old_model = models[old_idx]
            new_model = models[self.model_indices[provider]]
            logger.info(f"🔄 {provider}: смена модели {old_model} → {new_model}")
    
    async def _make_gigachat_request(self, prompt_data: Dict) -> Optional[Dict]:
        """Специальный метод для запроса к GigaChat с OAuth"""
        if not self.gigachat_auth:
            return None
        
        # Получаем токен
        access_token = await self.gigachat_auth.get_access_token()
        if not access_token:
            return None
        
        url = "https://gigachat.devices.sberbank.ru/api/v1/chat/completions"
        
        headers = {
            'Authorization': f'Bearer {access_token}',
            'Content-Type': 'application/json'
        }
        
        try:
            async with httpx.AsyncClient(timeout=30.0, verify=False) as client:
                response = await client.post(url, headers=headers, json=prompt_data)
                
                if response.status_code == 200:
                    return response.json()
                elif response.status_code == 401:
                    logger.warning("⚠️ GigaChat токен истёк, обновляю...")
                    self.gigachat_auth.access_token = None  # Сбрасываем токен
                    # Попробуем получить новый токен и повторить запрос
                    new_token = await self.gigachat_auth.get_access_token()
                    if new_token:
                        return await self._make_gigachat_request(prompt_data)
                    return None
                elif response.status_code == 429:
                    logger.warning("⏳ GigaChat: rate limit, жду 5 секунд...")
                    await asyncio.sleep(5)
                    return None
                else:
                    logger.error(f"❌ GigaChat API ошибка {response.status_code}: {response.text[:200]}")
                    return None
                    
        except httpx.TimeoutException:
            logger.error("⏰ GigaChat: таймаут запроса")
            return None
        except Exception as e:
            logger.error(f"❌ Ошибка запроса к GigaChat: {str(e)[:100]}")
            return None
    
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
        
        # Если нет провайдеров
        if not self.provider_priority:
            logger.info("ℹ️ Нет доступных ИИ-провайдеров, использую только SimpleAnalyzer")
            return None
        
        # Пробуем провайдеры по приоритету
        for provider in self.provider_priority:
            if not self.providers[provider]['enabled']:
                continue
            
            logger.info(f"📡 Пробую провайдер: {provider.upper()}")
            self.stats['by_provider'][provider]['requests'] += 1
            
            max_retries = min(2, len(self.providers[provider]['models']))
            
            for attempt in range(max_retries):
                try:
                    logger.info(f"   📨 Попытка {attempt+1}/{max_retries}")
                    
                    # Создаем запрос
                    prompt_data = self._create_prompt_for_provider(news_item, provider)
                    
                    # ОСОБАЯ ЛОГИКА ДЛЯ GIGACHAT
                    if provider == 'gigachat':
                        response_data = await self._make_gigachat_request(prompt_data)
                    else:
                        # OpenRouter - стандартный запрос
                        async with httpx.AsyncClient(timeout=30.0) as client:
                            response = await client.post(
                                url=self.providers[provider]['url'],
                                headers=self.providers[provider]['headers'],
                                json=prompt_data
                            )
                            response_data = response.json() if response.status_code == 200 else None
                    
                    if response_data:
                        ai_response = response_data.get("choices", [{}])[0].get("message", {}).get("content", "")
                        
                        if not ai_response:
                            logger.warning(f"   ⚠️ {provider}: пустой ответ")
                            continue
                        
                        # Парсинг JSON
                        analysis_result = self._parse_ai_response(ai_response, news_item, provider)
                        
                        if analysis_result:
                            self.stats['successful_requests'] += 1
                            self.stats['by_provider'][provider]['success'] += 1
                            
                            # Кэшируем
                            self.analysis_cache[cache_key] = analysis_result
                            if len(self.analysis_cache) > 100:
                                oldest = next(iter(self.analysis_cache))
                                del self.analysis_cache[oldest]
                            
                            logger.info(f"   ✅ {provider}: успешный анализ")
                            return analysis_result
                        else:
                            logger.warning(f"   ⚠️ {provider}: не удалось распарсить ответ")
                    
                    elif attempt < max_retries - 1:
                        self._switch_to_next_model(provider)
                        await asyncio.sleep(1)
                        continue
                        
                except httpx.TimeoutException:
                    logger.error(f"   ⏰ {provider}: таймаут")
                    if attempt < max_retries - 1:
                        self._switch_to_next_model(provider)
                        await asyncio.sleep(2)
                        continue
                    break
                    
                except Exception as e:
                    logger.error(f"   ❌ {provider}: ошибка - {str(e)[:100]}")
                    if attempt < max_retries - 1:
                        self._switch_to_next_model(provider)
                        await asyncio.sleep(1)
                        continue
                    break
            
            await asyncio.sleep(0.5)  # Пауза между провайдерами
        
        logger.info("ℹ️ Все ИИ-провайдеры недоступны, вернусь к SimpleAnalyzer")
        return None
    
    def _parse_ai_response(self, response: str, news_item: Dict, provider: str) -> Optional[Dict]:
        """Парсинг ответа ИИ (УСИЛЕННЫЙ)"""
        try:
            # Очистка ответа
            response = response.strip()
            
            # Детальный лог для отладки
            logger.debug(f"📨 {provider} raw response (first 500 chars): {response[:500]}")
            
            # Попытка 1: Найти JSON в ответе
            json_patterns = [
                r'\{.*\}',  # Любой JSON объект
                r'\{"analysis".*\}',  # Начинается с "analysis"
                r'```json\s*(.*?)\s*```',  # JSON в code block
                r'```\s*(.*?)\s*```'  # Любой code block
            ]
            
            json_str = None
            for pattern in json_patterns:
                match = re.search(pattern, response, re.DOTALL)
                if match:
                    json_str = match.group(1) if len(match.groups()) > 0 else match.group(0)
                    break
            
            # Если не нашли паттерн, пробуем взять весь ответ
            if not json_str:
                json_str = response
            
            # Убираем возможные остатки
            json_str = json_str.strip()
            if json_str.startswith('```'):
                json_str = json_str[3:]
            if json_str.endswith('```'):
                json_str = json_str[:-3]
            
            # Парсим JSON
            logger.debug(f"📨 {provider} parsing JSON: {json_str[:200]}...")
            data = json.loads(json_str)
            
            # Проверяем наличие analysis
            if 'analysis' not in data:
                logger.warning(f"   ⚠️ {provider}: нет ключа 'analysis' в JSON")
                return None
            
            analysis_data = data.get("analysis", {})
            
            # Если есть ошибка в анализе
            if 'error' in analysis_data:
                logger.info(f"   ℹ️ {provider}: анализ невозможен - {analysis_data.get('error')}")
                return None
            
            # Валидация
            required_fields = ['tickers', 'event_type', 'impact_score', 'relevance_score']
            if not all(field in analysis_data for field in required_fields):
                missing = [f for f in required_fields if f not in analysis_data]
                logger.warning(f"   ⚠️ {provider}: отсутствуют поля: {missing}")
                return None
            
            # Валидация значений
            if not isinstance(analysis_data.get('tickers', []), list):
                logger.warning(f"   ⚠️ {provider}: tickers не список")
                return None
            
            if not 1 <= analysis_data.get('impact_score', 0) <= 10:
                logger.warning(f"   ⚠️ {provider}: невалидный impact_score {analysis_data.get('impact_score')}")
                return None
            
            if not 1 <= analysis_data.get('relevance_score', 0) <= 100:
                logger.warning(f"   ⚠️ {provider}: невалидный relevance_score {analysis_data.get('relevance_score')}")
                return None
            
            # Создаем результат
            result = {
                'news_id': news_item.get('id', ''),
                'news_title': news_item.get('title', ''),
                'news_source': news_item.get('source', ''),
                'news_url': news_item.get('url', ''),
                'analysis_timestamp': datetime.now().isoformat(),
                
                'tickers': analysis_data.get('tickers', []),
                'event_type': analysis_data.get('event_type', 'other'),
                'impact_score': int(analysis_data.get('impact_score', 1)),
                'relevance_score': int(analysis_data.get('relevance_score', 30)),
                'sentiment': analysis_data.get('sentiment', 'neutral'),
                'horizon': analysis_data.get('horizon', 'short_term'),
                'summary': analysis_data.get('summary', ''),
                
                'ai_provider': provider,
                'ai_model': self.providers[provider]['models'][self.model_indices[provider]],
                'confidence': min(1.0, analysis_data.get('relevance_score', 30) / 100.0)
            }
            
            # Логируем успех
            tickers_str = ', '.join(result['tickers']) if result['tickers'] else 'НЕТ ТИКЕРОВ'
            logger.info(f"   ✅ {provider}: успешный анализ! Тикеры: {tickers_str} | Impact: {result['impact_score']}/10 | Relevance: {result['relevance_score']}/100")
            
            return result
            
        except json.JSONDecodeError as e:
            logger.error(f"   ❌ {provider}: невалидный JSON - {str(e)[:50]}")
            logger.debug(f"   💬 Ответ был: {response[:300]}")
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
            'providers': provider_stats,
            'cache_size': len(self.analysis_cache)
        }
