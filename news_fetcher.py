import os
import aiohttp
import asyncio
import logging
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from typing import List, Dict, Optional
import json

logger = logging.getLogger(__name__)

class NewsFetcher:
    """Сборщик новостей с улучшенной фильтрацией"""
    
    def __init__(self):
        self.mediastack_key = os.getenv("mediastackAPI")
        self.zenserp_key = os.getenv("ZENSEPTAPI")
        
        # Улучшенные RSS источники
        self.rss_feeds = {
            # ФИНАНСОВЫЕ источники
            "moex_main": "https://www.moex.com/export/news.aspx?lang=ru&cat=1",
            "moex_news": "https://www.moex.com/export/news.aspx?lang=ru&cat=100",
            "rbc_finance": "https://rssexport.rbc.ru/rbcnews/news/20/full.rss",
            "rbc_economics": "https://rssexport.rbc.ru/rbcnews/news/2/full.rss",
            "investing_russia": "https://ru.investing.com/rss/news.rss",
            # ДОБАВЛЕНО: Финансовые блоги
            "banki_news": "https://www.banki.ru/xml/news.rss",
            "quote_russia": "https://quote.rbc.ru/rss/news.rss"
        }
        
        # Фильтр ключевых слов ДЛЯ ФИНАНСОВЫХ новостей
        self.financial_keywords = [
            'акци', 'акций', 'акциями', 'дивиденд', 'дивиденды',
            'отчет', 'квартал', 'прибыль', 'выручка', 'убыток',
            'сбербанк', 'газпром', 'лукойл', 'норникель', 'ростелеком',
            'мосбиржа', 'втб', 'тинькофф', 'яндекс', 'озон',
            'бирж', 'котировк', 'инвест', 'трейд', 'портфел',
            'рубл', 'доллар', 'евро', 'нефт', 'газ', 'золот',
            'эмисси', 'облигац', 'фонд', 'рынок', 'экономик',
            'санкц', 'регулятор', 'цб', 'минфин', 'правительств',
            'покупк', 'продаж', 'сделка', 'слияни', 'поглощен',
            'рекоменду', 'аналитик', 'прогноз', 'ожидан', 'целев'
        ]
        
        logger.info("📰 NewsFetcher инициализирован")
        logger.info(f"🔑 Финансовых RSS источников: {len(self.rss_feeds)}")
    
    def _is_financial_news(self, text: str) -> bool:
        """Фильтрация ТОЛЬКО финансовых новостей"""
        text_lower = text.lower()
        return any(keyword in text_lower for keyword in self.financial_keywords)
    
    async def fetch_rss_feed(self, url: str, source_name: str) -> List[Dict]:
        """Получение новостей из RSS с фильтрацией"""
        articles = []
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=10, ssl=False) as response:
                    if response.status == 200:
                        xml_content = await response.text()
                        
                        try:
                            root = ET.fromstring(xml_content)
                        except:
                            # Попробуем другой парсер если XML битый
                            return articles
                        
                        for item in root.findall('.//item'):
                            title_elem = item.find('title')
                            description_elem = item.find('description')
                            link_elem = item.find('link')
                            pub_date_elem = item.find('pubDate')
                            
                            if title_elem is not None:
                                title = title_elem.text or ''
                                description = description_elem.text if description_elem is not None else ''
                                
                                # Объединяем текст для фильтрации
                                full_text = f"{title} {description}".lower()
                                
                                # Фильтруем ТОЛЬКО финансовые новости
                                if self._is_financial_news(full_text):
                                    articles.append({
                                        'id': f"{source_name}_{pub_date_elem.text if pub_date_elem else ''}_{len(articles)}",
                                        'source': source_name,
                                        'title': title,
                                        'description': description,
                                        'content': description,
                                        'url': link_elem.text if link_elem is not None else '',
                                        'published_at': pub_date_elem.text if pub_date_elem else '',
                                        'source_name': source_name,
                                        'fetched_at': datetime.now().isoformat(),
                                        'is_financial': True
                                    })
                        
                        logger.info(f"   ✅ {source_name}: {len(articles)} финансовых новостей")
            
        except asyncio.TimeoutError:
            logger.warning(f"⏰ {source_name}: таймаут")
        except Exception as e:
            logger.debug(f"🔧 {source_name} ошибка: {str(e)[:50]}")
        
        return articles
    
    async def fetch_all_news(self) -> List[Dict]:
        """Получение ВСЕХ новостей из ВСЕХ RSS параллельно"""
        logger.info("📥 Сбор финансовых новостей из RSS...")
        
        # Запускаем все RSS параллельно
        tasks = []
        for source_name, url in self.rss_feeds.items():
            tasks.append(self.fetch_rss_feed(url, source_name))
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Собираем все статьи
        all_articles = []
        for i, result in enumerate(results):
            source_name = list(self.rss_feeds.keys())[i]
            if isinstance(result, list):
                all_articles.extend(result)
                logger.info(f"   📊 {source_name}: {len(result)} финансовых новостей")
            elif isinstance(result, Exception):
                logger.warning(f"   ⚠️ {source_name}: ошибка")
        
        # Удаляем дубликаты по заголовку
        unique_articles = []
        seen_titles = set()
        
        for article in all_articles:
            title_key = article['title'][:80].lower().strip()
            if title_key and title_key not in seen_titles:
                seen_titles.add(title_key)
                unique_articles.append(article)
        
        removed = len(all_articles) - len(unique_articles)
        if removed > 0:
            logger.info(f"🔄 Удалено {removed} дубликатов")
        
        # Сортируем по времени (новые сначала)
        unique_articles.sort(
            key=lambda x: x.get('published_at', ''),
            reverse=True
        )
        
        logger.info(f"📊 ИТОГО: {len(unique_articles)} финансовых новостей")
        return unique_articles[:25]  # Ограничиваем 25
    
    def get_source_stats(self) -> Dict:
        """Статистика по источникам"""
        return {
            'rss_feeds_count': len(self.rss_feeds),
            'financial_keywords': len(self.financial_keywords),
            'mediastack_configured': bool(self.mediastack_key),
            'zenserp_configured': bool(self.zenserp_key)
        }
