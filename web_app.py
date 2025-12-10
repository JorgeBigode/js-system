from flask import Flask, render_template, jsonify, request, redirect, url_for, session, flash, send_from_directory, send_file
import pymysql
from config import DB_HOST, DB_USER, DB_PASS, DB_NAME
from werkzeug.security import check_password_hash
from werkzeug.utils import secure_filename
from functools import wraps
import datetime
import os
import io
import logging

try:
    from docxtpl import DocxTemplate
except ImportError:
    DocxTemplate = None

logging.basicConfig(level=logging.DEBUG)  # Configure o nível de log no início do arquivo

# Inicializa a aplicação Flask
app = Flask(__name__)
# Chave secreta para gerenciar sessões de usuário. ESSENCIAL para o login funcionar.
# Mude para um valor seguro e aleatório.
app.secret_key = 'chave-secreta-para-a-sessao-web'

UPLOAD_FOLDER = 'pdfs'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

def get_db_connection():
    """Cria e retorna uma conexão com o banco de dados."""
    connection = pymysql.connect(
        host=DB_HOST,
        user=DB_USER,
        password=DB_PASS,
        database=DB_NAME,
        charset='utf8mb4',
        cursorclass=pymysql.cursors.DictCursor
    )
    return connection

def login_required(f):
    """
    Decorator que verifica se o usuário está logado.
    Se não estiver, redireciona para a página de login.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Se o usuário não estiver logado
        if 'user_id' not in session: 
            # Se a requisição for uma chamada de API (XHR), retorna erro 401 em JSON
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify(error="Sessão expirada. Por favor, faça login novamente."), 401
            # Se for uma navegação normal, redireciona para a página de login
            else:
                flash('Por favor, faça login para acessar esta página.', 'warning')
                return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

@app.route('/login', methods=['GET', 'POST'])
def login():
    """Renderiza a página de login e processa o formulário de autenticação."""
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        if not username or not password:
            flash('Preencha todos os campos!', 'danger')
            return redirect(url_for('login'))

        try:
            with get_db_connection() as connection:
                with connection.cursor() as cursor:
                    # Busca usuário no banco (lógica igual ao seu login_app.py)
                    sql = "SELECT * FROM usuarios WHERE username = %s"
                    cursor.execute(sql, (username,))
                    user = cursor.fetchone()

                    # Verifica se o usuário existe e a senha está correta
                    if user and check_password_hash(user['password'], password):
                        # Armazena informações do usuário na sessão para "lembrar" dele
                        session.clear()
                        session['user_id'] = user['id']
                        session['username'] = user['username']
                        session['role'] = user['role']

                        # Atualiza último acesso (lógica igual ao seu login_app.py)
                        now = datetime.datetime.now()
                        update_sql = "UPDATE usuarios SET ultimo_acesso = %s, status = 'online' WHERE id = %s"
                        cursor.execute(update_sql, (now, user['id']))
                        connection.commit()

                        flash(f"Bem-vindo, {user['username']}!", 'success')
                        return redirect(url_for('home')) # Redireciona para a página principal
                    else:
                        flash('Usuário ou senha incorretos!', 'danger')
        except Exception as e:
            print(f"Erro ao autenticar na web: {e}")
            flash('Ocorreu um erro durante a autenticação. Tente novamente.', 'danger')

    # Se for um GET ou se o login falhar, mostra a página de login
    return render_template('login.html')

@app.route('/logout')
def logout():
    """Limpa a sessão do usuário e o redireciona para a tela de login."""
    session.clear()
    flash('Você foi desconectado com sucesso.', 'info')
    return redirect(url_for('login'))

@app.route('/')
@login_required # <-- AGORA ESTA PÁGINA EXIGE LOGIN
def home(): # type: ignore
    """Renderiza a página inicial."""
    user_info = {}
    try:
        with get_db_connection() as connection, connection.cursor() as cursor:
            # Busca todos os dados do usuário, incluindo o último acesso
            cursor.execute("SELECT username, role, ultimo_acesso FROM usuarios WHERE id = %s", (session['user_id'],))
            user_info = cursor.fetchone()
    except Exception as e:
        print(f"Erro ao buscar dados do usuário: {e}")
    # Garante que 'user' sempre tenha os dados, mesmo em caso de erro
    user = user_info or {'username': session.get('username'), 'role': session.get('role'), 'ultimo_acesso': None}
    return render_template('index.html', user=user)

@app.route('/api/slide-data')
@login_required # <-- A API TAMBÉM EXIGE LOGIN
def get_slide_data(): # type: ignore
    """Endpoint de API para buscar os dados do slide show."""
    try:
        with get_db_connection() as connection, connection.cursor() as cursor:
            sql = """
                SELECT 
                    p.idpedido,
                    p.numero_pedido AS pedido,
                    ac.cliente AS nome_cliente,
                    ac.endereco,
                    ci.id_item AS id_vinculo,
                    ci.status_producao,
                    pai.descricao AS equipamento_pai,
                    filho.descricao AS conjunto
                FROM cliente_item ci
                JOIN pedido p ON ci.idpedido = p.idpedido
                JOIN add_cliente ac ON p.idcliente = ac.idcliente
                JOIN itens pai ON ci.item_raiz_id = pai.id
                JOIN itens filho ON ci.id_item_fk = filho.id
                ORDER BY p.idpedido DESC;
            """
            cursor.execute(sql)
            slide_data = cursor.fetchall()
        return jsonify(slide_data)
    except Exception as e:
        print(f"Erro na API: {e}")
        return jsonify({"error": "Erro ao buscar dados"}), 500

@app.route('/pedidos')
@login_required
def pedidos_page(): # type: ignore
    """Renderiza a página de gerenciamento de pedidos."""
    # Cria um objeto 'user' para ser consistente com outros templates que herdam de layout.html
    user = {
        'username': session.get('username'),
        'role': session.get('role', 'user')
    }
    return render_template('pedidos.html', user=user)

@app.route('/api/pedidos', methods=['GET'])
@login_required
def get_pedidos(): # type: ignore
    """API para buscar todos os pedidos."""
    try:
        with get_db_connection() as connection, connection.cursor() as cursor:
            sql = """
                SELECT 
                    p.idpedido, p.numero_pedido, p.data_entrega, p.pdf,
                    c.idcliente, c.cliente, c.endereco
                FROM pedido p
                LEFT JOIN add_cliente c ON p.idcliente = c.idcliente
                ORDER BY p.numero_pedido DESC
            """
            cursor.execute(sql)
            pedidos = cursor.fetchall()
            # Formata a data para o frontend
            for pedido in pedidos:
                # Formata a data
                if pedido['data_entrega']:
                    pedido['data_entrega'] = pedido['data_entrega'].strftime('%Y-%m-%d')
                
                # Cria os campos 'id' e 'display' que o frontend espera para o modal de seleção
                pedido['id'] = pedido['idpedido']
                pedido['display'] = f"Nº {pedido['numero_pedido']} - {pedido.get('cliente', 'Cliente não definido')}"
            return jsonify(pedidos)
    except Exception as e:
        print(f"Erro na API de pedidos: {e}")
        return jsonify({"error": "Erro ao buscar pedidos"}), 500

@app.route('/api/pedidos', methods=['POST'])
@login_required
def create_pedido(): # type: ignore
    """API para criar um novo pedido."""
    try:
        numero_pedido = request.form['numero_pedido']
        idcliente = request.form['idcliente']
        data_entrega = request.form['data_entrega']
        pdf_file = request.files.get('pdf')

        pdf_filename = None
        if pdf_file and pdf_file.filename != '':
            pdf_filename = secure_filename(pdf_file.filename)
            pdf_path = os.path.join(app.config['UPLOAD_FOLDER'], pdf_filename)
            pdf_file.save(pdf_path)

        with get_db_connection() as connection, connection.cursor() as cursor:
            sql = "INSERT INTO pedido (numero_pedido, idcliente, data_entrega, pdf) VALUES (%s, %s, %s, %s)"
            cursor.execute(sql, (numero_pedido, idcliente, data_entrega, pdf_filename))
            connection.commit()

        return jsonify({"success": True, "message": "Pedido criado com sucesso!"}), 201

    except Exception as e:
        print(f"Erro ao criar pedido: {e}")
        return jsonify({"error": "Erro ao criar pedido"}), 500

@app.route('/api/pedidos/<int:pedido_id>', methods=['PUT'])
@login_required
def update_pedido(pedido_id): # type: ignore
    """API para atualizar um pedido existente."""
    try:
        numero_pedido = request.form['numero_pedido']
        idcliente = request.form['idcliente']
        data_entrega = request.form['data_entrega']
        pdf_file = request.files.get('pdf')

        with get_db_connection() as connection, connection.cursor() as cursor:
            # Busca o nome do PDF antigo para possível exclusão (se um novo for enviado)
            cursor.execute("SELECT pdf FROM pedido WHERE idpedido = %s", (pedido_id,))
            old_pdf = cursor.fetchone()

            pdf_filename = old_pdf['pdf'] if old_pdf else None
            if pdf_file and pdf_file.filename != '':
                pdf_filename = secure_filename(pdf_file.filename)
                pdf_path = os.path.join(app.config['UPLOAD_FOLDER'], pdf_filename)
                pdf_file.save(pdf_path)
                # Opcional: remover o arquivo PDF antigo se os nomes forem diferentes
                if old_pdf and old_pdf['pdf'] and old_pdf['pdf'] != pdf_filename:
                    old_pdf_path = os.path.join(app.config['UPLOAD_FOLDER'], old_pdf['pdf'])
                    if os.path.exists(old_pdf_path):
                        os.remove(old_pdf_path)

            sql = "UPDATE pedido SET numero_pedido = %s, idcliente = %s, data_entrega = %s, pdf = %s WHERE idpedido = %s"
            cursor.execute(sql, (numero_pedido, idcliente, data_entrega, pdf_filename, pedido_id))
            connection.commit()

        return jsonify({"success": True, "message": "Pedido atualizado com sucesso!"})

    except Exception as e:
        print(f"Erro ao atualizar pedido: {e}")
        return jsonify({"error": "Erro ao atualizar pedido"}), 500

@app.route('/api/clientes', methods=['GET'])
@login_required
def get_clientes(): # type: ignore
    """API para buscar todos os nomes de clientes únicos."""
    try:
        with get_db_connection() as connection, connection.cursor() as cursor:
            # Usamos DISTINCT para evitar nomes de clientes duplicados
            cursor.execute("SELECT DISTINCT cliente FROM add_cliente ORDER BY cliente")
            clientes = cursor.fetchall()
            return jsonify([c['cliente'] for c in clientes])
    except Exception as e:
        print(f"Erro na API de clientes: {e}")
        return jsonify({"error": "Erro ao buscar clientes"}), 500

@app.route('/api/enderecos', methods=['GET'])
@login_required
def get_enderecos(): # type: ignore
    """API para buscar endereços de um cliente específico."""
    cliente_nome = request.args.get('cliente')
    if not cliente_nome:
        return jsonify({"error": "Nome do cliente é obrigatório"}), 400
    try:
        with get_db_connection() as connection, connection.cursor() as cursor:
            # Retorna o id e o endereço para um dado nome de cliente
            sql = "SELECT idcliente, endereco FROM add_cliente WHERE cliente = %s ORDER BY endereco"
            cursor.execute(sql, (cliente_nome,))
            enderecos = cursor.fetchall()
            return jsonify(enderecos)
    except Exception as e:
        print(f"Erro na API de endereços: {e}")
        return jsonify({"error": "Erro ao buscar endereços"}), 500

@app.route('/api/clientes', methods=['POST'])
@login_required
def create_cliente(): # type: ignore
    """API para criar um novo cliente."""
    data = request.get_json()
    try:
        with get_db_connection() as connection, connection.cursor() as cursor:
            sql = "INSERT INTO add_cliente (cliente, endereco) VALUES (%s, %s)"
            cursor.execute(sql, (data['cliente'], data['endereco']))
            connection.commit()
            return jsonify({"success": True, "message": "Cliente criado com sucesso!"}), 201
    except Exception as e:
        print(f"Erro ao criar cliente: {e}")
        return jsonify({"error": "Erro ao criar cliente"}), 500

@app.route('/api/pedidos/<int:pedido_id>/gerar-folha')
@login_required
def gerar_folha_pedido(pedido_id): # type: ignore
    """Gera e serve a Folha de Pedido em formato .docx."""
    if not DocxTemplate:
        return jsonify({"error": "A biblioteca 'docx-template' não está instalada no servidor."}), 500

    template_path = 'PEDIDO.docx'
    if not os.path.exists(template_path):
        return jsonify({"error": f"O template '{template_path}' não foi encontrado no servidor."}), 500

    try:
        with get_db_connection() as connection, connection.cursor() as cursor:
            # 1. Buscar informações principais do pedido
            sql_pedido = """
                SELECT p.numero_pedido, p.data_entrega, c.cliente, c.endereco
                FROM pedido p
                JOIN add_cliente c ON p.idcliente = c.idcliente
                WHERE p.idpedido = %s
            """
            cursor.execute(sql_pedido, (pedido_id,))
            pedido_info = cursor.fetchone()

            if not pedido_info:
                return jsonify({"error": "Pedido não encontrado."}), 404

            # 2. Buscar produtos e quantidades (conforme lógica do app de exemplo)
            sql_produtos = """
                SELECT 
                    parent.descricao, 
                    SUM(ci.quantidade_prod) as quantidade
                FROM cliente_item ci
                JOIN item_composicao ic ON ci.id_composicao = ic.id
                JOIN itens parent ON ic.id_item_pai = parent.id
                WHERE ci.idpedido = %s
                GROUP BY parent.descricao
            """
            cursor.execute(sql_produtos, (pedido_id,))
            produtos_data = cursor.fetchall()

    except Exception as e:
        print(f"Erro de banco de dados ao gerar folha: {e}")
        return jsonify({"error": "Erro ao buscar dados para a folha de pedido."}), 500

    # 3. Preparar o contexto para o template
    data_entrega_obj = pedido_info.get('data_entrega')
    data_entrega_str = data_entrega_obj.strftime('%d/%m/%Y') if data_entrega_obj else ''

    context = {
        'CLIENTE': pedido_info.get('cliente', '').upper(),
        'ENDERECO': pedido_info.get('endereco', '').upper(),
        'PEDIDO': pedido_info.get('numero_pedido', ''),
        'DATA': data_entrega_str,
        'produtos': produtos_data
    }

    doc = DocxTemplate(template_path)
    doc.render(context)

    # 4. Salvar em memória e enviar como arquivo
    file_stream = io.BytesIO()
    doc.save(file_stream)
    file_stream.seek(0)

    return send_file(
        file_stream,
        as_attachment=True,
        download_name=f"Folha_Pedido_{pedido_info.get('numero_pedido', 'desconhecido')}.docx",
        mimetype='application/vnd.openxmlformats-officedocument.wordprocessingml.document'
    )

# Rota para servir os arquivos de PDF de forma segura
@app.route('/pdfs/<filename>')
@login_required # type: ignore
def serve_pdf(filename):
    # Supondo que os PDFs estão em uma pasta 'pdfs' na raiz do projeto
    return send_from_directory('pdfs', filename)

# Rota para a página da Trilhadeira
@app.route('/trilhadeira') # type: ignore
@login_required
def trilhadeira_page():
    """Renderiza a página da Trilhadeira."""
    # Cria um objeto 'user' para ser consistente com outros templates que herdam de layout.html
    user = {
        'username': session.get('username'),
        'role': session.get('role', 'user') # Fornece um papel padrão se não estiver definido
    }
    return render_template('trilhadeira.html', user=user)

# Rota de API para buscar os dados da Trilhadeira
@app.route('/api/trilhadeira')
@login_required # type: ignore
def get_trilhadeira_data():
    connection = None # Garante que a variável exista
    try:
        connection = get_db_connection() # Use sua função existente para conectar ao DB
        with connection.cursor() as cursor:
            # Esta query é uma adaptação da que está no seu código Tkinter
            sql = """
                SELECT 
                    p.idpedido, p.numero_pedido, ac.cliente, ac.endereco, p.data_entrega,
                    pt.idpedidos_tr, pt.status, pt.modelo, pt.montagem, pt.frete, 
                    pt.frequencia, pt.bica, pt.n_serie, pt.observacao
                FROM pedidos_tr AS pt
                JOIN pedido AS p ON pt.id_pedido = p.idpedido
                JOIN add_cliente AS ac ON p.idcliente = ac.idcliente
                ORDER BY p.data_entrega DESC, p.idpedido DESC
            """
            cursor.execute(sql)
            data = cursor.fetchall()
            
            # Converte objetos datetime para string para serem serializáveis em JSON
            for row in data:
                if row.get('data_entrega'):
                    row['data_entrega'] = row['data_entrega'].isoformat()

            return jsonify(data)
    except Exception as e:
        print(f"Erro na API da trilhadeira: {e}") # Adiciona um log do erro no console
        return jsonify({"error": str(e)}), 500
    finally:
        if connection:
            connection.close()

# Rota de API para buscar equipamentos disponíveis para a Trilhadeira
@app.route('/api/equipamentos-tr', methods=['GET'])
@login_required # type: ignore
def get_equipamentos_tr():
    """
    Endpoint para buscar equipamentos que podem ser adicionados à trilhadeira.
    Retorna uma lista de equipamentos em formato JSON.
    """
    connection = None
    try:
        connection = get_db_connection()
        with connection.cursor() as cursor:
            # Esta query busca itens de pedidos que ainda não foram adicionados à tabela 'pedidos_tr'.
            # Isso garante que você só possa adicionar um pedido à trilhadeira uma vez.
            sql = """
                SELECT DISTINCT i.id, i.descricao
                FROM itens i
                JOIN cliente_item ci ON i.id = ci.item_raiz_id
                WHERE ci.idpedido NOT IN (SELECT id_pedido FROM pedidos_tr)
                ORDER BY i.descricao;
            """

            cursor.execute(sql)
            equipamentos = cursor.fetchall()
        
        return jsonify(equipamentos)

    except Exception as e:
        print(f"Erro ao buscar equipamentos-tr: {e}")
        return jsonify({"error": "Falha ao buscar equipamentos no servidor"}), 500
    finally:
        if connection:
            connection.close()

# Rota para a página Cliente x Produto
@app.route('/cliente-produto')
@login_required # type: ignore
def cliente_produto_page():
    """Renderiza a página de vínculo Cliente x Produto."""
    user = {
        'username': session.get('username'),
        'role': session.get('role', 'user')
    }
    return render_template('cliente_produto.html', user=user)

@app.route('/api/itens-raiz', methods=['GET'])
@login_required
def get_itens_raiz(): # type: ignore
    """API para buscar todos os itens que são 'pais' (equipamentos)."""
    try:
        with get_db_connection() as connection, connection.cursor() as cursor:
            # Esta query busca todos os itens que são pais na tabela de composição,
            # ou seja, os equipamentos principais.
            sql = """ 
                SELECT DISTINCT i.id, i.codigo, i.descricao 
                FROM itens i
                JOIN item_composicao ic ON i.id = ic.id_item_pai
                ORDER BY i.descricao;
            """
            cursor.execute(sql)
            itens_raiz = cursor.fetchall()
            # Adiciona o campo 'display' a cada item para o frontend
            for item in itens_raiz:
                item['display'] = f"({item['codigo']}) {item['descricao']}"
            return jsonify(itens_raiz)
    except Exception as e:
        print(f"Erro na API de itens raiz: {e}")
        return jsonify({"error": "Erro ao buscar itens raiz"}), 500

@app.route('/api/composicao/<int:item_pai_id>', methods=['GET'])
@login_required
def get_composicao_por_pai(item_pai_id): # type: ignore
    """API para buscar a composição (filhos) de um item pai específico."""
    try:
        with get_db_connection() as connection, connection.cursor() as cursor:
            sql = """
                SELECT 
                    ic.id AS id_composicao,
                    ic.id_item_filho,
                    i.codigo AS codigo_filho,
                    i.descricao AS descricao_filho,
                    ic.quantidade
                FROM item_composicao ic
                JOIN itens i ON ic.id_item_filho = i.id
                WHERE ic.id_item_pai = %s
                ORDER BY i.descricao;
            """
            cursor.execute(sql, (item_pai_id,))
            composicao = cursor.fetchall()
            # Adiciona o campo 'display' esperado pelo frontend
            for item in composicao:
                item['display'] = f"({item['codigo_filho']}) {item['descricao_filho']}"
            return jsonify(composicao)
    except Exception as e:
        print(f"Erro na API de composição: {e}")
        return jsonify({"error": "Erro ao buscar composição do item"}), 500

@app.route('/api/vinculos-pedido/<int:pedido_id>', methods=['GET'])
@login_required
def get_vinculos_por_pedido_id(pedido_id): # type: ignore
    """API para buscar os vínculos de itens para um pedido específico."""
    try:
        with get_db_connection() as connection, connection.cursor() as cursor:
            sql = """
                SELECT 
                    ci.id_item      AS id_vinculo,
                    filho.id        AS id_item,
                    filho.codigo    AS codigo_item,
                    filho.descricao AS descricao_item,
                    ci.quantidade_prod AS quantidade,
                    ci.status_producao AS status,
                    CONCAT(ci.item_raiz_id, '-', ci.id_item_fk) AS caminho_estrutura,
                    pai.descricao   AS equipamento
                FROM cliente_item ci
                JOIN itens pai ON ci.item_raiz_id = pai.id
                JOIN itens filho ON ci.id_item_fk = filho.id
                WHERE ci.idpedido = %s
                ORDER BY pai.descricao, filho.descricao;
            """
            cursor.execute(sql, (pedido_id,))
            vinculos = cursor.fetchall()
            return jsonify(vinculos)
    except Exception as e:
        print(f"Erro na API de vínculos por pedido: {e}")
        return jsonify({"error": "Erro ao buscar vínculos do pedido"}), 500

@app.route('/api/vincular-item', methods=['POST'])
@login_required
def vincular_item(): # type: ignore
    """API para criar um novo vínculo de item a um pedido."""
    data = request.get_json()
    try:
        with get_db_connection() as connection, connection.cursor() as cursor:
            # Lógica simplificada para inserir os itens selecionados
            # Uma lógica mais complexa (como a do app desktop) poderia ser implementada aqui
            for id_comp in data['id_composicoes']:
                # Buscar id_item_filho a partir do id_composicao
                cursor.execute("SELECT id_item_filho FROM item_composicao WHERE id = %s", (id_comp,))
                comp_info = cursor.fetchone()
                if not comp_info:
                    continue

                sql = """
                    INSERT INTO cliente_item 
                    (idpedido, id_item_fk, id_composicao, quantidade_prod, item_raiz_id, status_producao, data_engenharia)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                """
                params = (
                    data['id_pedido'], comp_info['id_item_filho'], id_comp, data['quantidade_base'],
                    data['id_item_raiz'], 'Aguardando Programação', datetime.datetime.now()
                )
                cursor.execute(sql, params)
            connection.commit()
        return jsonify({"message": "Vínculo(s) criado(s) com sucesso!"}), 201
    except Exception as e:
        print(f"Erro ao vincular item: {e}")
        return jsonify({"error": "Erro ao criar vínculo"}), 500

@app.route('/api/vinculo/<int:vinculo_id>/quantidade', methods=['PUT'])
@login_required
def update_vinculo_quantidade(vinculo_id): # type: ignore
    data = request.get_json()
    with get_db_connection() as conn, conn.cursor() as cursor:
        cursor.execute("UPDATE cliente_item SET quantidade_prod = %s WHERE id_item = %s", (data['quantidade'], vinculo_id))
        conn.commit()
    return jsonify({"message": "Quantidade atualizada com sucesso!"})

@app.route('/api/vinculo/<int:vinculo_id>', methods=['DELETE']) # type: ignore
@login_required # type: ignore
def delete_vinculo(vinculo_id):
    with get_db_connection() as conn, conn.cursor() as cursor:
        cursor.execute("DELETE FROM cliente_item WHERE id_item = %s", (vinculo_id,))
        conn.commit()
    return jsonify({"message": "Vínculo excluído com sucesso!"})

@app.route('/cadastro-itens') # type: ignore
@login_required
def cadastro_itens_page():
    """Renderiza a página de Cadastro de Itens."""
    user = {
        'username': session.get('username'),
        'role': session.get('role', 'user')
    }
    # Assuming you have a 'cadastro_itens.html' template
    return render_template('cadastro_itens.html', user=user)

@app.route('/api/itens', methods=['GET'])
@login_required
def get_itens(): # type: ignore
    """API para buscar todos os itens."""
    try:
        with get_db_connection() as connection, connection.cursor() as cursor:
            # Retorna todos os itens para preencher as listas no frontend
            sql = "SELECT id, codigo, descricao FROM itens ORDER BY descricao"
            cursor.execute(sql)
            itens = cursor.fetchall()
            return jsonify(itens)
    except Exception as e:
        print(f"Erro na API de itens: {e}")
        return jsonify({"error": "Erro ao buscar itens"}), 500

@app.route('/api/item-composicao', methods=['GET'])
@login_required
def get_item_composicao(): # type: ignore
    """API para buscar toda a hierarquia de composição de itens."""
    try:
        with get_db_connection() as connection, connection.cursor() as cursor:
            sql = """
                SELECT 
                    ic.id, 
                    ic.id_item_pai,
                    p.codigo AS pai_codigo,
                    p.descricao AS pai_desc,
                    ic.id_item_filho,
                    f.codigo AS filho_codigo,
                    f.descricao AS filho_desc,
                    ic.quantidade
                FROM item_composicao ic
                /* Junta com a tabela de itens para obter os dados do PAI */
                JOIN itens p ON ic.id_item_pai = p.id
                /* Junta com a tabela de itens novamente para obter os dados do FILHO */
                JOIN itens f ON ic.id_item_filho = f.id
                ORDER BY p.descricao, f.descricao;
            """
            cursor.execute(sql)
            composicao = cursor.fetchall()
            return jsonify(composicao)
    except Exception as e:
        print(f"Erro na API de composição de itens: {e}")
        return jsonify({"error": "Erro ao buscar a composição dos itens"}), 500

@app.route('/material')
@login_required
def material_page(): # type: ignore
    """Renderiza a página de cadastro de materiais e carrega os dados das chapas."""
    user = {
        'username': session.get('username'),
        'role': session.get('role', 'user')
    }
    
    # Dados das chapas extraídos do HTML
    # Lista de chapas atualizada e completa
    chapa_data = {}
    chapa_data = {
        "Chapa Galvanizada": {
            '#20 GALV': {'bitola': 0.95, 'kg_m2': 8.09}, '#18 GALV': {'bitola': 1.25, 'kg_m2': 10.53},
            '#16 GALV': {'bitola': 1.55, 'kg_m2': 12.97}, '#14 GALV': {'bitola': 1.95, 'kg_m2': 16.02},
            '#12 GALV': {'bitola': 2.70, 'kg_m2': 22.12}, '#11 GALV': {'bitola': 3.00, 'kg_m2': 24.00}
        },
        "Chapa Preta": {
            '#20 PRETA': {'bitola': 0.91, 'kg_m2': 7.90}, '#18 PRETA': {'bitola': 1.27, 'kg_m2': 10.08},
            '#16 PRETA': {'bitola': 1.50, 'kg_m2': 12.21}, '#14 PRETA': {'bitola': 2.00, 'kg_m2': 15.26},
            '#12 PRETA': {'bitola': 2.65, 'kg_m2': 21.16}, '#11 PRETA': {'bitola': 3.00, 'kg_m2': 24.42},
            '#10 PRETA': {'bitola': 3.35, 'kg_m2': 27.46}, '#8 PRETA': {'bitola': 4.25, 'kg_m2': 33.35}, 
            '#3/16" PRETA': {'bitola': 4.75, 'kg_m2': 37.35}, '#1/4" PRETA': {'bitola': 6.35, 'kg_m2': 49.80},
            '#5/16" PRETA': {'bitola': 7.94, 'kg_m2': 62.25}, '#3/8" PRETA': {'bitola': 9.53, 'kg_m2': 74.70},
            '#1/2" PRETA': {'bitola': 12.7, 'kg_m2': 99.59}, '#5/8" PRETA': {'bitola': 15.88, 'kg_m2': 124.49},
            '#3/4" PRETA': {'bitola': 19.05, 'kg_m2': 149.39}, '#7/8" PRETA': {'bitola': 22.23, 'kg_m2': 174.29},
            '#1" PRETA': {'bitola': 25.4, 'kg_m2': 199.19}, '#1.1/8" PRETA': {'bitola': 28.58, 'kg_m2': 224.09},
            '#1.1/4" PRETA': {'bitola': 31.75, 'kg_m2': 248.98}, '#1.3/8" PRETA': {'bitola': 34.93, 'kg_m2': 273.88}
        },
        "Chapa PP": {
            '#12 1045': {'bitola': 2.65, 'kg_m2': 21.20}, '#11 1045': {'bitola': 3.00, 'kg_m2': 24.00},
            '#CHAPA PP': {'bitola': 2.00, 'kg_m2': 1}
        },
        "Chapa Aluminio": {
            '#Alum 1mm': {'bitola': 1, 'kg_m2': 7.85}, '#Alum 0,5mm': {'bitola': 0.5, 'kg_m2': 3.92}
        },
        "Chapa Expandida": {
            '#1/8" EXP': {'bitola': 3, 'kg_m2': 1.2}, '#3/16" EXP': {'bitola': 4.75, 'kg_m2': 8},
            '#1/4" EXP': {'bitola': 6.3, 'kg_m2': 11}
        },
        "Chapa Xadrez": {
            'CHAPA XADREZ 1/8': {'bitola': 3.00, 'kg_m2': 24.00}
        }
    }

    return render_template('material.html', user=user, chapa_data_json=chapa_data)

@app.route('/api/chapas', methods=['GET'])
@login_required
def get_chapas(): # type: ignore
    """API para buscar todas as chapas em estoque."""
    try:
        with get_db_connection() as connection, connection.cursor() as cursor:
            sql = """
                SELECT idmateriais, descricao_material, bitola, largura, comprimento, quant_kg, quant_un 
                FROM materiais
                WHERE tipo_material = 'chapa'
                ORDER BY descricao_material ASC
            """
            cursor.execute(sql)
            chapas = cursor.fetchall()
            return jsonify(chapas)
    except Exception as e:
        print(f"Erro na API de buscar chapas: {e}")
        return jsonify({"error": "Erro ao buscar chapas"}), 500

logging.basicConfig(level=logging.DEBUG)  # Configure o nível de log

@app.route('/api/chapas', methods=['POST'])
@login_required
def add_chapa(): # type: ignore
    """API para adicionar uma nova chapa."""
    try:
        data = request.get_json()
        logging.debug(f"Dados recebidos para adicionar chapa: {data}")
        with get_db_connection() as connection, connection.cursor() as cursor:
            sql = """
                INSERT INTO materiais 
                (categoria, tipo_material, descricao_material, bitola, largura, comprimento, quant_un, quant_kg, un_medida)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """
            params = (
                'chapa', 'chapa', data['descricao_material'], data['bitola'],
                data['largura'], data['comprimento'], data['quant_un'], data['quant_kg'], 'KG'
            )
            cursor.execute(sql, params)
            connection.commit()
        return jsonify({"message": "Chapa salva com sucesso!"}), 201
    except Exception as e: # type: ignore
        logging.error(f"Erro ao adicionar chapa: {e}")
        return jsonify({"error": "Erro ao salvar a chapa"}), 500

@app.route('/api/chapas/<int:chapa_id>', methods=['PUT'])
@login_required
def update_chapa(chapa_id): # type: ignore
    """API para atualizar uma chapa existente."""
    data = request.get_json()
    try:
        with get_db_connection() as connection, connection.cursor() as cursor:
            sql = """
                UPDATE materiais SET 
                descricao_material=%s, bitola=%s, largura=%s, comprimento=%s, quant_un=%s, quant_kg=%s
                WHERE idmateriais=%s
            """
            params = (data['descricao_material'], data['bitola'], data['largura'], data['comprimento'], data['quant_un'], data['quant_kg'], chapa_id)
            cursor.execute(sql, params)
            connection.commit()
        return jsonify({"message": "Chapa atualizada com sucesso!"})
    except Exception as e: # type: ignore
        logging.error(f"Erro ao atualizar chapa: {e}")
        return jsonify({"error": "Erro ao atualizar a chapa"}), 500

@app.route('/api/chapas/<int:chapa_id>', methods=['DELETE'])
@login_required
def delete_chapa(chapa_id): # type: ignore
    """API para deletar uma chapa."""
    try:
        with get_db_connection() as connection, connection.cursor() as cursor:
            cursor.execute("DELETE FROM materiais WHERE idmateriais = %s", (chapa_id,))
            connection.commit()
        return jsonify({"message": "Chapa deletada com sucesso!"})
    except Exception as e: # type: ignore
        logging.error(f"Erro ao deletar chapa: {e}")
        return jsonify({"error": "Erro ao deletar a chapa"}), 500

@app.route('/api/retalho', methods=['GET'])
@login_required
def get_retalhos(): # type: ignore
    """API para buscar todos os retalhos em estoque."""
    try:
        with get_db_connection() as connection, connection.cursor() as cursor:
            sql = """
                SELECT idmateriais, descricao_material, bitola, largura, comprimento, quant_kg, quant_un, codigo_material, estaleiro, reserva 
                FROM materiais 
                WHERE tipo_material = 'retalho'
                ORDER BY idmateriais DESC
            """
            cursor.execute(sql)
            retalhos = cursor.fetchall()
            return jsonify(retalhos)
    except Exception as e: # type: ignore
        logging.error(f"Erro na API de buscar retalhos: {e}")
        return jsonify({"error": "Erro ao buscar retalhos"}), 500

@app.route('/api/retalho', methods=['POST'])
@login_required
def add_retalho(): # type: ignore
    """API para adicionar um novo retalho."""
    data = request.get_json()
    try:
        with get_db_connection() as connection, connection.cursor() as cursor:
            sql = """
                INSERT INTO materiais 
                (categoria, tipo_material, descricao_material, bitola, largura, comprimento, quant_un, quant_kg, un_medida, estaleiro, reserva)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """
            params = (
                'chapa', 'retalho', data['descricao_material'], data['bitola'],
                data['largura'], data['comprimento'], data['quant_un'], data['quant_kg'],
                data['un_medida'], data['estaleiro'], data.get('reserva', False)
            )
            cursor.execute(sql, params)
            connection.commit()
        return jsonify({"message": "Retalho salvo com sucesso!"}), 201
    except Exception as e: # type: ignore
        logging.error(f"Erro ao adicionar retalho: {e}")
        return jsonify({"error": "Erro ao salvar o retalho"}), 500

@app.route('/api/retalho/<int:retalho_id>', methods=['DELETE'])
@login_required
def delete_retalho(retalho_id): # type: ignore
    """API para deletar um retalho."""
    try:
        with get_db_connection() as connection, connection.cursor() as cursor:
            cursor.execute("DELETE FROM materiais WHERE idmateriais = %s", (retalho_id,))
            connection.commit()
        return jsonify({"message": "Retalho deletado com sucesso!"})
    except Exception as e: # type: ignore
        logging.error(f"Erro ao deletar retalho: {e}")
        return jsonify({"error": "Erro ao deletar o retalho"}), 500

@app.route('/api/materiais/unitario', methods=['GET'])
@login_required
def get_materiais_unitarios():
    """API para buscar todos os materiais do tipo 'unitario' (Ferramentas Maquinas)."""
    try:
        with get_db_connection() as connection, connection.cursor() as cursor:
            sql = """
                SELECT idmateriais, descricao_material, quant_un, estaleiro, codigo_material 
                FROM materiais 
                WHERE tipo_material = 'unitario'
                ORDER BY idmateriais DESC
            """
            cursor.execute(sql)
            materiais = cursor.fetchall()
            return jsonify(materiais)
    except Exception as e:
        logging.error(f"Erro na API de buscar materiais unitários: {e}")
        return jsonify({"error": "Erro ao buscar materiais unitários"}), 500

@app.route('/api/materiais/unitario', methods=['POST'])
@login_required
def add_material_unitario():
    """API para adicionar um novo material unitário (ferramenta)."""
    data = request.get_json()
    try:
        # No frontend, 'maquina' é enviado, que corresponde a 'estaleiro' no banco.
        descricao = data.get('descricao_material')
        maquina = data.get('estaleiro')
        quant_un = data.get('quant_un', 0)

        if not descricao or not maquina:
            return jsonify({"error": "Descrição e Máquina são obrigatórios"}), 400

        with get_db_connection() as connection, connection.cursor() as cursor:
            sql = """
                INSERT INTO materiais 
                (tipo_material, descricao_material, quant_un, estaleiro, categoria)
                VALUES ('unitario', %s, %s, %s, 'Ferramentas Maquinas')
            """
            cursor.execute(sql, (descricao, quant_un, maquina))
            connection.commit()
        return jsonify({"message": "Item salvo com sucesso!"}), 201
    except Exception as e:
        logging.error(f"Erro ao adicionar material unitário: {e}")
        return jsonify({"error": "Erro ao salvar o item"}), 500

@app.route('/api/materiais/unitario/<int:material_id>', methods=['PUT'])
@login_required
def update_material_unitario(material_id):
    """API para atualizar um material unitário (ferramenta)."""
    data = request.get_json()
    try:
        descricao = data.get('descricao_material')
        maquina = data.get('estaleiro')
        quant_un = data.get('quant_un', 0)

        if not descricao or not maquina:
            return jsonify({"error": "Descrição e Máquina são obrigatórios"}), 400

        with get_db_connection() as connection, connection.cursor() as cursor:
            sql = "UPDATE materiais SET descricao_material=%s, quant_un=%s, estaleiro=%s WHERE idmateriais=%s"
            cursor.execute(sql, (descricao, quant_un, maquina, material_id))
            connection.commit()
        return jsonify({"message": "Item atualizado com sucesso!"})
    except Exception as e:
        logging.error(f"Erro ao atualizar material unitário: {e}")
        return jsonify({"error": "Erro ao atualizar o item"}), 500

@app.route('/api/materiais/unitario/<int:material_id>', methods=['DELETE'])
@login_required
def delete_material_unitario(material_id):
    """API para deletar um material unitário (ferramenta)."""
    return delete_chapa(material_id) # Reutiliza a mesma lógica de deleção

@app.route('/api/serra', methods=['GET'])
@login_required
def get_serra_items():
    """API para buscar todos os materiais do tipo 'serra'."""
    try:
        with get_db_connection() as connection, connection.cursor() as cursor:
            sql = """
                SELECT idmateriais, descricao_material, quant_un, estaleiro, codigo_material 
                FROM materiais 
                WHERE tipo_material = 'serra'
                ORDER BY idmateriais DESC
            """
            cursor.execute(sql)
            items = cursor.fetchall()
            return jsonify(items)
    except Exception as e:
        logging.error(f"Erro na API de buscar itens de serra: {e}")
        return jsonify({"error": "Erro ao buscar itens de serra"}), 500

if __name__ == '__main__':
    # Executa o servidor web. Acesse http://127.0.0.1:5000 no seu navegador.
    # O modo debug recarrega o servidor automaticamente quando você salva o arquivo.
    app.run(debug=True)
