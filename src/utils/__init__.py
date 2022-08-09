from .config import DBConfig, FlaskConfig

# login_manager = LoginManager()

def get_db_connection():
    conn = psycopg2.connect(
        host=DBConfig.HOST,
        database=DBConfig.DATABASE,
        user=DBConfig.USER,
        password=DBConfig.PASSWORD)
    return conn
