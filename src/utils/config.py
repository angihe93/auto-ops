import os

class FlaskConfig:
    SECRET_KEY = os.environ.get('SECRET_KEY')

class DBConfig:
    HOST = os.environ.get('DB_HOST')
    DATABASE = os.environ.get('DB_DB')
    USER = os.environ.get('DB_USER')
    PASSWORD = os.environ.get('DB_PW')
