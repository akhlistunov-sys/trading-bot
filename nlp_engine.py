# nlp_engine.py - ПОЛНЫЙ РАБОЧИЙ ФАЙЛ С BASE64 FIX
import logging
import json
import os
import asyncio
import httpx
import time
import uuid
import base64
import ssl
import certifi
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

# ==================== GIGACHAT OAUTH 2.0 ====================
class GigaChatAuth:
    """Класс для авторизации в GigaChat API через OAuth 2.0 Basic auth"""
    
    def __init__(self, client_id: str, client_secret: str, scope: str = "GIGACHAT_API_PERS"):
        self.client_id = client_id
        self.client_secret = client_secret
        self.scope = scope
        self.access_token = None
        self.token_expiry = 0
        
    def _create_ssl_context(self, strategy: str = "auto") -> ssl.SSLContext:
        """Создание SSL контекста для Render"""
        
        ssl_context = ssl.create_default_context()
        
        if strategy == "combined_cert":
            combined_cert = Path("certs/combined_ca.crt")
            if combined_cert.exists():
                ssl_context.load_verify_locations(cafile=str(combined_cert))
                logger.debug("✅ SSL: Использую объединённый сертификат")
                return ssl_context
        
        if strategy == "sber_cert":
            sber_cert = Path("certs/sber_root.crt")
            if sber_cert.exists():
                ssl_context.load_verify_locations(cafile=str(sber_cert))
                logger.debug("✅ SSL: Использую сертификат Sber")
                return ssl_context
        
        ssl_context.load_verify_locations(cafile=certifi.where())
        logger.debug("✅ SSL: Использую certifi")
        return ssl_context
    
    async def get_access_token(self) -> Optional[str]:
        """Получение access token через OAuth 2.0 Basic auth"""
        if self.access_token and time.time() < self.token_expiry - 60:
            return self.access_token
        
        url = "https://ngw.devices.sberbank.ru:9443/api/v2/oauth"
        
        # ОБРАБОТКА BASE64 СЕКРЕТА
        client_id = self.client_id
        client_secret = self.client_secret
        
        # Если secret в base64 (начинается с MDE5)
        if client_secret and client_secret.startswith('MDE5'):
            try:
                decoded = base64.b64decode(client_secret).decode('utf-8')
                if ':' in decoded:
                    parts = decoded.split(':', 1)
                    if len(parts) == 2:
                        client_id = parts[0]
                        client_secret = parts[1]
                        logger.info(f"🔑 Извлечено из base64: Client ID={client_id[:8]}..., Secret={client_secret[:8]}...")
            except Exception as e:
                logger.error(f"❌ Ошибка декодирования base64 secret: {e}")
                return None
        
        # Base64 кодирование client_id:client_secret
        auth_string = f"{client_id}:{client_secret}"
        auth_base64 = base64.b64encode(auth_string.encode()).decode()
        
        rquid = str(uuid.uuid4())
        
        headers = {
            'Content-Type': 'application/x-www-form-urlencoded',
            'Accept': 'application/json',
            'RqUID': rquid,
            'Authorization': f'Basic {auth_base64}'
        }
        
        payload = {'scope': self.scope}
        
        # ВСЕ SSL СТРАТЕГИИ
        ssl_strategies = ["combined_cert", "sber_cert", "certifi", "insecure"]
        
        for strategy in ssl_strategies:
            try:
                logger.info(f"🔑 Запрашиваю токен GigaChat (RqUID: {rquid[:8]}, SSL: {strategy})")
                
                if strategy == "insecure":
                    ssl_context = ssl.create_default_context()
                    ssl_context.check_hostname = False
                    ssl_context.verify_mode = ssl.CERT_NONE
                    verify = False
                else:
                    ssl_context = self._create_ssl_context(strategy)
                    verify = ssl_context
                
                async with httpx.AsyncClient(timeout=30.0, verify=verify) as client:
                    response = await client.post(url, headers=headers, data=payload)
                    
                    if response.status == 200:
                        data = response.json()
                        self.access_token = data.get('access_token')
                        expires_at = data.get('expires_at', 0)
                        
                        if expires_at > 1000000000000:
                            self.token_expiry = expires_at / 1000
                        else:
                            self.token_expiry = time.time() + 1800
                        
                        logger.info(f"✅ GigaChat: токен получен (действует 30 минут)")
                        return self.access_token
                    elif response.status_code == 401:
                        logger.error(f"❌ Ошибка авторизации: {response.text[:100]}")
                        return None
                    else:
                        logger.debug(f"⚠️ SSL стратегия {strategy} не сработала: {response.status_code}")
                        continue
                        
            except Exception as e:
                logger.debug(f"⚠️ SSL стратегия {strategy} ошибка: {str(e)[:50]}")
                continue
        
        logger.error("❌ Все SSL стратегии не сработали для GigaChat")
        return None

# ==================== ОСНОВНОЙ NLP КЛАСС ====================
class NlpEngine:
    """Гибридный ИИ-движок с ротацией моделей OpenRouter"""
    
    def __init__(self):
        logger.info("🔧 Инициализация гибридного NLP-движка для Render...")
        
        self._setup_ssl_for_render()
        
        gigachat_client_id = os.getenv('GIGACHAT_CLIENT_ID')
        gigachat_client_secret = os.getenv('GIGACHAT_CLIENT_SECRET')
        gigachat_scope = os.getenv('GIGACHAT_SCOPE', 'GIGACHAT_API_PERS')
        
        self.gigachat_auth = None
        if gigachat_client_id and gigachat_client_secret:
            self.gigachat_auth = GigaChatAuth(gigachat_client_id, gigachat_client_secret, gigachat_scope)
            logger.info(f"🔑 GigaChat OAuth настроен (Client ID: {gigachat_client_id[:8]}...)")
        else:
            logger.warning("⚠️ GigaChat отключен: нет Client ID или Client Secret")
        
        # ВСЕ OpenRouter модели
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
        logger.info(f"🧠 OpenRouter модели: {len(self.openrouter_models)}")
    
    def _setup_ssl_for_render(self):
        """Настройка SSL сертификатов для облачного деплоя"""
        try:
            certs_dir = Path("certs")
            certs_dir.mkdir(exist_ok=True)
            
            sber_cert_path = certs_dir / "sber_root.crt"
            if not sber_cert_path.exists():
                try:
                    import requests
                    response = requests.get(
                        "https://storage.yandexcloud.net/cloud-certs/CA.pem",
                        timeout=10
                    )
                    if response.status_code == 200:
                        sber_cert_path.write_text(response.text)
                        logger.info("✅ Сертификат Sber скачан")
                except Exception as e:
                    logger.debug(f"⚠️ Не удалось скачать сертификат Sber: {e}")
            
            combined_cert = certs_dir / "combined_ca.crt"
            
            with open(combined_cert, "wb") as outfile:
                with open(certifi.where(), "rb") as certifi_file:
                    outfile.write(certifi_file.read())
                
                if sber_cert_path.exists():
                    with open(sber_cert_path, "rb") as sber_file:
                        outfile.write(b"\n")
                        outfile.write(sber_file.read())
            
            logger.info(f"✅ SSL настроен для Render: {combined_cert}")
            
        except Exception as e:
            logger.warning(f"⚠️ Ошибка настройки SSL для Render: {e}")
    
    def _create_prompt_for_provider(self, news_item: Dict, provider: str, model: str = None) -> Dict:
        """Создание промпта для финансового анализа"""
        
        title = news_item.get('title', '')[:200]
        description = news_item.get('description', '')
        content = news_item.get('content', '') or description[:300]
        
        if provider == 'gigachat':
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
                "model": "GigaChat-2",
                "messages": [{"role": "user", "content": prompt_text}],
                "temperature": 0.1,
                "max_tokens": 500,
                "stream": False
            }
        else:
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
    
    def _create_ssl_context_for_request(self) -> ssl.SSLContext:
        """Создание SSL контекста для запросов"""
        try:
            combined_cert = Path("certs/combined_ca.crt")
            if combined_cert.exists():
                ssl_context = ssl.create_default_context()
                ssl_context.load_verify_locations(cafile=str(combined_cert))
                return ssl_context
        except:
            pass
        
        ssl_context = ssl.create_default_context()
        ssl_context.load_verify_locations(cafile=certifi.where())
        return ssl_context
    
    async def _make_gigachat_request(self, prompt_data: Dict) -> Optional[Dict]:
        """Запрос к GigaChat API"""
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
            'X-Request-ID': str(uuid.uuid4())
        }
        
        try:
            ssl_context = self._create_ssl_context_for_request()
            
            async with httpx.AsyncClient(timeout=30.0, verify=ssl_context) as client:
                response = await client.post(url, headers=headers, json=prompt_data)
                
                if response.status == 200:
                    return response.json()
                elif response.status == 401:
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
                
                if response.status == 200:
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
        cache_key = f"{news_item.get('source', '')}_{news_item.get('title', '')[:50]}".lower().replace(' ', '_')
        
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
                
                await asyncio.sleep(0.5)
        
        logger.info("ℹ️ Все ИИ-провайдеры недоступны или не нашли финансового содержания")
        return None
    
    def _parse_ai_response(self, response: str, news_item: Dict, provider: str) -> Optional[Dict]:
        """Парсинг ответа ИИ в структурированный анализ"""
        try:
            response = response.strip()
            
            start = response.find('{')
            end = response.rfind('}') + 1
            
            if start == -1 or end == 0:
                return None
            
            json_str = response[start:end]
            data = json.loads(json_str)
            
            tickers = data.get('tickers', [])
            if not isinstance(tickers, list):
                tickers = []
            
            valid_tickers = []
            for ticker in tickers:
                if isinstance(ticker, str) and 2 <= len(ticker) <= 5 and ticker.isalpha():
                    valid_tickers.append(ticker.upper())
            
            reason = data.get('reason', '').lower()
            if not valid_tickers or 'no financial' in reason:
                return None
            
            event_type = data.get('event_type', 'market_update')
            sentiment = data.get('sentiment', 'neutral')
            impact_score = min(10, max(1, int(data.get('impact_score', 5))))
            
            confidence = 0.7
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
    
    def get_current_provider(self) -> str:
        """Получение текущего активного провайдера"""
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
