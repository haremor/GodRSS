import sqlite3 as sql
import json

db = sql.connect('bot.sqlite', check_same_thread=False)
cur = db.cursor()

def init_db():
    cur.executescript(
        '''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY,
            user_id VARCHAR(10) NOT NULL UNIQUE,
            premium_status BOOLEAN NOT NULL DEFAULT 0,
            rss_feeds JSON NOT NULL
        )
        '''
    )

    db.commit()

def get_user(user_id):
    cur.execute(
        f'''
            SELECT * FROM users
            WHERE user_id = {user_id}
        '''
    )

    user = json.loads(cur.fetchone())

    return user

def create_user(user_id):
    cur.execute(
        f'''
            INSERT OR IGNORE INTO users (user_id, rss_feeds)
            VALUES ({user_id}, '[]')
        '''
    )

    db.commit()

    # Так мы сэкономим время на поиск нужного пользователя - просто взяв последнего
    user = cur.lastrowid

    return user

def add_feed_to_user(user_id, rss_feed):
    cur.execute(
        f'''
            SELECT rss_feeds
            FROM users
            WHERE user_id = {user_id}
        '''
    )

    rss_feeds_row = cur.fetchone()
    rss_feeds = json.loads(rss_feeds_row[0]) if rss_feeds_row else []

    if rss_feed not in rss_feeds:
        rss_feeds.append(rss_feed)

        cur.execute(
            f'''
                UPDATE users
                SET rss_feeds = '{json.dumps(rss_feeds)}'
                WHERE user_id = {user_id}
            '''
        )

        db.commit()

def remove_feed_from_user(user_id, rss_feed):
    cur.execute(
        f'''
            SELECT rss_feeds
            FROM users
            WHERE user_id = {user_id}
        '''
    )

    rss_feeds_row = cur.fetchone()
    rss_feeds = json.loads(rss_feeds_row[0]) if rss_feeds_row else []

    if rss_feed in rss_feeds:
        rss_feeds.remove(rss_feed)

        cur.execute(
            f'''
                UPDATE users
                SET rss_feeds = '{json.dumps(rss_feeds)}'
                WHERE user_id = {user_id}
            '''
        )

        db.commit()

def get_feeds(user_id):
    cur.execute(
        f'''
            SELECT rss_feeds
            FROM users
            WHERE user_id = '{user_id}'
        '''
    )

    try:
        rss_feeds_json = json.loads(cur.fetchone()[0])
    except TypeError:
        return

    return rss_feeds_json

def get_user_premium_status(user_id):
    cur.execute(
        f'''
            SELECT premium_status
            FROM users WHERE
            user_id = '{user_id}'
        '''
    )

    premium_status = cur.fetchone()

    return premium_status

def change_user_premium_status(user_id, status):
    cur.execute(
        f'''
            UPDATE users
            SET premium_status = {status}
            WHERE user_id = {user_id}
        '''
    )

    db.commit()