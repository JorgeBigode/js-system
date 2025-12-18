import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import customtkinter as ctk
from tkcalendar import DateEntry
from database import get_db_connection # Assumindo que você criou database.py
from datetime import datetime
import os
try:
    from docxtpl import DocxTemplate
except ImportError:
    messagebox.showerror("Dependência Faltando", "A biblioteca 'docx-template' não está instalada.\nExecute: pip install docx-template")
    DocxTemplate = None
from werkzeug.security import check_password_hash

class PedidosApp:
    def __init__(self, parent, user):
        self.parent = parent
        self.user = user
        self.main_frame = ctk.CTkFrame(self.parent, fg_color="transparent")
        self.main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Dados
        self.pedidos = []
        self.clientes_grouped = {}
        self.context_menu_pedido = None
        
        # Configurar interface
        self.create_widgets()
        
        # Carregar dados
        self.carregar_pedidos()
        self.carregar_clientes()

    def center_window(self, window, width, height):
        """Centraliza uma janela na tela."""
        # Assegura que as dimensões da janela foram atualizadas
        window.update_idletasks()
        screen_width = window.winfo_screenwidth()
        screen_height = window.winfo_screenheight()
        x = (screen_width / 2) - (width / 2)
        y = (screen_height / 2) - (height / 2)
        window.geometry(f'{width}x{height}+{int(x)}+{int(y)}')

        
    def create_widgets(self):
        # Frame principal
        # O main_frame agora é o frame principal da classe
        main_frame = self.main_frame
        
        # Barra de busca
        search_frame = ctk.CTkFrame(main_frame, fg_color="transparent")
        search_frame.pack(fill=tk.X, pady=(0, 10))
        
        ctk.CTkLabel(search_frame, text="Buscar:", text_color="white").pack(side=tk.LEFT, padx=(0, 5))
        self.search_var = tk.StringVar()
        search_entry = ctk.CTkEntry(search_frame, textvariable=self.search_var, width=250)
        search_entry.pack(side=tk.LEFT, padx=(0, 5))
        search_entry.bind('<KeyRelease>', self.filtrar_tabela)
        
        ctk.CTkButton(search_frame, text="Limpar", command=self.limpar_busca).pack(side=tk.LEFT)
        
        # Botão novo pedido
        ctk.CTkButton(search_frame, text="Novo Pedido", command=self.abrir_modal_novo).pack(side=tk.RIGHT)
        
        # Tabela de pedidos
        table_frame = ctk.CTkFrame(main_frame, fg_color="transparent")
        table_frame.pack(fill=tk.BOTH, expand=True)
        
        # Criar treeview com scrollbar
        scrollbar = ttk.Scrollbar(table_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.tree = ttk.Treeview(table_frame, columns=(
            "Pedido", "Cliente", "Localidade", "Data", "Folha", "PDF"
        ), show="headings", yscrollcommand=scrollbar.set)

        # Estilo para o Treeview
        style = ttk.Style()
        style.theme_use("default")
        style.configure("Treeview", background="#2b2b2b", foreground="white", fieldbackground="#2b2b2b", borderwidth=0)
        style.configure("Treeview.Heading", background="#171717", foreground="white", relief="flat")
        style.map("Treeview.Heading", background=[('active', '#333333')])
        style.map("Treeview", background=[('selected', '#003366')])

        # Adicionar tags para linhas zebradas
        self.tree.tag_configure('oddrow', background='#2b2b2b')
        self.tree.tag_configure('evenrow', background='#3c3c3c') # Cinza um pouco mais claro
        
        scrollbar.config(command=self.tree.yview)
        
        # Definir cabeçalhos
        self.tree.heading("Pedido", text="Pedido")
        self.tree.heading("Cliente", text="Cliente")
        self.tree.heading("Localidade", text="Localidade")
        self.tree.heading("Data", text="Data")
        self.tree.heading("Folha", text="Folha")
        self.tree.heading("PDF", text="PDF")
        
        # Definir largura das colunas
        self.tree.column("Pedido", width=100)
        self.tree.column("Cliente", width=200)
        self.tree.column("Localidade", width=200)
        self.tree.column("Data", width=100)
        self.tree.column("Folha", width=50)
        self.tree.column("PDF", width=50)
        
        self.tree.pack(fill=tk.BOTH, expand=True)
        
        # Bind duplo clique para editar
        self.tree.bind('<Double-1>', self.editar_pedido)

        # --- Menu de Contexto (Botão Direito) ---
        self.context_menu = tk.Menu(self.main_frame, tearoff=0)
        self.context_menu.add_command(label="Abrir PDF", command=self.abrir_pdf_selecionado)
        self.context_menu.add_command(label="Gerar Folha de Pedido", command=self.gerar_folha_pedido)

        # Bind do botão direito do mouse
        self.tree.bind('<Button-3>', self.mostrar_menu_contexto)
        
    def carregar_pedidos(self):
        try:
            with get_db_connection() as connection, connection.cursor() as cursor:
                sql = """
                SELECT 
                    p.*,
                    c.cliente,
                    c.endereco,
                    GROUP_CONCAT(DISTINCT e.equipamento_pai SEPARATOR ', ') AS equipamentos
                FROM pedido p
                LEFT JOIN add_cliente c ON p.idcliente = c.idcliente
                LEFT JOIN cliente_produto cp ON cp.id_cliente = c.idcliente
                LEFT JOIN equipamento_produto ep ON ep.id_equipamento_produto = cp.id_equipamento_produto
                LEFT JOIN equipamento e ON e.idequipamento = ep.idequipamento
                GROUP BY p.idpedido
                ORDER BY p.numero_pedido DESC  -- ALTERAÇÃO AQUI
                """
                cursor.execute(sql)
                self.pedidos = cursor.fetchall()
                
                self._preencher_tabela(self.pedidos)
                
        except Exception as e:
            messagebox.showerror("Erro", f"Erro ao carregar pedidos: {str(e)}")
    
    def _preencher_tabela(self, pedidos):
        """Limpa e preenche a tabela com a lista de pedidos fornecida."""
        # Limpar treeview
        for item in self.tree.get_children():
            self.tree.delete(item)
        
        # Preencher treeview
        for i, pedido in enumerate(pedidos):
            # Define a tag para a cor da linha (zebrado)
            tag = 'evenrow' if i % 2 == 0 else 'oddrow'
            data_entrega = pedido['data_entrega']
            if data_entrega:
                try:
                    # Converte para string para garantir compatibilidade
                    data_obj = datetime.strptime(str(data_entrega), '%Y-%m-%d')
                    data_formatada = data_obj.strftime('%d/%m/%Y')
                except (ValueError, TypeError):
                    data_formatada = str(data_entrega)
            else:
                data_formatada = ""
            
            self.tree.insert("", "end", values=(
                pedido['numero_pedido'],
                pedido['cliente'],
                pedido['endereco'],
                data_formatada,
                "📄",  # Ícone para folha
                "📄" if pedido['pdf'] else "-",  # Ícone para PDF se existir
            ), tags=(pedido['idpedido'], tag))

    def carregar_clientes(self):
        try:
            with get_db_connection() as connection, connection.cursor() as cursor:
                cursor.execute("SELECT idcliente, cliente, endereco FROM add_cliente ORDER BY cliente, endereco")
                rows = cursor.fetchall()
                
                # Agrupar por nome do cliente
                self.clientes_grouped = {}
                for row in rows:
                    nome = row['cliente']
                    if nome not in self.clientes_grouped:
                        self.clientes_grouped[nome] = []
                    self.clientes_grouped[nome].append({
                        'id': row['idcliente'],
                        'endereco': row['endereco']
                    })
                
        except Exception as e:
            messagebox.showerror("Erro", f"Erro ao carregar clientes: {str(e)}")
    
    def verificar_admin(self):
        # Verificar se o usuário é admin
        return self.user['role'] == 'admin'
    
    def filtrar_tabela(self, event=None):
        termo = self.search_var.get().lower()
        if not termo:
            self._preencher_tabela(self.pedidos)
            return

        pedidos_filtrados = []
        for pedido in self.pedidos:
            # Concatena os valores relevantes para a busca
            texto_busca = f"{pedido.get('numero_pedido', '')} {pedido.get('cliente', '')} {pedido.get('endereco', '')}".lower()
            if termo in texto_busca:
                pedidos_filtrados.append(pedido)
        
        self._preencher_tabela(pedidos_filtrados)
    
    def limpar_busca(self):
        self.search_var.set("")
        self._preencher_tabela(self.pedidos)

    def mostrar_menu_contexto(self, event):
        """Exibe o menu de contexto ao clicar com o botão direito."""
        item_id = self.tree.identify_row(event.y)
        if not item_id:
            return

        # Seleciona o item clicado
        self.tree.selection_set(item_id)
        
        # Obtém o ID do pedido a partir das tags do item
        pedido_id_tag = self.tree.item(item_id, "tags")
        if not pedido_id_tag:
            return
            
        pedido_id = int(pedido_id_tag[0])

        # Encontra o pedido completo na nossa lista de dados
        self.context_menu_pedido = next((p for p in self.pedidos if p['idpedido'] == pedido_id), None)

        if self.context_menu_pedido:
            # Habilita ou desabilita a opção de abrir PDF
            pdf_path = self.context_menu_pedido.get('pdf')
            if pdf_path and os.path.exists(pdf_path):
                self.context_menu.entryconfig("Abrir PDF", state="normal")
            else:
                self.context_menu.entryconfig("Abrir PDF", state="disabled")
            
            # Habilita a geração de folha de pedido
            if DocxTemplate:
                self.context_menu.entryconfig("Gerar Folha de Pedido", state="normal")

            # Mostra o menu na posição do cursor
            self.context_menu.post(event.x_root, event.y_root)

    def abrir_pdf_selecionado(self):
        """Abre o arquivo PDF do pedido selecionado no menu de contexto."""
        if self.context_menu_pedido and self.context_menu_pedido.get('pdf'):
            pdf_path = self.context_menu_pedido['pdf']
            os.startfile(pdf_path)

    def gerar_folha_pedido(self):
        """Gera um documento Word com base no template PEDIDO.docx."""
        if not self.context_menu_pedido:
            return
        if not DocxTemplate:
            messagebox.showerror("Erro", "A biblioteca 'docx-template' é necessária para esta função.")
            return

        template_path = 'PEDIDO.docx'
        if not os.path.exists(template_path):
            messagebox.showerror("Erro", f"O template '{template_path}' não foi encontrado no diretório da aplicação.")
            return

        pedido_info = self.context_menu_pedido
        idpedido = pedido_info['idpedido']

        try:
            with get_db_connection() as connection, connection.cursor() as cursor:
                # Busca produtos e quantidades (equipamentos pai)
                sql = """
                    SELECT 
                        parent.descricao, 
                        SUM(ci.quantidade_prod) as quantidade
                    FROM cliente_item ci
                    JOIN item_composicao ic ON ci.id_composicao = ic.id
                    JOIN itens parent ON ic.id_item_pai = parent.id
                    WHERE ci.idpedido = %s
                    GROUP BY parent.descricao
                """
                cursor.execute(sql, (idpedido,))
                produtos_data = cursor.fetchall()

        except Exception as e:
            messagebox.showerror("Erro de Banco de Dados", f"Erro ao buscar produtos do pedido: {e}")
            return

        # Prepara o contexto para o template
        data_entrega_obj = pedido_info.get('data_entrega')
        data_entrega_str = data_entrega_obj.strftime('%d/%m/%Y') if data_entrega_obj else ''

        context = {
            'CLIENTE': pedido_info.get('cliente', '').upper(),
            'ENDERECO': pedido_info.get('endereco', '').upper(),
            'PEDIDO': pedido_info.get('numero_pedido', ''),
            'DATA': data_entrega_str,
            'produtos': produtos_data  # Lista de dicionários para o loop
        }

        # Carrega o template e renderiza
        doc = DocxTemplate(template_path)
        doc.render(context)

        # Pede ao usuário para salvar o arquivo
        default_filename = f"Folha_Pedido_{pedido_info.get('numero_pedido', 'desconhecido')}.docx"
        filepath = filedialog.asksaveasfilename(
            defaultextension=".docx",
            filetypes=[("Documento Word", "*.docx")],
            initialfile=default_filename,
            title="Salvar Folha de Pedido"
        )

        if filepath:
            try:
                doc.save(filepath)
                messagebox.showinfo("Sucesso", f"Documento salvo com sucesso em:\n{filepath}")
            except Exception as e:
                messagebox.showerror("Erro ao Salvar", f"Não foi possível salvar o arquivo: {e}")
    
    def abrir_modal_novo(self):
        modal = tk.Toplevel(self.main_frame)
        modal.title("Novo Pedido")
        modal.transient(self.main_frame.winfo_toplevel())
        modal.grab_set()
        self.center_window(modal, 550, 400)
        
        # Frame principal
        frame = ctk.CTkFrame(modal)
        frame.pack(fill=tk.BOTH, expand=True)
        
        # Campos do formulário
        ctk.CTkLabel(frame, text="Número do Pedido:").grid(row=0, column=0, sticky=tk.W, pady=5, padx=10)
        numero_pedido = ctk.CTkEntry(frame, width=250)
        numero_pedido.grid(row=0, column=1, pady=5, padx=5)
        
        ctk.CTkLabel(frame, text="Cliente:").grid(row=1, column=0, sticky=tk.W, pady=5, padx=10)
        
        cliente_frame = ctk.CTkFrame(frame, fg_color="transparent")
        cliente_frame.grid(row=1, column=1, pady=5, padx=5, sticky="nsew")

        cliente_var = tk.StringVar()

        # --- Substituição do ComboBox por Listbox ---
        cliente_list_frame = ctk.CTkFrame(cliente_frame, fg_color="#2b2b2b")
        cliente_list_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        cliente_list_scrollbar = ttk.Scrollbar(cliente_list_frame, orient="vertical")
        cliente_listbox = tk.Listbox(cliente_list_frame, 
                                     yscrollcommand=cliente_list_scrollbar.set, 
                                     bg="#2b2b2b", fg="white", 
                                     selectbackground="#003366", 
                                     highlightthickness=0, 
                                     exportselection=False,
                                     height=4) # Altura inicial
        cliente_list_scrollbar.config(command=cliente_listbox.yview)
        cliente_list_scrollbar.pack(side="right", fill="y")
        cliente_listbox.pack(side="left", fill="both", expand=True)

        def on_cliente_select(event):
            w = event.widget
            if w.curselection():
                index = int(w.curselection()[0])
                value = w.get(index)
                cliente_var.set(value)

        cliente_listbox.bind('<<ListboxSelect>>', on_cliente_select)

        def open_add_client_modal():
            # Abrir modal e esperar fechar
            self.abrir_modal_novo_cliente(modal)
            # Atualizar combobox de clientes
            cliente_listbox.delete(0, tk.END)
            for name in self.clientes_grouped.keys():
                cliente_listbox.insert(tk.END, name)
        
        ctk.CTkButton(cliente_frame, text="+", width=30, command=open_add_client_modal).pack(side=tk.RIGHT)
        
        ctk.CTkLabel(frame, text="Endereço:").grid(row=2, column=0, sticky=tk.W, pady=5, padx=10)
        endereco_var = tk.StringVar()
        endereco_combo = ctk.CTkComboBox(frame, variable=endereco_var, width=250, state="readonly")
        
        # --- Substituição do ComboBox por Listbox para Endereço ---
        endereco_list_frame = ctk.CTkFrame(frame, fg_color="#2b2b2b")
        endereco_list_frame.grid(row=2, column=1, pady=5, padx=5, sticky="nsew")
        endereco_list_scrollbar = ttk.Scrollbar(endereco_list_frame, orient="vertical")
        endereco_listbox = tk.Listbox(endereco_list_frame, 
                                      yscrollcommand=endereco_list_scrollbar.set, 
                                      bg="#2b2b2b", fg="white", 
                                      selectbackground="#003366", 
                                      highlightthickness=0, 
                                      exportselection=False,
                                      height=3)
        endereco_list_scrollbar.config(command=endereco_listbox.yview)
        endereco_list_scrollbar.pack(side="right", fill="y")
        endereco_listbox.pack(side="left", fill="both", expand=True)

        def on_endereco_select(event):
            w = event.widget
            if w.curselection():
                index = int(w.curselection()[0])
                value = w.get(index)
                endereco_var.set(value)

        endereco_listbox.bind('<<ListboxSelect>>', on_endereco_select)
        
        ctk.CTkLabel(frame, text="Data de Entrega:").grid(row=3, column=0, sticky=tk.W, pady=5, padx=10)
        data_entrega = DateEntry(frame, width=27, background='darkblue',
                                 foreground='white', borderwidth=2, date_pattern='dd/mm/yyyy')
        data_entrega.grid(row=3, column=1, pady=5, padx=5, sticky=tk.W)
        
        # Atualizar endereços quando cliente for selecionado
        def atualizar_enderecos(event=None):
            cliente = cliente_var.get()
            endereco_listbox.delete(0, tk.END)
            endereco_var.set("")

            if cliente in self.clientes_grouped:
                enderecos_list = [e['endereco'] for e in self.clientes_grouped[cliente]]
                if enderecos_list:
                    for end in enderecos_list:
                        endereco_listbox.insert(tk.END, end)
                    endereco_listbox.select_set(0) # Seleciona o primeiro
                    endereco_var.set(enderecos_list[0])
                    endereco_listbox.config(state=tk.NORMAL)
                else:
                    endereco_listbox.insert(tk.END, "Nenhum endereço cadastrado")
                    endereco_listbox.config(state=tk.DISABLED)
            else:
                endereco_listbox.insert(tk.END, "Selecione um cliente")
                endereco_listbox.config(state=tk.DISABLED)

        cliente_var.trace_add('write', lambda *args: atualizar_enderecos())
        
        # Carregar clientes iniciais
        cliente_listbox.delete(0, tk.END)
        for name in self.clientes_grouped.keys():
            cliente_listbox.insert(tk.END, name)

        atualizar_enderecos()
        
        # Botões
        button_frame = ctk.CTkFrame(frame, fg_color="transparent")
        button_frame.grid(row=5, column=0, columnspan=2, pady=20)
        
        def salvar_pedido():
            num = numero_pedido.get().strip()
            cliente_nome = cliente_var.get().strip()
            endereco = endereco_var.get().strip()
            data_str = data_entrega.get().strip()
            pdf = pdf_path.get().strip()
            
            if not num or not cliente_nome or not endereco or not data_str:
                messagebox.showerror("Erro", "Preencha todos os campos obrigatórios")
                return
            
            # Encontrar ID do cliente
            cliente_id = None
            if cliente_nome in self.clientes_grouped:
                for cliente in self.clientes_grouped[cliente_nome]:
                    if cliente['endereco'] == endereco:
                        cliente_id = cliente['id']
                        break
            
            if not cliente_id:
                messagebox.showerror("Erro", "Cliente/endereço não encontrado")
                return
            
            # Converter data para o formato do banco de dados (YYYY-MM-DD)
            try:
                data_obj = datetime.strptime(data_str, '%d/%m/%Y')
                data_db = data_obj.strftime('%Y-%m-%d')
            except ValueError:
                messagebox.showerror("Erro", "Formato de data inválido. Use dd/mm/aaaa.")
                return

            try:
                with get_db_connection() as connection, connection.cursor() as cursor:
                    # Verificar se número de pedido já existe
                    cursor.execute("SELECT COUNT(*) as cnt FROM pedido WHERE numero_pedido = %s", (num,))
                    if cursor.fetchone()['cnt'] > 0:
                        messagebox.showerror("Erro", "Número de pedido já existe")
                        return
                    
                    # Inserir pedido
                    sql = """
                    INSERT INTO pedido (idcliente, numero_pedido, data_entrega, status, data_insercao)
                    VALUES (%s, %s, %s, 'pendente', NOW())
                    """
                    cursor.execute(sql, (cliente_id, num, data_db))
                    pedido_id = cursor.lastrowid
                    
                    # Processar PDF se fornecido
                    if pdf:
                        # Criar diretório se não existir
                        if not os.path.exists('pdfs'):
                            os.makedirs('pdfs')
                        
                        # Copiar arquivo
                        ext = os.path.splitext(pdf)[1]
                        novo_nome = f"pedido_{pedido_id}_{int(datetime.now().timestamp())}{ext}"
                        destino = os.path.join('pdfs', novo_nome)
                        
                        import shutil
                        shutil.copy2(pdf, destino)
                        
                        # Atualizar banco com caminho do PDF
                        cursor.execute("UPDATE pedido SET pdf = %s WHERE idpedido = %s", (destino, pedido_id))
                    
                    connection.commit()
                    messagebox.showinfo("Sucesso", "Pedido criado com sucesso")
                    modal.destroy()
                    self.carregar_pedidos()
                    
            except Exception as e:
                messagebox.showerror("Erro", f"Erro ao criar pedido: {str(e)}")

        ctk.CTkLabel(frame, text="PDF do Pedido:").grid(row=4, column=0, sticky=tk.W, pady=5, padx=10)
        pdf_path = tk.StringVar()
        pdf_entry = ctk.CTkEntry(frame, textvariable=pdf_path, width=250)
        pdf_entry.grid(row=4, column=1, pady=5, padx=5, sticky="w")

        def selecionar_pdf():
            caminho = filedialog.askopenfilename(
                title="Selecionar PDF",
                filetypes=[("Arquivos PDF", "*.pdf")]
            )
            if caminho:
                pdf_path.set(caminho)

        ctk.CTkButton(frame, text="Selecionar PDF", command=selecionar_pdf).grid(row=4, column=2, padx=5, pady=5)

        ctk.CTkButton(button_frame, text="Salvar", command=salvar_pedido).pack(side=tk.LEFT, padx=5)
        ctk.CTkButton(button_frame, text="Cancelar", command=modal.destroy).pack(side=tk.LEFT, padx=5)

    def abrir_modal_novo_cliente(self, parent_modal):
        modal = tk.Toplevel(self.main_frame)
        modal.title("Adicionar Novo Cliente")
        modal.transient(parent_modal) # Define o modal de novo pedido como pai
        modal.grab_set()
        # modal.configure(bg="#1f1f1f") # Definir cor de fundo do Toplevel
        self.center_window(modal, 400, 250)

        frame = ctk.CTkFrame(modal)
        frame.pack(fill=tk.BOTH, expand=True)

        ctk.CTkLabel(frame, text="Nome do Cliente:").grid(row=0, column=0, sticky=tk.W, pady=5, padx=10)
        nome_entry = ctk.CTkEntry(frame, width=250)
        nome_entry.grid(row=0, column=1, pady=5, padx=5)

        ctk.CTkLabel(frame, text="Endereço:").grid(row=1, column=0, sticky=tk.W, pady=5, padx=10)
        endereco_entry = ctk.CTkEntry(frame, width=250)
        endereco_entry.grid(row=1, column=1, pady=5, padx=5)

        def salvar_cliente():
            nome = nome_entry.get().strip()
            endereco = endereco_entry.get().strip()

            if not nome or not endereco:
                messagebox.showerror("Erro", "Nome e endereço são obrigatórios.", parent=modal)
                return

            try:
                with get_db_connection() as connection, connection.cursor() as cursor:
                        # Verificar se a combinação cliente/endereço já existe
                        sql_check = "SELECT idcliente FROM add_cliente WHERE cliente = %s AND endereco = %s"
                        cursor.execute(sql_check, (nome, endereco))
                        if cursor.fetchone():
                            messagebox.showerror("Erro", "Este cliente com este endereço já existe.", parent=modal)
                            return
                        # Inserir novo cliente
                        sql_insert = "INSERT INTO add_cliente (cliente, endereco) VALUES (%s, %s)"
                        cursor.execute(sql_insert, (nome, endereco))
                        connection.commit()

                messagebox.showinfo("Sucesso", "Cliente adicionado com sucesso!", parent=modal)
                self.carregar_clientes()  # Recarrega a lista de clientes na classe principal
                modal.destroy()

            except Exception as e:
                messagebox.showerror("Erro", f"Erro ao salvar cliente: {e}", parent=modal)
        
        button_frame = ctk.CTkFrame(frame, fg_color="transparent")
        button_frame.grid(row=2, column=0, columnspan=2, pady=20)
        
        ctk.CTkButton(button_frame, text="Salvar", command=salvar_cliente).pack(side=tk.LEFT, padx=10)
        ctk.CTkButton(button_frame, text="Cancelar", command=modal.destroy).pack(side=tk.LEFT, padx=10)
        
        parent_modal.wait_window(modal) # Pausa a execução até o modal de cliente ser fechado
    
    def editar_pedido(self, event):
        # Obter item selecionado
        item = self.tree.selection()[0]
        pedido_id = self.tree.item(item, "tags")[0]
        
        # Encontrar dados do pedido
        pedido = None
        for p in self.pedidos:
            if p['idpedido'] == int(pedido_id):
                pedido = p
                break
        
        if not pedido:
            return
        
        # Abrir modal de edição
        modal = tk.Toplevel(self.main_frame)
        modal.title("Editar Pedido")
        modal.transient(self.main_frame.winfo_toplevel())
        modal.grab_set()
        self.center_window(modal, 550, 400)
        
        # Frame principal
        frame = ctk.CTkFrame(modal)
        frame.pack(fill=tk.BOTH, expand=True)
        
        # Campos do formulário
        ctk.CTkLabel(frame, text="Número do Pedido:").grid(row=0, column=0, sticky=tk.W, pady=5, padx=10)
        numero_pedido = ctk.CTkEntry(frame, width=250)
        numero_pedido.insert(0, pedido['numero_pedido'])
        numero_pedido.grid(row=0, column=1, pady=5, padx=5)
        
        ctk.CTkLabel(frame, text="Cliente:").grid(row=1, column=0, sticky=tk.W, pady=5, padx=10)
        
        cliente_var = tk.StringVar()
        cliente_var.set(pedido.get('cliente', ''))

        # --- Listbox para Clientes na Edição ---
        cliente_list_frame = ctk.CTkFrame(frame, fg_color="#2b2b2b")
        cliente_list_frame.grid(row=1, column=1, pady=5, padx=5, sticky="nsew")
        cliente_list_scrollbar = ttk.Scrollbar(cliente_list_frame, orient="vertical")
        cliente_listbox = tk.Listbox(cliente_list_frame, 
                                     yscrollcommand=cliente_list_scrollbar.set, 
                                     bg="#2b2b2b", fg="white", 
                                     selectbackground="#003366", 
                                     highlightthickness=0, 
                                     exportselection=False,
                                     height=4)
        cliente_list_scrollbar.config(command=cliente_listbox.yview)
        cliente_list_scrollbar.pack(side="right", fill="y")
        cliente_listbox.pack(side="left", fill="both", expand=True)

        def on_cliente_select_edit(event):
            w = event.widget
            if w.curselection():
                index = int(w.curselection()[0])
                value = w.get(index)
                cliente_var.set(value)

        cliente_listbox.bind('<<ListboxSelect>>', on_cliente_select_edit)

        
        ctk.CTkLabel(frame, text="Endereço:").grid(row=2, column=0, sticky=tk.W, pady=5, padx=10)
        endereco_var = tk.StringVar()
        endereco_var.set(pedido.get('endereco', ''))

        # --- Listbox para Endereços na Edição ---
        endereco_list_frame = ctk.CTkFrame(frame, fg_color="#2b2b2b")
        endereco_list_frame.grid(row=2, column=1, pady=5, padx=5, sticky="nsew")
        endereco_list_scrollbar = ttk.Scrollbar(endereco_list_frame, orient="vertical")
        endereco_listbox = tk.Listbox(endereco_list_frame, 
                                      yscrollcommand=endereco_list_scrollbar.set, 
                                      bg="#2b2b2b", fg="white", 
                                      selectbackground="#003366", 
                                      highlightthickness=0, 
                                      exportselection=False,
                                      height=3)
        endereco_list_scrollbar.config(command=endereco_listbox.yview)
        endereco_list_scrollbar.pack(side="right", fill="y")
        endereco_listbox.pack(side="left", fill="both", expand=True)

        def on_endereco_select_edit(event):
            w = event.widget
            if w.curselection():
                index = int(w.curselection()[0])
                value = w.get(index)
                endereco_var.set(value)

        endereco_listbox.bind('<<ListboxSelect>>', on_endereco_select_edit)
        
        ctk.CTkLabel(frame, text="Data de Entrega:").grid(row=3, column=0, sticky=tk.W, pady=5, padx=10)
        data_entrega = DateEntry(frame, width=27, background='darkblue',
                                 foreground='white', borderwidth=2, date_pattern='dd/mm/yyyy')
        if pedido['data_entrega']:
            # O banco retorna um objeto date, que o DateEntry aceita
            data_entrega.set_date(pedido['data_entrega'])

        data_entrega.grid(row=3, column=1, pady=5, padx=5, sticky=tk.W)
        
        # Atualizar endereços quando cliente for selecionado
        def atualizar_enderecos(event=None):
            cliente = cliente_var.get()
            endereco_listbox.delete(0, tk.END)
            
            if cliente in self.clientes_grouped:
                enderecos_list = [e['endereco'] for e in self.clientes_grouped[cliente]]
                if enderecos_list:
                    for end in enderecos_list:
                        endereco_listbox.insert(tk.END, end)
                    
                    # Tenta manter o endereço atual selecionado, se não, seleciona o primeiro
                    current_endereco = endereco_var.get()
                    if current_endereco in enderecos_list:
                        idx = enderecos_list.index(current_endereco)
                        endereco_listbox.select_set(idx)
                    else:
                        endereco_listbox.select_set(0)
                        endereco_var.set(enderecos_list[0])
                    endereco_listbox.config(state=tk.NORMAL)
                else:
                    endereco_listbox.insert(tk.END, "Nenhum endereço cadastrado")
                    endereco_listbox.config(state=tk.DISABLED)
                    endereco_var.set("")
            else:
                endereco_listbox.insert(tk.END, "Selecione um cliente")
                endereco_listbox.config(state=tk.DISABLED)
                endereco_var.set("")

        cliente_var.trace_add('write', lambda *args: atualizar_enderecos())

        # Carregar e selecionar cliente inicial
        cliente_listbox.delete(0, tk.END)
        all_clients = list(self.clientes_grouped.keys())
        for name in all_clients:
            cliente_listbox.insert(tk.END, name)
        
        current_cliente = pedido.get('cliente')
        if current_cliente in all_clients:
            idx = all_clients.index(current_cliente)
            cliente_listbox.select_set(idx)

        atualizar_enderecos()
        
        # Botões
        button_frame = ctk.CTkFrame(frame, fg_color="transparent")
        button_frame.grid(row=5, column=0, columnspan=2, pady=20)
        
        def salvar_edicao():
            num = numero_pedido.get().strip()
            cliente_nome = cliente_var.get().strip()
            endereco = endereco_var.get().strip()
            data_str = data_entrega.get().strip()            
            
            if not num or not cliente_nome or not endereco or not data_str:
                messagebox.showerror("Erro", "Preencha todos os campos obrigatórios")
                return
            
            # Encontrar ID do cliente
            cliente_id = None
            if cliente_nome in self.clientes_grouped:
                for cliente in self.clientes_grouped[cliente_nome]:
                    if cliente['endereco'] == endereco:
                        cliente_id = cliente['id']
                        break
            
            if not cliente_id:
                messagebox.showerror("Erro", "Cliente/endereço não encontrado")
                return
            
            # Converter data para o formato do banco de dados (YYYY-MM-DD)
            try:
                data_obj = datetime.strptime(data_str, '%d/%m/%Y')
                data_db = data_obj.strftime('%Y-%m-%d')
            except ValueError:
                messagebox.showerror("Erro", "Formato de data inválido. Use dd/mm/aaaa.")
                return

            try:
                with get_db_connection() as connection, connection.cursor() as cursor:
                    # Verificar se número de pedido já existe (excluindo o atual)
                    cursor.execute("SELECT COUNT(*) as cnt FROM pedido WHERE numero_pedido = %s AND idpedido != %s", 
                                  (num, pedido_id))
                    if cursor.fetchone()['cnt'] > 0:
                        messagebox.showerror("Erro", "Número de pedido já existe")
                        return
                    
                    # Atualizar pedido
                    sql = """
                    UPDATE pedido 
                    SET idcliente = %s, numero_pedido = %s, data_entrega = %s
                    WHERE idpedido = %s
                    """
                    cursor.execute(sql, (cliente_id, num, data_db, pedido_id))
                    
                    connection.commit()
                    messagebox.showinfo("Sucesso", "Pedido atualizado com sucesso")
                    modal.destroy()
                    self.carregar_pedidos()
                    
            except Exception as e:
                messagebox.showerror("Erro", f"Erro ao atualizar pedido: {str(e)}")
        
        ctk.CTkButton(button_frame, text="Salvar", command=salvar_edicao).pack(side=tk.LEFT, padx=5)
        
        # Botão de excluir (apenas para admin)
        if self.verificar_admin():
            def excluir_pedido():
                if messagebox.askyesno("Confirmar", "Tem certeza que deseja excluir este pedido?"):
                    try:
                        with get_db_connection() as connection, connection.cursor() as cursor:
                            # Remover arquivo PDF se existir
                            if pedido['pdf'] and os.path.exists(pedido['pdf']):
                                os.remove(pedido['pdf'])
                            
                            # Excluir pedido
                            cursor.execute("DELETE FROM pedido WHERE idpedido = %s", (pedido_id,))
                            connection.commit()
                            
                            messagebox.showinfo("Sucesso", "Pedido excluído com sucesso")
                            modal.destroy()
                            self.carregar_pedidos()
                            
                    except Exception as e:
                        messagebox.showerror("Erro", f"Erro ao excluir pedido: {str(e)}")
            
            ctk.CTkButton(button_frame, text="Excluir", command=excluir_pedido, fg_color="red").pack(side=tk.LEFT, padx=5)
        
        ctk.CTkButton(button_frame, text="Cancelar", command=modal.destroy).pack(side=tk.LEFT, padx=5)

# Adicionar esta função ao menu_action na classe MainApp
def menu_action(self, item):
    if item == "SAIR":
        self.logout()
    elif item == "INICIO":
        self.show_home()
    elif item == "PEDIDOS":
        # Abrir a aba de pedidos
        pedidos_app = PedidosApp(self.root, self.user)
    else:
        self.show_content(item)