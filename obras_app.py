import tkinter as tk
from tkinter import ttk, messagebox, filedialog, font
import customtkinter as ctk
import pymysql
from tkcalendar import DateEntry
from config import DB_HOST, DB_USER, DB_PASS, DB_NAME
import os
import tempfile
import platform
import json
from datetime import datetime
from etiqueta_printer import EtiquetaPrinter # <-- ADICIONADO

# Import para geração de PDF
try:
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib import colors, units
    from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
    from reportlab.lib.units import inch # Importação que faltava
    REPORTLAB_AVAILABLE = True
    # Import para visualização de imagens
    try:
        from PIL import Image, ImageTk
        PIL_AVAILABLE = True
    except ImportError:
        PIL_AVAILABLE = False
except ImportError:
    messagebox.showerror("Dependência Faltando", "A biblioteca 'reportlab' não está instalada.\nExecute: pip install reportlab")
    REPORTLAB_AVAILABLE = False

WIN32_AVAILABLE = False
if platform.system() == "Windows":
    try:
        import win32print
        WIN32_AVAILABLE = True
    except ImportError:
        messagebox.showwarning("Dependência Opcional Faltando", "A biblioteca 'pywin32' não está instalada.\nExecute: pip install pywin32\nA seleção de impressora não funcionará diretamente.")


class ObrasApp:
    def __init__(self, parent, user):
        self.parent = parent # O frame ou janela pai onde esta app será exibida
        self.user = user
        
        # Frame principal para a ObrasApp dentro do conteúdo da MainApp
        self.main_frame = ctk.CTkFrame(self.parent, fg_color="transparent")
        self.main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        self.obras_data = []
        self.all_pedidos_for_modal = [] # Lista completa de pedidos para o modal
        self.produtos_por_pedido = {}
        self.anos_disponiveis = []
        self.permissoes_edicao = [] # Para simular as permissões do PHP
        self.etiqueta_config = self.carregar_config_etiqueta()
        self.create_widgets()
        self.full_text_map = {} # Armazena o texto completo dos itens da árvore
        self.main_frame.bind("<Configure>", self.on_tree_resize)
        self.carregar_obras()
        
    def center_window(self, window, width, height):
        """Centraliza uma janela na tela."""
        # Assegura que as dimensões da janela foram atualizadas
        window.update_idletasks()
        screen_width = window.winfo_screenwidth()
        screen_height = window.winfo_screenheight()
        x = (screen_width / 2) - (width / 2)
        y = (screen_height / 2) - (height / 2)
        window.geometry(f'{width}x{height}+{int(x)}+{int(y)}')

    def carregar_config_etiqueta(self):
        """Carrega as configurações da etiqueta de um arquivo JSON."""
        padrao = {
            'largura_mm': 100, 'altura_mm': 80,
            'margem_sup_mm': 5, 'margem_esq_mm': 5,
            'fonte_header': 8, 'fonte_cliente': 10,
            'fonte_equipamento': 12, 'fonte_conjunto': 10, 'fonte_quantidade': 12,
            'rotacionar': False,
            'metodo_impressao': 'gdi', # 'gdi' ou 'ppla'
        }
        try:
            with open('etiqueta_config.json', 'r') as f:
                config = json.load(f)
                padrao.update(config) # Atualiza o padrão com o que foi salvo
                return padrao
        except (FileNotFoundError, json.JSONDecodeError):
            return padrao

    def salvar_config_etiqueta(self):
        """Salva as configurações da etiqueta em um arquivo JSON."""
        try:
            with open('etiqueta_config.json', 'w') as f:
                json.dump(self.etiqueta_config, f, indent=4)
        except Exception as e:
            messagebox.showwarning("Salvar Configuração", f"Não foi possível salvar as configurações da etiqueta:\n{e}")

    def create_widgets(self):
        # Barra de filtros e ações
        filter_frame = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        filter_frame.pack(fill=tk.X, pady=(0, 10))
        
        ctk.CTkLabel(filter_frame, text="Ano:").pack(side=tk.LEFT, padx=(0, 5))
        self.ano_var = tk.StringVar()
        self.ano_combo = ctk.CTkComboBox(filter_frame, variable=self.ano_var, width=120, state="readonly")
        self.ano_combo.pack(side=tk.LEFT, padx=(0, 10))
        self.ano_combo.bind('<<ComboboxSelected>>', self.filtrar_obras)
        
        ctk.CTkLabel(filter_frame, text="Buscar Pedido:").pack(side=tk.LEFT, padx=(0, 5))
        self.search_var = tk.StringVar()
        search_entry = ctk.CTkEntry(filter_frame, textvariable=self.search_var, width=300)
        search_entry.pack(side=tk.LEFT, padx=(0, 5))
        search_entry.bind('<KeyRelease>', self.filtrar_obras)
        
        ctk.CTkButton(filter_frame, text="Limpar Filtros", command=self.limpar_filtros).pack(side=tk.LEFT)
        
        # Frame para as tabelas (pedidos e itens)
        tables_frame = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        tables_frame.pack(fill=tk.BOTH, expand=True)
        
        # Seleção de Pedido
        pedido_select_frame = ctk.CTkFrame(tables_frame, fg_color="transparent")
        pedido_select_frame.pack(fill=tk.X, pady=(10, 5))
        ctk.CTkLabel(pedido_select_frame, text="Selecione o Pedido:", font=('Arial', 12, 'bold')).pack(side=tk.LEFT, padx=(0, 10))
        
        # Campo de texto para exibir o pedido selecionado (substitui o ComboBox)
        self.pedido_select_var = tk.StringVar()
        self.pedido_entry = ctk.CTkEntry(pedido_select_frame, textvariable=self.pedido_select_var, state="readonly")
        self.pedido_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))

        # Adiciona o evento de duplo clique para abrir o modal de seleção
        self.pedido_entry.bind("<Double-1>", lambda event: self.abrir_modal_selecao_pedido())

        # Botão para abrir o modal de seleção
        ctk.CTkButton(pedido_select_frame, text="Selecionar Pedido", command=self.abrir_modal_selecao_pedido).pack(side=tk.LEFT)
        
        # Cabeçalho com dados do cliente
        self.cliente_header_frame = ctk.CTkFrame(tables_frame, border_width=1)
        # Este frame será exibido quando um pedido for selecionado
        ctk.CTkLabel(self.cliente_header_frame, text="Detalhes do Pedido Selecionado", font=('Arial', 10, 'bold')).pack(anchor='w', padx=10, pady=(5,0))

        # Labels para os detalhes dentro do cabeçalho
        self.cliente_nome_var = tk.StringVar()
        self.cliente_endereco_var = tk.StringVar()
        self.cliente_pedido_var = tk.StringVar()
        self.cliente_entrega_var = tk.StringVar()
        
        details_inner_frame = ctk.CTkFrame(self.cliente_header_frame, fg_color="transparent")
        details_inner_frame.pack(fill='x', padx=10, pady=5)

        ctk.CTkLabel(details_inner_frame, text="Cliente:").grid(row=0, column=0, sticky=tk.W, pady=2)
        ctk.CTkLabel(details_inner_frame, textvariable=self.cliente_nome_var, font=('Arial', 10, 'bold')).grid(row=0, column=1, sticky=tk.W, padx=5)

        ctk.CTkLabel(details_inner_frame, text="Endereço:").grid(row=1, column=0, sticky=tk.W, pady=2)
        ctk.CTkLabel(details_inner_frame, textvariable=self.cliente_endereco_var).grid(row=1, column=1, sticky=tk.W, padx=5)

        ctk.CTkLabel(details_inner_frame, text="Nº Pedido:").grid(row=0, column=2, sticky=tk.W, padx=(20, 0), pady=2)
        ctk.CTkLabel(details_inner_frame, textvariable=self.cliente_pedido_var).grid(row=0, column=3, sticky=tk.W, padx=5)

        ctk.CTkLabel(details_inner_frame, text="Data Entrega:").grid(row=1, column=2, sticky=tk.W, padx=(20, 0), pady=2)
        ctk.CTkLabel(details_inner_frame, textvariable=self.cliente_entrega_var).grid(row=1, column=3, sticky=tk.W, padx=5)

        # Botão para gerar relatório de itens
        ctk.CTkButton(self.cliente_header_frame, text="Relatório de Itens", command=self.abrir_modal_relatorio_itens).pack(side=tk.RIGHT, padx=10, pady=5)

        # Tabela de Itens do Pedido Selecionado
        ctk.CTkLabel(tables_frame, text="Itens do Pedido:", font=('Arial', 12, 'bold')).pack(anchor=tk.W, pady=(10, 5))
        self.itens_tree = ttk.Treeview(tables_frame, columns=(
            "Qtd", "Lote", "Engenharia", "Programação", "PCP", "Produção", "Qualidade", "Obs Programação", "Obs Produção", "Obs Qualidade", "Ações"
        ), show="tree headings")
        
        # Coluna da árvore hierárquica
        self.itens_tree.heading("#0", text="Estrutura do Produto")
        self.itens_tree.column("#0", minwidth=250, width=350, stretch=tk.YES)

        # Demais colunas
        self.itens_tree.heading("Qtd", text="Qtd")
        self.itens_tree.heading("Lote", text="Lote")
        self.itens_tree.heading("Engenharia", text="Engenharia")
        self.itens_tree.heading("Programação", text="Programação")
        self.itens_tree.heading("PCP", text="PCP") # type: ignore
        self.itens_tree.heading("Produção", text="Produção") # type: ignore
        self.itens_tree.heading("Qualidade", text="Qualidade") # type: ignore
        self.itens_tree.heading("Obs Programação", text="Obs. Programação")
        self.itens_tree.heading("Obs Produção", text="Obs. Produção")
        self.itens_tree.heading("Obs Qualidade", text="Obs. Qualidade")
        self.itens_tree.heading("Ações", text="Ações")
        
        # Configuração das colunas de dados
        # Colunas com stretch=False não se expandem
        self.itens_tree.column("Qtd", width=50, anchor=tk.CENTER, stretch=tk.NO)
        self.itens_tree.column("Lote", width=80, stretch=tk.NO)
        self.itens_tree.column("Engenharia", width=120, anchor=tk.CENTER, stretch=tk.NO)
        self.itens_tree.column("Programação", width=120, anchor=tk.CENTER, stretch=tk.NO)
        self.itens_tree.column("PCP", width=120, anchor=tk.CENTER, stretch=tk.NO)
        self.itens_tree.column("Produção", width=120, anchor=tk.CENTER, stretch=tk.NO)
        self.itens_tree.column("Qualidade", width=120, anchor=tk.CENTER, stretch=tk.NO)
        # Colunas de observação com stretch=YES para se expandirem
        self.itens_tree.column("Obs Programação", minwidth=120, width=150, stretch=tk.YES)
        self.itens_tree.column("Obs Produção", minwidth=120, width=150, stretch=tk.YES)
        self.itens_tree.column("Obs Qualidade", minwidth=120, width=150, stretch=tk.YES)
        self.itens_tree.column("Ações", width=80, anchor=tk.CENTER, stretch=tk.NO)
        
        self.itens_tree.pack(fill=tk.BOTH, expand=True)

        style = ttk.Style()
        style.theme_use("default")
        style.configure("Treeview", background="#2b2b2b", foreground="white", fieldbackground="#2b2b2b", borderwidth=0)
        style.configure("Treeview.Heading", background="#171717", foreground="white", relief="flat")
        style.map("Treeview.Heading", background=[('active', '#333333')])
        style.map("Treeview", background=[('selected', '#003366')])

        self.itens_tree.bind('<Double-1>', self.abrir_modal_edicao_item)
        self.itens_tree.bind('<Button-1>', self.on_tree_click) # Adiciona o bind para o clique do mouse

    def carregar_obras(self, ano=None, termo_busca=None):
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

            # Define as permissões de edição com base no cargo do usuário
            if self.user['role'] in ('admin', 'editor'):
                self.permissoes_edicao = ['data_pcp', 'data_producao', 'data_qualidade', 'obs_producao']
            else:
                self.permissoes_edicao = []
            
            with connection.cursor() as cursor:
                # Carregar anos disponíveis para o filtro
                cursor.execute("SELECT DISTINCT YEAR(data_insercao) AS ano FROM pedido WHERE data_insercao IS NOT NULL ORDER BY ano DESC")
                self.anos_disponiveis = [str(row['ano']) for row in cursor.fetchall()] if cursor.rowcount > 0 else []
                self.ano_combo.configure(values=["Todos os Anos"] + self.anos_disponiveis)
                self.ano_combo.set("Todos os Anos")

                # Carrega a lista completa de pedidos para o modal de seleção, uma única vez.
                if not self.all_pedidos_for_modal:
                    cursor.execute("""
                        SELECT p.numero_pedido, ac.cliente, ac.endereco 
                        FROM pedido p JOIN add_cliente ac ON p.idcliente = ac.idcliente 
                        ORDER BY p.idpedido DESC
                    """)
                    self.all_pedidos_for_modal = [f"{p['numero_pedido']} - {p['cliente']} ({p['endereco']})" for p in cursor.fetchall()]

                # Salva a seleção atual para tentar restaurá-la depois
                pedido_selecionado_anteriormente = self.pedido_select_var.get()
                
                # Consulta para pedidos
                pedidos_sql = """
                    SELECT 
                        p.idpedido, p.idcliente, p.numero_pedido, p.data_entrega, p.data_insercao,
                        ac.cliente, ac.endereco
                    FROM pedido p
                    JOIN add_cliente ac ON p.idcliente = ac.idcliente
                """
                conditions = []
                params = []

                if ano and ano != "Todos os Anos":
                    conditions.append("YEAR(p.data_insercao) = %s")
                    params.append(int(ano))
                
                if termo_busca:
                    conditions.append("(p.numero_pedido LIKE %s OR ac.cliente LIKE %s OR ac.endereco LIKE %s)")
                    params.extend([f"%{termo_busca}%", f"%{termo_busca}%", f"%{termo_busca}%"])

                if conditions:
                    pedidos_sql += " WHERE " + " AND ".join(conditions)
                
                pedidos_sql += " ORDER BY p.idpedido DESC"
                
                cursor.execute(pedidos_sql, params)
                self.obras_data = cursor.fetchall()
                
                # Preencher o combobox de pedidos
                self.pedido_display_list = []
                for pedido in self.obras_data:
                    display_text = f"{pedido['numero_pedido']} - {pedido['cliente']} ({pedido['endereco']})"
                    self.pedido_display_list.append(display_text)

                # Tenta restaurar a seleção anterior ou seleciona o primeiro item
                if pedido_selecionado_anteriormente in self.pedido_display_list:
                    self.pedido_select_var.set(pedido_selecionado_anteriormente)
                elif self.pedido_display_list:
                    self.pedido_select_var.set(self.pedido_display_list[0])
                else:
                    self.pedido_select_var.set('')
                
                self.on_pedido_select() # Carrega os itens do pedido selecionado (ou limpa se nenhum)

                # Carregar todos os itens para todos os pedidos filtrados
                if self.obras_data:
                    pedido_ids = [p['idpedido'] for p in self.obras_data]
                    
                    itens_sql = f"""
                        SELECT 
                            ci.id_item AS id_vinculo,
                            ci.idpedido,
                            ci.quantidade_prod,
                            ci.lote,
                            ci.data_engenharia,
                            ci.data_programacao,
                            ci.data_pcp,
                            ci.data_producao,
                            ci.data_qualidade,
                            ci.caminho,
                            ci.tag,
                            ci.data_prog_fim,
                            ci.obs_detalhes,
                            ci.obs_programacao,
                            ci.obs_producao,

                            -- Equipamento (item raiz)
                            pi.id AS equipamento_id,
                            pi.codigo AS codigo_equipamento,
                            pi.descricao AS nome_equipamento,

                            -- Conjunto (item filho)
                            si.id AS conjunto_id,
                            si.codigo AS codigo_conjunto,
                            si.descricao AS conjunto

                        FROM cliente_item ci
                        JOIN item_composicao ic ON ci.id_composicao = ic.id
                        JOIN itens pi ON ci.item_raiz_id = pi.id        -- Equipamento pai
                        JOIN itens si ON ic.id_item_filho = si.id       -- Conjunto (filho)
                        WHERE ci.idpedido IN ({','.join(['%s']*len(pedido_ids))})
                        ORDER BY ci.idpedido, pi.descricao, ci.data_engenharia
                    """
                    cursor.execute(itens_sql, pedido_ids)
                    itens_raw = cursor.fetchall()
                    
                    self.produtos_por_pedido = {}
                    for item in itens_raw:
                        self.produtos_por_pedido.setdefault(item['idpedido'], []).append(item)
                else:
                    self.produtos_por_pedido = {}
                    # Limpar a treeview de itens se nenhum pedido for encontrado
                    for item in self.itens_tree.get_children():
                        self.itens_tree.delete(item)
            
            # Garante que os dados do primeiro pedido sejam exibidos na carga inicial
            self.on_pedido_select()


        except Exception as e:
            messagebox.showerror("Erro", f"Erro ao carregar obras: {str(e)}")
        finally:
            if connection:
                connection.close()

    def filtrar_obras(self, event=None):
        ano = self.ano_var.get()
        termo = self.search_var.get().strip()
        self.carregar_obras(ano=ano, termo_busca=termo)

    def abrir_modal_selecao_pedido(self):
        """Abre uma janela modal para selecionar um pedido de uma lista pesquisável."""
        if not hasattr(self, 'pedido_display_list') or not self.pedido_display_list:
            messagebox.showwarning("Aviso", "Nenhum pedido carregado para selecionar.")
            return

        modal = ctk.CTkToplevel(self.main_frame)
        modal.title("Selecionar Pedido")
        modal.geometry("500x400")
        modal.transient(self.main_frame)
        modal.grab_set()
        self.center_window(modal, 500, 400)

        search_var = tk.StringVar()
        
        ctk.CTkLabel(modal, text="Buscar:").pack(padx=10, pady=(10, 0), anchor="w")
        search_entry = ctk.CTkEntry(modal, textvariable=search_var)
        search_entry.pack(padx=10, fill="x")

        listbox_frame = ctk.CTkFrame(modal)
        listbox_frame.pack(padx=10, pady=10, fill="both", expand=True)

        listbox = tk.Listbox(listbox_frame, height=15, bg="#2b2b2b", fg="white", selectbackground="#1f6aa5", highlightthickness=0, borderwidth=0)
        listbox_scrollbar = ctk.CTkScrollbar(listbox_frame, command=listbox.yview)
        listbox.configure(yscrollcommand=listbox_scrollbar.set)
        
        listbox.pack(side="left", fill="both", expand=True)
        listbox_scrollbar.pack(side="right", fill="y")

        def update_listbox(data):
            listbox.delete(0, "end")
            for item in data:
                listbox.insert("end", item)

        def on_search(*args):
            term = search_var.get().lower()
            filtered_items = [item for item in self.all_pedidos_for_modal if term in item.lower()]
            update_listbox(filtered_items)

        search_entry.bind("<KeyRelease>", on_search)

        # Garante que o campo de busca esteja limpo e a lista completa ao abrir
        search_var.set("")
        on_search()

        def on_confirm():
            selected_indices = listbox.curselection()
            if not selected_indices:
                messagebox.showwarning("Seleção", "Por favor, selecione um item da lista.", parent=modal)
                return
            selected_item = listbox.get(selected_indices[0])
            self.pedido_select_var.set(selected_item)
            self.on_pedido_select() # Atualiza a tela principal
            modal.destroy()

        ctk.CTkButton(modal, text="Confirmar", command=on_confirm).pack(pady=10)
        # Bind duplo clique para confirmar
        listbox.bind("<Double-1>", lambda e: on_confirm())

    def limpar_filtros(self):
        self.ano_var.set("Todos os Anos")
        self.search_var.set("")
        self.carregar_obras()

    def on_pedido_select(self, event=None):
        selected_text = self.pedido_select_var.get()
        if not selected_text:
            # Limpar a treeview de itens se nenhum pedido estiver selecionado
            for item in self.itens_tree.get_children():
                self.itens_tree.delete(item)
            self.cliente_header_frame.pack_forget() # Esconde o cabeçalho
            return

        # Encontrar o pedido correspondente nos dados carregados
        selected_pedido = None
        for pedido in self.obras_data:
            display_text = f"{pedido['numero_pedido']} - {pedido['cliente']} ({pedido['endereco']})"
            if display_text == selected_text:
                selected_pedido = pedido
                break
        
        if selected_pedido:
            # Preenche o cabeçalho com os dados do cliente/pedido
            self.cliente_nome_var.set(selected_pedido.get('cliente', ''))
            self.cliente_endereco_var.set(selected_pedido.get('endereco', ''))
            self.cliente_pedido_var.set(selected_pedido.get('numero_pedido', ''))
            data_entrega = selected_pedido.get('data_entrega')
            data_formatada = data_entrega.strftime('%d/%m/%Y') if data_entrega else 'N/A'
            self.cliente_entrega_var.set(data_formatada)
            
            # Exibe o frame do cabeçalho
            self.cliente_header_frame.pack(fill=tk.X, pady=10, before=self.itens_tree.master.winfo_children()[2])

            pedido_id = selected_pedido['idpedido']
            self.exibir_itens_do_pedido(pedido_id)
        else:
            # Limpa tudo se o pedido não for encontrado
            for item in self.itens_tree.get_children():
                self.itens_tree.delete(item)
            self.cliente_header_frame.pack_forget()

    def exibir_itens_do_pedido(self, pedido_id):
        # Limpar a treeview de itens
        for iid in self.itens_tree.get_children():
            self.itens_tree.delete(iid)
        self.full_text_map.clear()

        itens_do_pedido = sorted(self.produtos_por_pedido.get(pedido_id, []), key=lambda x: x.get('caminho', '') or '')

        parent_map = {}

        # Font para cálculo da largura do texto
        default_font = font.nametofont("TkDefaultFont")

        def make_iid(pedido_id, path_part, id_vinculo=None):
            safe_path = path_part.replace('>', '-').replace(' ', '_').replace('/', '_')
            return f"p{pedido_id}|{safe_path}" + (f"|{id_vinculo}" if id_vinculo else "")

        for item in itens_do_pedido:
            caminho = (item.get('caminho') or '').strip()

            # fallback: monte a partir das descrições se caminho estiver vazio
            if not caminho:
                if item.get('nome_equipamento'):
                    caminho = item.get('nome_equipamento')
                    if item.get('conjunto'):
                        caminho = f"{caminho} > {item.get('conjunto')}"
                elif item.get('conjunto'):
                    caminho = item.get('conjunto')

            path_parts = [p.strip() for p in caminho.split('>') if p.strip()] if caminho else []
            if not path_parts:
                path_parts = [item.get('conjunto') or item.get('nome_equipamento') or "Item"]

            # campos descritivos / códigos (vêm do SELECT que sugeri)
            equipamento_descr = item.get('nome_equipamento') or (path_parts[0] if len(path_parts) >= 1 else '')
            conjunto_descr = item.get('conjunto') or (path_parts[-1] if len(path_parts) >= 1 else '')

            equipamento_code = str(item.get('codigo_equipamento') or '')
            conjunto_code = str(item.get('codigo_conjunto') or '')

            for level in range(1, len(path_parts) + 1):
                sub_path = ' > '.join(path_parts[:level])
                if sub_path in parent_map:
                    continue

                parent_sub_path = ' > '.join(path_parts[:level - 1]) if level > 1 else ""
                parent_iid = parent_map.get(parent_sub_path, "")

                is_leaf = (level == len(path_parts))
                iid = make_iid(pedido_id, sub_path, item.get('id_vinculo') if is_leaf else None)

                # Formatar datas
                data_prog_fim = item.get('data_prog_fim')
                if data_prog_fim and hasattr(data_prog_fim, 'year') and data_prog_fim.year > 1:
                    programacao_display = data_prog_fim.strftime('%d/%m/%y %H:%M')
                elif item.get('data_programacao'):
                    programacao_display = 'Em Programação'
                else:
                    programacao_display = 'N/A'

                datas = {
                    'engenharia': item['data_engenharia'].strftime('%d/%m/%y %H:%M') if item.get('data_engenharia') else 'N/A',
                    'programacao': programacao_display,
                    'pcp': item['data_pcp'].strftime('%d/%m/%y %H:%M') if item.get('data_pcp') else 'N/A',
                    'producao': item['data_producao'].strftime('%d/%m/%y %H:%M') if item.get('data_producao') else 'N/A',
                    'qualidade': item['data_qualidade'].strftime('%d/%m/%y %H:%M') if item.get('data_qualidade') else 'N/A',
                }

                if is_leaf:
                    # Para itens "folha", o texto na árvore será a quantidade e a descrição
                    full_text = f"({item.get('quantidade_prod', 'x')}x) {conjunto_code} - {conjunto_descr}" if conjunto_code else f"({item.get('quantidade_prod', 'x')}x) {conjunto_descr}"
                    self.full_text_map[iid] = full_text
                    texto_arvore = self._truncate_text(full_text, self.itens_tree.column('#0', 'width'), default_font, margin=35)

                    obs_programacao_trunc = self._truncate_text(item.get('obs_programacao', ''), self.itens_tree.column('Obs Programação', 'width'), default_font)
                    obs_detalhes_trunc = self._truncate_text(item.get('obs_detalhes', ''), self.itens_tree.column('Obs Qualidade', 'width'), default_font)
                    obs_producao_trunc = self._truncate_text(item.get('obs_producao', ''), self.itens_tree.column('Obs Produção', 'width'), default_font)

                    valores = (
                        item.get('quantidade_prod', ''), # Qtd
                        item.get('lote', ''),
                        datas['engenharia'],
                        datas['programacao'],
                        datas['pcp'],
                        datas['producao'],
                        datas['qualidade'],
                        obs_programacao_trunc,
                        obs_producao_trunc,
                        obs_detalhes_trunc,
                        "✏️  📷" # Adicionado ícone de câmera
                    )
                else:
                    # Para nós pais/intermediários, o texto na árvore é o nome da estrutura
                    current_part_name = path_parts[level - 1]
                    if level == 1:
                        full_text = f"{equipamento_code} - {equipamento_descr}" if equipamento_code else f"{equipamento_descr}"
                        self.full_text_map[iid] = full_text
                        texto_arvore = self._truncate_text(full_text, self.itens_tree.column('#0', 'width'), default_font, margin=35)
                    else:
                        self.full_text_map[iid] = current_part_name
                        texto_arvore = self._truncate_text(current_part_name, self.itens_tree.column('#0', 'width'), default_font, margin=35)

                    # Nós pais agora têm o botão de impressão na coluna "Ações"
                    valores = ('', '', '', '', '', '', '', '', '', '', "🖨️  📅")

                # tags
                tags = ('preencher-datas',) # Adiciona tag para identificar o botão de preencher datas

                if is_leaf:
                    if item.get('data_qualidade'): tags = ('linha-qualidade',)
                    elif item.get('data_producao'): tags = ('linha-producao',)
                    elif item.get('data_pcp'): tags = ('linha-pcp',)
                    elif item.get('data_programacao'): tags = ('linha-programacao',)
                    elif item.get('data_engenharia'): tags = ('linha-engenharia',)
                else:
                    tags = ('equipamento-titulo', 'imprimir-etiqueta', 'preencher-datas') # Adiciona tag para identificar o botão

                try:
                    self.itens_tree.insert(parent_iid, "end", iid=iid, text=texto_arvore, values=valores, tags=tags)
                except tk.TclError:
                    alt_iid = f"{iid}__{len(parent_map)}" # Evita IIDs duplicados
                    self.itens_tree.insert(parent_iid, "end", iid=alt_iid, text=texto_arvore, values=valores, tags=tags)
                    iid = alt_iid

                parent_map[sub_path] = iid

        # Estilos: negrito para o pai e cores para estados
        try:
            self.itens_tree.tag_configure('equipamento-titulo', font=('TkDefaultFont', 10, 'bold'))
        except Exception:
            pass

        self.itens_tree.tag_configure('linha-qualidade', background='#d4edda', foreground='black') # Verde
        self.itens_tree.tag_configure('linha-producao', background='#FFDDC1', foreground='black')  # Laranja
        self.itens_tree.tag_configure('linha-pcp', background='#FFF3CD', foreground='black')      # Amarelo
        self.itens_tree.tag_configure('linha-programacao', background='#CCE5FF', foreground='black')# Azul
        self.itens_tree.tag_configure('linha-engenharia', background='#F5C6CB', foreground='black') # Vermelho

    def on_tree_click(self, event):
        """Verifica se o clique foi no ícone de impressão."""
        # Identifica a região, coluna e item clicado
        region = self.itens_tree.identify_region(event.x, event.y)
        if region != 'cell':
            return

        column_id = self.itens_tree.identify_column(event.x)
        item_iid = self.itens_tree.identify_row(event.y)

        # Verifica se o clique foi na coluna "Ações" (a 11ª coluna, ID #11)
        if column_id == "#11":
            item_tags = self.itens_tree.item(item_iid, 'tags')
            
            # Se for um nó pai (equipamento), verifica qual ícone foi clicado
            if 'equipamento-titulo' in item_tags:
                x, y, width, height = self.itens_tree.bbox(item_iid, column=column_id)
                # O texto é "🖨️  📅". O clique na primeira metade abre a impressão, a segunda o preenchimento de datas.
                if event.x < x + (width / 2):
                    self.abrir_modal_preview_etiqueta(item_iid)
                else:
                    self.preencher_datas_multiplas(item_iid)
                return # Ação para o nó pai foi tratada


            # Se for um nó filho (conjunto), verifica qual ícone foi clicado
            try:
                id_vinculo = int(item_iid.split('|')[-1])
            except (IndexError, ValueError):
                return # Não é um item válido para ação

            # Obtém a bounding box da célula para estimar a posição do clique
            x, y, width, height = self.itens_tree.bbox(item_iid, column=column_id)
            
            # O texto é "✏️  📷". O clique no primeiro terço abre a edição, o resto abre as fotos.
            if event.x < x + (width / 3):
                # Simula o evento de duplo clique para reutilizar a função de edição
                self.itens_tree.focus(item_iid) # Foca no item para que a função saiba qual é
                self.abrir_modal_edicao_item(event)
            else:
                self.ver_fotos(id_vinculo)

    def imprimir_etiquetas_equipamento(self, equipamento_iid):
        """Gera e salva um PDF com etiquetas para todos os filhos diretos de um equipamento."""
        if not REPORTLAB_AVAILABLE:
            messagebox.showerror("Funcionalidade Indisponível", "A biblioteca 'reportlab' é necessária para esta função.")
            return

        # 1. Obter informações do pedido
        selected_text = self.pedido_select_var.get()
        pedido_info = next((p for p in self.obras_data if f"{p['numero_pedido']} - {p['cliente']} ({p['endereco']})" == selected_text), None)
        if not pedido_info:
            messagebox.showerror("Erro", "Não foi possível encontrar os dados do pedido selecionado.")
            return

        # 2. Encontrar os itens filhos do equipamento clicado
        itens_para_imprimir = []
        for child_iid in self.itens_tree.get_children(equipamento_iid):
            # Apenas processa filhos diretos que são folhas (têm um id_vinculo)
            if 'imprimir-etiqueta' not in self.itens_tree.item(child_iid, 'tags'):
                try:
                    id_vinculo = int(child_iid.split('|')[-1])
                    item_data = next((item for item in self.produtos_por_pedido.get(pedido_info['idpedido'], []) if item['id_vinculo'] == id_vinculo), None)
                    if item_data:
                        itens_para_imprimir.append(item_data)
                except (ValueError, IndexError):
                    continue # Ignora nós que não são folhas

        if not itens_para_imprimir:
            messagebox.showinfo("Aviso", "Nenhum item filho encontrado para gerar etiquetas para este equipamento.")
            return

        # 3. Gerar o PDF em um arquivo temporário e abrir o diálogo de impressão
        self._gerar_e_imprimir_etiquetas(pedido_info, itens_para_imprimir)

    def abrir_modal_preview_etiqueta(self, equipamento_iid):
        """Abre um modal de pré-visualização para a etiqueta antes de imprimir."""
        # 1. Obter informações do pedido
        selected_text = self.pedido_select_var.get()
        pedido_info = next((p for p in self.obras_data if f"{p['numero_pedido']} - {p['cliente']} ({p['endereco']})" == selected_text), None)
        if not pedido_info:
            messagebox.showerror("Erro", "Não foi possível encontrar os dados do pedido selecionado.")
            return

        # 2. Encontrar os itens filhos do equipamento clicado
        itens_para_imprimir = []
        for child_iid in self.itens_tree.get_children(equipamento_iid):
            if 'imprimir-etiqueta' not in self.itens_tree.item(child_iid, 'tags'):
                try:
                    id_vinculo = int(child_iid.split('|')[-1])
                    item_data = next((item for item in self.produtos_por_pedido.get(pedido_info['idpedido'], []) if item['id_vinculo'] == id_vinculo), None)
                    if item_data:
                        itens_para_imprimir.append(item_data)
                except (ValueError, IndexError):
                    continue

        if not itens_para_imprimir:
            messagebox.showinfo("Aviso", "Nenhum item filho encontrado para gerar etiquetas para este equipamento.")
            return

        # Usa o primeiro item para a pré-visualização
        item_preview = itens_para_imprimir[0]

        modal = ctk.CTkToplevel(self.main_frame)
        modal.title("Pré-visualização da Etiqueta")
        modal.transient(self.main_frame)
        modal.grab_set()
        self.center_window(modal, 800, 550) # Aumenta o tamanho para acomodar a preview

        # Frame principal que divide a tela em duas colunas
        main_preview_frame = ctk.CTkFrame(modal, fg_color="transparent")
        main_preview_frame.pack(fill="both", expand=True, padx=10, pady=10)
        main_preview_frame.grid_columnconfigure(0, weight=1)
        main_preview_frame.grid_columnconfigure(1, weight=1)
        main_preview_frame.grid_rowconfigure(0, weight=1)

        # --- Coluna da Esquerda: Campos de Edição ---
        edit_frame = ctk.CTkFrame(main_preview_frame)
        edit_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 10))

        ctk.CTkLabel(edit_frame, text="Editar Informações", font=('Arial', 14, 'bold')).pack(pady=10)

        ctk.CTkLabel(edit_frame, text="Cliente:", anchor="w").pack(fill="x", padx=10, pady=(10, 0))
        cliente_entry = ctk.CTkEntry(edit_frame, font=('Arial', 12))
        cliente_entry.insert(0, pedido_info.get('cliente', ''))
        cliente_entry.pack(fill="x", padx=10, pady=(0, 10))

        ctk.CTkLabel(edit_frame, text="Endereço:", anchor="w").pack(fill="x", padx=10, pady=(5, 0))
        endereco_entry = ctk.CTkEntry(edit_frame, font=('Arial', 12))
        endereco_entry.insert(0, pedido_info.get('endereco', ''))
        endereco_entry.pack(fill="x", padx=10, pady=(0, 10))

        ctk.CTkLabel(edit_frame, text="Equipamento:", anchor="w").pack(fill="x", padx=10, pady=(10, 0))
        equipamento_entry = ctk.CTkEntry(edit_frame, font=('Arial', 12))
        equipamento_entry.insert(0, item_preview.get('nome_equipamento', ''))
        equipamento_entry.pack(fill="x", padx=10, pady=(0, 10))

        ctk.CTkLabel(edit_frame, text="Conjunto:", anchor="w").pack(fill="x", padx=10, pady=(5, 0))
        conjunto_entry = ctk.CTkEntry(edit_frame, font=('Arial', 12))
        conjunto_entry.insert(0, item_preview.get('conjunto', ''))
        conjunto_entry.pack(fill="x", padx=10, pady=(0, 10))

        ctk.CTkLabel(edit_frame, text="Quantidade:", anchor="w").pack(fill="x", padx=10, pady=(5, 0))
        quantidade_entry = ctk.CTkEntry(edit_frame, font=('Arial', 12))
        quantidade_entry.insert(0, str(item_preview.get('quantidade_prod', '')))
        quantidade_entry.pack(fill="x", padx=10, pady=(0, 20))

        # --- Campo para Selecionar Impressora ---
        printer_frame = ctk.CTkFrame(edit_frame)
        printer_frame.pack(fill='x', padx=10, pady=10)
        ctk.CTkLabel(printer_frame, text="Impressora:", anchor="w").pack(side="left", padx=(0, 5))
        
        printer_var = tk.StringVar()
        printer_combo = ctk.CTkComboBox(printer_frame, variable=printer_var, state="readonly")
        printer_combo.pack(side="left", fill="x", expand=True)

        if WIN32_AVAILABLE:
            # Combina flags para listar impressoras locais e de rede conectadas
            printers = [printer[2] for printer in win32print.EnumPrinters(win32print.PRINTER_ENUM_LOCAL | win32print.PRINTER_ENUM_CONNECTIONS)]
            printer_combo.configure(values=printers)
            printer_var.set(win32print.GetDefaultPrinter())

        # --- Coluna da Direita: Pré-visualização Visual ---
        preview_frame = ctk.CTkFrame(main_preview_frame)
        preview_frame.grid(row=0, column=1, sticky="nsew", padx=(10, 0))

        ctk.CTkLabel(preview_frame, text="Pré-visualização da Impressão", font=('Arial', 14, 'bold')).pack(pady=10)

        # Adiciona um label para mostrar o método de impressão atual
        metodo_atual_texto = "Método: " + ("Nativo (PPLA)" if self.etiqueta_config.get('metodo_impressao', 'gdi') == 'ppla' else "Windows (GDI)")
        metodo_atual_label = ctk.CTkLabel(preview_frame, text=metodo_atual_texto, font=('Arial', 10, 'italic'), text_color="gray")
        metodo_atual_label.pack(pady=(0,5))

        # Frame que simula a etiqueta com borda
        etiqueta_visual_frame = ctk.CTkFrame(preview_frame, border_width=2, border_color="gray", width=350, height=300)
        etiqueta_visual_frame.pack(pady=10, padx=10)
        etiqueta_visual_frame.pack_propagate(False) # Impede que o frame mude de tamanho

        # Labels da pré-visualização
        # Adiciona bordas e espaçamento para simular melhor a tabela do PDF
        cfg = self.etiqueta_config
        
        header_frame = ctk.CTkFrame(etiqueta_visual_frame, fg_color="transparent", border_width=1, border_color="gray")
        header_frame.pack(fill='x', padx=10, pady=(10, 5))
        header_frame.grid_columnconfigure(0, weight=1)
        header_frame.grid_columnconfigure(1, weight=1)

        ped_label = ctk.CTkLabel(header_frame, text="", font=('Helvetica', cfg['fonte_header']), justify="left")
        ped_label.grid(row=0, column=0, sticky="w")
        data_label = ctk.CTkLabel(header_frame, text="", font=('Helvetica', cfg['fonte_header']), justify="right")
        data_label.grid(row=0, column=1, sticky="e")

        cliente_label = ctk.CTkLabel(etiqueta_visual_frame, text="", font=('Helvetica', cfg['fonte_cliente']), justify="center", wraplength=320)
        cliente_label.pack(pady=5, padx=10, fill='x', ipady=5, side='top')
        
        equipamento_label = ctk.CTkLabel(etiqueta_visual_frame, text="", font=('Helvetica', cfg['fonte_equipamento'], 'bold'), justify="center", wraplength=320)
        equipamento_label.pack(pady=5, padx=10, fill='x', ipady=5, side='top')
        
        conjunto_label = ctk.CTkLabel(etiqueta_visual_frame, text="", font=('Helvetica', cfg['fonte_conjunto']), justify="center", wraplength=320)
        conjunto_label.pack(pady=5, padx=10, fill='x', ipady=5, side='top')

        quantidade_label = ctk.CTkLabel(etiqueta_visual_frame, text="", font=('Helvetica', cfg['fonte_quantidade'], 'bold'), justify="center", wraplength=320)
        quantidade_label.pack(pady=5, padx=10, fill='x', ipady=5, side='top')

        def update_preview(*args):
            """Atualiza a pré-visualização visual com os dados dos campos de edição."""
            data_hora_atual = datetime.now().strftime('%d/%m/%Y %H:%M')
            ped_label.configure(text=f"PED: {pedido_info['numero_pedido']}")
            data_label.configure(text=data_hora_atual)
            
            cliente_text = f"{cliente_entry.get()}\n{endereco_entry.get()}"
            cliente_label.configure(text=cliente_text)
            
            equipamento_label.configure(text=equipamento_entry.get())
            conjunto_label.configure(text=conjunto_entry.get())
            quantidade_label.configure(text=f"QTDE: {quantidade_entry.get()}")

            # Atualiza também o tamanho das fontes em tempo real
            new_cfg = self.etiqueta_config
            ped_label.configure(font=('Helvetica', new_cfg['fonte_header']))
            data_label.configure(font=('Helvetica', new_cfg['fonte_header']))
            cliente_label.configure(font=('Helvetica', new_cfg['fonte_cliente']))
            equipamento_label.configure(font=('Helvetica', new_cfg['fonte_equipamento'], 'bold'))
            conjunto_label.configure(font=('Helvetica', new_cfg['fonte_conjunto']))
            quantidade_label.configure(font=('Helvetica', new_cfg['fonte_quantidade'], 'bold'))

            # Atualiza o label do método de impressão
            metodo_texto = "Método: " + ("Nativo (PPLA)" if new_cfg.get('metodo_impressao', 'gdi') == 'ppla' else "Windows (GDI)")
            metodo_atual_label.configure(text=metodo_texto)

        # Atualiza a preview ao iniciar e a cada alteração nos campos
        for entry in [cliente_entry, endereco_entry, equipamento_entry, conjunto_entry, quantidade_entry]:
            entry.bind("<KeyRelease>", update_preview)
        update_preview() # Chamada inicial

        # --- Botões de Ação ---
        button_frame = ctk.CTkFrame(modal, fg_color="transparent")
        button_frame.pack(pady=(0, 10), fill='x')

        def on_print():
            # Atualiza os dados com os valores dos campos de edição
            pedido_info['cliente'] = cliente_entry.get()
            pedido_info['endereco'] = endereco_entry.get()
            # Atualiza os dados para todos os itens a serem impressos
            for item in itens_para_imprimir:
                item['nome_equipamento'] = equipamento_entry.get()
                item['conjunto'] = conjunto_entry.get()
                item['quantidade_prod'] = quantidade_entry.get()

            selected_printer = printer_var.get()
            if WIN32_AVAILABLE and not selected_printer:
                messagebox.showwarning("Impressão", "Por favor, selecione uma impressora.", parent=modal)
                return

            try:
                # Instancia e usa a nova classe de impressão
                printer = EtiquetaPrinter(config=self.etiqueta_config, main_window_handle=self.main_frame)
                printer.gerar_pdf_e_imprimir(
                    pedido_info,
                    itens_para_imprimir,
                    printer_name=selected_printer,
                    print_direct=True)
            except Exception as e:
                messagebox.showerror("Erro de Impressão", f"Falha ao iniciar a impressão:\n{e}", parent=modal)

            modal.destroy()

        ctk.CTkButton(button_frame, text="Imprimir", command=on_print).pack(side="left", padx=20)
        ctk.CTkButton(button_frame, text="Cancelar", command=modal.destroy).pack(side="left", padx=10)

        def abrir_config_modal(update_callback):
            config_modal = ctk.CTkToplevel(modal)
            config_modal.title("Configurar Etiqueta")
            config_modal.transient(modal)
            config_modal.grab_set()
            self.center_window(config_modal, 350, 520)

            ctk.CTkLabel(config_modal, text="Dimensões (mm)", font=('Arial', 12, 'bold')).pack(pady=(10,5))
            
            widgets = {}
            # Campos de configuração
            config_fields = [
                ("Largura:", 'largura_mm'), ("Altura:", 'altura_mm'),
                ("Margem Superior:", 'margem_sup_mm'), ("Margem Esquerda:", 'margem_esq_mm'),
            ]
            for label, key in config_fields:
                frame = ctk.CTkFrame(config_modal, fg_color="transparent")
                frame.pack(fill='x', padx=20, pady=2)
                ctk.CTkLabel(frame, text=label, width=150, anchor='w').pack(side='left')
                entry = ctk.CTkEntry(frame, width=100)
                entry.insert(0, str(self.etiqueta_config.get(key, '')))
                entry.pack(side='left')
                widgets[key] = (entry, 'entry')

            ctk.CTkLabel(config_modal, text="Tamanho das Fontes (pt)", font=('Arial', 12, 'bold')).pack(pady=(15,5))
            font_fields = [
                ("Cabeçalho:", 'fonte_header'), ("Cliente:", 'fonte_cliente'),
                ("Equipamento:", 'fonte_equipamento'), ("Conjunto:", 'fonte_conjunto'),
                ("Quantidade:", 'fonte_quantidade'),
            ]
            for label, key in font_fields:
                frame = ctk.CTkFrame(config_modal, fg_color="transparent")
                frame.pack(fill='x', padx=20, pady=2)
                ctk.CTkLabel(frame, text=label, width=150, anchor='w').pack(side='left')
                entry = ctk.CTkEntry(frame, width=100)
                entry.insert(0, str(self.etiqueta_config.get(key, '')))
                entry.pack(side='left')
                widgets[key] = (entry, 'entry')

            # --- Adiciona a opção de Rotação ---
            ctk.CTkLabel(config_modal, text="Opções", font=('Arial', 12, 'bold')).pack(pady=(15,5))
            rotacao_frame = ctk.CTkFrame(config_modal, fg_color="transparent")
            rotacao_frame.pack(fill='x', padx=20, pady=2)
            rotacao_var = tk.BooleanVar(value=self.etiqueta_config.get('rotacionar', False))
            checkbox = ctk.CTkCheckBox(rotacao_frame, text="Rotacionar (Paisagem)", variable=rotacao_var)
            checkbox.pack(side='left')
            widgets['rotacionar'] = (rotacao_var, 'check')

            # --- Adiciona a opção de Método de Impressão ---
            ctk.CTkLabel(config_modal, text="Método de Impressão", font=('Arial', 12, 'bold')).pack(pady=(15,5))
            metodo_frame = ctk.CTkFrame(config_modal, fg_color="transparent")
            metodo_frame.pack(fill='x', padx=20, pady=2)
            metodo_var = tk.StringVar(value=self.etiqueta_config.get('metodo_impressao', 'gdi'))
            
            ctk.CTkLabel(metodo_frame, text="Método:", width=150, anchor='w').pack(side='left')
            metodo_combo = ctk.CTkComboBox(metodo_frame, variable=metodo_var, values=['gdi', 'ppla'], width=100, state='readonly')
            metodo_combo.pack(side='left')
            widgets['metodo_impressao'] = (metodo_var, 'combo')


            def update_layout_and_preview(*args):
                """Lê os valores dos campos, atualiza o config e chama o callback de preview."""
                try:
                    for key, (widget, widget_type) in widgets.items():
                        if widget_type == 'entry':
                            value = widget.get()
                            if value.isdigit():
                                self.etiqueta_config[key] = int(value)
                        elif widget_type == 'check':
                            self.etiqueta_config[key] = widget.get()
                        elif widget_type == 'combo':
                            self.etiqueta_config[key] = widget.get()

                    update_callback() # Atualiza a preview na outra janela
                except (ValueError, tk.TclError) as e:
                    # Ignora erros durante a digitação
                    pass

            # Vincula a atualização em tempo real a cada campo de entrada
            for widget, widget_type in widgets.values():
                if widget_type == 'entry':
                    widget.bind("<KeyRelease>", update_layout_and_preview)
                elif widget_type == 'check':
                    widget.trace_add('write', update_layout_and_preview)
                elif widget_type == 'combo':
                    widget.trace_add('write', update_layout_and_preview)

            def on_save_config():
                try:
                    update_layout_and_preview() # Garante que o último valor seja pego
                    self.salvar_config_etiqueta()
                    messagebox.showinfo("Sucesso", "Configurações salvas!", parent=config_modal)
                    config_modal.destroy()
                except ValueError:
                    messagebox.showerror("Erro", "Todos os valores devem ser números inteiros.", parent=config_modal)
                except Exception as e:
                    messagebox.showerror("Erro", f"Erro ao salvar: {e}", parent=config_modal)

            ctk.CTkButton(config_modal, text="Salvar", command=on_save_config).pack(pady=20)

        # Botão para abrir as configurações
        ctk.CTkButton(button_frame, text="Configurar Layout", command=lambda: abrir_config_modal(update_preview)).pack(side="right", padx=20)

    def _truncate_text(self, text, max_width, font_obj):
        """Trunca o texto com '...' se exceder a largura máxima da coluna."""
        if not isinstance(text, str):
            return text
        
        text_width = font_obj.measure(text)
        
        # Se o texto não couber, trunca
        if text_width > max_width - margin:
            temp_text = text
            # Reduz o texto até que ele (com '...') caiba na largura
            while font_obj.measure(temp_text + '...') > max_width - margin and len(temp_text) > 0:
                text = text[:-1]
            final_text = text + '...'
        else:
            final_text = text
        
        # Substitui espaços por 'non-breaking spaces' para forçar uma única linha no Treeview
        return final_text.replace(' ', '\u00A0')

    def abrir_modal_edicao_item(self, event):
        selected_item_id = self.itens_tree.focus()
        if not selected_item_id:
            return
        
        # Obter os valores da linha selecionada
        item_values = self.itens_tree.item(selected_item_id, 'values')
        
        # O modal de edição só deve abrir para itens "folha" (que têm dados)
        # Nós intermediários têm o campo 'Qtd' (índice 3) vazio.
        if not item_values or not item_values[0]: # Checa se é um nó pai (coluna Qtd agora é a 0)
            return

        # O iid da folha agora contém o id_vinculo no final: "p<pedido>|<caminho>|<id_vinculo>"
        try:
            id_vinculo = int(selected_item_id.split('|')[-1])
        except (IndexError, ValueError):
            messagebox.showerror("Erro", "Não foi possível identificar o ID do item selecionado.")
            return

        # Encontrar o item completo nos dados carregados
        item_para_editar = None
        for pedido_id, itens in self.produtos_por_pedido.items():
            for item in itens:
                if item['id_vinculo'] == id_vinculo:
                    item_para_editar = item
                    break
            if item_para_editar:
                break

        if not item_para_editar:
            messagebox.showerror("Erro", "Item não encontrado para edição.")
            return
        
        modal = ctk.CTkToplevel(self.main_frame)
        modal.title(f"Editar Item: {item_para_editar['conjunto']}")
        modal.transient(self.main_frame)
        modal.grab_set()
        self.center_window(modal, 450, 600) # Aumenta o tamanho do modal
        
        # Função auxiliar para verificar se uma data é válida (não nula e não '0000-00-00')
        def is_date_valid(date_obj):
            return date_obj and hasattr(date_obj, 'year') and date_obj.year > 1

        # Frame principal com abas
        frame = ctk.CTkFrame(modal, fg_color="transparent")
        frame.pack(fill=tk.BOTH, expand=True)
        
        # Campos de edição
        fields = [
            ("Quantidade", "quantidade_prod", int),
            ("Lote", "lote", str),
            ("Data PCP", "data_pcp", datetime),
            ("Data Produção", "data_producao", datetime),
            ("Data Qualidade", "data_qualidade", datetime),
            ("Obs. Produção", "obs_producao", str),
            ("Obs. Qualidade", "obs_detalhes", str),
        ]
        
        entries = {}
        for i, (label_text, field_name, field_type) in enumerate(fields):
            ctk.CTkLabel(frame, text=f"{label_text}:").grid(row=i, column=0, sticky=tk.W, pady=2, padx=10)
            
            # Pega o valor atual para exibir, mesmo que não seja editável
            current_value = item_para_editar.get(field_name)
            
            # Lógica de bloqueio de campos de data
            is_editable = True
            if field_name == 'data_pcp':
                # Só pode editar PCP se a data de fim da programação estiver preenchida
                if not is_date_valid(item_para_editar.get('data_prog_fim')):
                    is_editable = False
            elif field_name == 'data_producao':
                # Só pode editar Produção se a data do PCP estiver preenchida
                if not is_date_valid(item_para_editar.get('data_pcp')):
                    is_editable = False
            elif field_name == 'data_qualidade':
                # Só pode editar Qualidade se a data da Produção estiver preenchida
                if not is_date_valid(item_para_editar.get('data_producao')):
                    is_editable = False

            if field_type == datetime:
                # Frame para agrupar o campo de data/hora e o botão de preenchimento automático
                datetime_frame = ctk.CTkFrame(frame, fg_color="transparent")
                datetime_frame.grid(row=i, column=1, pady=2, padx=5, sticky=tk.W)

                # Campo de texto para data e hora
                datetime_entry = ctk.CTkEntry(datetime_frame, width=200, placeholder_text="dd/mm/aaaa HH:MM")
                datetime_entry.pack(side=tk.LEFT)

                # Função para o botão "agora"
                def set_current_time(entry_widget):
                    entry_widget.delete(0, tk.END)
                    entry_widget.insert(0, datetime.now().strftime('%d/%m/%Y %H:%M'))

                # Botão para preencher com a data e hora atuais
                now_button = ctk.CTkButton(datetime_frame, text="▶️", width=30, command=lambda e=datetime_entry: set_current_time(e))
                now_button.pack(side=tk.LEFT, padx=5)
                
                if current_value:
                    datetime_entry.insert(0, current_value.strftime('%d/%m/%Y %H:%M'))
                entries[field_name] = (datetime_entry, field_type)
                
                if not is_editable or (field_name not in self.permissoes_edicao and self.user['role'] != 'admin'):
                    datetime_entry.configure(state='disabled')
                    now_button.configure(state='disabled')
            else:
                entry = ctk.CTkEntry(frame, width=250)
                if current_value is not None:
                    entry.insert(0, str(current_value))
                entry.grid(row=i, column=1, pady=2, padx=5, sticky=tk.W)
                if field_type != datetime:
                    # Torna Quantidade e Lote não editáveis
                    if field_name in ["quantidade_prod", "lote"]:
                        entry.configure(state='disabled')
                    else:
                        # Apenas campos editáveis são adicionados para salvar
                        entries[field_name] = (entry, field_type)

        # --- Seção de Fotos ---
        photo_frame = ctk.CTkFrame(frame, border_width=1)
        photo_frame.grid(row=len(fields), column=0, columnspan=2, pady=(20, 10), padx=10, sticky="ew")

        ctk.CTkLabel(photo_frame, text="Gerenciamento de Fotos", font=('Arial', 12, 'bold')).pack(pady=(5, 10))

        # Label para mostrar a contagem de fotos
        fotos_count_label = ctk.CTkLabel(photo_frame, text="Fotos anexadas: 0")
        fotos_count_label.pack(pady=5)

        def atualizar_contagem_fotos():
            """Lê o JSON e atualiza o label com a quantidade de fotos."""
            uploads_dir = 'uploads'
            json_path = os.path.join(uploads_dir, 'images.json')
            count = 0
            if os.path.exists(json_path):
                try:
                    with open(json_path, 'r', encoding='utf-8') as f:
                        images_map = json.load(f)
                        item_entry = images_map.get(str(id_vinculo))
                        if isinstance(item_entry, dict):
                            # Novo formato: {"info": ..., "files": [...]}
                            count = len(item_entry.get('files', []))
                        elif isinstance(item_entry, list):
                            # Formato antigo: [...]
                            count = len(item_entry)
                except (json.JSONDecodeError, FileNotFoundError):
                    count = 0 # Se houver erro na leitura, considera 0
            fotos_count_label.configure(text=f"Fotos anexadas: {count}")

        def anexar_fotos():
            """Abre o diálogo para selecionar e salvar fotos."""
            filepaths = filedialog.askopenfilenames(
                title="Selecione as fotos",
                filetypes=[("Imagens", "*.jpg *.jpeg *.png *.gif *.bmp"), ("Todos os arquivos", "*.*")]
            )
            if not filepaths:
                return

            uploads_dir = 'uploads'
            os.makedirs(uploads_dir, exist_ok=True)
            json_path = os.path.join(uploads_dir, 'images.json')

            try:
                with open(json_path, 'r+', encoding='utf-8') as f:
                    images_map = json.load(f)
            except (FileNotFoundError, json.JSONDecodeError):
                images_map = {}

            # Verifica se a entrada atual é do formato antigo (lista) e a converte
            current_entry = images_map.get(str(id_vinculo))
            if isinstance(current_entry, list):
                # Converte do formato antigo para o novo
                item_data = {"info": {}, "files": current_entry}
            else:
                # Usa a entrada existente (se for um dict) ou inicializa uma nova
                item_data = current_entry if isinstance(current_entry, dict) else {"info": {}, "files": []}
            image_list = item_data.get('files', [])

            # Coleta os metadados para salvar no JSON
            pedido_info = next((p for p in self.obras_data if p['idpedido'] == item_para_editar['idpedido']), {})
            item_data['info'] = {
                "pedido": pedido_info.get('numero_pedido', ''),
                "cliente": pedido_info.get('cliente', ''),
                "conjunto": item_para_editar.get('conjunto', ''),
                "lote": item_para_editar.get('lote', ''),
                "quantidade": item_para_editar.get('quantidade_prod', ''),
                "equipamento_pai": item_para_editar.get('nome_equipamento', '')
            }

            for filepath in filepaths:
                base, ext = os.path.splitext(os.path.basename(filepath))
                new_filename = f"item_{id_vinculo}_{datetime.now().strftime('%Y%m%d%H%M%S%f')}{ext}"
                dest_path = os.path.join(uploads_dir, new_filename)
                
                import shutil
                try:
                    shutil.copy(filepath, dest_path)
                    image_list.append(new_filename)
                except Exception as e:
                    messagebox.showerror("Erro ao Copiar", f"Não foi possível salvar o arquivo {os.path.basename(filepath)}:\n{e}", parent=modal)

            item_data['files'] = list(set(image_list)) # Usa set para evitar duplicatas
            images_map[str(id_vinculo)] = item_data

            with open(json_path, 'w', encoding='utf-8') as f:
                json.dump(images_map, f, indent=4)

            messagebox.showinfo("Sucesso", f"{len(filepaths)} foto(s) anexada(s) com sucesso!", parent=modal)
            atualizar_contagem_fotos()

        # Botões para gerenciar fotos
        photo_buttons_frame = ctk.CTkFrame(photo_frame, fg_color="transparent")
        photo_buttons_frame.pack(pady=10)
        ctk.CTkButton(photo_buttons_frame, text="Anexar Fotos", command=anexar_fotos).pack(side=tk.LEFT, padx=10)
        ctk.CTkButton(photo_buttons_frame, text="Ver Fotos", command=lambda: self.ver_fotos(id_vinculo)).pack(side=tk.LEFT, padx=10)

        # Atualiza a contagem inicial
        atualizar_contagem_fotos()
        
        def salvar_edicao():
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
                with connection.cursor() as cursor:
                    update_fields = []
                    update_params = []
                    
                    for label_text, field_name, field_type in fields:
                        if field_name in entries or field_type == datetime: # Apenas processa campos editáveis
                            # Pula campos que não estão habilitados para edição
                            if field_name == 'data_pcp' and not is_date_valid(item_para_editar.get('data_prog_fim')): continue
                            if field_name == 'data_producao' and not is_date_valid(item_para_editar.get('data_pcp')): continue
                            if field_name == 'data_qualidade' and not is_date_valid(item_para_editar.get('data_producao')): continue

                            widget, _ = entries[field_name]
                            new_value = None

                            if field_type == datetime:
                                datetime_str = widget.get().strip()
                                
                                # Apenas processa se o campo foi preenchido
                                if datetime_str:
                                    new_value = datetime.strptime(datetime_str, '%d/%m/%Y %H:%M')
                            else: # int ou str
                                if field_name not in entries: continue # Pula campos não editáveis como qtd e lote
                                new_value_str = widget.get().strip()
                                # Apenas processa se o valor mudou do original
                                if new_value_str != str(item_para_editar.get(field_name) or ''):
                                    new_value = new_value_str
                            
                            # Apenas atualiza se o valor mudou
                            if new_value != item_para_editar.get(field_name):
                                update_fields.append(f"{field_name} = %s")
                                update_params.append(new_value)
                    
                    if update_fields:
                        sql = f"UPDATE cliente_item SET {', '.join(update_fields)} WHERE id_item = %s"
                        update_params.append(id_vinculo)
                        cursor.execute(sql, update_params)
                        connection.commit()
                        messagebox.showinfo("Sucesso", "Item atualizado com sucesso!")
                        modal.destroy()
                        self.carregar_obras(self.ano_var.get(), self.search_var.get()) # Recarrega para refletir as mudanças
                    else:
                        messagebox.showinfo("Info", "Nenhuma alteração detectada.", parent=modal)
                        modal.destroy()
                        
            except ValueError:
                messagebox.showerror("Erro", "Formato de número inválido.")
            except Exception as e:
                messagebox.showerror("Erro", f"Erro ao salvar edição: {str(e)}")
            finally:
                if connection:
                    connection.close()
        
        button_frame = ctk.CTkFrame(frame, fg_color="transparent")
        button_frame.grid(row=len(fields) + 1, column=0, columnspan=2, pady=(20, 10))
        ctk.CTkButton(button_frame, text="Salvar", command=salvar_edicao).pack(side=tk.LEFT, padx=5)
        ctk.CTkButton(button_frame, text="Cancelar", command=modal.destroy).pack(side=tk.LEFT, padx=5)

    def abrir_modal_relatorio_itens(self):
        """Abre um modal para selecionar equipamentos e gerar um relatório em PDF."""
        if not REPORTLAB_AVAILABLE:
            messagebox.showerror("Funcionalidade Indisponível", "A biblioteca 'reportlab' é necessária para gerar relatórios em PDF.")
            return

        selected_text = self.pedido_select_var.get()
        if not selected_text:
            messagebox.showwarning("Aviso", "Nenhum pedido selecionado.")
            return

        # Encontrar o pedido e seus itens
        selected_pedido = next((p for p in self.obras_data if f"{p['numero_pedido']} - {p['cliente']} ({p['endereco']})" == selected_text), None)
        if not selected_pedido:
            messagebox.showerror("Erro", "Pedido selecionado não encontrado nos dados.")
            return

        pedido_id = selected_pedido['idpedido']
        itens_do_pedido = self.produtos_por_pedido.get(pedido_id, [])
        if not itens_do_pedido:
            messagebox.showinfo("Relatório", "Este pedido não possui itens para gerar relatório.")
            return

        # Agrupar itens por equipamento
        equipamentos = {}
        for item in itens_do_pedido:
            equip_id = item['equipamento_id']
            if equip_id not in equipamentos:
                equipamentos[equip_id] = {
                    'nome': item['nome_equipamento'],
                    'codigo': item['codigo_equipamento'],
                    'itens': []
                }
            equipamentos[equip_id]['itens'].append(item)

        # Criar o modal
        modal = ctk.CTkToplevel(self.main_frame)
        modal.title("Gerar Relatório de Itens")
        self.center_window(modal, 600, 500)
        modal.grab_set()

        ctk.CTkLabel(modal, text="Selecione os equipamentos para o relatório:", font=('Arial', 12, 'bold')).pack(pady=10)

        scrollable_frame = ctk.CTkScrollableFrame(modal)
        scrollable_frame.pack(fill="both", expand=True, padx=10, pady=5)

        equip_vars = {}
        for equip_id, equip_data in equipamentos.items():
            var = tk.BooleanVar(value=True) # Começa selecionado
            equip_vars[equip_id] = var
            check = ctk.CTkCheckBox(scrollable_frame, text=f"({equip_data['codigo']}) {equip_data['nome']}", variable=var)
            check.pack(anchor="w", padx=10, pady=2)

        def gerar_pdf():
            selected_equip_ids = [equip_id for equip_id, var in equip_vars.items() if var.get()]
            if not selected_equip_ids:
                messagebox.showwarning("Seleção", "Selecione ao menos um equipamento.", parent=modal)
                return

            default_filename = f"Relatorio_Itens_Pedido_{selected_pedido['numero_pedido']}.pdf"
            filepath = filedialog.asksaveasfilename(
                defaultextension=".pdf",
                filetypes=[("Arquivos PDF", "*.pdf")],
                initialfile=default_filename,
                title="Salvar Relatório PDF"
            )
            if not filepath:
                return

            try:
                self.criar_documento_pdf(filepath, selected_pedido, equipamentos, selected_equip_ids)
                messagebox.showinfo("Sucesso", f"Relatório salvo com sucesso em:\n{filepath}", parent=modal)
                modal.destroy()
            except Exception as e:
                messagebox.showerror("Erro ao Gerar PDF", f"Ocorreu um erro: {e}", parent=modal)

        ctk.CTkButton(modal, text="Gerar PDF", command=gerar_pdf).pack(pady=10)

    def criar_documento_pdf(self, filepath, pedido_info, todos_equipamentos, selected_equip_ids):
        """Cria o documento PDF com os dados fornecidos."""
        doc = SimpleDocTemplate(filepath, pagesize=landscape(A4), topMargin=0.5*inch, bottomMargin=0.5*inch)
        styles = getSampleStyleSheet()
        styles.add(ParagraphStyle(name='Center', alignment=TA_CENTER))
        styles.add(ParagraphStyle(name='EquipHeader', fontSize=12, fontName='Helvetica-Bold', spaceAfter=6))
        story = []

        # --- Cabeçalho do Cliente ---
        story.append(Paragraph("Relatório de Itens do Pedido", styles['h1']))
        story.append(Spacer(1, 0.2*inch))

        data_entrega_str = pedido_info['data_entrega'].strftime('%d/%m/%Y') if pedido_info.get('data_entrega') else 'N/A'
        # Reorganiza o cabeçalho em 2 linhas e 4 colunas
        header_data = [
            [f"Cliente:", f"{pedido_info.get('cliente', '')}", "Endereço:", f"{pedido_info.get('endereco', '')}"],
            [f"Nº Pedido:", f"{pedido_info.get('numero_pedido', '')}", "Data Entrega:", data_entrega_str],
        ]
        # Ajusta as larguras das colunas para o layout paisagem
        header_table = Table(header_data, colWidths=[1.5*inch, 4*inch, 1.5*inch, 3.5*inch])
        header_table.setStyle(TableStyle([
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            # Deixa os rótulos em negrito
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'), 
            ('FONTNAME', (2, 0), (2, -1), 'Helvetica-Bold'),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ]))
        story.append(header_table)
        story.append(Spacer(1, 0.3*inch))

        # --- Lista de Equipamentos e Itens ---
        for equip_id in selected_equip_ids:
            equip_data = todos_equipamentos[equip_id]
            story.append(Paragraph(f"Equipamento: ({equip_data['codigo']}) {equip_data['nome']}", styles['EquipHeader']))

            # Tabela de itens para este equipamento
            # Adiciona as colunas de data ao cabeçalho da tabela de itens
            table_data = [[
                "Qtd.", "Código", "Descrição (Conjunto)", "Engenharia", "Programação", "PCP", "Produção", "Qualidade"
            ]]
            # Filtra para mostrar apenas os itens que são filhos diretos do equipamento (caminho com 2 partes)
            itens_filho = [item for item in equip_data['itens'] if len((item.get('caminho') or '').split('>')) == 2]

            for item in itens_filho:
                # Formata as datas para exibição
                def format_date(date_obj):
                    return date_obj.strftime('%d/%m/%y') if date_obj and hasattr(date_obj, 'year') and date_obj.year > 1 else ''

                table_data.append([
                    item.get('quantidade_prod', ''),
                    item.get('codigo_conjunto', ''),
                    item.get('conjunto', ''),
                    format_date(item.get('data_engenharia')),
                    format_date(item.get('data_programacao')),
                    format_date(item.get('data_pcp')),
                    format_date(item.get('data_producao')),
                    format_date(item.get('data_qualidade')),
                ])
            
            # Ajusta as larguras das colunas para o layout paisagem
            item_table = Table(table_data, colWidths=[
                0.6*inch, 1.2*inch, 4.8*inch, 0.8*inch, 0.8*inch, 0.8*inch, 0.8*inch, 0.8*inch
            ])
            item_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
                ('GRID', (0, 0), (-1, -1), 1, colors.black)
            ]))
            story.append(item_table)
            story.append(Spacer(1, 0.3*inch))

        doc.build(story)

    def show_tag_modal(self, id_vinculo):
        messagebox.showinfo("Observações", f"Funcionalidade de mostrar observações para o item {id_vinculo} (a ser implementada).")

    def preencher_datas_multiplas(self, equipamento_iid):
        """Abre um modal para preencher em lote as datas de produção ou qualidade dos itens de um equipamento."""
        
        # 1. Obter informações do pedido
        selected_text = self.pedido_select_var.get()
        pedido_info = next((p for p in self.obras_data if f"{p['numero_pedido']} - {p['cliente']} ({p['endereco']})" == selected_text), None)
        if not pedido_info:
            messagebox.showerror("Erro", "Não foi possível encontrar os dados do pedido selecionado.")
            return

        # 2. Encontrar todos os itens "folha" (com id_vinculo) do equipamento clicado, incluindo subconjuntos
        def get_all_leaf_children(parent_iid):
            """Função recursiva para encontrar todos os nós 'folha' (itens finais) sob um nó pai."""
            children = self.itens_tree.get_children(parent_iid)
            # Se o nó não tem filhos, ele é uma folha.
            if not children:
                return [parent_iid]
            
            # Se tem filhos, percorre cada um deles.
            leaf_nodes = []
            for child_iid in children:
                leaf_nodes.extend(get_all_leaf_children(child_iid))
            return leaf_nodes
        
        all_child_iids = get_all_leaf_children(equipamento_iid)

        itens_filho_para_atualizar = []
        for child_iid in all_child_iids:
            try:
                id_vinculo = int(child_iid.split('|')[-1])
                item_data = next((item for item in self.produtos_por_pedido.get(pedido_info['idpedido'], []) if item['id_vinculo'] == id_vinculo), None)
                if item_data:
                    itens_filho_para_atualizar.append(item_data)
            except (ValueError, IndexError):
                continue

        if not itens_filho_para_atualizar:
            messagebox.showinfo("Aviso", "Nenhum item filho encontrado para este equipamento.", parent=self.main_frame)
            return

        # 3. Criar o modal de confirmação
        modal = ctk.CTkToplevel(self.main_frame)
        modal.title("Preenchimento em Lote")
        self.center_window(modal, 400, 250)
        modal.grab_set()

        ctk.CTkLabel(modal, text="Qual data deseja preencher?", font=('Arial', 14, 'bold')).pack(pady=20)

        radio_var = tk.StringVar(value="producao")
        
        ctk.CTkRadioButton(modal, text="Data de Produção", variable=radio_var, value="producao").pack(anchor='w', padx=50, pady=5)
        ctk.CTkRadioButton(modal, text="Data de Qualidade", variable=radio_var, value="qualidade").pack(anchor='w', padx=50, pady=5)

        def _is_valid_date_for_check(date_obj):
            """Verifica se um objeto de data é uma data válida e não uma 'zero date'."""
            return date_obj is not None and hasattr(date_obj, 'year') and date_obj.year > 1

        def on_confirm():
            campo_data = f"data_{radio_var.get()}"
            data_atual = datetime.now()
            
            ids_para_atualizar = []
            for item in itens_filho_para_atualizar:
                # Condição para atualizar data de produção
                if campo_data == 'data_producao':
                   # Data de PCP deve ser válida e data de produção não pode ser válida
                    if _is_valid_date_for_check(item.get('data_pcp')) and not _is_valid_date_for_check(item.get('data_producao')):
                        ids_para_atualizar.append(item['id_vinculo'])
                
                # Condição para atualizar data de qualidade
                elif campo_data == 'data_qualidade':
                    # Data de produção deve ser válida e data de qualidade não pode ser válida
                    if _is_valid_date_for_check(item.get('data_producao')) and not _is_valid_date_for_check(item.get('data_qualidade')):
                        ids_para_atualizar.append(item['id_vinculo'])

            if not ids_para_atualizar:
                messagebox.showwarning("Aviso", "Nenhum item elegível para atualização foi encontrado.", parent=modal)
                return

            confirm_msg = (f"Você está prestes a preencher a '{campo_data.replace('_', ' ').title()}' "
                           f"para {len(ids_para_atualizar)} item(ns).\nDeseja continuar?")
            if not messagebox.askyesno("Confirmar Ação", confirm_msg, parent=modal):
                return

            # Executar a atualização no banco de dados
            connection = None
            try:
                connection = pymysql.connect(host=DB_HOST, user=DB_USER, password=DB_PASS, database=DB_NAME)
                with connection.cursor() as cursor:
                    # Cria uma string de placeholders (%s, %s, ...)
                    placeholders = ', '.join(['%s'] * len(ids_para_atualizar))
                    sql = f"UPDATE cliente_item SET {campo_data} = %s WHERE id_item IN ({placeholders})"
                    
                    # Os parâmetros são a data atual e a lista de IDs
                    params = [data_atual] + ids_para_atualizar
                    
                    cursor.execute(sql, params)
                    connection.commit()

                messagebox.showinfo("Sucesso", f"{cursor.rowcount} item(ns) atualizado(s) com sucesso!", parent=modal)
                modal.destroy()
                # Recarrega os dados para refletir as mudanças na tela
                self.filtrar_obras()

            except Exception as e:
                messagebox.showerror("Erro de Banco de Dados", f"Falha ao atualizar os itens:\n{e}", parent=modal)
            finally:
                if connection:
                    connection.close()

        button_frame = ctk.CTkFrame(modal, fg_color="transparent")
        button_frame.pack(pady=30, fill='x', padx=50)

        ctk.CTkButton(button_frame, text="Confirmar", command=on_confirm).pack(side='left', expand=True, padx=(0, 5))
        ctk.CTkButton(button_frame, text="Cancelar", command=modal.destroy, fg_color="gray").pack(side='right', expand=True, padx=(5, 0))

    def ver_fotos(self, id_vinculo):
        """Abre uma galeria de fotos para o item selecionado."""
        if not PIL_AVAILABLE:
            messagebox.showerror("Dependência Faltando", "A biblioteca 'Pillow' é necessária para ver as fotos.\nExecute: pip install Pillow")
            return

        uploads_dir = 'uploads'
        json_path = os.path.join(uploads_dir, 'images.json')

        if not os.path.exists(json_path):
            messagebox.showwarning("Arquivo não encontrado", f"O arquivo de mapeamento de imagens não foi encontrado em:\n{json_path}", parent=self.main_frame)
            return

        try:
            with open(json_path, 'r', encoding='utf-8') as f:
                images_map = json.load(f)
        except (json.JSONDecodeError, FileNotFoundError) as e:
            messagebox.showerror("Erro ao ler JSON", f"Não foi possível ler o arquivo de imagens:\n{e}", parent=self.main_frame)
            return

        # Lida com ambos os formatos de JSON (antigo e novo)
        item_entry = images_map.get(str(id_vinculo))
        if isinstance(item_entry, dict):
            # Novo formato: {"info": ..., "files": [...]}
            image_files = item_entry.get('files', [])
        elif isinstance(item_entry, list):
            # Formato antigo: [...]
            image_files = item_entry
        else:
            image_files = []

        if not image_files:
            messagebox.showinfo("Fotos", f"Nenhuma foto encontrada para o item {id_vinculo}.", parent=self.main_frame)
            return

        # Cria a janela da galeria
        gallery_window = ctk.CTkToplevel(self.main_frame)
        gallery_window.title(f"Fotos do Item {id_vinculo}")
        gallery_window.geometry("800x600")
        gallery_window.transient(self.main_frame)
        gallery_window.grab_set()
        self.center_window(gallery_window, 800, 600)

        current_image_index = 0

        # Label para exibir a imagem
        image_label = ctk.CTkLabel(gallery_window, text="")
        image_label.pack(expand=True, fill="both", padx=10, pady=10)

        # Label para o contador de imagens
        counter_label = ctk.CTkLabel(gallery_window, text="")
        counter_label.pack(pady=(0, 5))

        def show_image(index):
            nonlocal current_image_index
            current_image_index = index
            
            image_path = os.path.join(uploads_dir, image_files[index])
            if not os.path.exists(image_path):
                image_label.configure(text=f"Imagem não encontrada:\n{image_path}", image=None)
                return

            img = Image.open(image_path)
            # Redimensiona a imagem para caber na janela, mantendo a proporção
            img.thumbnail((780, 520))
            # Usa ctk.CTkImage em vez de ImageTk.PhotoImage para evitar o warning
            ctk_image = ctk.CTkImage(light_image=img, dark_image=img, size=img.size)
            
            image_label.configure(image=ctk_image, text="")
            image_label.image = ctk_image # Mantém a referência

            counter_label.configure(text=f"{index + 1} / {len(image_files)}")

        def next_image():
            show_image((current_image_index + 1) % len(image_files))

        def prev_image():
            show_image((current_image_index - 1 + len(image_files)) % len(image_files))

        # Botões de navegação
        btn_frame = ctk.CTkFrame(gallery_window, fg_color="transparent")
        btn_frame.pack(pady=10)
        ctk.CTkButton(btn_frame, text="< Anterior", command=prev_image).pack(side="left", padx=20)
        ctk.CTkButton(btn_frame, text="Próximo >", command=next_image).pack(side="right", padx=20)

        # Exibe a primeira imagem
        show_image(0)
