import logging
import json
import os
import asyncio
import httpx
import time
from datetime import datetime
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

# ==================== GIGACHAT OAUTH 2.0 КЛАСС ====================
class GigaChatAuth:
    """Класс для авторизации в GigaChat API через Client ID (OAuth 2.0)"""
    
    def __init__(self, client_id: str, scope: str = "GIGACHAT_API_PERS"):
        self.client_id = client_id
        self.scope = scope
        self.access_token = None
        self.token_expiry = 0
        
    async def get_access_token(self) -> Optional[str]:
        """Получение access token через OAuth 2.0"""
        # Если токен ещё действителен (с запасом 60 секунд)
        if self.access_token and time.time() < self.token_expiry - 60:
            return self.access_token
        
        url = "https://ngw.devices.sberbank.ru:9443/api/v2/oauth"
        
        headers = {
            'Content-Type': 'application/x-www-form-urlencoded',
            'Accept': 'application/json',
            'RqUID': '6f0b1291-c7f3-434c-9a4c-8344d4f34364',  # Уникальный ID запроса
            'Authorization': f'Basic {self.client_id}'
        }
        
        payload = {'scope': self.scope}
        
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
        
        # ========== ИНИЦИАЛИЗАЦИЯ GIGACHAT OAUTH ==========
        gigachat_client_id = os.getenv('GIGACHAT_CLIENT_ID')  # 019ac4e1-9416-7c5b-8722-fd5b09d85848
        gigachat_scope = os.getenv('GIGACHAT_SCOPE', 'GIGACHAT_API_PERS')
        
        # Инициализируем только если есть Client ID
        self.gigachat_auth = None
        if gigachat_client_id:
            self.gigachat_auth = GigaChatAuth(gigachat_client_id, gigachat_scope)
            logger.info(f"🔑 GigaChat OAuth настроен (Client ID: {gigachat_client_id[:8]}...)")
        else:
            logger.warning("⚠️ GIGACHAT_CLIENT_ID не найден, GigaChat отключен")
        
        # ========== КОНФИГУРАЦИЯ ПРОВАЙДЕРОВ ==========
        self.providers = {
            'gigachat': {
                'url': 'https://gigachat.devices.sberbank.ru/api/v1/chat/completions',
                'client_id': gigachat_client_id,
                'scope': gigachat_scope,
                'models': ['GigaChat', 'GigaChat-Pro'],
                'headers': {},  # Заполняются динамически с токеном
                'enabled': bool(gigachat_client_id),
                'priority': 1,  # Высший приоритет
                'auth': self.gigachat_auth  # Ссылка на объект авторизации
            },
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
        
        # Сортируем провайдеры по приоритету (только включенные)
        self.provider_priority = sorted(
            [p for p in self.providers.keys() if self.providers[p]['enabled']],
            key=lambda x: self.providers[x]['priority']
        )
        
        if not self.provider_priority:
            logger.warning("⚠️ Ни один ИИ-провайдер не настроен")
        
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
            1. Учитывай общие рыночные условия.
            2. Обращай внимание на время публикации.
            3. Различай факты и мнения/прогнозы.
            
            ИНСТРУКЦИИ:
            1. Найди ВСЕ упоминания российских компаний и их тикеров (Сбербанк → SBER, Газпром → GAZP, Лукойл → LKOH, Яндекс → YNDX, Мосбиржа → MOEX)
            2. Определи тип события: earnings_report, dividend, merger_acquisition, regulatory, geopolitical, market_update, corporate_action, other
            3. Оцени важность (impact_score): 1-10
            4. Оцени релевантность для трейдинга (relevance_score): 1-100
            5. Определи тональность: positive, negative, neutral, mixed
            6. Определи горизонт влияния: immediate, short_term, medium_term, long_term
            7. Кратко объясни суть (2-3 предложения на русском)
            
            ВОЗВРАЩАЙ ТОЛЬКО JSON:
            {
                "analysis": {
                    "tickers": ["TICKER1", "TICKER2"],
                    "event_type": "тип_события",
                    "impact_score": число,
                    "relevance_score": число,
                    "sentiment": "тональность",
                    "horizon": "горизонт",
                    "summary": "краткая суть"
                }
            }
            
            ТОЛЬКО JSON, БЕЗ ДОПОЛНИТЕЛЬНОГО ТЕКСТА!"""
            
        else:  # openrouter
            system_prompt = """You are a financial analyst AI. Analyze news and return strictly in JSON format.
            
            IMPORTANT: Find Russian stock tickers (Sberbank → SBER, Gazprom → GAZP, Lukoil → LKOH, Yandex → YNDX, Moscow Exchange → MOEX)
            
            ANALYSIS INSTRUCTIONS:
            1. Extract all company mentions and their tickers
            2. Determine event type: earnings_report, dividend, merger_acquisition, regulatory, geopolitical, market_update, corporate_action, other
            3. Rate importance (impact_score): 1-10
            4. Rate relevance for trading (relevance_score): 1-100
            5. Determine sentiment: positive, negative, neutral, mixed
            6. Determine impact horizon: immediate, short_term, medium_term, long_term
            7. Provide brief summary
            
            RETURN ONLY JSON:
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
        
        # Выбираем модель
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
                    self.gigachat_auth.access_token = None
                    return await self._make_gigachat_request(prompt_data)
                else:
                    logger.error(f"❌ GigaChat API ошибка: {response.status_code}")
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
            logger.warning("⚠️ Нет доступных ИИ-провайдеров")
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
                    break
            
            await asyncio.sleep(0.5)
        
        logger.error("❌ Все провайдеры недоступны для анализа новости")
        return None
    
    def _parse_ai_response(self, response: str, news_item: Dict, provider: str) -> Optional[Dict]:
        """Парсинг ответа ИИ"""
        try:
            # Очистка ответа
            response = response.strip()
            
            # Удаляем markdown
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
            
            # Валидация
            required_fields = ['tickers', 'event_type', 'impact_score', 'relevance_score']
            if not all(field in analysis_data for field in required_fields):
                logger.warning(f"   ⚠️ {provider}: отсутствуют обязательные поля")
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
            
            # Логируем
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
