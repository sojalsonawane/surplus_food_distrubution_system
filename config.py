import os
from pathlib import Path
from dotenv import load_dotenv

# Base directory of the project
BASE_DIR = Path(__file__).resolve().parent

# Load .env file
load_dotenv(BASE_DIR / '.env')


class Config:
    """Base configuration with shared defaults."""
    SECRET_KEY = os.getenv('SECRET_KEY', 'default_fallback_secret_key_change_me')

    # MySQL Configuration
    MYSQL_HOST = os.getenv('MYSQL_HOST', 'localhost')
    MYSQL_PORT = int(os.getenv('MYSQL_PORT', 3306))
    MYSQL_USER = os.getenv('MYSQL_USER', 'root')
    MYSQL_PASSWORD = os.getenv('MYSQL_PASSWORD', 'root')
    MYSQL_DATABASE = os.getenv('MYSQL_DATABASE', 'surplus_food_db')

    # Uploads
    UPLOAD_FOLDER = os.path.join(BASE_DIR, os.getenv('UPLOAD_FOLDER', 'static/uploads'))
    MAX_CONTENT_LENGTH = int(os.getenv('MAX_CONTENT_LENGTH', 5 * 1024 * 1024))  # 5MB default

    ALLOWED_IMAGE_EXTENSIONS = {'png', 'jpg', 'jpeg'}
    ALLOWED_DOCUMENT_EXTENSIONS = {'png', 'jpg', 'jpeg', 'pdf'}

    # Session & Security Settings
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    PERMANENT_SESSION_LIFETIME = 86400  # 24 hours in seconds


class DevelopmentConfig(Config):
    """Development environment configuration."""
    DEBUG = True
    TESTING = False
    SESSION_COOKIE_SECURE = False


class ProductionConfig(Config):
    """Production environment configuration."""
    DEBUG = False
    TESTING = False
    SESSION_COOKIE_SECURE = True


class TestingConfig(Config):
    """Testing environment configuration."""
    DEBUG = True
    TESTING = True
    MYSQL_DATABASE = 'surplus_food_test_db'
    SESSION_COOKIE_SECURE = False


config_by_name = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'testing': TestingConfig,
    'default': DevelopmentConfig
}


def get_config():
    """Retrieve configuration based on FLASK_ENV."""
    env = os.getenv('FLASK_ENV', 'development').lower()
    return config_by_name.get(env, DevelopmentConfig)
