import os, pymysql
from dotenv import load_dotenv
load_dotenv()
def get_conn():
    return pymysql.connect(
        host=os.getenv("DB_HOST","127.0.0.1"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASS"),
        database=os.getenv("DB_NAME"),
        cursorclass=pymysql.cursors.DictCursor,
        autocommit=True
    )
