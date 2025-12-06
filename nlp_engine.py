import logging
import json
import os
import httpx
import asyncio
from datetime import datetime
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

class NlpEngine:
    """Гибридный ИИ-движок с поддержкой GigaChat и OpenRouter"""
    
    def __init__(self):
        logger.info("🔧 Инициализация гибридного NLP-движка...")
        
        # Инициализация провайдеров
        self.providers = {
            'gigachat': {
                'url': 'https://gigachat.devices.sberbank.ru/api/v1/chat/completions',
                'token': os.getenv('GIGACHATAPI'),
                'models': ['GigaChat', 'GigaChat-Pro'],
                'headers': {
                    'Authorization': f'Bearer {os.getenv("GIGACHATAPI")}',
                    'Content-Type': 'application/json'
                },
                'enabled': bool(os.getenv('GIGACHATAPI')),
                'priority': 1  # Высший приоритет
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
        
        # Сортируем провайдеры по приоритету
        self.provider_priority = sorted(
            [p for p in self.providers.keys() if self.providers[p]['enabled']],
            key=lambda x: self.providers[x]['priority']
        )
        
        if not self.provider_priority:
            raise ValueError("❌ Ни один ИИ-провайдер не настроен (нужен GIGACHATAPI или OPENROUTER_API_TOKEN)")
        
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
        logger.info(f"📊 Доступные провайдеры: {', '.join(self.provider_priority)}")
        
        # Логируем конфигурацию каждого провайдера
        for provider in self.provider_priority:
            models = self.providers[provider]['models']
            enabled = self.providers[provider]['enabled']
            status = "✅" if enabled else "❌"
            logger.info(f"   {status} {provider.upper()}: {len(models)} моделей")
            for model in models:
                logger.info(f"      • {model}")
    
    def _create_cache_key(self, news_item: Dict) -> str:
        """Создание ключа для кэша"""
        title = news_item.get('title', '')[:50].replace(' ', '_').lower()
        source = news_item.get('source', '')[:20].replace(' ', '_').lower()
        content_hash = hash(news_item.get('content', '')[:200]) % 10000
        return f"{source}_{title}_{content_hash}"
    
    # ... (импорты и начало класса без изменений)

    def _create_prompt_for_provider(self, news_item: Dict, provider: str) -> Dict:
        """Создание промпта в зависимости от провайдера"""
        
        title = news_item.get('title', '')
        description = news_item.get('description', '')
        content = news_item.get('content', '') or description
        source = news_item.get('source_name', news_item.get('source', 'Unknown'))
        
        # Общая инструкция с учетом рыночного контекста
        market_context_instruction = """
        ВАЖНО: Учитывай общий контекст рынка. Положительная новость в день общего падения рынка 
        может иметь меньший эффект. Отрицательная новость на растущем рынке может быть проигнорирована.
        Оценивай влияние новости не изолированно, а в контексте возможной текущей волатильности.
        """
        
        if provider == 'gigachat':
            # Промпт для GigaChat (оптимизирован для русского)
            system_prompt = f"""Ты — финансовый аналитик Сбербанка. Анализируй новости российского рынка акций.
            
            {market_context_instruction}
            
            ИНСТРУКЦИИ:
            1. Найди все упоминания российских компаний и их тикеров (примеры: Сбербанк → SBER, Газпром → GAZP, Лукойл → LKOH)
            2. Определи тип события: earnings_report, dividend, merger_acquisition, regulatory, geopolitical, market_update, corporate_action, other
            3. Оцени важность (impact_score): 1-3=низкая, 4-6=средняя, 7-8=высокая, 9-10=критическая
            4. Оцени релевантность для трейдинга (relevance_score): 1-100
            5. Определи тональность: positive, negative, neutral, mixed
            6. Определи горизонт влияния: immediate, short_term, medium_term, long_term
            7. Кратко объясни суть (2-3 предложения на русском)
            
            ВОЗВРАЩАЙ ТОЛЬКО JSON В СТРОГОМ ФОРМАТЕ:
            {{
                "analysis": {{
                    "tickers": ["TICKER1", "TICKER2"],
                    "event_type": "тип_события",
                    "impact_score": число,
                    "relevance_score": число,
                    "sentiment": "тональность",
                    "horizon": "горизонт",
                    "summary": "краткая суть"
                }}
            }}
            
            ТОЛЬКО JSON, БЕЗ ДОПОЛНИТЕЛЬНОГО ТЕКСТА!"""
            
        else:  # openrouter и другие
            # Универсальный промпт
            system_prompt = f"""Ты — финансовый аналитик ИИ. Анализируй новости и возвращай строго в JSON формате.
            
            {market_context_instruction}
            
            ИНСТРУКЦИИ:
            1. Extract all company mentions and their tickers
            2. Determine event type: earnings_report, dividend, merger_acquisition, regulatory, geopolitical, market_update, corporate_action, other
            3. Rate importance (impact_score): 1-10
            4. Rate relevance for trading (relevance_score): 1-100
            5. Determine sentiment: positive, negative, neutral, mixed
            6. Determine impact horizon: immediate, short_term, medium_term, long_term
            7. Provide brief summary
            
            RETURN ONLY JSON IN THIS EXACT FORMAT:
            {{
                "analysis": {{
                    "tickers": ["TICKER1", "TICKER2"],
                    "event_type": "event_type",
                    "impact_score": number,
                    "relevance_score": number,
                    "sentiment": "sentiment",
                    "horizon": "horizon",
                    "summary": "brief summary"
                }}
            }}
            
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

# ... (остальная часть файла без изменений)
