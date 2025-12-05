import logging
import json
import os
import httpx
from typing import Dict, List, Optional
import statistics
from dotenv import load_dotenv  # ← ДОБАВЬ ЭТУ СТРОКУ

# ЗАГРУЗИТЬ ПЕРЕМЕННЫЕ ИЗ .env
load_dotenv()  # ← ДОБАВЬ ЭТУ СТРОКУ

logger = logging.getLogger(__name__)

class AICore:
    """ИИ-ядро для принятия торговых решений через OpenRouter"""
    
    def __init__(self):
        self.api_key = os.getenv("OPENROUTER_API_KEY")
        if not self.api_key:
            raise ValueError("❌ OPENROUTER_API_KEY не найден в переменных окружения")
        
        self.api_url = "https://openrouter.ai/api/v1/chat/completions"
        self.model = "google/gemini-2.0-flash-exp:free"  # Стабильная модель
        # Кэш решений для экономии API
        self.decision_cache = {}
        
    async def get_trading_decision(self, market_data: Dict) -> List[Dict]:
        """Получает торговые решения от ИИ"""
        
        # Проверяем кэш (если уже анализировали похожую ситуацию)
        cache_key = self._create_cache_key(market_data)
        if cache_key in self.decision_cache:
            logger.info("🔄 Использую кэшированное решение ИИ")
            return self.decision_cache[cache_key]
        
        # Формируем промпт для ИИ
        prompt = self._create_prompt(market_data)
        
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    url=self.api_url,
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json",
                        "HTTP-Referer": "https://github.com",  # Требование OpenRouter
                        "X-Title": "Trading AI"
                    },
                    json={
                        "model": self.model,
                        "messages": [
                            {
                                "role": "system",
                                "content": """Ты — профессиональный алгоритмический трейдер. 
                                Анализируй данные рынка и возвращай ТОЛЬКО JSON с торговыми сигналами.
                                Формат: {"signals": [{"action": "BUY/SELL", "ticker": "SBER/VTBR", "reason": "объяснение", "confidence": 0.0-1.0}]}
                                Никакого пояснительного текста, только JSON."""
                            },
                            {"role": "user", "content": prompt}
                        ],
                        "temperature": 0.1,  # Низкая креативность для точности
                        "max_tokens": 500
                    }
                )
                
                if response.status_code == 200:
                    result = response.json()
                    ai_response = result["choices"][0]["message"]["content"]
                    
                    # Извлекаем JSON из ответа
                    signals = self._parse_ai_response(ai_response)
                    
                    # Кэшируем решение
                    self.decision_cache[cache_key] = signals
                    if len(self.decision_cache) > 10:
                        self.decision_cache.pop(next(iter(self.decision_cache)))
                    
                    logger.info(f"🧠 ИИ вернул {len(signals)} сигналов")
                    return signals
                else:
                    logger.error(f"❌ Ошибка OpenRouter API: {response.status_code}")
                    return []
                    
        except Exception as e:
            logger.error(f"❌ Ошибка связи с ИИ: {e}")
            return []
    
    def _create_prompt(self, market_data: Dict) -> str:
        """Создаёт промпт для ИИ на основе рыночных данных"""
        
        prompt = f"""
        ДАННЫЕ РЫНКА:
        - Время: {market_data.get('timestamp', 'N/A')}
        - Капитал: {market_data.get('balance', 100000)} руб.
        - Позиции: {json.dumps(market_data.get('positions', {}), indent=2)}
        
        ТЕКУЩИЕ ЦЕНЫ:
        {json.dumps(market_data.get('prices', {}), indent=2)}
        
        ИСТОРИЧЕСКИЕ ДАННЫЕ:
        - Среднее соотношение SBER/VTBR: {market_data.get('mean_ratio', 0):.4f}
        - Текущее соотношение: {market_data.get('current_ratio', 0):.4f}
        - Z-score отклонения: {market_data.get('z_score', 0):.2f}
        - Стандартное отклонение: {market_data.get('std_ratio', 0):.4f}
        
        АНАЛИЗИРУЙ:
        1. Парный арбитраж SBER/VTBR (нормализация: 1 SBER = 1000 VTBR)
        2. Текущее отклонение от исторического среднего
        3. Риск-менеджмент (макс 2% риска на сделку)
        4. Время дня (активные/неактивные часы)
        
        ПРАВИЛА:
        - Вход при |Z-score| > 2.0
        - Выход при |Z-score| < 0.5
        - Тейк-профит: +1.5%
        - Стоп-лосс: -1.0%
        
        ВЕРНИ JSON С СИГНАЛАМИ (или пустой массив если нет возможностей):
        """
        return prompt
    
    def _parse_ai_response(self, response: str) -> List[Dict]:
        """Парсит ответ ИИ в структурированные сигналы"""
        try:
            # Ищем JSON в ответе
            start_idx = response.find('{')
            end_idx = response.rfind('}') + 1
            
            if start_idx == -1 or end_idx == 0:
                return []
            
            json_str = response[start_idx:end_idx]
            data = json.loads(json_str)
            
            signals = []
            for signal in data.get("signals", []):
                # Валидация сигнала
                if all(key in signal for key in ['action', 'ticker', 'reason']):
                    signals.append({
                        'action': signal['action'],
                        'ticker': signal['ticker'],
                        'reason': signal['reason'],
                        'confidence': signal.get('confidence', 0.5),
                        'strategy': 'AI Core',
                        'take_profit': signal.get('take_profit'),
                        'stop_loss': signal.get('stop_loss')
                    })
            
            return signals
            
        except json.JSONDecodeError as e:
            logger.error(f"❌ ИИ вернул невалидный JSON: {response[:100]}...")
            return []
        except Exception as e:
            logger.error(f"❌ Ошибка парсинга ответа ИИ: {e}")
            return []
    
    def _create_cache_key(self, market_data: Dict) -> str:
        """Создаёт ключ для кэша на основе данных"""
        prices = market_data.get('prices', {})
        ratio = market_data.get('current_ratio', 0)
        return f"{prices.get('SBER', 0):.1f}_{prices.get('VTBR', 0):.3f}_{ratio:.4f}"
