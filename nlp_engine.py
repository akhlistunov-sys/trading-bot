import logging
import json
import os
import httpx
import asyncio
from datetime import datetime
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

class NlpEngine:
    def __init__(self):
        self.providers = {
            'gigachat': {
                'url': 'https://gigachat.devices.sberbank.ru/api/v1/chat/completions',
                'token': os.getenv('GIGACHATAPI'),
                'models': ['GigaChat', 'GigaChat-Pro'],
                'headers': {
                    'Authorization': f'Bearer {os.getenv("GIGACHATAPI")}',
                    'Content-Type': 'application/json'
                }
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
                    'Content-Type': 'application/json'
                }
            }
        }
        
        self.current_model_idx = 0
        self.model = self.model_priority[self.current_model_idx]
        self.api_url = "https://openrouter.ai/api/v1/chat/completions"
        
        # Статистика
        self.total_requests = 0
        self.successful_requests = 0
        self.model_switches = 0
        self.analysis_cache = {}
        self.cache_hits = 0
        self.cache_misses = 0
        
        # Задержка между запросами
        self.request_delay = 2
        
        logger.info(f"🤖 NLP-движок инициализирован")
        logger.info(f"🧠 Модели в каскаде ({len(self.model_priority)}):")
        for i, model in enumerate(self.model_priority):
            status = "✅" if i == 0 else "🧪" if "deepseek" in model else "🔧"
            logger.info(f"   {i+1}. {status} {model}")
    
    def _switch_to_next_model(self):
        """Переключение на следующую модель в каскаде"""
        old_model = self.model
        self.current_model_idx = (self.current_model_idx + 1) % len(self.model_priority)
        self.model = self.model_priority[self.current_model_idx]
        self.model_switches += 1
        
        logger.info(f"🔄 Смена модели: {old_model} → {self.model}")
        return self.model
    
    def _create_cache_key(self, news_item: Dict) -> str:
        """Создание ключа для кэша"""
        title = news_item.get('title', '')[:50].replace(' ', '_').lower()
        source = news_item.get('source', '')[:20].replace(' ', '_').lower()
        content_hash = hash(news_item.get('content', '')[:100]) % 10000
        return f"{source}_{title}_{content_hash}"
    
    def _create_analysis_prompt(self, news_item: Dict) -> str:
        """Создание промпта для анализа новости"""
        
        title = news_item.get('title', '')
        description = news_item.get('description', '')
        content = news_item.get('content', '') or description
        source = news_item.get('source_name', news_item.get('source', 'Unknown'))
        
        prompt = f"""
        ===== АНАЛИЗ ФИНАНСОВОЙ НОВОСТИ =====
        
        📰 ИСТОЧНИК: {source}
        🏷️ ЗАГОЛОВОК: {title}
        
        📝 ТЕКСТ НОВОСТИ:
        {content[:1200]}
        
        ===== ИНСТРУКЦИЯ ДЛЯ АНАЛИЗА =====
        
        Ты — финансовый аналитик ИИ. Проанализируй новость выше и ответь В СТРОГОМ JSON ФОРМАТЕ.
        
        ВОЗВРАЩАЙ ТОЛЬКО JSON В СЛЕДУЮЩЕМ ФОРМАТЕ:
        {{
            "analysis": {{
                "tickers": ["TICKER1", "TICKER2"],
                "event_type": "earnings_report | dividend | merger_acquisition | regulatory | geopolitical | market_update | corporate_action | other",
                "impact_score": 1-10,
                "relevance_score": 1-100,
                "sentiment": "positive | negative | neutral | mixed",
                "horizon": "immediate | short_term | medium_term | long_term",
                "summary": "краткая суть на русском (2-3 предложения)"
            }}
        }}
        
        ИНСТРУКЦИИ:
        1. Извлеки все упоминания компаний и их тикеров (примеры: "Сбербанк" → SBER, "Газпром" → GAZP, "Лукойл" → LKOH)
        2. Оцени важность (impact_score): 1-3=низкая, 4-6=средняя, 7-8=высокая, 9-10=критическая
        3. Оцени релевантность для трейдинга (relevance_score): 1-100
        4. Определи тональность новости для акций
        5. Кратко объясни суть
        
        ТОЛЬКО JSON, БЕЗ ДОПОЛНИТЕЛЬНОГО ТЕКСТА, БЕЗ МАРКДАУНА, БЕЗ ОБЪЯСНЕНИЙ!
        """
        
        return prompt
    
    async def analyze_news(self, news_item: Dict) -> Optional[Dict]:
        """Анализ одной новости с помощью ИИ"""
        
        self.total_requests += 1
        
        # Проверка кэша
        cache_key = self._create_cache_key(news_item)
        if cache_key in self.analysis_cache:
            self.cache_hits += 1
            logger.info(f"🔄 Использую кэшированный анализ (hits: {self.cache_hits})")
            return self.analysis_cache[cache_key]
        
        self.cache_misses += 1
        news_title = news_item.get('title', '')[:50]
        logger.info(f"🧠 Анализ новости #{self.total_requests}: {news_title}...")
        
        # Пробуем разные модели при ошибках
        max_retries = min(3, len(self.model_priority))
        last_error = None
        
        for attempt in range(max_retries):
            try:
                logger.info(f"📨 Попытка {attempt+1}/{max_retries} с моделью: {self.model}")
                
                prompt = self._create_analysis_prompt(news_item)
                
                async with httpx.AsyncClient(timeout=30.0) as client:
                    response = await client.post(
                        url=self.api_url,
                        headers={
                            "Authorization": f"Bearer {self.api_key}",
                            "Content-Type": "application/json",
                            "HTTP-Referer": "https://github.com",
                            "X-Title": "News NLP Trading AI"
                        },
                        json={
                            "model": self.model,
                            "messages": [
                                {
                                    "role": "system",
                                    "content": "Ты — финансовый аналитик ИИ. Анализируй новости и возвращай строго в JSON формате. Никакого дополнительного текста!"
                                },
                                {"role": "user", "content": prompt}
                            ],
                            "temperature": 0.1,  # Низкая температура для консистентности
                            "max_tokens": 600
                        }
                    )
                
                logger.info(f"📥 Ответ модели: статус {response.status_code}")
                
                if response.status_code == 200:
                    result = response.json()
                    ai_response = result["choices"][0]["message"]["content"]
                    
                    self.successful_requests += 1
                    
                    # Парсинг JSON ответа
                    analysis_result = self._parse_ai_response(ai_response, news_item)
                    
                    if analysis_result:
                        # Кэшируем результат
                        self.analysis_cache[cache_key] = analysis_result
                        if len(self.analysis_cache) > 50:
                            oldest = next(iter(self.analysis_cache))
                            del self.analysis_cache[oldest]
                        
                        logger.info(f"✅ Успешный анализ новости (модель: {self.model})")
                        return analysis_result
                    else:
                        logger.warning(f"⚠️ Не удалось распарсить ответ ИИ")
                        last_error = "Parse error"
                        
                elif response.status_code in [400, 404]:
                    # Проблема с моделью
                    error_data = response.json()
                    error_msg = error_data.get('error', {}).get('message', 'Unknown error')
                    
                    logger.warning(f"⚠️ Ошибка модели {self.model}: {error_msg[:100]}")
                    
                    if attempt < max_retries - 1:
                        self._switch_to_next_model()
                        logger.info(f"⏳ Задержка {self.request_delay} сек перед следующей моделью...")
                        await asyncio.sleep(self.request_delay)
                        continue
                    else:
                        last_error = f"Все модели недоступны: {error_msg}"
                        break
                
                elif response.status_code == 429:
                    # Rate limit
                    logger.warning(f"⚠️ Rate limit для модели {self.model}")
                    
                    if attempt < max_retries - 1:
                        self._switch_to_next_model()
                        logger.info(f"⏳ Задержка {self.request_delay * 2} сек из-за rate limit...")
                        await asyncio.sleep(self.request_delay * 2)
                        continue
                    else:
                        last_error = "Rate limit на всех моделях"
                        break
                
                else:
                    last_error = f"HTTP {response.status_code}"
                    break
                    
            except httpx.TimeoutException:
                last_error = "Таймаут 30с"
                logger.error(f"⏰ Таймаут на модели {self.model}")
                if attempt < max_retries - 1:
                    self._switch_to_next_model()
                    await asyncio.sleep(3)
                    continue
                break
                
            except Exception as e:
                last_error = str(e)
                logger.error(f"❌ Ошибка анализа: {str(e)[:100]}")
                break
        
        if last_error:
            logger.error(f"❌ Все попытки анализа failed: {last_error}")
        
        return None
    
    def _parse_ai_response(self, response: str, news_item: Dict) -> Optional[Dict]:
        """Парсинг ответа ИИ"""
        try:
            # Очистка ответа - удаляем лишний текст
            response = response.strip()
            
            # Ищем JSON в ответе (удаляем возможные markdown кодовые блоки)
            if '```json' in response:
                response = response.split('```json')[1].split('```')[0].strip()
            elif '```' in response:
                response = response.split('```')[1].split('```')[0].strip()
            
            # Ищем первый { и последний }
            start_idx = response.find('{')
            end_idx = response.rfind('}') + 1
            
            if start_idx == -1 or end_idx == 0:
                logger.warning(f"⚠️ ИИ не вернул JSON: {response[:100]}...")
                return None
            
            json_str = response[start_idx:end_idx]
            data = json.loads(json_str)
            
            analysis_data = data.get("analysis", {})
            
            # Валидация обязательных полей
            required_fields = ['tickers', 'event_type', 'impact_score', 'relevance_score']
            if not all(field in analysis_data for field in required_fields):
                logger.warning("⚠️ В ответе ИИ отсутствуют обязательные поля")
                return None
            
            # Создаем полный результат анализа
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
                'ai_model': self.model,
                'confidence': min(1.0, analysis_data.get('relevance_score', 30) / 100.0)
            }
            
            # Логируем результат
            tickers_str = ', '.join(result['tickers']) if result['tickers'] else 'НЕТ ТИКЕРОВ'
            logger.info(f"📊 Результат: {tickers_str} | Impact: {result['impact_score']}/10 | Relevance: {result['relevance_score']}/100")
            
            return result
            
        except json.JSONDecodeError as e:
            logger.error(f"❌ Невалидный JSON от ИИ: {str(e)[:50]}")
            logger.debug(f"💬 Ответ ИИ: {response[:200]}")
            return None
        except Exception as e:
            logger.error(f"❌ Ошибка парсинга ответа ИИ: {str(e)[:50]}")
            return None
    
    def get_current_model(self) -> str:
        """Получение текущей активной модели"""
        return self.model
    
    def get_stats(self) -> Dict:
        """Статистика работы NLP-движка"""
        success_rate = (self.successful_requests / self.total_requests * 100) if self.total_requests > 0 else 0
        
        return {
            'total_requests': self.total_requests,
            'successful_requests': self.successful_requests,
            'success_rate': round(success_rate, 1),
            'current_model': self.model,
            'model_index': self.current_model_idx,
            'model_switches': self.model_switches,
            'cache_size': len(self.analysis_cache),
            'cache_hits': self.cache_hits,
            'cache_misses': self.cache_misses,
            'cache_hit_rate': round((self.cache_hits / (self.cache_hits + self.cache_misses) * 100), 1) if (self.cache_hits + self.cache_misses) > 0 else 0
        }
