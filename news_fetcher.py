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
    """Сборщик новостей из различных источников"""
    
    def __init__(self):
        self.newsapi_key = os.getenv("NewsAPI")
        self.zenserp_key = os.getenv("ZENSEPTAPI")
        
        # Кэш для новостей (чтобы избежать дубликатов в рамках одной сессии)
        self.news_cache = {}
        
        # Источники RSS MOEX
        self.moex_feeds = {
            "all_news": "https://moex.com/export/news.aspx?cat=100",
            "main_news": "https://moex.com/export/news.aspx?cat=101"
        }
        
        logger.info("📰 NewsFetcher инициализирован")
    
    async def fetch_newsapi(self) -> List[Dict]:
        """Получение новостей через NewsAPI.org"""
        if not self.newsapi_key:
            logger.warning("⚠️ NewsAPI ключ не найден")
            return []
        
        url = "https://newsapi.org/v2/everything"
        
        params = {
            'q': 'акции OR дивиденды OR отчетность OR квартал OR прибыль',
            'language': 'ru',
            'sortBy': 'publishedAt',
            'pageSize': 20,
            'apiKey': self.newsapi_key,
            'from': (datetime.now() - timedelta(hours=24)).strftime('%Y-%m-%dT%H:%M:%S')
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params, timeout=10) as response:
                    if response.status == 200:
                        data = await response.json()
                        articles = []
                        
                        for article in data.get('articles', []):
                            articles.append({
                                'id': f"newsapi_{article.get('publishedAt', '')}_{len(articles)}",
                                'source': 'NewsAPI',
                                'title': article.get('title', ''),
                                'description': article.get('description', ''),
                                'content': article.get('content', ''),
                                'url': article.get('url', ''),
                                'published_at': article.get('publishedAt', ''),
                                'author': article.get('author', ''),
                                'source_name': article.get('source', {}).get('name', ''),
                                'fetched_at': datetime.now().isoformat()
                            })
                        
                        logger.info(f"✅ NewsAPI: получено {len(articles)} новостей")
                        return articles
                    else:
                        logger.error(f"❌ NewsAPI ошибка: {response.status}")
                        return []
                        
        except Exception as e:
            logger.error(f"❌ Ошибка NewsAPI: {e}")
            return []
    
    async def fetch_zenserp(self) -> List[Dict]:
        """Получение новостей через Zenserp (Google News)"""
        if not self.zenserp_key:
            logger.warning("⚠️ Zenserp ключ не найден")
            return []
        
        url = "https://app.zenserp.com/api/v2/search"
        headers = {'apikey': self.zenserp_key}
        
        params = {
            'q': 'акции Россия биржа Мосбиржа дивиденды',
            'tbm': 'nws',
            'num': 15,
            'hl': 'ru',
            'gl': 'ru',
            'tbs': 'qdr:d'
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers, params=params, timeout=10) as response:
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
                        
        except Exception as e:
            logger.error(f"❌ Ошибка Zenserp: {e}")
            return []
    
    async def fetch_moex_rss(self) -> List[Dict]:
        """Получение новостей с MOEX RSS с использованием XML парсера"""
        articles = []
        
        try:
            for feed_name, feed_url in self.moex_feeds.items():
                async with aiohttp.ClientSession() as session:
                    async with session.get(feed_url, timeout=10) as response:
                        if response.status == 200:
                            xml_content = await response.text()
                            
                            # Простой парсинг RSS XML
                            root = ET.fromstring(xml_content)
                            
                            # Ищем элементы item
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
    
    def _deduplicate_news(self, all_articles: List[Dict]) -> List[Dict]:
        """Удаление дубликатов новостей по заголовку и содержанию"""
        seen_keys = set()
        unique_articles = []
        
        for article in all_articles:
            # Создаем ключ для проверки дубликатов
            title_key = article.get('title', '').strip().lower()[:100]
            desc_key = article.get('description', '').strip().lower()[:50]
            cache_key = f"{title_key}_{desc_key}"
            
            if cache_key not in seen_keys:
                seen_keys.add(cache_key)
                unique_articles.append(article)
        
        logger.info(f"🔄 Удалено {len(all_articles) - len(unique_articles)} дубликатов")
        return unique_articles
    
    async def fetch_rbc_rss(self) -> List[Dict]:
    """Резервный источник: RSS лента РБК (бесплатно)"""
    articles = []
    rss_urls = [
        "https://rssexport.rbc.ru/rbcnews/news/30/full.rss",
        "https://rssexport.rbc.ru/rbcnews/news/20/full.rss"  # Финансы
    ]
    
    try:
        for url in rss_urls:
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
                                articles.append({
                                    'id': f"rbc_{pub_date_elem.text if pub_date_elem else ''}_{len(articles)}",
                                    'source': 'RBC',
                                    'title': title_elem.text or '',
                                    'description': description_elem.text if description_elem is not None else '',
                                    'url': link_elem.text if link_elem is not None else '',
                                    'published_at': pub_date_elem.text if pub_date_elem is not None else '',
                                    'source_name': 'РБК',
                                    'fetched_at': datetime.now().isoformat()
                                })
        
        logger.info(f"✅ RBC RSS: получено {len(articles)} новостей")
        return articles
        
    except Exception as e:
        logger.error(f"❌ Ошибка RBC RSS: {e}")
        return []
        
    async def fetch_all_news(self) -> List[Dict]:
        """Получение всех новостей из всех источников"""
        logger.info("📥 Начинаю сбор новостей из всех источников...")
        
        # Запускаем все запросы параллельно
        newsapi_task = self.fetch_newsapi()
        zenserp_task = self.fetch_zenserp()
        moex_task = self.fetch_moex_rss()
        
        results = await asyncio.gather(
            newsapi_task,
            zenserp_task,
            moex_task,
            rbc_task,
            return_exceptions=True
        )
        
        # Обработка результатов
        all_articles = []
        for result in results:
            if isinstance(result, list):
                all_articles.extend(result)
            elif isinstance(result, Exception):
                logger.error(f"❌ Исключение при сборе новостей: {result}")
        
        # Удаление дубликатов
        unique_articles = self._deduplicate_news(all_articles)
        
        logger.info(f"📊 Всего уникальных новостей: {len(unique_articles)}")
        return unique_articles
    
    def get_source_stats(self) -> Dict:
        """Статистика по источникам"""
        return {
            'newsapi_configured': bool(self.newsapi_key),
            'zenserp_configured': bool(self.zenserp_key),
            'moex_feeds': len(self.moex_feeds),
            'cache_size': len(self.news_cache)
        }
