# models.py
import hashlib
from datetime import datetime, timezone
from sqlalchemy import create_engine, Column, Integer, String, Enum, DateTime, TIMESTAMP, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship, scoped_session
from config import DB_URL

Base = declarative_base()

class User(Base):
    __tablename__ = 'usuarios' # Nome da tabela no banco
    
    id = Column(Integer, primary_key=True)
    username = Column(String(50), unique=True, nullable=False)
    password = Column(String(255), nullable=False)
    role = Column(Enum('admin','editor','viewer','operador'))
    status = Column(Enum('online','ausente','ocupado','offline'))
    ultimo_acesso = Column(DateTime)
    foto_perfil = Column(String(255))
    created_at = Column(TIMESTAMP)

class RememberToken(Base):
    __tablename__ = 'remember_tokens'
    id = Column(Integer, primary_key=True)
    selector = Column(String(20), unique=True, nullable=False)
    validator_hash = Column(String(64), nullable=False)
    user_id = Column(Integer, ForeignKey('usuarios.id'), nullable=False) # Aponta para a tabela 'usuarios'
    expires_at = Column(DateTime(timezone=True), nullable=False)
    user = relationship("User")

    def is_expired(self):
        """Verifica se o token expirou."""
        return datetime.now(timezone.utc) > self.expires_at

    def is_valid(self, validator: str):
        """Verifica se o validador fornecido corresponde ao hash armazenado."""
        return self.validator_hash == hashlib.sha256(validator.encode()).hexdigest()

# --- Centralização da Configuração do Banco de Dados ---

_engine = None

def get_engine():
    """Retorna uma única instância do engine SQLAlchemy."""
    global _engine
    if _engine is None:
        _engine = create_engine(DB_URL)
    return _engine

def get_session():
    """Retorna uma nova sessão do banco de dados."""
    engine = get_engine()
    return scoped_session(sessionmaker(bind=engine))