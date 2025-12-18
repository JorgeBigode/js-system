import pymysql
from contextlib import contextmanager
from config import DB_HOST, DB_USER, DB_PASS, DB_NAME

@contextmanager
def get_db_connection():
    """
    Fornece uma conexão com o banco de dados que é fechada automaticamente.
    Usa um cursor de dicionário para retornar as linhas como dicionários.
    """
    connection = None
    try:
        connection = pymysql.connect(
            host=DB_HOST,
            user=DB_USER,
            password=DB_PASS,
            database=DB_NAME,
            charset='utf8mb4',
            cursorclass=pymysql.cursors.DictCursor
        )
        yield connection
    finally:
        if connection:
            connection.close()