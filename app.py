# app.py
import os
import secrets
import hashlib
import bcrypt as bcrypt_module  
import json              
from datetime import datetime, timezone, timedelta
from flask import (
    Flask, request, render_template, redirect, url_for, session, make_response, jsonify, send_file, abort, current_app, flash
)
from markupsafe import Markup
from werkzeug.security import check_password_hash
from werkzeug.utils import secure_filename
from sqlalchemy import func, desc
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import scoped_session, sessionmaker
from sqlalchemy import text
# models & config
from models import Base, User, RememberToken, get_engine, get_session
import config

# passlib handlers (passlib bcrypt + legacy handlers)
from passlib.context import CryptContext
from menu_content import get_user_html, is_admin
from menu import menu_bp

# optional: small debug prints at startup

# Setup passlib context for multiple hash formats
pwd_context = CryptContext(
    schemes=["bcrypt", "phpass", "md5_crypt", "pbkdf2_sha256"],
    deprecated="auto"
)

app = Flask(__name__, static_folder='static', template_folder='templates')
app.secret_key = config.SECRET_KEY
app.permanent_session_lifetime = config.PERMANENT_SESSION_LIFETIME
app.register_blueprint(menu_bp)

# Database setup
engine = get_engine()
Base.metadata.create_all(engine)
SessionLocal = scoped_session(sessionmaker(bind=engine))

@app.teardown_appcontext
def shutdown_session(exception=None):
    """Garante que a sessão do banco de dados seja removida após cada requisição."""
    SessionLocal.remove()


# Logger (write simple debug + timings)
def write_debug_log(entries: dict):
    with open(config.LOG_FILE, 'a', encoding='utf-8') as f:
        f.write(datetime.now(timezone.utc).strftime('[%Y-%m-%d %H:%M:%S] '))
        for k, v in entries.items():
            f.write(f"{k}: {v}\n")
        f.write("\n")

@app.before_request
def before_request_logging():
    entries = {
        "REQUEST_METHOD": request.method,
        "QUERY_STRING": request.query_string.decode('utf-8', errors='ignore'),
        "HTTP_X_REQUESTED_WITH": request.headers.get('X-Requested-With', 'NOT SET'),
        "SERVER_NAME": request.host,
        "SCRIPT_NAME": request.path
    }
    write_debug_log(entries)

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
                resp.set_cookie(config.REMEMBER_COOKIE_NAME, new_cookie, expires=expires, httponly=True, samesite='Lax')
                return resp

    if request.method == 'POST':
        # Normalize username for search (case-insensitive)
        username_input = request.form.get('usuario', '').strip()
        username_norm = username_input.lower()
        password = request.form.get('senha', '').strip()
        sistema_selecionado = request.form.get('sistema_selecionado', '').strip()
        lembrar = request.form.get('lembrar')

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

            if user:
                stored_hash = (user.password or '').strip()
                # Use passlib context to automatically verify any supported hash
                try:
                    valid = pwd_context.verify(password, stored_hash)
                except Exception:
                    valid = False

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
                resp.set_cookie('sistema_selecionado', sistema_selecionado, expires=expires, path='/', httponly=False, samesite='Lax')
                resp.set_cookie('username', user.username, expires=expires, path='/', httponly=False, samesite='Lax')

                if lembrar:
                    cookie_val, token_expires = create_remember_token(db, user.id, days=config.REMEMBER_COOKIE_DURATION_DAYS)
                    resp.set_cookie(config.REMEMBER_COOKIE_NAME, cookie_val, expires=token_expires, httponly=True, samesite='Lax')

                return resp
            else:
                flash("Usuário não encontrado ou senha inválida.", "error")

                return render_template(
                'login.html',
                username_cookie=username_cookie,
                sistema_cookie=sistema_cookie,
                show_menu=False  # sinaliza ao template para não renderizar o menu
            )

    # Default return for a GET request when no other conditions are met
    return render_template(
        'login.html',
        username_cookie=username_cookie,
        sistema_cookie=sistema_cookie,
        show_menu=False
    )

@app.context_processor
def inject_user_helpers():
    # user_html já é string; is_admin() -> bool
    # define show_menu True por padrão (templates podem sobrescrever)
    return dict(user_html=get_user_html(), is_admin=is_admin(), show_menu=True)


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
    db = SessionLocal()
    try:
        sql = text("""
        SELECT c.idcliente,
               c.pedido,
               c.cliente AS nome_cliente,
               c.endereco,
               cp.id_vinculo,
               cp.status_producao,
               e.equipamento_pai,
               p.conjunto
        FROM cliente AS c
        LEFT JOIN cliente_produto AS cp ON c.idcliente = cp.id_cliente
        LEFT JOIN equipamento_produto AS ep ON cp.id_equipamento_produto = ep.id_equipamento_produto
        LEFT JOIN equipamento AS e ON ep.idequipamento = e.idequipamento
        LEFT JOIN produto AS p ON ep.idproduto = p.idproduto
        WHERE cp.id_vinculo IS NOT NULL
        ORDER BY c.idcliente
        """)
        result = db.execute(sql)
        rows = result.mappings().all() # SQLAlchemy 2.0+ style

        if not rows:
            return "Nenhum pedido encontrado."

        # agrupa por id_vinculo (mesma estrutura que o PHP)
        pedidos = {}
        for r in rows:
            key = r.get('id_vinculo')
            pedidos.setdefault(key, []).append(r)

        # renderiza o template (seu template Jinja pode usar item.pedido ou item['pedido'])
        return render_template(
            "inicio.html",
            pedidos=pedidos,
            user_html=get_user_html(),
            is_admin=is_admin()
        )

    except Exception as e:
        import traceback
        traceback.print_exc()
        return f"Erro ao carregar pedidos: {e}", 500

@app.route('/pedido', methods=['GET', 'POST'])
def pedido():
    db = SessionLocal()
    
    # Proteção de rota
    if not session.get('user_id'):
        return redirect(url_for('login'))

    # Lógica de exclusão (GET com parâmetro)
    if request.method == 'GET' and 'delete' in request.args:
        if not is_admin():
            flash("Você não tem permissão para excluir pedidos.", "error")
            return redirect(url_for('pedido'))
        
        pedido_id_to_delete = request.args.get('delete')
        if pedido_id_to_delete:
            try:
                # Usando SQL puro para deletar da tabela 'cliente' que parece conter os pedidos
                # ATENÇÃO: Verifique se o nome da tabela e a coluna de ID estão corretos.
                # Assumindo que 'cliente' é a tabela e 'idcliente' é a chave primária.
                db.execute(text("DELETE FROM cliente WHERE idcliente = :id"), {'id': pedido_id_to_delete})
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
            # Lógica para atualizar o pedido no banco de dados.
            # Esta parte precisa ser implementada com base na sua estrutura de DB.
            # Exemplo:
            # pedido_obj = db.execute(text("SELECT * FROM cliente WHERE idcliente = :id"), {'id': pedido_id}).first()
            # if pedido_obj:
            #     db.execute(text("""
            #         UPDATE cliente SET pedido = :num, cliente = :nome, endereco = :local, data_entrega = :data 
            #         WHERE idcliente = :id
            #     """), {
            #         'num': request.form.get('edit_pedido'),
            #         'nome': request.form.get('edit_cliente'),
            #         'local': request.form.get('edit_local'),
            #         'data': request.form.get('edit_data_entrega'),
            #         'id': pedido_id
            #     })
            #     db.commit()
            #     flash("Pedido atualizado com sucesso.", "success")
            flash("Funcionalidade de edição ainda não implementada no backend.", "info")

        # Criação de Novo Pedido
        else:
            try:
                # ATENÇÃO: Assumindo que a tabela 'cliente' armazena os pedidos.
                # O nome da tabela e das colunas deve ser verificado.
                # O campo 'client_id' do formulário parece ser o 'id_vinculo_cliente'
                # que relaciona o cliente ao seu endereço.
                sql = text("""
                    INSERT INTO cliente (pedido, id_vinculo_cliente, data_entrega) 
                    VALUES (:pedido, :client_id, :data_entrega)
                """)
                db.execute(sql, {
                    'pedido': request.form.get('pedido'),
                    'client_id': request.form.get('client_id'),
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
        # Carregar lista de pedidos
        # Esta query junta as tabelas para obter os detalhes do pedido.
        # Verifique os nomes das tabelas e colunas.
        pedidos_sql = text("""
            SELECT 
                c.idcliente, 
                c.pedido as numero_pedido, 
                vc.nome_cliente as cliente, 
                vc.endereco,
                c.data_entrega,
                c.pdf
            FROM cliente c
            JOIN vinculo_cliente vc ON c.id_vinculo_cliente = vc.id
            ORDER BY c.idcliente DESC
        """)
        pedidos_result = db.execute(pedidos_sql).mappings().all()

        # Carregar clientes para os modais
        clientes_sql = text("SELECT id, nome_cliente, endereco FROM vinculo_cliente ORDER BY nome_cliente, endereco")
        clientes_result = db.execute(clientes_sql).mappings().all()
        
        clientes_agrupados = {}
        for cliente in clientes_result:
            nome = cliente['nome_cliente']
            if nome not in clientes_agrupados:
                clientes_agrupados[nome] = []
            clientes_agrupados[nome].append({'id': cliente['id'], 'endereco': cliente['endereco']})

        clientes_json = json.dumps(clientes_agrupados)

    except Exception as e:
        flash(f"Erro ao carregar dados da página: {e}", "error")
        pedidos_result = []
        clientes_json = "{}"

    return render_template(
        'pedido.html',
        pedidos=pedidos_result,
        clientes_json=Markup(clientes_json),
        is_admin=is_admin()
    )

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
    resp.set_cookie(config.REMEMBER_COOKIE_NAME, '', expires=0)
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

if __name__ == '__main__':
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == '--create-user':
        create_user_cli()
        sys.exit(0)
    app.run(debug=True, host='0.0.0.0', port=5000)
