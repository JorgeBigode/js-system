# config.py
import os
from datetime import timedelta
from dotenv import load_dotenv

# Carrega as variáveis de ambiente do arquivo .env
load_dotenv()


# DB - Configuração carregada do ambiente (.env)
DB_HOST = os.getenv("DB_HOST")
DB_USER = os.getenv("DB_USER")
DB_PASS = os.getenv("DB_PASS")
DB_NAME = os.getenv("DB_NAME")
DB_PORT = os.getenv("DB_PORT")

# Constrói o caminho absoluto para o certificado ca.pem
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SSL_CA_PATH = os.path.join(BASE_DIR, 'ca.pem')

# URL de conexão para SQLAlchemy. O `ssl_ca` requer o arquivo ca.pem no diretório raiz.
DB_URL = f"mysql+pymysql://{DB_USER}:{DB_PASS}@{DB_HOST}:{DB_PORT}/{DB_NAME}?ssl_ca={SSL_CA_PATH}"

# App
SECRET_KEY = os.getenv("SECRET_KEY", os.urandom(32))  # chave secreta do Flask
PERMANENT_SESSION_LIFETIME = timedelta(days=7)        # tempo de sessão

# Cookies / Remember-me
REMEMBER_COOKIE_NAME = "remember_token"
REMEMBER_COOKIE_DURATION_DAYS = 30

# Logs
LOG_FILE = os.path.join(os.path.dirname(__file__), 'error.log')
