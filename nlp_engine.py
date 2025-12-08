# nlp_engine.py - ПОЛНОСТЬЮ ИСПРАВЛЕННАЯ ВЕРСИЯ
import logging
import json
import os
import asyncio
import httpx
import time
import uuid
import base64
import ssl
from datetime import datetime
from typing import Dict, List, Optional
import certifi

logger = logging.getLogger(__name__)

# ==================== GIGACHAT OAUTH 2.0 (ИСПРАВЛЕННЫЙ) ====================
class GigaChatAuth:
    """Класс для авторизации в GigaChat API через OAuth 2.0 Basic auth"""
    
    def __init__(self, client_id: str, client_secret: str, scope: str = "GIGACHAT_API_PERS"):
        self.client_id = client_id
        self.client_secret = client_secret
        self.scope = scope
        self.access_token = None
        self.token_expiry = 0
        
        # Base64 кодирование client_id:client_secret
        auth_string = f"{self.client_id}:{self.client_secret}"
        self.auth_base64 = base64.b64encode(auth_string.encode()).decode()
        
    async def get_access_token(self) -> Optional[str]:
        """Получение access token через OAuth 2.0 Basic auth"""
        if self.access_token and time.time() < self.token_expiry - 60:
            return self.access_token
        
        url = "https://ngw.devices.sberbank.ru:9443/api/v2/oauth"
        
        # ОБЯЗАТЕЛЬНЫЙ RqUID (uuid4)
        rquid = str(uuid.uuid4())
        
        headers = {
            'Content-Type': 'application/x-www-form-urlencoded',
            'Accept': 'application/json',
            'RqUID': rquid,  # ОБЯЗАТЕЛЬНЫЙ ЗАГОЛОВОК
            'Authorization': f'Basic {self.auth_base64}'
        }
        
        payload = {
            'scope': self.scope
        }
        
        try:
            logger.info(f"🔑 Запрашиваю токен GigaChat (RqUID: {rquid[:8]}...)")
            
            # Создаем SSL контекст с сертификатом Sber
            ssl_context = ssl.create_default_context()
            
            # Пробуем загрузить сертификат Sber
            cert_paths = [
                'sber_root.crt',
                '/etc/ssl/certs/sberbank-root-ca.pem',
                '/usr/local/share/ca-certificates/sberbank.crt'
            ]
            
            cert_loaded = False
            for cert_path in cert_paths:
                if os.path.exists(cert_path):
                    try:
                        ssl_context.load_verify_locations(cafile=cert_path)
                        logger.info(f"✅ Загружен сертификат Sber: {cert_path}")
                        cert_loaded = True
                        break
                    except Exception as e:
                        logger.debug(f"⚠️ Не удалось загрузить сертификат {cert_path}: {e}")
            
            # Если сертификат не найден, используем системные
            if not cert_loaded:
                ssl_context.load_verify_locations(cafile=certifi.where())
                logger.info("⚠️ Использую системные сертификаты")
            
            async with httpx.AsyncClient(
                timeout=30.0,
                verify=ssl_context  # ПРАВИЛЬНЫЙ SSL КОНТЕКСТ
            ) as client:
                response = await client.post(url, headers=headers, data=payload)
                
                if response.status_code == 200:
                    data = response.json()
                    self.access_token = data.get('access_token')
                    expires_at = data.get('expires_at', 0)
                    
                    # expires_at в миллисекундах, конвертируем в секунды
                    if expires_at > 1000000000000:  # Если в миллисекундах
                        self.token_expiry = expires_at / 1000
                    else:
                        self.token_expiry = time.time() + 1800  # 30 минут по умолчанию
                    
                    logger.info(f"✅ GigaChat: получен токен (действует до: {datetime.fromtimestamp(self.token_expiry).strftime('%H:%M:%S')})")
                    return self.access_token
                else:
                    logger.error(f"❌ GigaChat auth ошибка {response.status_code}: {response.text[:100]}")
                    return None
                    
        except Exception as e:
            logger.error(f"❌ Ошибка получения токена GigaChat: {str(e)[:100]}")
            return None

# ==================== ОСНОВНОЙ NLP КЛАСС (С РОТАЦИЕЙ МОДЕЛЕЙ) ====================
class NlpEngine:
    """Гибридный ИИ-движок с ротацией моделей OpenRouter"""
    
    def __init__(self):
        logger.info("🔧 Инициализация гибридного NLP-движка...")
        
        gigachat_client_id = os.getenv('GIGACHAT_CLIENT_ID')
        gigachat_client_secret = os.getenv('GIGACHAT_CLIENT_SECRET')
        gigachat_scope = os.getenv('GIGACHAT_SCOPE', 'GIGACHAT_API_PERS')
        
        self.gigachat_auth = None
        if gigachat_client_id and gigachat_client_secret:
            self.gigachat_auth = GigaChatAuth(gigachat_client_id, gigachat_client_secret, gigachat_scope)
            logger.info(f"🔑 GigaChat OAuth настроен (Client ID: {gigachat_client_id[:8]}...)")
        else:
            logger.warning("⚠️ GigaChat отключен: нет Client ID или Client Secret")
        
        # Ротация моделей OpenRouter (бесплатные)
        self.openrouter_models = [
            'google/gemini-2.0-flash:free',
            'mistralai/mistral-7b-instruct:free',
            'meta-llama/llama-3.2-3b-instruct:free',
            'huggingfaceh4/zephyr-7b-beta:free'
        ]
        
        self.providers = {
            'gigachat': {
                'url': 'https://gigachat.devices.sberbank.ru/api/v1/chat/completions',
                'enabled': bool(gigachat_client_id and gigachat_client_secret),
                'priority': 1,
                'auth': self.gigachat_auth
            },
            'openrouter': {
                'url': 'https://openrouter.ai/api/v1/chat/completions',
                'token': os.getenv('OPENROUTER_API_TOKEN'),
                'enabled': bool(os.getenv('OPENROUTER_API_TOKEN')),
                'priority': 2,
                'models': self.openrouter_models
            }
        }
        
        self.provider_priority = sorted(
            [p for p in self.providers.keys() if self.providers[p]['enabled']],
            key=lambda x: self.providers[x]['priority']
        )
        
        self.analysis_cache = {}
        
        self.stats = {
            'total_requests': 0,
            'successful_requests': 0,
            'by_provider': {p: {'requests': 0, 'success': 0} for p in self.provider_priority},
            'cache_hits': 0,
            'cache_misses': 0
        }
        
        logger.info(f"🤖 Гибридный NLP-движок инициализирован")
        logger.info(f"📊 Доступные провайдеры: {', '.join(self.provider_priority)}")
        logger.info(f"🧠 OpenRouter модели: {len(self.openrouter_models)} бесплатных")
    
    # ==================== ОСНОВНЫЕ МЕТОДЫ ====================
    
    def _create_prompt_for_provider(self, news_item: Dict, provider: str, model: str = None) -> Dict:
        """Создание промпта для финансового анализа"""
        
        title = news_item.get('title', '')[:200]
        description = news_item.get('description', '')
        content = news_item.get('content', '') or description[:300]
        
        if provider == 'gigachat':
            # Промпт для GigaChat (ИСПРАВЛЕННЫЙ - правильная модель)
            prompt_text = f"""Анализируй финансовую новость для трейдинга на российском рынке.

Новость: {title}

Задача:
1. Найди упоминания российских компаний и их биржевые тикеры MOEX (пример: Сбербанк -> SBER, Газпром -> GAZP).
2. Определи тип события: dividend (дивиденды), earnings_report (отчетность), merger (слияние), regulatory (регуляторные новости), market_update (общие новости).
3. Оцени тональность: positive, negative, neutral.
4. Оцени силу влияния на цену (1-10): 1=слабое, 10=сильное.
5. Краткое обоснование (1 предложение).

Верни ТОЛЬКО JSON в формате:
{{
    "tickers": ["SBER"],
    "event_type": "dividend",
    "sentiment": "positive",
    "impact_score": 7,
    "reason": "Совет директоров рекомендовал увеличение дивидендов"
}}

Если тикеров нет или новость не финансовая: {{"tickers": [], "reason": "No financial content"}}
Только JSON, никакого текста!"""
            
            return {
                "model": "GigaChat-2",  # ИСПРАВЛЕНО: правильное название модели
                "messages": [{"role": "user", "content": prompt_text}],
                "temperature": 0.1,
                "max_tokens": 500,
                "stream": False
            }
        else:
            # Промпт для OpenRouter (разные модели)
            system_prompt = """Ты финансовый аналитик. Анализируй новости российского рынка.
Верни ТОЛЬКО JSON в формате: 
{"tickers": ["SBER"], "event_type": "dividend", "sentiment": "positive", "impact_score": 7, "reason": "..."}
Если нет финансового содержания: {"tickers": [], "reason": "No financial content"}"""
            
            return {
                "model": model or 'google/gemini-2.0-flash:free',
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": f"Новость: {title}\n\n{content[:200]}"}
                ],
                "temperature": 0.1,
                "max_tokens": 400,
                "response_format": {"type": "json_object"}
            }
    
    async def _make_gigachat_request(self, prompt_data: Dict) -> Optional[Dict]:
        """Запрос к GigaChat API (ИСПРАВЛЕННЫЙ - правильный SSL)"""
        if not self.gigachat_auth:
            return None
        
        access_token = await self.gigachat_auth.get_access_token()
        if not access_token:
            return None
        
        url = "https://gigachat.devices.sberbank.ru/api/v1/chat/completions"
        
        headers = {
            'Authorization': f'Bearer {access_token}',
            'Content-Type': 'application/json',
            'Accept': 'application/json',
            'X-Request-ID': str(uuid.uuid4())  # Добавляем для логирования
        }
        
        try:
            # Создаем SSL контекст
            ssl_context = ssl.create_default_context()
            
            # Пробуем загрузить сертификат Sber
            cert_paths = [
                'sber_root.crt',
                '/etc/ssl/certs/sberbank-root-ca.pem'
            ]
            
            cert_loaded = False
            for cert_path in cert_paths:
                if os.path.exists(cert_path):
                    try:
                        ssl_context.load_verify_locations(cafile=cert_path)
                        cert_loaded = True
                        break
                    except:
                        pass
            
            # Если сертификат не найден, используем системные
            if not cert_loaded:
                ssl_context.load_verify_locations(cafile=certifi.where())
            
            async with httpx.AsyncClient(
                timeout=30.0,
                verify=ssl_context  # ПРАВИЛЬНЫЙ SSL КОНТЕКСТ
            ) as client:
                response = await client.post(url, headers=headers, json=prompt_data)
                
                if response.status_code == 200:
                    return response.json()
                elif response.status_code == 401:
                    logger.warning("⚠️ GigaChat токен истёк, обновляю...")
                    self.gigachat_auth.access_token = None
                    return None
                else:
                    logger.error(f"❌ GigaChat ошибка {response.status_code}: {response.text[:100]}")
                    return None
                    
        except Exception as e:
            logger.error(f"❌ Ошибка запроса к GigaChat: {str(e)[:100]}")
            return None
    
    async def _try_openrouter_model(self, model: str, news_item: Dict) -> Optional[Dict]:
        """Попытка запроса к конкретной модели OpenRouter"""
        try:
            prompt_data = self._create_prompt_for_provider(news_item, 'openrouter', model)
            
            headers = {
                "Authorization": f"Bearer {self.providers['openrouter']['token']}",
                "Content-Type": "application/json",
                "HTTP-Referer": "https://github.com"
            }
            
            async with httpx.AsyncClient(timeout=20.0) as client:
                response = await client.post(
                    url=self.providers['openrouter']['url'],
                    headers=headers,
                    json=prompt_data
                )
                
                if response.status_code == 200:
                    return response.json()
                else:
                    logger.debug(f"   ⚠️ OpenRouter {model}: {response.status_code}")
                    return None
                    
        except Exception as e:
            logger.debug(f"   ⚠️ OpenRouter {model} ошибка: {str(e)[:50]}")
            return None
    
    async def analyze_news(self, news_item: Dict) -> Optional[Dict]:
        """Анализ новости с ротацией провайдеров и моделей"""
        
        self.stats['total_requests'] += 1
        cache_key = self._create_cache_key(news_item)
        
        if cache_key in self.analysis_cache:
            self.stats['cache_hits'] += 1
            return self.analysis_cache[cache_key]
        
        self.stats['cache_misses'] += 1
        
        # 1. Пробуем GigaChat
        if 'gigachat' in self.provider_priority and self.providers['gigachat']['enabled']:
            logger.info("📡 Пробую провайдер: GIGACHAT")
            self.stats['by_provider']['gigachat']['requests'] += 1
            
            try:
                prompt_data = self._create_prompt_for_provider(news_item, 'gigachat')
                response_data = await self._make_gigachat_request(prompt_data)
                
                if response_data:
                    ai_response = response_data.get("choices", [{}])[0].get("message", {}).get("content", "")
                    
                    if ai_response:
                        analysis_result = self._parse_ai_response(ai_response, news_item, 'gigachat')
                        
                        if analysis_result:
                            self.stats['successful_requests'] += 1
                            self.stats['by_provider']['gigachat']['success'] += 1
                            self.analysis_cache[cache_key] = analysis_result
                            logger.info("   ✅ GigaChat: успешный анализ")
                            return analysis_result
            except Exception as e:
                logger.debug(f"   ⚠️ GigaChat ошибка: {str(e)[:50]}")
        
        # 2. Пробуем OpenRouter с ротацией моделей
        if 'openrouter' in self.provider_priority and self.providers['openrouter']['enabled']:
            logger.info("📡 Пробую провайдер: OPENROUTER")
            
            for model in self.openrouter_models:
                self.stats['by_provider']['openrouter']['requests'] += 1
                logger.debug(f"   Модель: {model}")
                
                response_data = await self._try_openrouter_model(model, news_item)
                
                if response_data:
                    ai_response = response_data.get("choices", [{}])[0].get("message", {}).get("content", "")
                    
                    if ai_response:
                        analysis_result = self._parse_ai_response(ai_response, news_item, 'openrouter')
                        
                        if analysis_result:
                            self.stats['successful_requests'] += 1
                            self.stats['by_provider']['openrouter']['success'] += 1
                            self.analysis_cache[cache_key] = analysis_result
                            logger.info(f"   ✅ OpenRouter ({model}): успешный анализ")
                            return analysis_result
                
                await asyncio.sleep(0.5)  # Пауза между запросами
        
        logger.info("ℹ️ Все ИИ-провайдеры недоступны или не нашли финансового содержания")
        return None
    
    def _parse_ai_response(self, response: str, news_item: Dict, provider: str) -> Optional[Dict]:
        """Парсинг ответа ИИ в структурированный анализ"""
        try:
            response = response.strip()
            
            # Ищем JSON в ответе
            start = response.find('{')
            end = response.rfind('}') + 1
            
            if start == -1 or end == 0:
                return None
            
            json_str = response[start:end]
            data = json.loads(json_str)
            
            tickers = data.get('tickers', [])
            if not isinstance(tickers, list):
                tickers = []
            
            # Фильтруем только валидные тикеры (3-5 букв, uppercase)
            valid_tickers = []
            for ticker in tickers:
                if isinstance(ticker, str) and 2 <= len(ticker) <= 5 and ticker.isalpha():
                    valid_tickers.append(ticker.upper())
            
            # Если нет тикеров или причина "No financial content" - пропускаем
            reason = data.get('reason', '').lower()
            if not valid_tickers or 'no financial' in reason:
                return None
            
            event_type = data.get('event_type', 'market_update')
            sentiment = data.get('sentiment', 'neutral')
            impact_score = min(10, max(1, int(data.get('impact_score', 5))))
            
            # Рассчитываем confidence на основе качества анализа
            confidence = 0.7  # базовый для ИИ
            if event_type != 'market_update':
                confidence += 0.1
            if sentiment != 'neutral':
                confidence += 0.1
            if impact_score >= 7:
                confidence += 0.1
            confidence = min(0.9, confidence)
            
            result = {
                'news_id': news_item.get('id', ''),
                'news_title': news_item.get('title', ''),
                'news_source': news_item.get('source', ''),
                'tickers': valid_tickers,
                'event_type': event_type,
                'impact_score': impact_score,
                'relevance_score': 70 if valid_tickers else 30,
                'sentiment': sentiment,
                'horizon': 'short_term',
                'summary': data.get('reason', f"Найдено {len(valid_tickers)} тикеров"),
                'confidence': confidence,
                'ai_provider': provider,
                'analysis_timestamp': datetime.now().isoformat(),
                'simple_analysis': False
            }
            
            logger.info(f"   📊 {provider}: {len(valid_tickers)} тикеров, {event_type}, {sentiment}")
            return result
            
        except Exception as e:
            logger.debug(f"   ⚠️ Ошибка парсинга ответа {provider}: {str(e)[:50]}")
            return None
    
    def _create_cache_key(self, news_item: Dict) -> str:
        title = news_item.get('title', '')[:50].replace(' ', '_').lower()
        source = news_item.get('source', '')[:20].replace(' ', '_').lower()
        return f"{source}_{title}"
    
    def get_current_provider(self) -> str:
        return self.provider_priority[0] if self.provider_priority else "none"
    
    def get_stats(self) -> Dict:
        success_rate = (self.stats['successful_requests'] / self.stats['total_requests'] * 100) if self.stats['total_requests'] > 0 else 0
        
        provider_stats = {}
        for provider in self.providers:
            req = self.stats['by_provider'].get(provider, {}).get('requests', 0)
            succ = self.stats['by_provider'].get(provider, {}).get('success', 0)
            rate = (succ / req * 100) if req > 0 else 0
            provider_stats[provider] = {
                'requests': req,
                'success': succ,
                'success_rate': round(rate, 1),
                'enabled': self.providers[provider]['enabled']
            }
        
        return {
            'total_requests': self.stats['total_requests'],
            'successful_requests': self.stats['successful_requests'],
            'success_rate': round(success_rate, 1),
            'cache_hits': self.stats['cache_hits'],
            'cache_misses': self.stats['cache_misses'],
            'current_provider': self.get_current_provider(),
            'openrouter_models': len(self.openrouter_models),
            'providers': provider_stats
        }
