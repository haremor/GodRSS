# TODO:
    # JSON to bytes

import telebot
from copy import deepcopy
from json import load, dumps, loads
from datetime import datetime
from time import sleep
from sqlite3 import Error as SqlError
from dataclasses import dataclass, field

import db
from rss_utils import parse_feed, find_rss_feeds

db.init_db()

with open('config.json', 'r') as f:
    config = load(f)

API_KEY = config['api_key']
INITIAL_NEWS_LOAD = config['initial_news_load']
# Количество минут между запросами
POLLING_RATE = config['polling_rate'] * 60
PREMIUM_POLLING_RATE = config['premium_polling_rate'] * 60

bot = telebot.TeleBot(API_KEY)
types = telebot.types

@dataclass
class User:
    temp_urls: list = field(default_factory=list)
    polling_state: bool = True

class UserData:
    def __init__(self):
        self.user_data = {}

    def add_user(self, user_id):
        self.user_data[user_id] = User()

    def add_temp_url(self, user_id, urls):
        if user_id in self.user_data:
            self.user_data[user_id].temp_urls.append(urls)

    def clear_temp_urls(self, user_id):
        if user_id in self.user_data:
            self.user_data[user_id].temp_urls = []

    def update_polling_state(self, user_id, state):
        if user_id in self.user_data:
            self.user_data[user_id].polling_state = state

        return self.user_data[user_id].polling_state

    def get_temp_urls(self, user_id):
        user_id = int(user_id)
        if user_id in self.user_data:
            return self.user_data.get(user_id, None).temp_urls

    def get_polling_state(self, user_id):
        if user_id in self.user_data:
            return self.user_data.get(user_id, None).polling_state

user_registry = UserData()

@bot.message_handler(commands=['start'])
def start(message):
    start_command = types.BotCommand(command='start', description='Start the Bot')
    help_command = types.BotCommand(command='help', description='Get Help')
    get_user_feeds_command = types.BotCommand(command='my_feeds', description='Get All User Feeds')
    unsubscribe_command = types.BotCommand(command='unsubscribe', description='Unsubscribe From Feed')
    poll_start_command = types.BotCommand(command='poll_start', description='Start recieving news')
    poll_stop_command = types.BotCommand(command='poll_stop', description='Stop recieving news')

    bot.set_my_commands([start_command, help_command, get_user_feeds_command, unsubscribe_command, poll_start_command, poll_stop_command])
    bot.set_chat_menu_button(message.chat.id, types.MenuButtonCommands('commands'))

    # Инициализируем нового пользователя по id
    user_id = message.from_user.id
    user_registry.add_user(user_id)
    user_feeds = db.get_feeds(user_id)

    # Загружаем данные пользователя
    if user_feeds:
        user_registry.add_temp_url(user_id, user_feeds)

    print(f'{user_id} has joined')
    bot.send_message(message.chat.id, 'Bot started')

@bot.message_handler(commands=['help'])
def help(message):
    bot.send_message(message.chat.id, 'Send a URL to get a preview of a feed.\nThen you will be asked if you want to subscribe to it.\nManage your feeds with the /my_feeds command.\nFigure out the rest)')

# Хэндлер URL
@bot.message_handler(func=lambda msg: not msg.text.startswith('/'))
def get_feed(message):
    site_url = message.text

    find_rss_feeds_result = find_rss_feeds(site_url)
    
    error_msg = None

    # Здесь мы смотрим на наличие ошибки. Условие нужно для удачного ответа (будет set)
    if not isinstance(find_rss_feeds_result, set):
        if find_rss_feeds_result['error_code'] == 0:
            error_msg = find_rss_feeds_result['msg']
        elif find_rss_feeds_result['error_code'] == 1:
            error_msg = find_rss_feeds_result['msg']

    if not error_msg:
        user_id = message.from_user.id
        # Иначе массив ссылок пользователя будет полниться
        user_registry.clear_temp_urls(user_id)

        if not len(find_rss_feeds_result) == 0:
            # Отправка пользователю ссылки найденных RSS-лент
            keyboard = types.InlineKeyboardMarkup()

            for i, feed_link in enumerate(find_rss_feeds_result):
                user_registry.add_temp_url(user_id, feed_link)
                # Каждая ссылка будет иметь id, который будет передаваться через кнопку функции-обработчику ссылок на RSS-ленты
                feed_link_id = str(i)
                # Текстом кнопки будет URL RSS-ленты, а callback_data - id в глобальном объекте пользователей, соответствующий URL RSS-ленты... И все это, просто чтобы обойти ограничение callback_data Telegram в 64 байта
                feed_select_button = types.InlineKeyboardButton(feed_link, callback_data=f'{user_id}/{feed_link_id}')
                keyboard.add(feed_select_button)

            bot.send_message(message.chat.id, 'Found RSS feeds:', reply_markup=keyboard)
        else:
            bot.send_message(message.chat.id, 'No RSS feeds found')
    else:
        bot.send_message(message.chat.id, error_msg)

@bot.message_handler(commands=['my_feeds'])
def get_user_feeds(message):
    user_id = message.from_user.id
    chat_id = message.chat.id
    
    rss_feeds_tuple = db.get_feeds(user_id)

    if rss_feeds_tuple:
        feed_msg = ''

        for i, feed_url in enumerate(rss_feeds_tuple, 1):
            feed_msg += f'{i}. {feed_url}\n'

        bot.send_message(chat_id, f'Your subscriptions:\n{feed_msg}')
    else:
        bot.send_message(chat_id, 'No feeds')

@bot.message_handler(commands=['unsubscribe'])
def unsubscribe_from_feed(message):
    user_id = message.from_user.id
    chat_id = message.chat.id

    rss_feeds_tuple = db.get_feeds(user_id)

    keyboard = types.InlineKeyboardMarkup()

    if rss_feeds_tuple:
        user_registry.clear_temp_urls(user_id)

        for i, feed_url in enumerate(rss_feeds_tuple):
            user_registry.add_temp_url(user_id, feed_url)
            feed_link_id = str(i)
            feed_msg = f'{i + 1}. {feed_url}\n'

            feed_select_button = types.InlineKeyboardButton(feed_msg, callback_data=f'remove/{user_id}/{feed_link_id}')
            keyboard.add(feed_select_button)

        bot.send_message(message.chat.id, 'Select a feed to unsubscribe from:', reply_markup=keyboard)
    else:
        bot.send_message(chat_id, 'No feeds')

@bot.message_handler(commands=['poll_start'])
def start_polling(message):
    user_id = message.from_user.id
    chat_id = message.chat.id
    user_has_premium_status = db.get_user_premium_status(user_id)
    polling_state = user_registry.update_polling_state(user_id, 1)

    def __find_new_uncommon_entries(old_feed, new_feed):
        old_feed_json_set = set()
        new_feed_json_set = set()

        for entry in old_feed:
            old_feed_json_set.add(dumps(entry))

        for entry in new_feed:
            new_feed_json_set.add(dumps(entry))

        new_uncommon_json_set = new_feed_json_set - old_feed_json_set

        new_uncommon = []
        for entry_json in new_uncommon_json_set:
            new_uncommon.append(loads(entry_json))

        return new_uncommon

    def __poll_news(saved_feed_states):
        for feed_url in saved_feed_states:
            print(feed_url)
            feed_data = parse_feed(feed_url)

            saved_feed_states[feed_url] = feed_data

    user_feeds = db.get_feeds(user_id)
    saved_feed_states = {}.fromkeys(user_feeds)

    while True:
        news = []

        while not news:
            __poll_news(saved_feed_states)
            original_feeds = deepcopy(saved_feed_states)

            if user_has_premium_status[0]:
                sleep(PREMIUM_POLLING_RATE)
            else:
                sleep(POLLING_RATE)

            __poll_news(saved_feed_states)
            new_feeds = deepcopy(saved_feed_states)

            for feed in saved_feed_states:
                polling_state = user_registry.get_polling_state(user_id)
                if not polling_state:
                    return

                original_feed = original_feeds[feed]
                new_feed = new_feeds[feed]

                new_entries = __find_new_uncommon_entries(original_feed, new_feed)
                print(new_entries)
                news.extend(new_entries)

        posts = []
        # Получаем посты
        for entry in news:
            entry_link = entry['link']
            entry_title = entry['title']
            entry_image = entry['image']
            entry_published = entry['published']
            new_post = {'link': entry_link,'title': entry_title, 'image': entry_image, 'published': entry_published}
            posts.append(new_post)

        for post in posts:
            print(post)
            post_link = post['link']
            post_title = post['title']
            # Без него мы не поймем, есть ли вообще изображение
            post_image = post['image']
            post_published = post['published']
            try:
                post_published = datetime.fromisoformat(post_published)
                post_published = post_published.strftime('%d-%m-%Y (%H:%M:%S)')
            except Exception as e:
                print(e)
            # На случай, если изображения нет в ленте. post_image - ссылка на изображение, и, если её нет (<class '_io.BufferedReader'>), используем no_image
            if not isinstance(post_image, str):
                bot.send_photo(chat_id, post_image, f'Source:\n{post_link}\n\n<a href="{post_link}">{post_title}</a>\n\n<i>Published: {post_published} GMT +0</i>', parse_mode='HTML')
            else:
                bot.send_message(chat_id, f'{post_link}\n\nPublished: {post_published} GMT +0')

@bot.message_handler(commands=['poll_stop'])
def stop_polling(message):
    user_id = message.from_user.id
    user_registry.update_polling_state(user_id, 0)

@bot.callback_query_handler(func=lambda _: True)
def get_feed_preview(call):
    call_message = call.message

    # Пользователь решил подписаться
    if call.data.startswith('yes'):
        call_data = call.data.split('/')

        user_id = call_data[1]
        feed_link_id = call_data[2]

        user_urls = user_registry.get_temp_urls(user_id)
        url = user_urls[int(feed_link_id)]

        # Добавляем пользователя только когда он решает на что-то подписаться
        db.create_user(user_id)
        if url in db.get_feeds(user_id):
            bot.send_message(call_message.chat.id, f'You are already subscribed to {url}')
        else:
            db.add_feed_to_user(user_id, url)
            bot.send_message(call_message.chat.id, f'Subscribed to {url}')

        # Дать понять, что кнопка нажата. Иначе кнопки будут выглядеть "зависшими"
        bot.answer_callback_query(call.id)
    elif call.data.startswith('remove'):
        call_data = call.data.split('/')

        user_id = call_data[1]
        feed_link_id = int(call_data[2])

        user_urls = user_registry.get_temp_urls(user_id)
        url = user_urls[int(feed_link_id)]

        try:
            db.remove_feed_from_user(user_id, url)
            bot.send_message(call_message.chat.id, f'Unsubscribed from {url}')
        except SqlError as e:
            print(e)

        bot.answer_callback_query(call.id)
    # Preview
    else:
        user_id = call.data.split('/')[0]
        feed_link_id = int(call.data.split('/')[1])

        user_urls = user_registry.get_temp_urls(user_id)
        url = user_urls[int(feed_link_id)]
        posts = []
        # Получаем посты
        try:
            callback_data = url
            rss_data = parse_feed(callback_data)

            for i, entry in enumerate(rss_data):
                if i == INITIAL_NEWS_LOAD:
                    break

                entry_link = entry['link']
                entry_title = entry['title']
                entry_image = entry['image']
                entry_published = entry['published']

                new_post = {'link': entry_link,'title': entry_title, 'image': entry_image, 'published': entry_published}
                posts.append(new_post)

        except SqlError as e:
            print(e)
            bot.send_message(call_message.chat.id, 'Invalid URL')

        for post in posts:
            print(post)
            post_link = post['link']
            post_title = post['title']
            post_image = post['image']
            post_published = post['published']
            try:
                post_published = datetime.fromisoformat(post_published)
                post_published = post_published.strftime('%d-%m-%Y (%H:%M:%S)')
            except Exception as e:
                print(e)

            if not isinstance(post_image, str):
                bot.send_photo(call_message.chat.id, post_image, f'<a href="{post_link}">{post_title}</a>\n\n<i>Published: {post_published} GMT +0</i>', parse_mode='HTML')
            else:
                bot.send_message(call_message.chat.id, f'{post_link}\n\nPublished: {post_published} GMT +0')
    
        markup = types.InlineKeyboardMarkup()

        markup.add(types.InlineKeyboardButton('Subscribe', callback_data=f'yes/{user_id}/{feed_link_id}'))

        bot.send_message(call_message.chat.id, 'Do you wish to subscribe to this feed?', reply_markup=markup)

        bot.answer_callback_query(call.id)


if __name__ == "__main__":
    while True:
        try:
            # Пропускать старые обновления
            bot.infinity_polling(skip_pending=True)
        except Exception as e:
            print(e)