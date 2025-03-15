import os
from datetime import timedelta
from dotenv import load_dotenv

load_dotenv()


class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY', 'dev_key_change_in_production')
    MONGODB_URI = os.environ.get(
        'MONGODB_URI', 'mongodb://localhost:27017/chatbot')
    SESSION_TYPE = 'mongodb'
    SESSION_MONGODB = None  # Will be set in app.py
    SESSION_MONGODB_DB = 'chatbot'
    SESSION_MONGODB_COLLECT = 'sessions'
    PERMANENT_SESSION_LIFETIME = timedelta(days=30)
    ADMIN_USERNAME = os.environ.get('ADMIN_USERNAME', 'admin')
    ADMIN_PASSWORD = os.environ.get(
        'ADMIN_PASSWORD_HASH')  # Stored as bcrypt hash
    GEMINI_KEY = os.environ.get('GEMINI_KEY', None)
    OPENAI_KEY = os.environ.get('OPENAI_KEY', None)
    CLAUDE_KEY = os.environ.get('CLAUDE_KEY', None)
    BOT_NAME = os.environ.get('BOT_NAME',"GO Globe Bot")
