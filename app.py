# app.py
import os
import secrets
import hashlib
import json
import traceback
from datetime import datetime, timezone, timedelta
import logging

from flask import (
    Flask, request, render_template, redirect, url_for, session, make_response,
    jsonify, send_file, abort, current_app, flash
)
from markupsafe import Markup
from werkzeug.middleware.proxy_fix import ProxyFix
from werkzeug.utils import secure_filename
from sqlalchemy import func, desc, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import scoped_session, sessionmaker

# models & config
from models import Base, User, RememberToken, get_engine, get_session
import config

# passlib handlers (passlib bcrypt + legacy handlers)
from passlib.context import CryptContext
from menu_content import get_user_html, is_admin
from menu import menu_bp

# Setup passlib context for multiple hash formats
pwd_context = CryptContext(
    schemes=["bcrypt", "phpass", "md5_crypt", "pbkdf2_sha256"],
    deprecated="auto"
)

print("passlib bcrypt exemplo:", pwd_context.hash("teste")[:60], "...")

# -------------------------
# Flask app + logging
# -------------------------
app = Flask(__name__, static_folder='static', template_folder='templates')
app.secret_key = config.SECRET_KEY
app.permanent_session_lifetime = config.PERMANENT_SESSION_LIFETIME

# Logging to stdout (Render captures stdout/stderr)
LOG_LEVEL = os.getenv("LOG_LEVEL", "DEBUG")
logging.basicConfig(level=getattr(logging, LOG_LEVEL.upper(), logging.DEBUG),
                    format='%(asctime)s %(levelname)s %(name)s: %(message)s')
logger = logging.getLogger(__name__)

# Enable debug if running on Render or if FLASK_DEBUG is set
app.debug = (os.getenv("RENDER", "0") == "1") or (os.getenv("FLASK_DEBUG", "0") == "1")
if app.debug:
    logger.warning("Flask debug mode is ENABLED (app.debug=True)")

# -------------------------
# Cookie policy (dev vs prod)
# -------------------------
# You can override with env: FORCE_COOKIE_SECURE=0/1
force_cookie_secure = os.getenv("FORCE_COOKIE_SECURE", None)
if force_cookie_secure is not None:
    cookie_secure = bool(int(force_cookie_secure))
else:
    # in debug (local) avoid secure=True to make testing easy
    cookie_secure = not app.debug

# samesite: in production with secure cookies and cross-site usage, use 'None'
cookie_samesite = 'None' if cookie_secure else 'Lax'

# apply to Flask session cookie
app.config.update(
    SESSION_COOKIE_SECURE=cookie_secure,
    SESSION_COOKIE_SAMESITE=cookie_samesite,
    SESSION_COOKIE_HTTPONLY=True
)

logger.info("Cookie policy: secure=%s, samesite=%s, session_cookie_httpOnly=%s",
            app.config['SESSION_COOKIE_SECURE'],
            app.config['SESSION_COOKIE_SAMESITE'],
            app.config['SESSION_COOKIE_HTTPONLY'])

# ProxyFix: configurable via env vars (use only x_for and x_proto by default)
try:
    proxy_x_for = int(os.getenv('PROXY_X_FOR', '1'))
    proxy_x_proto = int(os.getenv('PROXY_X_PROTO', '1'))
except Exception:
    proxy_x_for, proxy_x_proto = 1, 1

# Use only x_for and x_proto (x_host and x_prefix often break detection)
app.wsgi_app = ProxyFix(app.wsgi_app,
                        x_for=proxy_x_for,
                        x_proto=proxy_x_proto)

app.register_blueprint(menu_bp)

# Database setup
engine = get_engine()
Base.metadata.create_all(engine)
SessionLocal = scoped_session(sessionmaker(bind=engine))

@app.teardown_appcontext
def shutdown_session(exception=None):
    """Garante que a sessão do banco de dados seja removida após cada requisição."""
    SessionLocal.remove()

# Logger (write simple debug + timings) - mantém seu arquivo de log local também
def write_debug_log(entries: dict):
    try:
        with open(config.LOG_FILE, 'a', encoding='utf-8') as f:
            f.write(datetime.now(timezone.utc).strftime('[%Y-%m-%d %H:%M:%S] '))
            for k, v in entries.items():
                f.write(f"{k}: {v}\n")
            f.write("\n")
    except Exception as e:
        # se não der para escrever no arquivo, garantir que algo seja logado no stdout
        logger.exception("Falha ao escrever em config.LOG_FILE: %s", e)

@app.before_request
def before_request_logging():
    entries = {
        "REQUEST_METHOD": request.method,
        "QUERY_STRING": request.query_string.decode('utf-8', errors='ignore'),
        "HTTP_X_REQUESTED_WITH": request.headers.get('X-Requested-With', 'NOT SET'),
        "SERVER_NAME": request.host,
        "SCRIPT_NAME": request.path
    }
    # escreve no arquivo local (se houver) e no stdout
    write_debug_log(entries)
    logger.debug("Request: %s %s", request.method, request.path)

# -------------------------
# Helpers: remember-me token
# -------------------------
def create_remember_token(db, user_id, days=config.REMEMBER_COOKIE_DURATION_DAYS):
    selector = secrets.token_hex(10)
    validator = secrets.token_urlsafe(32)
    validator_hash = hashlib.sha256(validator.encode()).hexdigest()
    expires = datetime.now(timezone.utc) + timedelta(days=days)
    token = RememberToken(
        selector=selector,
        validator_hash=validator_hash,
        user_id=user_id,
        expires_at=expires
    )
    db.add(token)
    db.commit()
    return f"{selector}:{validator}", expires

def rotate_remember_token(db, token_obj):
    user_id = token_obj.user_id
    db.delete(token_obj)
    db.commit()
    return create_remember_token(db, user_id)

def consume_remember_cookie(db, cookie_value):
    try:
        selector, validator = cookie_value.split(':', 1)
    except Exception:
        return None
    token = db.query(RememberToken).filter_by(selector=selector).first()
    if not token:
        return None
    if token.is_expired():
        db.delete(token)
        db.commit()
        return None
    if token.is_valid(validator):
        user = db.query(User).filter_by(id=token.user_id).first()
        new_cookie, expires = rotate_remember_token(db, token)
        return user, new_cookie, expires
    else:
        # possible theft: delete token
        db.delete(token)
        db.commit()
        return None

# small helper to set cookies with consistent attributes
def set_app_cookie(resp, key, value, expires=None, httponly=False, path='/'):
    resp.set_cookie(
        key,
        value,
        expires=expires,
        path=path,
        httponly=httponly,
        samesite=app.config['SESSION_COOKIE_SAMESITE'],
        secure=app.config['SESSION_COOKIE_SECURE']
    )

# -------------------------
# Routes
# -------------------------
@app.route('/', methods=['GET', 'POST'])
def login():
    db = SessionLocal()
    username_cookie = request.cookies.get('username', '')
    sistema_cookie = request.cookies.get('sistema_selecionado', '')

    # Install check
    if 'bypass_install_check' not in request.args:
        any_user = db.query(User).first()
        if not any_user:
            return redirect(url_for('install'))

    # If session active -> redirect by role/sistema
    if session.get('user_id') and session.get('username') and session.get('role'):
        role = session.get('role')
        if role == 'viewer':
            return redirect('/gestao_setores')
        elif role in ('admin', 'editor', 'operador'):
            if sistema_cookie == 'producao':
                return redirect('/inicio')
            elif sistema_cookie == 'apontamento':
                return redirect('/apontamento_qr')
            else:
                # Fallback para caso o cookie não esteja definido ou seja inválido
                return redirect('/inicio')

    # Auto-login via remember cookie
    if not session.get('user_id'):
        remember_cookie = request.cookies.get(config.REMEMBER_COOKIE_NAME)
        if remember_cookie:
            try:
                result = consume_remember_cookie(db, remember_cookie)
                if result:
                    user, new_cookie, expires = result
                    session.permanent = True
                    session['user_id'] = user.id
                    session['username'] = user.username
                    session['role'] = user.role
                    resp = make_response(redirect(
                        '/gestao_setores' if user.role == 'viewer' else
                        ('/inicio' if request.cookies.get('sistema_selecionado') == 'producao' else '/apontamento_qr')
                    ))
                    # remember cookie (consistent policy)
                    set_app_cookie(resp, config.REMEMBER_COOKIE_NAME, new_cookie, expires=expires, httponly=True, path='/')
                    return resp
            except Exception:
                logger.exception("Erro ao consumir remember cookie")

    if request.method == 'POST':
        # Log inicial do POST
        logger.debug("=== POST / LOGIN ===")
        logger.debug("Form recebido: %s", dict(request.form))
        logger.debug("Cookies na requisição: %s", dict(request.cookies))

        try:
            # Normalize username for search (case-insensitive)
            username_input = request.form.get('username', '').strip()
            username_norm = username_input.lower()
            password = request.form.get('password', '').strip()
            sistema_selecionado = request.form.get('sistema_selecionado', '').strip()
            lembrar = request.form.get('lembrar')

            logger.debug("Usuário digitado: %s | Sistema selecionado: %s | Lembrar: %s",
                         username_input, sistema_selecionado, lembrar)

            if not username_input:
                flash("Preencha seu usuário.", "error")
            elif not password:
                flash("Preencha sua senha.", "error")
            elif not sistema_selecionado:
                flash("Selecione um sistema.", "error")
            else:
                # case-insensitive lookup using SQL func.lower
                user = db.query(User).filter(func.lower(User.username) == username_norm).first()
                valid = False

                logger.debug("Usuario encontrado: %s", getattr(user, 'id', None))

                if user:
                    stored_hash = (user.password or '').strip()
                    logger.debug("stored_hash preview: %s", (stored_hash[:30] + '...') if stored_hash else '<empty>')
                    # Use passlib context to automatically verify any supported hash
                    try:
                        valid = pwd_context.verify(password, stored_hash)
                    except Exception as e:
                        # If hash is unknown, log it clearly
                        logger.exception("Erro ao verificar senha: %s", e)
                        valid = False

                logger.debug("Senha válida?: %s", valid)

                if valid:
                    # Successful login -> set session & cookies
                    session.permanent = True
                    session['user_id'] = user.id
                    session['username'] = user.username
                    session['role'] = user.role

                    resp = make_response(redirect(
                        '/gestao_setores' if user.role == 'viewer' else
                        ('/inicio' if sistema_selecionado == 'producao' else '/apontamento_qr')
                    ))

                    expires = datetime.now(timezone.utc) + timedelta(days=config.REMEMBER_COOKIE_DURATION_DAYS)

                    # set cookies using consistent helper so policy is uniform
                    set_app_cookie(resp, 'sistema_selecionado', sistema_selecionado, expires=expires, httponly=False, path='/')
                    set_app_cookie(resp, 'username', user.username, expires=expires, httponly=False, path='/')

                    if lembrar:
                        cookie_val, token_expires = create_remember_token(db, user.id, days=config.REMEMBER_COOKIE_DURATION_DAYS)
                        set_app_cookie(resp, config.REMEMBER_COOKIE_NAME, cookie_val, expires=token_expires, httponly=True, path='/')

                    logger.info("Login bem-sucedido para: %s (id=%s)", user.username, user.id)
                    logger.debug("Cookies definidos neste response? secure=%s samesite=%s", app.config['SESSION_COOKIE_SECURE'], app.config['SESSION_COOKIE_SAMESITE'])
                    return resp
                else:
                    logger.info("Falha no login para usuário: %s", username_input)
                    flash("Usuário não encontrado ou senha inválida.", "error")

                    return render_template(
                        'login.html',
                        username_cookie=username_cookie,
                        sistema_cookie=sistema_cookie,
                        show_menu=False  # sinaliza ao template para não renderizar o menu
                    )
        except Exception as e:
            logger.exception("ERRO GERAL NO LOGIN: %s", e)
            traceback.print_exc()
            return f"Erro interno no login: {e}", 500

    # Default return for a GET request when no other conditions are met
    return render_template(
        'login.html',
        username_cookie=username_cookie,
        sistema_cookie=sistema_cookie,
        show_menu=False
    )

def is_admin():
    """Retorna True se o usuário da sessão for admin."""
    return session.get('role') == 'admin'

def get_user_html():
    """
    Retorna um pequeno bloco HTML (ou string) com informações do usuário logado.
    O template pode mostrar isso com {{ user_html|safe }} se precisar renderizar HTML.
    """
    username = session.get('username')
    role = session.get('role', '')
    if not username:
        return ""
    # use Markup para evitar auto-escape caso queira HTML. No template, preferir {{ user_html|safe }}
    return Markup(f"<div class='user-info'>Usuário: <strong>{username}</strong> — <small>{role}</small></div>")

@app.context_processor
def inject_user_helpers():
    # user_html já é string; is_admin() -> bool
    # define show_menu True por padrão (templates podem sobrescrever)
    return dict(user_html=get_user_html(), is_admin=is_admin(), show_menu=True)

@app.route('/install', methods=['GET', 'POST'])
def install():
    db = SessionLocal()
    existing = db.query(User).first()
    if existing:
        return redirect(url_for('login'))

    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()
        role = request.form.get('role', 'admin')
        if not username or not password:
            flash("Usuário e senha são obrigatórios.", "error")
        else:
            # Use passlib context to hash new passwords (consistent)
            hashed = pwd_context.hash(password)
            u = User(username=username, password=hashed, role=role)
            db.add(u)
            try:
                db.commit()
                flash("Usuário criado. Faça login.", "success")
                return redirect(url_for('login'))
            except IntegrityError:
                db.rollback()
                flash("Nome de usuário já existe.", "error")
    return '''
    <h2>Instalação inicial</h2>
    <form method="post">
      <label>username: <input name="username"></label><br>
      <label>password: <input name="password" type="password"></label><br>
      <label>role:
        <select name="role">
          <option value="admin">admin</option>
          <option value="viewer">viewer</option>
        </select>
      </label><br>
      <button type="submit">Criar</button>
    </form>
    '''

# placeholders
@app.route('/gestao_setores')
def gestao_setores():
    return "<h2>Gestão de Setores (placeholder)</h2>"

@app.route('/inicio')
def inicio():
    # Proteção de rota: se não estiver logado, redireciona para o login
    if not session.get('user_id'):
        return redirect(url_for('login'))

    db = SessionLocal()
    try:
        # Busca o objeto do usuário para passar ao template
        user = db.query(User).filter_by(id=session.get('user_id')).first()

        # renderiza o template (seu template Jinja pode usar item.pedido ou item['pedido'])
        return render_template(
            "index.html",
            user=user  # Passa o objeto de usuário para o template
        )
    except Exception as e:
        logger.exception("Erro ao carregar pedidos: %s", e)
        traceback.print_exc()
        return f"Erro ao carregar pedidos: {e}", 500

@app.route('/api/slide-data')
def api_slide_data():
    """Endpoint da API para fornecer dados para o dashboard."""
    if not session.get('user_id'):
        return jsonify({"error": "Não autorizado"}), 401

    db = SessionLocal()
    try:
        sql = text("""
        SELECT
            c.cliente AS nome_cliente,
            cp.status_producao,
            e.equipamento_pai,
            p.conjunto
        FROM cliente AS c
        LEFT JOIN cliente_produto AS cp ON c.idcliente = cp.id_cliente
        LEFT JOIN equipamento_produto AS ep ON cp.id_equipamento_produto = ep.id_equipamento_produto
        LEFT JOIN equipamento AS e ON ep.idequipamento = e.idequipamento
        LEFT JOIN produto AS p ON ep.idproduto = p.idproduto
        WHERE cp.status_producao IS NOT NULL 
          AND cp.status_producao != ''
          AND cp.status_producao != 'Finalizado'
        ORDER BY c.idcliente
        """)
        result = db.execute(sql).mappings().all()
        # Converte a lista de RowMapping para uma lista de dicionários
        data = [dict(row) for row in result]
        return jsonify(data)
    except Exception as e:
        logger.exception("Erro na API /api/slide-data: %s", e)
        return jsonify({"error": "Erro interno ao buscar dados"}), 500

@app.route('/pedido', methods=['GET', 'POST'], endpoint='pedidos_page')
def pedido():
    db = SessionLocal()
    
    # Proteção de rota
    if not session.get('user_id'):
        return redirect(url_for('login'))

    # Lógica de exclusão (GET com parâmetro)
    if request.method == 'GET' and 'delete' in request.args:
        if not is_admin():
            flash("Você não tem permissão para excluir.", "error")
            return redirect(url_for('pedido')) # Redireciona para a mesma página
        
        pedido_id_to_delete = request.args.get('delete')
        if pedido_id_to_delete:
            try:
                # Corrigido para deletar da tabela 'pedido' usando 'idpedido'
                db.execute(text("DELETE FROM pedido WHERE idpedido = :id"), {'id': pedido_id_to_delete})
                db.commit()
                flash(f"Pedido {pedido_id_to_delete} excluído com sucesso.", "success")
            except Exception as e:
                db.rollback()
                flash(f"Erro ao excluir o pedido: {e}", "error")
        return redirect(url_for('pedido'))

    # Lógica de criação e edição (POST)
    if request.method == 'POST':
        # Edição de Pedido
        if 'submit_edit' in request.form:
            pedido_id = request.form.get('pedido_id')
            flash("Funcionalidade de edição ainda não implementada no backend.", "info")
        # Criação de Novo Pedido
        else:
            try:
                # Corrigido para inserir na tabela 'pedido' com as colunas corretas
                sql = text("""
                    INSERT INTO pedido (numero_pedido, idcliente, data_entrega, status, data_insercao) 
                    VALUES (:numero_pedido, :idcliente, :data_entrega, 'pendente', NOW())
                """)
                db.execute(sql, {
                    'numero_pedido': request.form.get('pedido'),
                    'idcliente': request.form.get('client_id'),
                    'data_entrega': request.form.get('data_entrega')
                })
                db.commit()
                flash("Novo pedido criado com sucesso!", "success")
            except Exception as e:
                db.rollback()
                flash(f"Erro ao criar o pedido: {e}", "error")

        return redirect(url_for('pedido'))

    # Lógica para carregar dados para a página (GET)
    try:
        # Busca o usuário logado para passar ao template
        user = db.query(User).filter_by(id=session.get('user_id')).first()

        # Corrigido para buscar das tabelas 'pedido' e 'add_cliente'
        pedidos_sql = text("""
            SELECT 
                p.idpedido, 
                p.numero_pedido, 
                ac.cliente, 
                ac.endereco,
                p.data_entrega,
                p.pdf
            FROM pedido p
            LEFT JOIN add_cliente ac ON p.idcliente = ac.idcliente
            ORDER BY p.idpedido DESC
        """)
        pedidos_result = db.execute(pedidos_sql).mappings().all()

        # Corrigido para buscar da tabela 'add_cliente'
        clientes_sql = text("SELECT idcliente, cliente, endereco FROM add_cliente ORDER BY cliente, endereco")
        clientes_result = db.execute(clientes_sql).mappings().all()
        
        clientes_agrupados = {}
        for cliente in clientes_result:
            nome = cliente['cliente']
            if nome not in clientes_agrupados:
                clientes_agrupados[nome] = []
            clientes_agrupados[nome].append({'id': cliente['idcliente'], 'endereco': cliente['endereco']})

        clientes_json = json.dumps(clientes_agrupados)

    except Exception as e:
        logger.exception("Erro ao carregar dados da página: %s", e)
        flash(f"Erro ao carregar dados da página: {e}", "error")
        # Garante que as variáveis existam mesmo em caso de erro
        pedidos_result = []
        clientes_json = "{}"
        user = db.query(User).filter_by(id=session.get('user_id')).first()

    return render_template(
        'pedidos.html',
        pedidos=pedidos_result,
        user=user, # Passa o objeto de usuário para o template
        clientes_json=Markup(clientes_json),
        is_admin=is_admin()
    )

@app.route('/trilhadeira')
def trilhadeira_page():
    """Placeholder para a página da Trilhadeira, para resolver o BuildError do menu."""
    return "<h2>Página da Trilhadeira (placeholder)</h2>"

@app.route('/cadastro_itens')
def cadastro_itens_page():
    """Placeholder para a página de Cadastro de Itens, para resolver o BuildError do menu."""
    return "<h2>Página de Cadastro de Itens (placeholder)</h2>"

@app.route('/material')
def material_page():
    """Placeholder para a página de Material, para resolver o BuildError do menu."""
    return "<h2>Página de Material (placeholder)</h2>"

@app.route('/cliente_produto')
def cliente_produto_page():
    """Placeholder para a página de Cliente/Produto, para resolver o BuildError do menu."""
    return "<h2>Página de Cliente/Produto (placeholder)</h2>"

@app.route('/apontamento_qr')
def apontamento_qr():
    return "<h2>Apontamento QR (placeholder)</h2>"

@app.route('/logout')
def logout():
    db = SessionLocal()
    user_id = session.get('user_id')
    if user_id:
        tokens = db.query(RememberToken).filter_by(user_id=user_id).all()
        for t in tokens:
            db.delete(t)
        db.commit()
    session.clear()
    resp = make_response(redirect(url_for('login')))
    # limpar cookie de remember com os mesmos atributos
    set_app_cookie(resp, config.REMEMBER_COOKIE_NAME, '', expires=0, httponly=True, path='/')
    return resp

def create_user_cli():
    db = SessionLocal()
    username = input("username: ").strip()
    password = input("password: ").strip()
    role = input("role [admin/viewer/editor/operador] (default admin): ").strip() or 'admin'
    hashed = pwd_context.hash(password)
    u = User(username=username, password=hashed, role=role)
    db.add(u)
    try:
        db.commit()
        print("Usuário criado.")
    except IntegrityError:
        db.rollback()
        print("Erro: usuário já existe.")

# Global exception handler (opcional, registra e mostra 500)
@app.errorhandler(Exception)
def handle_exception(e):
    logger.exception("Unhandled exception: %s", e)
    traceback.print_exc()
    return "Erro interno no servidor.", 500

if __name__ == '__main__':
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == '--create-user':
        create_user_cli()
        sys.exit(0)
    app.run(debug=app.debug, host='0.0.0.0', port=int(os.getenv('PORT', 5000)))
