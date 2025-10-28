"""
Database connection module for the supplement store
"""
import pymysql
from pymysql.cursors import DictCursor
import os
from dotenv import load_dotenv
load_dotenv()
# Load environment variables
load_dotenv()

def get_conn():
    """
    Create and return a database connection
    
    Returns:
        pymysql.Connection: Database connection with DictCursor
    
    Raises:
        Exception: If connection fails
    """
    try:
        conn = pymysql.connect(
        host=os.getenv("DB_HOST","127.0.0.1"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASS"),
        database=os.getenv("DB_NAME"),
        cursorclass=pymysql.cursors.DictCursor,
        autocommit=True
        charset='utf8mb4',
        cursorclass=DictCursor
        )
        return conn
    except Exception as e:
        print(f"Database connection error: {e}")
        raise