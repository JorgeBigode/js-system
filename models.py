from sqlalchemy import create_engine, Column, Integer, String, Enum, DateTime, TIMESTAMP
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from werkzeug.security import generate_password_hash, check_password_hash
from config import DB_URL

Base = declarative_base()

class User(Base):
    __tablename__ = 'usuarios'
    
    id = Column(Integer, primary_key=True)
    username = Column(String(50), unique=True, nullable=False)
    password = Column(String(255), nullable=False)
    role = Column(Enum('admin','editor','viewer','operador'))
    status = Column(Enum('online','ausente','ocupado','offline'))
    ultimo_acesso = Column(DateTime)
    foto_perfil = Column(String(255))
    created_at = Column(TIMESTAMP)

    def set_password(self, password):
        self.password = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password, password)

# Configuração do banco
engine = create_engine(DB_URL)
Base.metadata.create_all(engine)
Session = sessionmaker(bind=engine)