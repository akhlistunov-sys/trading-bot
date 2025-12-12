# news_prefilter.py - УСИЛЕННЫЙ ПРЕФИЛЬТР
import logging
import re
from typing import Dict

logger = logging.getLogger(__name__)

class NewsPreFilter:
    def __init__(self):
        self.hard_reject_patterns = [
            r'удар\s+по', r'авария', r'теракт', r'пожар', r'сбой',
            r'структурные\s+ноты', r'технические\s+работы',
            r'итоги\s+торгов.*облигациями', r'уведомление.*о\s+проведении',
            r'изменение\s+расписания', r'расписание\s+торгов',
            r'press\s+release', r'appointment\s+of',
            r'корпоративная.*ответственность', r'it\s+update',
            r'программное\s+обеспечение.*обновление'
        ]
        self.financial_keywords = [
            'дивиденд', 'отчетность', 'квартал', 'прибыль', 'выручка', 'убыток',
            'слияние', 'поглощение', 'рекомендация', 'аналитик', 'прогноз',
            'санкц', 'регулятор', 'цб', 'минфин', 'штраф', 'дивидендная политика',
            'роспуск', 'кредит', 'долг', 'реструктуризация', 'банкротство'
        ]
        logger.info("🔧 NewsPreFilter инициализирован")

    def is_tradable(self, news_item: Dict) -> bool:
        title = news_item.get('title', '').lower()
        content = news_item.get('content', '').lower() or news_item.get('description', '').lower()
        full_text = f"{title} {content[:500]}"

        for pattern in self.hard_reject_patterns:
            if re.search(pattern, full_text, re.IGNORECASE):
                logger.debug(f"❌ Hard reject: {pattern[:40]}")
                return False

        has_financial = any(keyword in full_text for keyword in self.financial_keywords)
        if has_financial:
            logger.debug(f"✅ Accept: финансовые термины найдены")
            return True

        logger.debug(f"❌ Reject: нет финансовых терминов")
        return False
