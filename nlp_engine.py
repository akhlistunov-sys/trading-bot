# nlp_engine.py - ИСПРАВЛЕННЫЙ КОД (сохраняем финансовый анализ)
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
import re

logger = logging.getLogger(__name__)

# ==================== GIGACHAT OAUTH 2.0 ====================
class GigaChatAuth:
    """Класс для авторизации в GigaChat API"""
    
    def __init__(self, client_id: str, client_secret: str, scope: str = "GIGACHAT_API_PERS"):
        self.client_id = client_id
        self.client_secret = client_secret  # УЖЕ base64
        self.scope = scope
        self.access_token = None
        self.token_expiry = 0
        
    async def get_access_token(self) -> Optional[str]:
        """Получение access token"""
        
        if self.access_token and time.time() < self.token_expiry - 60:
            return self.access_token
        
        url = "https://ngw.devices.sberbank.ru:9443/api/v2/oauth"
        rquid = str(uuid.uuid4())
        
        # Убираем кавычки если есть
        client_secret_clean = self.client_secret
        if client_secret_clean.startswith('"') and client_secret_clean.endswith('"'):
            client_secret_clean = client_secret_clean[1:-1]
            logger.warning("⚠️ Убрал кавычки из client_secret")
        
        headers = {
            'Content-Type': 'application/x-www-form-urlencoded',
            'Accept': 'application/json',
            'RqUID': rquid,
            'Authorization': f'Basic {client_secret_clean}'  # УЖЕ base64!
        }
        
        data = {'scope': self.scope}
        
        try:
            async with httpx.AsyncClient(timeout=30.0, verify=False) as client:
                response = await client.post(url, headers=headers, data=data)
                
                if response.status_code == 200:
                    result = response.json()
                    self.access_token = result.get('access_token')
                    self.token_expiry = time.time() + 1800  # 30 минут
                    
                    logger.info(f"✅ GigaChat токен получен! (RqUID: {rquid[:8]})")
                    return self.access_token
                else:
                    logger.error(f"❌ GigaChat ошибка {response.status_code}: {response.text[:100]}")
                    return None
        except Exception as e:
            logger.error(f"❌ Ошибка запроса GigaChat: {str(e)[:100]}")
            return None

# ==================== ОСНОВНОЙ NLP КЛАСС ====================
class NlpEngine:
    """Гибридный ИИ-движок с УЛУЧШЕННЫМИ промптами"""
    
    def __init__(self):
        logger.info("🔧 Инициализация гибридного NLP-движка...")
        
        # Настраиваем SSL сертификаты для Render
        self._setup_ssl_for_render()
        
        gigachat_client_id = os.getenv('GIGACHAT_CLIENT_ID')
        gigachat_client_secret = os.getenv('GIGACHAT_CLIENT_SECRET')
        gigachat_scope = os.getenv('GIGACHAT_SCOPE', 'GIGACHAT_API_PERS')
        
        self.gigachat_auth = None
        if gigachat_client_id and gigachat_client_secret:
            # УБИРАЕМ КАВЫЧКИ если есть
            if gigachat_client_secret.startswith('"') and gigachat_client_secret.endswith('"'):
                gigachat_client_secret = gigachat_client_secret[1:-1]
                logger.warning("⚠️ Убрал кавычки из GIGACHAT_CLIENT_SECRET")
            
            self.gigachat_auth = GigaChatAuth(gigachat_client_id, gigachat_client_secret, gigachat_scope)
            logger.info(f"🔑 GigaChat OAuth настроен")
        else:
            logger.warning("⚠️ GigaChat отключен: нет Client ID или Client Secret")
        
        # СЕМАФОР для ограничения 1 одновременного запроса к GigaChat
        self.gigachat_semaphore = asyncio.Semaphore(1)
        
        # Ротация моделей OpenRouter (рабочие бесплатные)
        self.openrouter_models = [
            'google/gemini-2.0-flash:free',
            'mistralai/mistral-7b-instruct:free',
            'meta-llama/llama-3.2-3b-instruct:free'
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
            'cache_misses': 0,
            'gigachat_queue_waits': 0,
            'parsing_errors': 0,
            'no_financial_content': 0
        }
        
        logger.info(f"🤖 Гибридный NLP-движок инициализирован")
        logger.info(f"📊 Доступные провайдеры: {', '.join(self.provider_priority)}")
        logger.info(f"🔒 GigaChat семафор: 1 одновременный запрос")
    
    def _setup_ssl_for_render(self):
        """Настройка SSL сертификатов для облачного деплоя"""
        try:
            certs_dir = Path("certs")
            certs_dir.mkdir(exist_ok=True)
            
            combined_cert = certs_dir / "combined_ca.crt"
            
            with open(combined_cert, "wb") as outfile:
                with open(certifi.where(), "rb") as certifi_file:
                    outfile.write(certifi_file.read())
            
            logger.info(f"✅ SSL настроен для Render: {combined_cert}")
            
        except Exception as e:
            logger.warning(f"⚠️ Ошибка настройки SSL для Render: {e}")
    
    def _create_prompt_for_provider(self, news_item: Dict, provider: str, model: str = None) -> Dict:
        """Создание промпта для финансового анализа - УЛУЧШЕННЫЙ ДЛЯ МОЕКС"""
        
        title = news_item.get('title', '')[:200]
        description = news_item.get('description', '')
        content = news_item.get('content', '') or description[:300]
        
        # Определяем язык новости
        has_russian = any(char in title.lower() for char in 'абвгдеёжзийклмнопрстуфхцчшщъыьэюя')
        has_english = any(char in title.lower() for char in 'abcdefghijklmnopqrstuvwxyz')
        
        if provider == 'gigachat':
            if has_russian or (not has_english and not has_russian):
                # Русские новости - УЛУЧШЕННЫЙ ПРОМПТ
                prompt_text = f"""Ты финансовый аналитик MOEX. Проанализируй новость для торговли акциями.

Новость: {title}

ВАЖНО: Даже если новость короткая или общая — найди ВОЗМОЖНЫЕ тикеры MOEX.

Примеры:
- "Сбербанк" или "банки" → SBER
- "Газпром" или "нефтегаз" → GAZP
- "Рынок акций", "биржевые торги" → SBER, GAZP, LKOH (голубые фишки)
- "Дивиденды", "отчетность" → ищи компании
- "Нефть", "энергетика" → ROSN, LKOH, GAZP
- "Металлы" → GMKN, ALRS, POLY
- "Технологии" → YNDX, OZON
- "Розничная торговля" → MGNT, FIVE
- "Финансы", "банковский сектор" → SBER, VTBR, TCSG

Основные тикеры MOEX: SBER, GAZP, LKOH, ROSN, NVTK, GMKN, YNDX, OZON, MOEX, VTBR, TCSG, MGNT, FIVE, TATN, ALRS, CHMF, NLMK, SNGS, MTSS, AFKS, RTKM, PHOR

Задача:
1. Найди ВСЕ возможные тикеры (даже если упоминание косвенное)
2. Тип события: dividend (дивиденды), earnings_report (отчетность), regulatory (новости регуляторов), market_update (рыночные новости)
3. Тональность: positive, negative, neutral
4. Влияние на цену (1-10): 1=минимальное, 10=сильное
5. Краткая причина (1 фраза)

Верни ТОЛЬКО JSON:
{{
    "tickers": ["SBER", "GAZP"],
    "event_type": "market_update",
    "sentiment": "neutral",
    "impact_score": 5,
    "reason": "Упоминание банковского сектора"
}}

Если тикеров НЕТ: {{"tickers": [], "reason": "Тикеры не найдены"}}
Только JSON!"""
            else:
                # Английские новости
                prompt_text = f"""You are a MOEX financial analyst. Analyze news for stock trading.

News: {title}

IMPORTANT: Even if the news is short or general — find POSSIBLE MOEX tickers.

Examples:
- "Sberbank" or "banks" → SBER
- "Gazprom" or "oil and gas" → GAZP
- "Stock market", "exchange trading" → SBER, GAZP, LKOH (blue chips)
- "Dividends", "earnings" → look for companies
- "Oil", "energy" → ROSN, LKOH, GAZP
- "Metals" → GMKN, ALRS, POLY
- "Technology" → YNDX, OZON
- "Retail" → MGNT, FIVE
- "Finance", "banking sector" → SBER, VTBR, TCSG

Main MOEX tickers: SBER, GAZP, LKOH, ROSN, NVTK, GMKN, YNDX, OZON, MOEX, VTBR, TCSG, MGNT, FIVE, TATN, ALRS, CHMF, NLMK, SNGS, MTSS, AFKS, RTKM, PHOR

Task:
1. Find ALL possible tickers (even indirect mentions)
2. Event type: dividend, earnings_report, regulatory, market_update
3. Sentiment: positive, negative, neutral
4. Impact on price (1-10): 1=minimal, 10=strong
5. Brief reason (1 phrase)

Return ONLY JSON:
{{
    "tickers": ["SBER", "GAZP"],
    "event_type": "market_update",
    "sentiment": "neutral",
    "impact_score": 5,
    "reason": "Banking sector mentioned"
}}

If NO tickers: {{"tickers": [], "reason": "No tickers found"}}
ONLY JSON!"""
            
            return {
                "model": "GigaChat-2",
                "messages": [{"role": "user", "content": prompt_text}],
                "temperature": 0.1,
                "max_tokens": 500,
                "stream": False
            }
        else:
            # OpenRouter промпт
            system_prompt = """You are a financial analyst specializing in Russian stock market.
Analyze news and return ONLY JSON in format: 
{"tickers": ["SBER"], "event_type": "dividend", "sentiment": "positive", "impact_score": 7, "reason": "..."}
If no financial content: {"tickers": [], "reason": "No financial content"}
Important: Use MOEX ticker symbols (SBER, GAZP, LKOH, GMKN, YNDX, OZON, etc.)"""
            
            user_content = f"News: {title}\n\n{content[:200]}"
            
            # Определяем модель
            if model and 'gemini' in model:
                # Gemini-specific format
                return {
                    "model": model,
                    "messages": [
                        {"role": "user", "parts": [{"text": system_prompt}]},
                        {"role": "model", "parts": [{"text": "I understand. I will analyze financial news and return only JSON."}]},
                        {"role": "user", "parts": [{"text": user_content}]}
                    ],
                    "temperature": 0.1,
                    "max_tokens": 400
                }
            else:
                # Standard format
                return {
                    "model": model or 'google/gemini-2.0-flash:free',
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_content}
                    ],
                    "temperature": 0.1,
                    "max_tokens": 400
                }
    
    async def _make_gigachat_request(self, prompt_data: Dict) -> Optional[Dict]:
        """Запрос к GigaChat API с ограничением 1 запрос"""
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
            async with httpx.AsyncClient(timeout=30.0, verify=False) as client:
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
    
    async def analyze_news(self, news_item: Dict) -> Optional[Dict]:
        """Анализ новости с последовательной обработкой GigaChat"""
        
        self.stats['total_requests'] += 1
        cache_key = self._create_cache_key(news_item)
        
        if cache_key in self.analysis_cache:
            self.stats['cache_hits'] += 1
            return self.analysis_cache[cache_key]
        
        self.stats['cache_misses'] += 1
        
        # 1. Пробуем GigaChat с ОГРАНИЧЕНИЕМ 1 запрос
        if 'gigachat' in self.provider_priority and self.providers['gigachat']['enabled']:
            logger.debug(f"📡 Пробую GigaChat: {news_item.get('title', '')[:50]}")
            self.stats['by_provider']['gigachat']['requests'] += 1
            
            # ОЖИДАЕМ СЕМАФОР для ограничения 1 запроса
            async with self.gigachat_semaphore:
                self.stats['gigachat_queue_waits'] += 1
                
                try:
                    prompt_data = self._create_prompt_for_provider(news_item, 'gigachat')
                    response_data = await self._make_gigachat_request(prompt_data)
                    
                    if response_data:
                        ai_response = response_data.get("choices", [{}])[0].get("message", {}).get("content", "")
                        
                        if ai_response:
                            # ЛОГИРУЕМ сырой ответ для отладки
                            logger.debug(f"📥 GigaChat raw: {ai_response[:100]}")
                            
                            analysis_result = self._parse_ai_response(ai_response, news_item, 'gigachat')
                            
                            if analysis_result:
                                self.stats['successful_requests'] += 1
                                self.stats['by_provider']['gigachat']['success'] += 1
                                self.analysis_cache[cache_key] = analysis_result
                                logger.debug(f"✅ GigaChat: {len(analysis_result['tickers'])} тикеров")
                                return analysis_result
                            else:
                                logger.debug(f"⚠️ GigaChat: анализ не получен")
                except Exception as e:
                    logger.debug(f"⚠️ GigaChat ошибка: {str(e)[:50]}")
                
                # Пауза между запросами GigaChat
                await asyncio.sleep(1)
        
        # 2. Пробуем OpenRouter (последовательно)
        if 'openrouter' in self.provider_priority and self.providers['openrouter']['enabled']:
            logger.debug("📡 Пробую провайдер: OPENROUTER")
            
            for model in self.openrouter_models:
                self.stats['by_provider']['openrouter']['requests'] += 1
                
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
                            response_data = response.json()
                            ai_response = response_data.get("choices", [{}])[0].get("message", {}).get("content", "")
                            
                            if ai_response:
                                analysis_result = self._parse_ai_response(ai_response, news_item, 'openrouter')
                                
                                if analysis_result:
                                    self.stats['successful_requests'] += 1
                                    self.stats['by_provider']['openrouter']['success'] += 1
                                    self.analysis_cache[cache_key] = analysis_result
                                    logger.debug(f"✅ OpenRouter ({model}): успешный анализ")
                                    return analysis_result
                        
                except Exception as e:
                    logger.debug(f"⚠️ OpenRouter {model} ошибка: {str(e)[:50]}")
                
                await asyncio.sleep(0.5)
        
        logger.debug("ℹ️ Все ИИ-провайдеры недоступны или не нашли тикеров")
        return None
    
    def _parse_ai_response(self, response: str, news_item: Dict, provider: str) -> Optional[Dict]:
        """Парсинг ответа ИИ - СОХРАНЯЕМ ОРИГИНАЛЬНУЮ ЛОГИКУ"""
        try:
            response = response.strip()
            
            # Логируем ответ для отладки
            logger.debug(f"🔍 {provider} raw response: {response[:200]}...")
            
            # Пытаемся найти JSON разными способами
            json_str = None
            
            # Способ 1: Ищем между { и }
            start = response.find('{')
            end = response.rfind('}') + 1
            
            if start != -1 and end != 0 and end > start:
                json_str = response[start:end]
            
            # Способ 2: Регулярное выражение (если первый способ не сработал)
            if not json_str:
                json_pattern = r'\{[^{}]*\}'
                matches = re.findall(json_pattern, response, re.DOTALL)
                if matches:
                    # Берем самый длинный JSON
                    json_str = max(matches, key=len)
            
            # Способ 3: Ищем JSON с любыми пробелами
            if not json_str:
                # Пробуем найти начало и конец JSON
                for start_idx in range(len(response)):
                    if response[start_idx] == '{':
                        brace_count = 0
                        for end_idx in range(start_idx, len(response)):
                            if response[end_idx] == '{':
                                brace_count += 1
                            elif response[end_idx] == '}':
                                brace_count -= 1
                                if brace_count == 0:
                                    json_str = response[start_idx:end_idx+1]
                                    break
                        if json_str:
                            break
            
            if not json_str:
                self.stats['parsing_errors'] += 1
                logger.debug(f"❌ {provider}: Не найден JSON в ответе")
                return None
            
            logger.debug(f"✅ {provider} JSON найден: {json_str[:150]}...")
            
            data = json.loads(json_str)
            
            tickers = data.get('tickers', [])
            if not isinstance(tickers, list):
                tickers = []
            
            # ВАЖНО: Сохраняем оригинальную проверку
            reason = data.get('reason', '').lower()
            if not tickers or 'no financial' in reason or 'not financial' in reason:
                self.stats['no_financial_content'] += 1
                logger.debug(f"⚠️ {provider}: Нет финансового содержания: {reason}")
                return None
            
            valid_tickers = []
            for ticker in tickers:
                if isinstance(ticker, str) and 2 <= len(ticker) <= 5:
                    # Приводим к верхнему регистру и проверяем на буквы/цифры
                    ticker_upper = ticker.upper()
                    if any(c.isalpha() for c in ticker_upper):
                        valid_tickers.append(ticker_upper)
            
            if not valid_tickers:
                self.stats['no_financial_content'] += 1
                logger.debug(f"⚠️ {provider}: Нет валидных тикеров")
                return None
            
            event_type = data.get('event_type', 'market_update')
            sentiment = data.get('sentiment', 'neutral')
            
            # Парсим impact_score
            impact_score = 5  # default
            try:
                raw_impact = data.get('impact_score')
                if raw_impact is not None:
                    impact_score = int(raw_impact)
            except:
                pass
            
            impact_score = min(10, max(1, impact_score))
            
            # Расчет confidence
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
                'summary': data.get('reason', f"Found {len(valid_tickers)} tickers"),
                'confidence': confidence,
                'ai_provider': provider,
                'analysis_timestamp': datetime.now().isoformat(),
                'simple_analysis': False
            }
            
            logger.debug(f"📊 {provider}: {len(valid_tickers)} тикеров, {event_type}, {sentiment}, impact:{impact_score}")
            return result
            
        except json.JSONDecodeError as e:
            self.stats['parsing_errors'] += 1
            logger.debug(f"❌ {provider}: Ошибка парсинга JSON: {str(e)[:50]}")
            return None
        except Exception as e:
            self.stats['parsing_errors'] += 1
            logger.debug(f"❌ {provider}: Ошибка парсинга: {str(e)[:50]}")
            return None
    
    def _create_cache_key(self, news_item: Dict) -> str:
        """Создание ключа кэша"""
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
            'gigachat_queue_waits': self.stats['gigachat_queue_waits'],
            'parsing_errors': self.stats['parsing_errors'],
            'no_financial_content': self.stats['no_financial_content'],
            'current_provider': self.get_current_provider(),
            'openrouter_models': len(self.openrouter_models),
            'providers': provider_stats
        }
