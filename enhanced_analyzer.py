# enhanced_analyzer.py - ИСПРАВЛЕННЫЙ
import re
import logging
from typing import List, Dict, Set
from datetime import datetime

logger = logging.getLogger(__name__)

class EnhancedAnalyzer:
    """Улучшенный анализатор с полным словарём тикеров и определением событий"""
    
    def __init__(self):
        # ==================== ПОЛНЫЙ СЛОВАРЬ ТИКЕРОВ MOEX ====================
        self.TICKER_MAP = self._create_full_ticker_map()
        
        # Словари для определения событий
        self.EVENT_KEYWORDS = {
            'dividend': [
                'дивиденд', 'дивиденды', 'дивидендных', 'дивидендную',
                'выплата дивидендов', 'рекомендация дивидендов',
                'совет директоров рекомендовал', 'утвердил дивиденды',
                'дивидендная политика', 'размер дивидендов'
            ],
            'earnings_report': [
                'отчетность', 'квартальный отчет', 'годовой отчет',
                'финансовые результаты', 'прибыль', 'выручка', 'убыток',
                'ebitda', 'чистая прибыль', 'операционная прибыль',
                'превысил ожидания', 'не достиг ожиданий',
                'квартал', 'полугодие', 'девять месяцев'
            ],
            'merger_acquisition': [
                'слияние', 'поглощение', 'приобретение', 'выкуп',
                'консолидация', 'реорганизация', 'реструктуризация',
                'поглощает', 'приобретает', 'выкупает'
            ],
            'regulatory': [
                'санкции', 'санкцион', 'ограничения', 'запрет',
                'цб', 'центральный банк', 'банк россии',
                'минфин', 'правительство', 'регулятор',
                'надзор', 'инспекция', 'проверка',
                'штраф', 'наказание', 'предписание'
            ],
            'market_update': [
                'котировки', 'торги', 'бирж', 'рынок',
                'аналитик', 'эксперт', 'прогноз',
                'рекомендует', 'советует', 'ожидает'
            ]
        }
        
        # Словари тональности
        self.POSITIVE_WORDS = [
            'рост', 'увелич', 'повыш', 'рекорд', 'успех',
            'прогресс', 'улучшен', 'позитив', 'оптимизм',
            'сильн', 'стабильн', 'прибыль', 'доход',
            'превысил', 'выше ожиданий', 'улучшение',
            'расширение', 'развитие', 'инноваци'
        ]
        
        self.NEGATIVE_WORDS = [
            'падение', 'снижен', 'убыток', 'сокращен',
            'проблем', 'риск', 'сложност', 'кризис',
            'негатив', 'ухудшен', 'слаб', 'нестабильн',
            'потеря', 'обвал', 'коллапс', 'дефолт',
            'ниже ожиданий', 'ухудшение', 'сокращение'
        ]
        
        logger.info(f"🧠 EnhancedAnalyzer инициализирован")
        logger.info(f"   Тикеров: {len(self.TICKER_MAP)}")
        logger.info(f"   Типов событий: {len(self.EVENT_KEYWORDS)}")
    
    def _create_full_ticker_map(self) -> Dict[str, str]:
        """Создание полного словаря тикеров MOEX"""
        ticker_map = {}
        
        # Банки и финансы
        banks = {
            'сбербанк': 'SBER', 'сбер': 'SBER', 'сбербанка': 'SBER',
            'втб': 'VTBR', 'втб банк': 'VTBR',
            'тинькофф': 'TCSG', 'тинькофф банк': 'TCSG',
            'альфа банк': 'ALFA', 'альфа-банк': 'ALFA',
            'открытие': 'FCIT', 'банк открытие': 'FCIT',
            'россельхозбанк': 'RUGR', 'рсхб': 'RUGR',
            'совкомбанк': 'SVCB', 'совком': 'SVCB',
            'мкб': 'CBOM', 'московский кредитный банк': 'CBOM',
            'система': 'AFKS', 'афк система': 'AFKS'
        }
        
        # Нефть и газ
        oil_gas = {
            'газпром': 'GAZP', 'газ': 'GAZP',
            'лукойл': 'LKOH', 'лук': 'LKOH',
            'роснефть': 'ROSN', 'роспефть': 'ROSN',
            'новатэк': 'NVTK', 'novatek': 'NVTK',
            'татнефть': 'TATN', 'tatneft': 'TATN',
            'башнефть': 'BANE', 'bashneft': 'BANE',
            'сургутнефтегаз': 'SNGS', 'сургут': 'SNGS',
            'транснефть': 'TRNFP', 'transneft': 'TRNFP'
        }
        
        # Металлургия и добыча
        metals = {
            'норильский никель': 'GMKN', 'норникель': 'GMKN',
            'алроса': 'ALRS', 'алросы': 'ALRS',
            'полиметалл': 'POLY', 'polymetal': 'POLY',
            'северсталь': 'CHMF', 'severstal': 'CHMF',
            'нлмк': 'NLMK', 'nlmk': 'NLMK',
            'ммк': 'MAGN', 'магнитогорск': 'MAGN',
            'распадская': 'RASP', 'распадской': 'RASP',
            'полюс': 'PLZL', 'polyus': 'PLZL'
        }
        
        # Розничная торговля
        retail = {
            'магнит': 'MGNT', 'магнита': 'MGNT',
            'х5 ритейл': 'FIVE', 'x5': 'FIVE',
            'лэнта': 'LNTA', 'lenta': 'LNTA',
            'озон': 'OZON', 'ozon': 'OZON',
            'яндекс': 'YNDX', 'yandex': 'YNDX',
            'м.видео': 'MVID', 'мвидео': 'MVID',
            'детский мир': 'DSKY', 'детского мира': 'DSKY',
            'черкизово': 'GCHE', 'черкизова': 'GCHE',
            'окей': 'OKEY', 'oke': 'OKEY'
        }
        
        # Технологии
        tech = {
            'яндекс': 'YNDX', 'yandex': 'YNDX',
            'озон': 'OZON', 'ozon': 'OZON',
            'циан': 'CIAN', 'cian': 'CIAN',
            'позитив': 'POSI', 'positive': 'POSI',
            'вк': 'VKCO', 'vk': 'VKCO',
            'киви': 'QIWI', 'qiwi': 'QIWI'
        }
        
        # Энергетика
        energy = {
            'интер рао': 'IRAO', 'inter rao': 'IRAO',
            'русгидро': 'HYDR', 'rushydro': 'HYDR',
            'россети': 'RSTI', 'rosseti': 'RSTI',
            'фск': 'FEES', 'fsk': 'FEES',
            'эн+': 'ENPL', 'en+': 'ENPL',
            'татэнерго': 'TGKA', 'tgc': 'TGKA'
        }
        
        # Объединяем все словари
        all_dicts = [banks, oil_gas, metals, retail, tech, energy]
        
        for d in all_dicts:
            ticker_map.update(d)
        
        # Добавляем общие термины
        general_terms = {
            'мосбиржа': 'MOEX', 'moex': 'MOEX',
            'ростелеком': 'RTKM', 'rostelecom': 'RTKM',
            'фосагро': 'PHOR', 'phosagro': 'PHOR',
            'аэрофлот': 'AFLT', 'aeroflot': 'AFLT',
            'глобалтранс': 'GLTR', 'globaltrans': 'GLTR',
            'пик': 'PIKK', 'pikk': 'PIKK',
            'лср': 'LSRG', 'lsr': 'LSRG',
            'эталон': 'ETLN', 'etalon': 'ETLN',
            'самолет': 'SMLT', 'samolyot': 'SMLT'
        }
        
        ticker_map.update(general_terms)
        
        return ticker_map
    
    def analyze_news(self, news_item: Dict) -> Dict:
        """Полный анализ новости с определением событий"""
        title = news_item.get('title', '').lower()
        content = news_item.get('content', '').lower() or news_item.get('description', '').lower()
        text = title + ' ' + content[:500]  # Ограничиваем для производительности
        
        # 1. Извлечение тикеров
        tickers = self._extract_tickers(text)
        
        # 2. Определение типа события
        event_type, event_confidence = self._detect_event_type(text)
        
        # 3. Анализ тональности
        sentiment, sentiment_score = self._analyze_sentiment(text)
        
        # 4. Оценка влияния
        impact_score = self._calculate_impact_score(
            event_type, event_confidence, 
            sentiment, sentiment_score,
            len(tickers)
        )
        
        # 5. Релевантность
        relevance_score = self._calculate_relevance_score(tickers, event_type, impact_score)
        
        # 6. Confidence
        confidence = self._calculate_confidence(
            event_confidence, sentiment_score,
            len(tickers), relevance_score
        )
        
        # 7. Суммаризация
        summary = self._generate_summary(tickers, event_type, sentiment, impact_score)
        
        return {
            'news_id': news_item.get('id', ''),
            'news_title': news_item.get('title', ''),
            'news_source': news_item.get('source', ''),
            'tickers': tickers,
            'event_type': event_type,
            'event_confidence': event_confidence,
            'impact_score': impact_score,
            'relevance_score': relevance_score,
            'sentiment': sentiment,
            'sentiment_score': sentiment_score,
            'horizon': 'short_term',
            'summary': summary,
            'confidence': confidence,
            'simple_analysis': True,
            'ai_provider': 'enhanced',
            'analysis_timestamp': datetime.now().isoformat()
        }
    
    def _extract_tickers(self, text: str) -> List[str]:
        """Извлечение тикеров из текста"""
        found_tickers = set()
        
        for keyword, ticker in self.TICKER_MAP.items():
            if keyword in text:
                found_tickers.add(ticker)
        
        # Удаляем дубликаты и возвращаем список
        return list(found_tickers)
    
    def _detect_event_type(self, text: str) -> tuple:
        """Определение типа события"""
        event_scores = {}
        
        for event_type, keywords in self.EVENT_KEYWORDS.items():
            score = 0
            for keyword in keywords:
                if keyword in text:
                    score += 1
            
            event_scores[event_type] = score
        
        # Находим событие с максимальным счётом
        max_event = max(event_scores, key=event_scores.get)
        max_score = event_scores[max_event]
        
        # Нормализуем confidence (0-1)
        total_keywords = len(self.EVENT_KEYWORDS[max_event])
        confidence = min(1.0, max_score / max(total_keywords, 1))
        
        # Если confidence слишком низкий, считаем market_update
        if confidence < 0.3:
            return 'market_update', 0.3
        
        return max_event, confidence
    
    def _analyze_sentiment(self, text: str) -> tuple:
        """Анализ тональности"""
        positive_count = sum(1 for word in self.POSITIVE_WORDS if word in text)
        negative_count = sum(1 for word in self.NEGATIVE_WORDS if word in text)
        
        total = positive_count + negative_count
        
        if total == 0:
            return 'neutral', 0.5
        
        sentiment_score = positive_count / total
        
        if sentiment_score > 0.6:
            return 'positive', sentiment_score
        elif sentiment_score < 0.4:
            return 'negative', sentiment_score
        else:
            return 'neutral', 0.5
    
    def _calculate_impact_score(self, event_type: str, event_confidence: float,
                               sentiment: str, sentiment_score: float,
                               tickers_count: int) -> int:
        """Расчёт силы влияния на цену (1-10)"""
        score = 5  # Базовый
        
        # Влияние типа события
        event_weights = {
            'dividend': 3,
            'earnings_report': 3,
            'merger_acquisition': 2,
            'regulatory': 2,
            'market_update': 0
        }
        
        score += event_weights.get(event_type, 0)
        
        # Влияние confidence
        score += int(event_confidence * 2)
        
        # Влияние тональности
        if sentiment != 'neutral':
            score += 1
        
        # Влияние количества тикеров
        if tickers_count > 0:
            score += min(2, tickers_count)
        
        return min(10, max(1, score))
    
    def _calculate_relevance_score(self, tickers: List[str], 
                                  event_type: str, impact_score: int) -> int:
        """Расчёт релевантности новости для трейдинга"""
        score = 40  # Базовый
        
        if tickers:
            score += 30
        
        if event_type != 'market_update':
            score += 20
        
        if impact_score >= 7:
            score += 10
        
        return min(100, score)
    
    def _calculate_confidence(self, event_confidence: float, sentiment_score: float,
                             tickers_count: int, relevance_score: int) -> float:
        """Расчёт общей confidence (0-1)"""
        confidence = 0.4  # Базовый
        
        confidence += event_confidence * 0.3
        
        # Если есть тикеры
        if tickers_count > 0:
            confidence += 0.2
        
        # Если релевантность высокая
        if relevance_score >= 70:
            confidence += 0.1
        
        return min(0.9, confidence)
    
    def _generate_summary(self, tickers: List[str], event_type: str,
                         sentiment: str, impact_score: int) -> str:
        """Генерация текстового описания анализа"""
        if not tickers:
            return f"Тикеры не найдены, {event_type}, {sentiment}"
        
        tickers_str = ', '.join(tickers[:3])
        
        event_names = {
            'dividend': 'дивиденды',
            'earnings_report': 'отчетность',
            'merger_acquisition': 'слияния/поглощения',
            'regulatory': 'регуляторные новости',
            'market_update': 'рыночные новости'
        }
        
        sentiment_names = {
            'positive': 'позитивная',
            'negative': 'негативная',
            'neutral': 'нейтральная'
        }
        
        event_name = event_names.get(event_type, event_type)
        sentiment_name = sentiment_names.get(sentiment, sentiment)
        
        return f"{tickers_str}: {event_name}, {sentiment_name} тональность, влияние: {impact_score}/10"
    
    def quick_filter(self, news_item: Dict) -> bool:
        """Быстрая предфильтрация финансовых новостей - УПРОЩЕННАЯ ВЕРСИЯ"""
        
        # УПРОЩАЕМ: В тестовом режиме пропускаем больше новостей
        title = news_item.get('title', '').lower()
        content = news_item.get('content', '').lower() or news_item.get('description', '').lower()
        text = title + ' ' + content[:200]
        
        # 1. Проверяем наличие финансовых терминов (русские и английские)
        financial_terms = [
            # Русские
            'акци', 'дивиденд', 'отчет', 'прибыль', 'выручка',
            'квартал', 'финанс', 'сделк', 'слияни', 'поглощен',
            'рост', 'падение', 'банк', 'компани', 'рынок',
            'бирж', 'инвест', 'трейд',
            # Английские (для investing.com)
            'stock', 'share', 'dividend', 'earnings', 'profit',
            'revenue', 'quarter', 'financial', 'deal', 'merger',
            'acquisition', 'growth', 'decline', 'bank', 'company',
            'market', 'exchange', 'invest', 'trade'
        ]
        
        has_financial = any(term in text for term in financial_terms)
        
        # 2. Проверяем наличие тикеров или названий компаний
        has_ticker = False
        for keyword in self.TICKER_MAP.keys():
            if keyword in text:
                has_ticker = True
                break
        
        # 3. ЛОГИКА ПРИНЯТИЯ (УПРОЩЕННАЯ):
        # - Если есть финансовые термины ИЛИ тикеры → пропускаем
        # - В тестовом режиме пропускаем больше
        
        trading_mode = 'AGGRESSIVE_TEST'  # Можно получить из os.getenv
        
        if trading_mode == 'AGGRESSIVE_TEST':
            # В агрессивном тестовом режиме пропускаем почти все
            if has_financial or has_ticker:
                return True
            # Даже если нет финансовых терминов, но есть длинный текст — пробуем
            if len(text) > 50:  # Не очень короткие новости
                return True
        
        # Обычный режим
        return has_financial or has_ticker
