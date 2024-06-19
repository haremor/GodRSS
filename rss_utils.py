import requests
from requests.exceptions import ConnectionError

import re
import feedparser
from urllib.parse import urlparse, urlsplit
from bs4 import BeautifulSoup

# Чтобы не создавать отличные ссылки
def __load_image_placeholder():
    with open('static/no_image.jpg', 'rb') as f:
        return f.read()

# Функция парсинга изображений (из объекта entries)
def __parse_entry_image(entry):
    # У нас уже есть массив enclosures в получаемом от feedparser объекте, так что проверяем его длину
    if len(entry['enclosures']) > 0:
        if entry['enclosures'][0]['type'] == 'image/jpeg' or entry['enclosures'][0]['type'] == 'image/png':
            item_image = entry['enclosures'][0]['href']

            return item_image

    if 'media_content' in entry:
        entry_image_content_url = entry['media_content'][0]['url']

        if '.jpg' in entry_image_content_url or '.png' in entry_image_content_url:
            item_image = entry['media_content'][0]['url']

            return item_image
            
    if 'media_thumbnail' in entry:
        item_image = entry['media_thumbnail'][0]['url']
    
        return item_image

# Функция-валидатор URL
def __is_url_valid(url):
    parsed_url = urlparse(url)
    pattern = r'^[a-zA-Z0-9-]+(\.[a-zA-Z0-9-]+)*\.[a-zA-Z]{2,}$'

    if re.match(pattern, parsed_url.netloc):
        return True

    return False

# Функция разбора RSS-ленты
def parse_feed(url):
    if url.startswith('https://') or url.startswith('http://'):
        feed_data = feedparser.parse(url)
    else:
        feed_data = feedparser.parse('http://' + url)

    entries = feed_data['entries']
    parsed_data = []

    for entry in entries:
        parsed_data_chunk = {}

        entry_link = entry.get('link')
        entry_title = entry.get('title')

        '''
        Автоматически найдёт:
        /atom10:feed/atom10:entry/atom10:published
        /atom03:feed/atom03:entry/atom03:issued
        /rss/channel/item/dcterms:issued
        /rss/channel/item/pubDate
        /rdf:RDF/rdf:item/dcterms:issued
        '''

        entry_published = entry.get('published')

        if __parse_entry_image(entry):
            entry_image = __parse_entry_image(entry)

        # Если изображения поста нет, используем изображение ленты (пример: lenta.ru)
        elif feed_data.get('feed').get('image'):
            entry_image = feed_data.get('feed').get('image')

        # Handler отсутствия изображения в ленте
        else:
            entry_image = ''
            # entry_image = __load_image_placeholder

        parsed_data_chunk.update({'link': entry_link, 'title': entry_title, 'image': entry_image, 'published': entry_published})
        parsed_data.append(parsed_data_chunk)

    return parsed_data

# Функция поиска RSS-лент
def find_rss_feeds(url):
    # Чтобы была возможность обойтись без схемы в ссылке
    # Браузерный клиент всё равно соединится через https при его доступности
    if not url.startswith(('http://', 'https://')):
       url = 'https://' + url

    if not __is_url_valid(url):
        return {'error_code': 0, 'msg': 'Malformed URL'}

    try:
        requests.get(url)
    except ConnectionError:
        return {'error_code': 1, 'msg': 'Site does not exist'}

    page = requests.get(url)
    soup = BeautifulSoup(page.content, "html.parser")
    link_tags = soup.find_all('link')

    # Массив RSS-каналов (используем set на случай дубликатов)
    rss_feed_sources = set()

    # Проверям type с помощью regex
    for link in link_tags:
        if link.has_attr('type'):
            mime_type_pattern = r'^application\/xml|text\/xml|application\/atom\+xml|application\/rss\+xml$'

            if re.search(mime_type_pattern, link.get('type')):
                link_href = link.get('href')

                base_url = urlsplit(url)
                base_url = base_url.scheme + '://' + base_url.netloc

                # Проверка на полноту ссылки
                if not link_href.startswith('http'):
                    link_href = base_url + link_href
                
                rss_feed_sources.add(link_href)

    return rss_feed_sources