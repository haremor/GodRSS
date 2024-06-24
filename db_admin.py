import sqlite3 as sql
import db

conn = sql.connect('bot.sqlite', check_same_thread=False)

db.init_db()

user_id = '1013991164'

status = db.get_user_premium_status(user_id)
db.change_user_premium_status(user_id, True)

print(f'The status of user "{user_id}" has been changed to: {status[0]}')

conn.close()