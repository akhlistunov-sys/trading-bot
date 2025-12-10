# news_prefilter.py - ПОЛНЫЙ С ДОБАВЛЕННЫМ МЕТОДОМ
import logging
import re
from typing import Dict, List

logger = logging.getLogger(__name__)

class NewsPreFilter:
    """Ужесточенный пре-фильтр для финансовых новостей"""
    
    def __init__(self):
        # ЖЕСТКИЕ ОТСЕВЫ (технические/неторговые)
        self.reject_keywords = [
            # Технические работы
            'структурные ноты', 'технические работы', 'профилактические работы',
            'технический перерыв', 'изменение расписания', 'дополнительные условия',
            'уведомление о проведении', 'об итогах торгов', 'итоги торгов',
            'расписание торгов', 'о проведении торгов', 'профилактика',
            
            # Облигации/долги
            'облигаци', 'купон', 'погашен', 'дефолт', 'банкротств', 'долг',
            'заем', 'кредит', 'выпуск облигаций',
            
            # Неторговые
            'пресс-релиз', 'пресс релиз', 'анонс мероприятия',
            'благотворительн', 'спортивн', 'культурн', 'социальн',
            'мероприятие', 'конференц', 'форум', 'выставк'
        ]
        
        # ПРИНЯТИЕ (только торговые сигналы)
        self.accept_keywords = [
            # Компании
            'сбербанк', 'газпром', 'лукойл', 'норильск', 'яндекс', 'озон',
            'норникель', 'тинькофф', 'втб', 'магнит', 'татнефть', 'аэрофлот',
            'русгидро', 'интер рао', 'афк система', 'ростелеком',
            
            # Финансовые события
            'дивиденд', 'отчетность', 'квартал', 'финансовые результаты',
            'прибыль', 'выручка', 'убыток', 'ebitda', 'чистая прибыль',
            
            # Рынок
            'котировк', 'бирж', 'рынок', 'инвест', 'трейд', 'акци',
            'аналитик', 'прогноз', 'ожидан', 'целевая цена',
            'повышает', 'снижает', 'пересматривает',
            
            # Экономика
            'санкц', 'цб', 'центральный банк', 'минфин', 'правительств',
            'регулятор', 'надзор', 'штраф',
            
            # Товары
            'нефт', 'газ', 'золот', 'рубл', 'доллар', 'евro',
        ]
        
        # АБСОЛЮТНЫЙ отсев
        self.hard_reject_patterns = [
            r'структурные ноты',
            r'технические работы',
            r'итоги торгов.*облигациями',
            r'уведомление.*о проведении',
            r'изменение расписания',
            r'расписание торгов'
        ]
        
        # Статистика
        self.stats = {
            'total_checked': 0,
            'accepted': 0,
            'rejected': 0,
            'hard_rejected': 0
        }
        
        logger.info(f"🔧 NewsPreFilter инициализирован (УЖЕСТОЧЕННЫЙ)")
        logger.info(f"   Отсев: {len(self.reject_keywords)} ключевых слов")
        logger.info(f"   Принятие: {len(self.accept_keywords)} ключевых слов")
    
    def is_tradable(self, news_item: Dict) -> bool:
        """Определяет, является ли новость торговым сигналом"""
        self.stats['total_checked'] += 1
        
        title = news_item.get('title', '').lower()
        content = news_item.get('content', '').lower() or news_item.get('description', '').lower()
        full_text = f"{title} {content[:500]}"
        
        # 1. АБСОЛЮТНЫЙ отсев
        for pattern in self.hard_reject_patterns:
            if re.search(pattern, full_text, re.IGNORECASE):
                self.stats['hard_rejected'] += 1
                logger.debug(f"❌ Hard reject: {pattern[:40]}")
                return False
        
        # 2. Подсчет ключевых слов
        accept_count = sum(1 for kw in self.accept_keywords if kw in full_text)
        reject_count = sum(1 for kw in self.reject_keywords if kw in full_text)
        
        # 3. Решение
        if reject_count >= 3 and accept_count <= 1:
            self.stats['rejected'] += 1
            logger.debug(f"❌ Reject: reject={reject_count}, accept={accept_count}")
            return False
        
        if accept_count >= 1:
            self.stats['accepted'] += 1
            logger.debug(f"✅ Accept: accept={accept_count}")
            return True
        
        # MOEX источники - более строго
        if 'moex' in news_item.get('source', '').lower():
            if any(word in title for word in ['облигациями', 'структурные', 'итоги']):
                self.stats['rejected'] += 1
                return False
            if accept_count >= 3:
                self.stats['accepted'] += 1
                return True
        
        self.stats['rejected'] += 1
        logger.debug(f"❌ Default reject: accept={accept_count}")
        return False
    
    def get_filter_stats(self, sample_news: List[Dict] = None) -> Dict:
        """Получение статистики фильтрации - НОВЫЙ МЕТОД"""
        if sample_news:
            # Анализ сэмпла
            sample_stats = {
                'total': len(sample_news),
                'accepted': 0,
                'rejected': 0,
                'accept_rate': 0
            }
            
            for news in sample_news:
                if self.is_tradable(news):
                    sample_stats['accepted'] += 1
                else:
                    sample_stats['rejected'] += 1
            
            if sample_stats['total'] > 0:
                sample_stats['accept_rate'] = round((sample_stats['accepted'] / sample_stats['total']) * 100, 1)
            
            return {
                'overall_stats': self.stats,
                'sample_analysis': sample_stats,
                'accept_keywords_count': len(self.accept_keywords),
                'reject_keywords_count': len(self.reject_keywords),
                'hard_patterns_count': len(self.hard_reject_patterns)
            }
        
        # Простая статистика
        total = self.stats['total_checked']
        if total > 0:
            accept_rate = round((self.stats['accepted'] / total) * 100, 1)
            reject_rate = round((self.stats['rejected'] / total) * 100, 1)
        else:
            accept_rate = reject_rate = 0
        
        return {
            'total_checked': total,
            'accepted': self.stats['accepted'],
            'rejected': self.stats['rejected'],
            'hard_rejected': self.stats['hard_rejected'],
            'accept_rate_percent': accept_rate,
            'reject_rate_percent': reject_rate,
            'keywords': {
                'accept_count': len(self.accept_keywords),
                'reject_count': len(self.reject_keywords),
                'hard_patterns': len(self.hard_reject_patterns)
            }
        }
