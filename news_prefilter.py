# news_prefilter.py - УСИЛЕННЫЙ ПРЕФИЛЬТР
import logging
import re
from typing import Dict, List

logger = logging.getLogger(__name__)

class NewsPreFilter:
    """Ужесточенный пре-фильтр для финансовых новостей - УСИЛЕННЫЙ"""
    
    def __init__(self):
        # ЖЕСТКИЕ ОТСЕВЫ (технические/неторговые) - РАСШИРЕННЫЙ
        self.reject_keywords = [
            # Технические работы
            'структурные ноты', 'технические работы', 'профилактические работы',
            'технический перерыв', 'изменение расписания', 'дополнительные условия',
            'уведомление о проведении', 'об итогах торгов', 'итоги торгов',
            'расписание торгов', 'о проведении торгов', 'профилактика',
            
            # Облигации/долги
            'облигаци', 'купон', 'погашен', 'дефолт', 'банкротств', 'долг',
            'заем', 'кредит', 'выпуск облигаций', 'bond', 'coupon', 'debt',
            
            # Неторговые
            'пресс-релиз', 'пресс релиз', 'анонс мероприятия',
            'благотворительн', 'спортивн', 'культурн', 'социальн',
            'мероприятие', 'конференц', 'форум', 'выставк', 'press release',
            'event', 'conference', 'forum', 'exhibition',
            
            # Новости компаний (не торговые)
            'назначен', 'уволился', 'перешел', 'покинул', 'возглавит',
            'appointed', 'resigned', 'joined', 'left', 'appointment',
            
            # Корпоративные (не торговые)
            'социальная ответственность', 'экологическ', 'устойчивое развитие',
            'корпоративн', 'социальный проект', 'social responsibility',
            
            # Технологии (не торговые)
            'ит-', 'цифров', 'технологи', 'программ', 'софт', 'it', 'digital',
            'software', 'update', 'release'
        ]
        
        # ПРИНЯТИЕ (только торговые сигналы) - РАСШИРЕННЫЙ
        self.accept_keywords = [
            # Ключевые компании
            'сбербанк', 'газпром', 'лукойл', 'норильск', 'яндекс', 'озон',
            'норникель', 'тинькофф', 'втб', 'магнит', 'татнефть', 'аэрофлот',
            'русгидро', 'интер рао', 'афк система', 'ростелеком',
            'sberbank', 'gazprom', 'lukoil', 'nornickel', 'yandex', 'ozon',
            'tinkoff', 'vtb', 'magnit', 'tatneft', 'aeroflot',
            
            # Финансовые события - КЛЮЧЕВЫЕ!
            'дивиденд', 'отчетность', 'квартал', 'финансовые результаты',
            'прибыль', 'выручка', 'убыток', 'ebitda', 'чистая прибыль',
            'dividend', 'earnings', 'quarter', 'financial results',
            'profit', 'revenue', 'loss', 'net income',
            
            # Рынок и трейдинг
            'котировк', 'бирж', 'рынок', 'инвест', 'трейд', 'акци',
            'аналитик', 'прогноз', 'ожидан', 'целевая цена',
            'повышает', 'снижает', 'пересматривает', 'рекомендует',
            'stock', 'share', 'market', 'exchange', 'invest', 'trade',
            'analyst', 'forecast', 'expect', 'target price', 'raises',
            'cuts', 'downgrades', 'upgrades', 'recommends',
            
            # Экономика и регуляторы
            'санкц', 'цб', 'центральный банк', 'минфин', 'правительств',
            'регулятор', 'надзор', 'штраф', 'санкции', 'санкцион',
            'sanctions', 'central bank', 'ministry of finance', 'regulator',
            
            # Товары и валюта
            'нефт', 'газ', 'золот', 'рубл', 'доллар', 'евро',
            'oil', 'gas', 'gold', 'ruble', 'dollar', 'euro',
            
            # Корпоративные действия (торговые)
            'слияние', 'поглощение', 'приобретение', 'выкуп',
            'merger', 'acquisition', 'takeover', 'buyout',
            
            # Рекомендации аналитиков
            'купить', 'продать', 'держать', 'перевес', 'нейтрально',
            'buy', 'sell', 'hold', 'overweight', 'neutral'
        ]
        
        # АБСОЛЮТНЫЙ отсев - РАСШИРЕННЫЙ
        self.hard_reject_patterns = [
            r'структурные ноты',
            r'технические работы',
            r'итоги торгов.*облигациями',
            r'уведомление.*о проведении',
            r'изменение расписания',
            r'расписание торгов',
            r'press release',
            r'appointment of',
            r'corporate social responsibility',
            r'it update',
            r'software release'
        ]
        
        # Статистика
        self.stats = {
            'total_checked': 0,
            'accepted': 0,
            'rejected': 0,
            'hard_rejected': 0,
            'accept_keywords_found': 0,
            'reject_keywords_found': 0
        }
        
        logger.info(f"🔧 NewsPreFilter инициализирован (УСИЛЕННЫЙ)")
        logger.info(f"   Отсев: {len(self.reject_keywords)} ключевых слов")
        logger.info(f"   Принятие: {len(self.accept_keywords)} ключевых слов")
        logger.info(f"   Жестких паттернов: {len(self.hard_reject_patterns)}")
    
    def is_tradable(self, news_item: Dict) -> bool:
        """Определяет, является ли новость торговым сигналом - УСИЛЕННЫЙ"""
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
        
        # 2. Подсчет ключевых слов (УСИЛЕННЫЙ)
        accept_count = sum(1 for kw in self.accept_keywords if kw in full_text)
        reject_count = sum(1 for kw in self.reject_keywords if kw in full_text)
        
        self.stats['accept_keywords_found'] += accept_count
        self.stats['reject_keywords_found'] += reject_count
        
        # 3. УСИЛЕННАЯ логика принятия
        
        # Критерий 1: Много reject-слов
        if reject_count >= 3:
            self.stats['rejected'] += 1
            logger.debug(f"❌ Reject: много reject-слов ({reject_count})")
            return False
        
        # Критерий 2: Мало accept-слов
        if accept_count == 0:
            self.stats['rejected'] += 1
            logger.debug(f"❌ Reject: нет accept-слов")
            return False
        
        # Критерий 3: Баланс accept/reject
        if reject_count > accept_count:
            self.stats['rejected'] += 1
            logger.debug(f"❌ Reject: reject({reject_count}) > accept({accept_count})")
            return False
        
        # Критерий 4: Для коротких новостей нужны ключевые слова
        if len(full_text) < 100 and accept_count < 2:
            self.stats['rejected'] += 1
            logger.debug(f"❌ Reject: короткая новость без ключевых слов")
            return False
        
        # Критерий 5: Проверка источников
        source = news_item.get('source', '').lower()
        if 'investing' in source and accept_count < 2:
            # Investing.com часто спам - нужны четкие сигналы
            self.stats['rejected'] += 1
            logger.debug(f"❌ Reject: investing.com без четких сигналов")
            return False
        
        # ВСЕ проверки пройдены
        self.stats['accepted'] += 1
        logger.debug(f"✅ Accept: accept={accept_count}, reject={reject_count}")
        return True
    
    def get_filter_stats(self, sample_news: List[Dict] = None) -> Dict:
        """Получение статистики фильтрации"""
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
                'keywords_stats': {
                    'accept_count': len(self.accept_keywords),
                    'reject_count': len(self.reject_keywords),
                    'avg_accept_per_news': round(self.stats['accept_keywords_found'] / max(1, self.stats['total_checked']), 2),
                    'avg_reject_per_news': round(self.stats['reject_keywords_found'] / max(1, self.stats['total_checked']), 2)
                },
                'hard_patterns_count': len(self.hard_reject_patterns)
            }
        
        # Простая статистика
        total = self.stats['total_checked']
        if total > 0:
            accept_rate = round((self.stats['accepted'] / total) * 100, 1)
            reject_rate = round((self.stats['rejected'] / total) * 100, 1)
            hard_reject_rate = round((self.stats['hard_rejected'] / total) * 100, 1)
        else:
            accept_rate = reject_rate = hard_reject_rate = 0
        
        return {
            'total_checked': total,
            'accepted': self.stats['accepted'],
            'rejected': self.stats['rejected'],
            'hard_rejected': self.stats['hard_rejected'],
            'accept_rate_percent': accept_rate,
            'reject_rate_percent': reject_rate,
            'hard_reject_rate_percent': hard_reject_rate,
            'keywords_found': {
                'accept_total': self.stats['accept_keywords_found'],
                'reject_total': self.stats['reject_keywords_found']
            }
        }
