import logging
import json
import os
import httpx
import asyncio
from typing import Dict, List, Optional
from datetime import datetime

logger = logging.getLogger(__name__)

class NlpEngine:
    """ИИ-движок для анализа новостей с использованием каскада LLM"""
    
    def __init__(self):
        logger.info("🔧 Инициализация NLP-движка...")
        
        # API ключ OpenRouter
        self.api_key = os.getenv("OPENROUTER_API_TOKEN")
        if not self.api_key:
            raise ValueError("❌ OPENROUTER_API_TOKEN не найден")
        
        # Каскад моделей (правильные имена)
        self.model_priority = [
            "google/gemini-2.0-flash-exp:free",
            "meta-llama/llama-3.3-70b-instruct:free",
            "qwen/qwen3-235b-a22b:free",
            "google/gemma-3-27b:free",
            "meta-llama/llama-3.2-3b-instruct:free"
        ]
        
        self.current_model_idx = 0
        self.model = self.model_priority[self.current_model_idx]
        self.api_url = "https://openrouter.ai/api/v1/chat/completions"
        
        # Статистика
        self.total_requests = 0
        self.successful_requests = 0
        self.model_switches = 0
        self.analysis_cache = {}
        
        logger.info(f"🤖 NLP-движок инициализирован")
        logger.info(f"🧠 Текущая модель: {self.model}")
        logger.info(f"📋 Всего моделей в каскаде: {len(self.model_priority)}")
    
    def _switch_to_next_model(self):
        """Переключение на следующую модель в каскаде"""
        old_model = self.model
        self.current_model_idx = (self.current_model_idx + 1) % len(self.model_priority)
        self.model = self.model_priority[self.current_model_idx]
        self.model_switches += 1
        
        logger.info(f"🔄 Смена модели: {old_model} → {self.model}")
        return self.model
    
    def _create_analysis_prompt(self, news_item: Dict) -> str:
        """Создание промпта для анализа новости"""
        
        # Основные поля новости
        title = news_item.get('title', '')
        description = news_item.get('description', '')
        content = news_item.get('content', '') or description
        source = news_item.get('source_name', news_item.get('source', 'Unknown'))
        
        prompt = f"""
        ===== АНАЛИЗ ФИНАНСОВОЙ НОВОСТИ =====
        
        📰 ИСТОЧНИК: {source}
        🏷️ ЗАГОЛОВОК: {title}
        
        📝 ТЕКСТ НОВОСТИ:
        {content[:1500]}
        
        ===== ИНСТРУКЦИЯ ДЛЯ АНАЛИЗА =====
        
        Ты — профессиональный финансовый аналитик ИИ. Проанализируй новость выше и ответь В СТРОГОМ JSON ФОРМАТЕ.
        
        АНАЛИЗИРУЙ СЛЕДУЮЩИЕ АСПЕКТЫ:
        1. Извлеки все упоминания компаний и их тикеров (например: "Сбербанк" → SBER, "Газпром" → GAZP)
        2. Определи тип события:
           - earnings_report: Квартальные/годовые отчеты
           - dividend: Дивидендные новости
           - merger_acquisition: Слияния и поглощения
           - regulatory: Регуляторные изменения
           - geopolitical: Геополитические события
           - market_update: Общие рыночные новости
           - corporate_action: Корпоративные действия
           - other: Другое
        3. Оцени важность (impact_score) от 1 до 10:
           - 1-3: Незначительное влияние
           - 4-6: Среднее влияние на отдельные компании
           - 7-8: Серьезное влияние на сектор
           - 9-10: Критическое влияние на рынок
        4. Оцени релевантность (relevance_score) от 1 до 100:
           - 0-30: Низкая релевантность для трейдинга
           - 31-70: Средняя релевантность
           - 71-100: Высокая релевантность
        5. Определи тональность (sentiment):
           - positive: Позитивная новость
           - negative: Негативная новость
           - neutral: Нейтральная новость
           - mixed: Смешанная тональность
        6. Определи горизонт влияния (horizon):
           - immediate: Влияние сегодня/завтра
           - short_term: Влияние в течение недели
           - medium_term: Влияние в течение месяца
           - long_term: Долгосрочное влияние
        7. Составь краткую суть на русском (2-3 предложения)
        
        ВОЗВРАЩАЙ ТОЛЬКО JSON В СЛЕДУЮЩЕМ ФОРМАТЕ:
        {{
            "analysis": {{
                "tickers": ["TICKER1", "TICKER2"],
                "event_type": "тип_события",
                "impact_score": число_от_1_до_10,
                "relevance_score": число_от_1_до_100,
                "sentiment": "тональность",
                "horizon": "горизонт",
                "summary": "краткая суть на русском"
            }}
        }}
        
        ТОЛЬКО JSON, БЕЗ ДОПОЛНИТЕЛЬНОГО ТЕКСТА!
        """
        
        return prompt
    
    async def analyze_news(self, news_item: Dict) -> Optional[Dict]:
        """Анализ одной новости с помощью ИИ"""
        
        self.total_requests += 1
        request_id = self.total_requests
        
        logger.info(f"🧠 Анализ новости #{request_id}: {news_item.get('title', '')[:50]}...")
        
        # Проверка кэша
        cache_key = f"{news_item.get('title', '')[:50]}_{news_item.get('source', '')}"
        if cache_key in self.analysis_cache:
            logger.info(f"🔄 Использую кэшированный анализ")
            return self.analysis_cache[cache_key]
        
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
                            "temperature": 0.1,
                            "max_tokens": 800
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
                        
                        logger.info(f"✅ Успешный анализ новости")
                        return analysis_result
                    else:
                        logger.warning(f"⚠️ Не удалось распарсить ответ ИИ")
                        last_error = "Parse error"
                        
                elif response.status_code in [400, 404, 429]:
                    # Проблема с моделью или rate limit
                    error_data = response.json()
                    error_msg = error_data.get('error', {}).get('message', 'Unknown error')
                    
                    logger.warning(f"⚠️ Ошибка модели {self.model}: {error_msg[:100]}")
                    
                    if attempt < max_retries - 1:
                        # Переключаем модель перед следующей попыткой
                        next_model = self._switch_to_next_model()
                        logger.info(f"⏳ Задержка 2 сек перед моделью {next_model}...")
                        await asyncio.sleep(2)
                        continue
                    else:
                        last_error = f"Все модели недоступны: {error_msg}"
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
            # Ищем JSON в ответе
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
            logger.info(f"📊 Анализ: {tickers_str} | Impact: {result['impact_score']}/10 | Relevance: {result['relevance_score']}/100")
            
            return result
            
        except json.JSONDecodeError as e:
            logger.error(f"❌ Невалидный JSON от ИИ: {str(e)[:50]}")
            return None
        except Exception as e:
            logger.error(f"❌ Ошибка парсинга ответа ИИ: {str(e)[:50]}")
            return None
    
    def get_current_model(self) -> str:
        """Получение текущей активной модели"""
        return self.model
    
    def get_stats(self) -> Dict:
        """Статистика работы NLP-движка"""
        return {
            'total_requests': self.total_requests,
            'successful_requests': self.successful_requests,
            'success_rate': (self.successful_requests / self.total_requests * 100) if self.total_requests > 0 else 0,
            'current_model': self.model,
            'model_switches': self.model_switches,
            'cache_size': len(self.analysis_cache)
        }
