import os
import psycopg2
from dotenv import load_dotenv

load_dotenv()  # .env dosyasını yükler

def get_db_connection():
    return psycopg2.connect(os.getenv("DATABASE_URL"))
