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
    """Сборщик новостей из различных источников с резервированием"""
    
    def __init__(self):
        # Ключи API - Mediastack теперь основной, Zenserp резервный
        self.mediastack_key = os.getenv("mediastackAPI")
        self.zenserp_key = os.getenv("ZENSEPTAPI")
        
        # Кэш для новостей
        self.news_cache = {}
        
        # Источники RSS
        self.moex_feeds = {
            "all_news": "https://moex.com/export/news.aspx?cat=100",
            "main_news": "https://moex.com/export/news.aspx?cat=101"
        }
        
        # Резервный RSS РБК
        self.rbc_feeds = [
            "https://rssexport.rbc.ru/rbcnews/news/30/full.rss",  # Главные новости
            "https://rssexport.rbc.ru/rbcnews/news/20/full.rss"   # Финансы
        ]
        
        logger.info("📰 NewsFetcher инициализирован")
        logger.info(f"🔑 Источники: Mediastack={'✅' if self.mediastack_key else '❌'}, "
                   f"Zenserp={'✅' if self.zenserp_key else '❌'}, "
                   f"MOEX RSS=✅, RBC RSS=✅")
    
    async def fetch_mediastack(self) -> List[Dict]:
        """ОСНОВНОЙ ИСТОЧНИК: Получение новостей через Mediastack API"""
        if not self.mediastack_key:
            logger.warning("⚠️ Mediastack ключ не найден")
            return []
        
        url = "http://api.mediastack.com/v1/news"
        
        params = {
            'access_key': self.mediastack_key,
            'languages': 'ru',
            'keywords': 'акции дивиденды отчетность прибыль биржа Мосбиржа',
            'limit': 25,
            'sort': 'published_desc',
            'countries': 'ru',
            'categories': 'business',
            'date': (datetime.now() - timedelta(hours=24)).strftime('%Y-%m-%d')
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params, timeout=15) as response:
                    if response.status == 200:
                        data = await response.json()
                        
                        # Проверка на ошибки API
                        if 'error' in data:
                            error_msg = data['error'].get('message', 'Unknown error')
                            logger.error(f"❌ Mediastack API error: {error_msg}")
                            return []
                        
                        articles = []
                        
                        for article in data.get('data', []):
                            articles.append({
                                'id': f"mediastack_{article.get('published_at', '')}_{len(articles)}",
                                'source': 'Mediastack',
                                'title': article.get('title', ''),
                                'description': article.get('description', ''),
                                'content': article.get('description', ''),  # Используем description как content
                                'url': article.get('url', ''),
                                'published_at': article.get('published_at', ''),
                                'author': article.get('author', ''),
                                'source_name': article.get('source', ''),
                                'category': article.get('category', 'business'),
                                'fetched_at': datetime.now().isoformat()
                            })
                        
                        logger.info(f"✅ Mediastack: получено {len(articles)} новостей")
                        return articles
                    else:
                        logger.error(f"❌ Mediastack HTTP ошибка: {response.status}")
                        return []
                        
        except asyncio.TimeoutError:
            logger.error("❌ Mediastack: таймаут запроса")
            return []
        except Exception as e:
            logger.error(f"❌ Ошибка Mediastack: {str(e)[:100]}")
            return []
    
    async def fetch_zenserp(self) -> List[Dict]:
        """РЕЗЕРВНЫЙ ИСТОЧНИК: Получение новостей через Zenserp (Google News)"""
        if not self.zenserp_key:
            logger.warning("⚠️ Zenserp ключ не найден")
            return []
        
        url = "https://app.zenserp.com/api/v2/search"
        headers = {'apikey': self.zenserp_key}
        
        params = {
            'q': 'акции Россия биржа Мосбиржа дивиденды квартал отчетность',
            'tbm': 'nws',
            'num': 15,
            'hl': 'ru',
            'gl': 'ru',
            'tbs': 'qdr:d'  # За последние 24 часа
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers, params=params, timeout=15) as response:
                    if response.status == 200:
                        data = await response.json()
                        articles = []
                        
                        if 'news_results' in data:
                            for item in data['news_results']:
                                articles.append({
                                    'id': f"zenserp_{item.get('date', '')}_{len(articles)}",
                                    'source': 'Zenserp',
                                    'title': item.get('title', ''),
                                    'description': item.get('snippet', ''),
                                    'url': item.get('url', ''),
                                    'published_at': item.get('date', ''),
                                    'source_name': item.get('source', 'Unknown'),
                                    'fetched_at': datetime.now().isoformat()
                                })
                        
                        logger.info(f"✅ Zenserp: получено {len(articles)} новостей")
                        return articles
                    else:
                        logger.error(f"❌ Zenserp ошибка: {response.status}")
                        return []
                        
        except asyncio.TimeoutError:
            logger.error("❌ Zenserp: таймаут запроса")
            return []
        except Exception as e:
            logger.error(f"❌ Ошибка Zenserp: {e}")
            return []
    
    async def fetch_moex_rss(self) -> List[Dict]:
        """ИСТОЧНИК С БИРЖИ: Получение новостей с MOEX RSS"""
        articles = []
        
        try:
            for feed_name, feed_url in self.moex_feeds.items():
                async with aiohttp.ClientSession() as session:
                    async with session.get(feed_url, timeout=10) as response:
                        if response.status == 200:
                            xml_content = await response.text()
                            
                            # Парсинг RSS XML
                            root = ET.fromstring(xml_content)
                            
                            for item in root.findall('.//item'):
                                title_elem = item.find('title')
                                description_elem = item.find('description')
                                link_elem = item.find('link')
                                pub_date_elem = item.find('pubDate')
                                
                                if title_elem is not None:
                                    articles.append({
                                        'id': f"moex_{pub_date_elem.text if pub_date_elem else ''}_{len(articles)}",
                                        'source': 'MOEX',
                                        'feed_type': feed_name,
                                        'title': title_elem.text or '',
                                        'description': description_elem.text if description_elem is not None else '',
                                        'content': description_elem.text if description_elem is not None else '',
                                        'url': link_elem.text if link_elem is not None else '',
                                        'published_at': pub_date_elem.text if pub_date_elem is not None else '',
                                        'source_name': 'Московская биржа',
                                        'fetched_at': datetime.now().isoformat()
                                    })
            
            logger.info(f"✅ MOEX RSS: получено {len(articles)} новостей")
            return articles
            
        except Exception as e:
            logger.error(f"❌ Ошибка MOEX RSS: {e}")
            return []
    
    async def fetch_rbc_rss(self) -> List[Dict]:
        """ЭКСТРЕННЫЙ ИСТОЧНИК: RSS лента РБК (всегда бесплатно)"""
        articles = []
        
        try:
            for url in self.rbc_feeds:
                async with aiohttp.ClientSession() as session:
                    async with session.get(url, timeout=10) as response:
                        if response.status == 200:
                            xml_content = await response.text()
                            root = ET.fromstring(xml_content)
                            
                            for item in root.findall('.//item'):
                                title_elem = item.find('title')
                                description_elem = item.find('description')
                                link_elem = item.find('link')
                                pub_date_elem = item.find('pubDate')
                                
                                if title_elem is not None:
                                    # Фильтруем только финансовые новости
                                    title = title_elem.text or ''
                                    description = description_elem.text if description_elem is not None else ''
                                    text = (title + ' ' + description).lower()
                                    
                                    financial_keywords = ['акци', 'бирж', 'дивид', 'рубл', 'доллар', 'нефт', 'газ', 
                                                         'сбербанк', 'втб', 'газпром', 'экономик', 'рынок', 'инвест']
                                    
                                    if any(keyword in text for keyword in financial_keywords):
                                        articles.append({
                                            'id': f"rbc_{pub_date_elem.text if pub_date_elem else ''}_{len(articles)}",
                                            'source': 'RBC',
                                            'title': title,
                                            'description': description,
                                            'content': description,
                                            'url': link_elem.text if link_elem is not None else '',
                                            'published_at': pub_date_elem.text if pub_date_elem is not None else '',
                                            'source_name': 'РБК',
                                            'fetched_at': datetime.now().isoformat()
                                        })
            
            logger.info(f"✅ RBC RSS: получено {len(articles)} финансовых новостей")
            return articles
            
        except Exception as e:
            logger.error(f"❌ Ошибка RBC RSS: {e}")
            return []
    
    def _deduplicate_news(self, all_articles: List[Dict]) -> List[Dict]:
        """Удаление дубликатов новостей по заголовку"""
        seen_titles = set()
        unique_articles = []
        
        for article in all_articles:
            # Нормализуем заголовок для сравнения
            title = article.get('title', '').strip().lower()
            title_key = title[:80]  # Берем первую часть заголовка
            
            if title_key and title_key not in seen_titles:
                seen_titles.add(title_key)
                unique_articles.append(article)
        
        removed = len(all_articles) - len(unique_articles)
        if removed > 0:
            logger.info(f"🔄 Удалено {removed} дубликатов, осталось {len(unique_articles)} уникальных")
        
        return unique_articles
    
    async def fetch_all_news(self) -> List[Dict]:
        """Получение всех новостей из ВСЕХ источников параллельно"""
        logger.info("📥 Начинаю сбор новостей из всех источников...")
        
        # Запускаем ВСЕ источники параллельно для максимальной надежности
        tasks = [
            self.fetch_mediastack(),  # Основной
            self.fetch_zenserp(),     # Резервный
            self.fetch_moex_rss(),    # С биржи
            self.fetch_rbc_rss()      # Бесплатный гарантированный
        ]
        
        results = await asyncio.gather(
            *tasks,
            return_exceptions=True  # Если один источник упал - остальные работают
        )
        
        # Собираем успешные результаты
        all_articles = []
        source_names = ['Mediastack', 'Zenserp', 'MOEX', 'RBC']
        
        for i, result in enumerate(results):
            if isinstance(result, list):
                all_articles.extend(result)
                logger.info(f"   📊 {source_names[i]}: {len(result)} новостей")
            elif isinstance(result, Exception):
                logger.error(f"   ❌ {source_names[i]} упал: {str(result)[:50]}")
        
        # Удаление дубликатов
        unique_articles = self._deduplicate_news(all_articles)
        
        logger.info(f"📊 ИТОГО: {len(unique_articles)} уникальных новостей")
        
        # Сортируем по времени публикации (новые сначала)
        unique_articles.sort(
            key=lambda x: x.get('published_at', ''),
            reverse=True
        )
        
        return unique_articles[:15]  # Ограничиваем 15 новостями для скорости
    
    def get_source_stats(self) -> Dict:
        """Статистика по источникам"""
        return {
            'mediastack_configured': bool(self.mediastack_key),
            'zenserp_configured': bool(self.zenserp_key),
            'moex_feeds': len(self.moex_feeds),
            'rbc_feeds': len(self.rbc_feeds),
            'cache_size': len(self.news_cache)
        }
