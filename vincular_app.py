import tkinter as tk
from tkinter import ttk, messagebox, simpledialog, font
import customtkinter as ctk
import pymysql
import datetime
from config import DB_HOST, DB_USER, DB_PASS, DB_NAME

class VincularApp:
    def __init__(self, parent, user):
        self.parent = parent
        self.user = user
        self.main_frame = ctk.CTkFrame(self.parent, fg_color="transparent")
        self.main_frame.pack(fill=tk.BOTH, expand=True)

        self.all_composicoes = {}
        self.comps_by_pai = {}

        self.create_widgets()
        self.load_initial_data()

    def _execute_query(self, query, params=None, fetch=None):
        conn = None
        try:
            conn = pymysql.connect(
                host=DB_HOST, user=DB_USER, password=DB_PASS,
                database=DB_NAME, charset='utf8mb4',
                cursorclass=pymysql.cursors.DictCursor
            )
            with conn.cursor() as cursor:
                cursor.execute(query, params or ())
                if fetch == 'one':
                    return cursor.fetchone()
                elif fetch == 'all':
                    return cursor.fetchall()
                else:
                    conn.commit()
                    return True
        except pymysql.Error as e:
            messagebox.showerror("Erro de Banco de Dados", f"Erro: {e}")
            if conn:
                conn.rollback()
            return None if fetch else False
        finally:
            if conn:
                conn.close()

    def create_widgets(self):
        # --- Frame do Formulário ---
        form_outer_frame = ctk.CTkFrame(self.main_frame)
        form_outer_frame.pack(fill="x", padx=10, pady=10)
        ctk.CTkLabel(form_outer_frame, text="Vincular Itens ao Pedido", font=ctk.CTkFont(weight="bold")).pack(anchor="w", padx=10, pady=(5, 0))
        form_frame = ctk.CTkFrame(form_outer_frame)
        form_frame.pack(fill="x", padx=10, pady=10)

        # --- Linha 1: Pedido e Item Raiz ---
        row1 = ctk.CTkFrame(form_frame, fg_color="transparent")
        row1.pack(fill='x', pady=5)

        # --- Seleção de Pedido ---
        ctk.CTkLabel(row1, text="Pedido:", width=100).pack(side='left')
        self.pedido_var = tk.StringVar()
        self.pedido_entry = ctk.CTkEntry(row1, textvariable=self.pedido_var, state="readonly")
        self.pedido_entry.pack(side='left', padx=5, fill='x', expand=True)
        ctk.CTkButton(row1, text="Selecionar", width=100, command=self.select_pedido).pack(side='left', padx=(0, 5))

        # --- Seleção de Item Raiz ---
        ctk.CTkLabel(row1, text="Item Raiz (Equipamento):").pack(side='left', padx=(20, 5))
        self.item_raiz_var = tk.StringVar()
        self.item_raiz_entry = ctk.CTkEntry(row1, textvariable=self.item_raiz_var, state="readonly")
        self.item_raiz_entry.pack(side='left', padx=5, fill='x', expand=True)
        ctk.CTkButton(row1, text="Selecionar", width=100, command=self.select_item_raiz).pack(side='left', padx=(0, 5))

        # --- Widgets Antigos (agora removidos) ---
        # self.pedido_combo = ctk.CTkComboBox(row1, variable=self.pedido_var, state="readonly", width=300, command=self.on_pedido_selected)
        # self.pedido_combo.pack(side='left', padx=5, fill='x', expand=True)
        # self.item_raiz_combo = ctk.CTkComboBox(row1, variable=self.item_raiz_var, state="readonly", width=300, command=self.on_item_raiz_selected)
        # self.item_raiz_combo.pack(side='left', padx=5, fill='x', expand=True)
        
        # --- Linha 2: Itens da Composição (em um Listbox) ---
        row2 = ctk.CTkFrame(form_frame, fg_color="transparent")
        row2.pack(fill='x', pady=5, expand=True)

        ctk.CTkLabel(row2, text="Itens da Composição:", width=100).pack(side='left', anchor='n', pady=(0, 5))
        self.itens_listbox_frame = ctk.CTkFrame(row2, fg_color="transparent")
        self.itens_listbox_frame.pack(side='left', fill='both', expand=True)
        self.itens_listbox = tk.Listbox(self.itens_listbox_frame, selectmode='extended', height=8,
                                        bg="#2b2b2b", fg="white", borderwidth=0, highlightthickness=0,
                                        selectbackground="#1f6aa5", selectforeground="white")
        self.itens_listbox.pack(side='left', fill='both', expand=True)
        
        listbox_scrollbar = ctk.CTkScrollbar(self.itens_listbox_frame, command=self.itens_listbox.yview)
        self.itens_listbox.configure(yscrollcommand=listbox_scrollbar.set)
        listbox_scrollbar.pack(side='right', fill='y')

        # --- Linha 3: Campos Adicionais ---
        row3 = ctk.CTkFrame(form_frame, fg_color="transparent")
        row3.pack(fill='x', pady=5)

        ctk.CTkLabel(row3, text="Quantidade:", width=100).pack(side='left')
        self.quantidade_var = tk.StringVar(value="1")
        self.quantidade_entry = ctk.CTkEntry(row3, textvariable=self.quantidade_var, width=100)
        self.quantidade_entry.pack(side='left', padx=5)

        self.include_desc_var = tk.BooleanVar(value=True)
        ctk.CTkCheckBox(row3, text="Incluir itens subsequentes (filhos/netos)", variable=self.include_desc_var).pack(side='left', padx=20)

        # --- Botão de Salvar ---
        save_button = ctk.CTkButton(form_frame, text="Salvar Vínculo", command=self.save_vinculo)
        save_button.pack(pady=10)

        # --- Frame da Lista de Vínculos ---
        list_outer_frame = ctk.CTkFrame(self.main_frame)
        list_outer_frame.pack(fill="both", expand=True, padx=10, pady=10)
        ctk.CTkLabel(list_outer_frame, text="Itens Já Vinculados ao Pedido", font=ctk.CTkFont(weight="bold")).pack(anchor="w", padx=10, pady=(5, 0))
        list_frame = ctk.CTkFrame(list_outer_frame)
        list_frame.pack(fill="both", expand=True, padx=10, pady=10)

        style = ttk.Style()
        style.theme_use("default")
        style.configure("Custom.Treeview", background="#2b2b2b", foreground="white", fieldbackground="#2b2b2b", borderwidth=0)
        style.configure("Custom.Treeview.Heading", background="#171717", foreground="white", relief="flat", font=('Arial', 10, 'bold'))
        style.map("Custom.Treeview.Heading", background=[('active', '#333333')])
        style.map("Custom.Treeview", background=[('selected', '#00529B')])

        columns = ('id_vinculo', 'item_fk', 'descricao', 'quantidade', 'caminho', 'status')
        self.vinculos_tree = ttk.Treeview(list_frame, columns=columns, show='headings', height=10, style="Custom.Treeview")

        headings = {
            'id_vinculo': 'ID Vínculo', 'item_fk': 'ID Item', 'descricao': 'Descrição do Item',
            'quantidade': 'Quantidade', 'caminho': 'Caminho na Estrutura', 'status': 'Status'
        }
        widths = {
            'id_vinculo': 80, 'item_fk': 80, 'descricao': 300,
            'quantidade': 100, 'caminho': 300, 'status': 150
        }

        for col, text in headings.items():
            self.vinculos_tree.heading(col, text=text)
            self.vinculos_tree.column(col, width=widths[col], anchor='w')

        self.vinculos_tree.pack(side='left', fill='both', expand=True)
        
        tree_scrollbar = ctk.CTkScrollbar(list_frame, command=self.vinculos_tree.yview)
        self.vinculos_tree.configure(yscrollcommand=tree_scrollbar.set)
        tree_scrollbar.pack(side='right', fill='y')

        # --- Menu de Contexto para a Treeview de Vínculos ---
        self.vinculos_tree.bind("<Button-3>", self.show_vinculo_context_menu)
        self.vinculo_context_menu = tk.Menu(self.vinculos_tree, tearoff=0)
        self.vinculo_context_menu.add_command(label="Alterar Quantidade", command=self.alterar_quantidade_vinculo)
        self.vinculo_context_menu.add_command(label="Excluir Vínculo", command=self.excluir_vinculo)
        self.selected_vinculo_id = None

    def load_initial_data(self):
        # Carregar Pedidos
        sql_pedidos = """
            SELECT p.idpedido, p.numero_pedido, c.cliente
            FROM pedido p JOIN add_cliente c ON p.idcliente = c.idcliente
            ORDER BY p.idpedido DESC
        """
        pedidos = self._execute_query(sql_pedidos, fetch='all')
        if pedidos:
            self.pedido_map = {f"{p['numero_pedido']} - {p['cliente']}": p['idpedido'] for p in pedidos}
            # Não configura mais o combobox, os dados são usados no modal
            # self.pedido_combo.configure(values=list(self.pedido_map.keys()))

        # Carregar Itens Raiz
        sql_itens_raiz = """
            SELECT DISTINCT i.id, i.codigo, i.descricao
            FROM itens i JOIN item_composicao ic ON i.id = ic.id_item_pai
            ORDER BY i.codigo
        """
        itens_raiz = self._execute_query(sql_itens_raiz, fetch='all')
        if itens_raiz:
            self.item_raiz_map = {f"{i['codigo']} - {i['descricao']}": i['id'] for i in itens_raiz}
            # Não configura mais o combobox, os dados são usados no modal
            # self.item_raiz_combo.configure(values=list(self.item_raiz_map.keys()))

        # Carregar todas as composições em memória para performance
        sql_all_comps = "SELECT id, id_item_pai, id_item_filho, quantidade FROM item_composicao"
        all_comps_data = self._execute_query(sql_all_comps, fetch='all')
        if all_comps_data:
            for comp in all_comps_data:
                pai_id = comp['id_item_pai']
                if pai_id not in self.comps_by_pai:
                    self.comps_by_pai[pai_id] = []
                self.comps_by_pai[pai_id].append(comp)
                self.all_composicoes[comp['id']] = comp

    def select_pedido(self):
        """Abre o modal de seleção para Pedidos."""
        if not hasattr(self, 'pedido_map'):
            messagebox.showwarning("Aguarde", "Os dados dos pedidos ainda estão sendo carregados.")
            return
        
        items_list = list(self.pedido_map.keys())
        
        def on_select_callback(selected_item):
            self.pedido_var.set(selected_item)
            self.on_pedido_selected()

        self._open_selection_modal("Selecionar Pedido", items_list, on_select_callback)

    def select_item_raiz(self):
        """Abre o modal de seleção para Itens Raiz."""
        if not hasattr(self, 'item_raiz_map'):
            messagebox.showwarning("Aguarde", "Os dados dos itens ainda estão sendo carregados.")
            return
            
        items_list = list(self.item_raiz_map.keys())

        def on_select_callback(selected_item):
            self.item_raiz_var.set(selected_item)
            self.on_item_raiz_selected()

        self._open_selection_modal("Selecionar Item Raiz", items_list, on_select_callback)

    def _open_selection_modal(self, title, items, callback):
        """Cria e exibe uma janela modal para seleção de um item em uma lista pesquisável."""
        modal = ctk.CTkToplevel(self.main_frame)
        modal.title(title)
        modal.geometry("500x400")
        modal.transient(self.main_frame)
        modal.grab_set()

        # --- Centraliza a janela modal ---
        modal.update_idletasks() # Garante que as dimensões da janela principal estão atualizadas
        main_win = self.main_frame.winfo_toplevel()
        x = main_win.winfo_x() + (main_win.winfo_width() // 2) - (modal.winfo_width() // 2)
        y = main_win.winfo_y() + (main_win.winfo_height() // 2) - (modal.winfo_height() // 2)
        modal.geometry(f"+{x}+{y}")
        # --- Fim da centralização ---

        search_var = tk.StringVar()
        
        ctk.CTkLabel(modal, text="Buscar:").pack(padx=10, pady=(10, 0), anchor="w")
        search_entry = ctk.CTkEntry(modal, textvariable=search_var)
        search_entry.pack(padx=10, fill="x")

        listbox = tk.Listbox(modal, height=15, bg="#2b2b2b", fg="white", selectbackground="#1f6aa5")
        listbox.pack(padx=10, pady=10, fill="both", expand=True)

        def update_listbox(data):
            listbox.delete(0, "end")
            for item in data:
                listbox.insert("end", item)

        # A função de trace recebe argumentos que não usamos, então usamos *args
        def on_search(*args):
            term = search_var.get().lower()
            filtered_items = [item for item in items if term in item.lower()]
            update_listbox(filtered_items)

        search_entry.bind("<KeyRelease>", on_search) # Usar KeyRelease é mais eficiente
        update_listbox(items) # Popula a lista inicial

        def on_confirm():
            selected_indices = listbox.curselection()
            if not selected_indices:
                messagebox.showwarning("Seleção", "Por favor, selecione um item da lista.", parent=modal)
                return
            selected_item = listbox.get(selected_indices[0])
            callback(selected_item)
            modal.destroy()

        ctk.CTkButton(modal, text="Confirmar", command=on_confirm).pack(pady=10)

    def on_pedido_selected(self, event=None):
        selected_text = self.pedido_var.get()
        id_pedido = self.pedido_map.get(selected_text)
        if not id_pedido:
            return

        # Limpa a lista de vínculos
        for i in self.vinculos_tree.get_children():
            self.vinculos_tree.delete(i)

        # Query ajustada para buscar todos os campos necessários, alinhada com a API web
        sql = """
            SELECT 
                ci.id_item      AS id_vinculo,
                filho.id        AS item_fk,
                filho.codigo    AS codigo_item,
                filho.descricao AS descricao,
                ci.quantidade_prod AS quantidade,
                ci.status_producao AS status,
                CONCAT(ci.item_raiz_id, '-', ci.id_item_fk) AS caminho,
                pai.descricao   AS equipamento
            FROM cliente_item ci
            JOIN itens pai ON ci.item_raiz_id = pai.id
            JOIN itens filho ON ci.id_item_fk = filho.id
            WHERE ci.idpedido = %s
            ORDER BY pai.descricao, filho.descricao;
        """
        vinculos = self._execute_query(sql, (id_pedido,), fetch='all') or []

        # Font para cálculo da largura do texto
        default_font = font.nametofont("TkDefaultFont")

        # Insere explicitamente os valores na ordem dos headings
        for v in vinculos:
            # Trunca os textos longos para evitar quebra de linha
            descricao_trunc = self._truncate_text(v.get('descricao'), self.vinculos_tree.column('descricao', 'width'), default_font)
            caminho_trunc = self._truncate_text(v.get('caminho'), self.vinculos_tree.column('caminho', 'width'), default_font)

            values = (
                v.get('id_vinculo'),
                v.get('item_fk'),
                descricao_trunc,
                v.get('quantidade'),
                caminho_trunc,
                v.get('status')
            )
            self.vinculos_tree.insert('', 'end', values=values)

    def _truncate_text(self, text, max_width, font_obj):
        """Trunca o texto com '...' se exceder a largura máxima da coluna."""
        if not isinstance(text, str):
            return text
        
        text_width = font_obj.measure(text)
        if text_width > max_width:
            while font_obj.measure(text + '...') > max_width and len(text) > 0:
                text = text[:-1]
            return text + '...'
        return text

    def on_item_raiz_selected(self, event=None):
        self.itens_listbox.delete(0, 'end')
        selected_text = self.item_raiz_var.get()
        id_raiz = self.item_raiz_map.get(selected_text)
        if not id_raiz:
            return

        # Usar BFS para encontrar filhos diretos
        if id_raiz in self.comps_by_pai:
            for comp in self.comps_by_pai[id_raiz]:
                id_filho = comp['id_item_filho']
                # Precisamos buscar a descrição do filho
                filho_info = self._execute_query("SELECT codigo, descricao FROM itens WHERE id = %s", (id_filho,), fetch='one')
                if filho_info:
                    label = f"{filho_info['codigo']} - {filho_info['descricao']}"
                    # Armazenar o ID da composição no listbox
                    self.itens_listbox.insert('end', f"{comp['id']}:{label}")

    def save_vinculo(self):
        # --- Validações ---
        id_pedido = self.pedido_map.get(self.pedido_var.get())
        if not id_pedido:
            messagebox.showerror("Erro", "Selecione um pedido válido.")
            return

        id_item_raiz_selecionado = self.item_raiz_map.get(self.item_raiz_var.get())
        if not id_item_raiz_selecionado:
            messagebox.showerror("Erro", "Selecione um Item Raiz (Equipamento) válido.")
            return

        selected_indices = self.itens_listbox.curselection()
        if not selected_indices:
            messagebox.showerror("Erro", "Selecione pelo menos um item da composição.")
            return

        try:
            quantidade_input = float(self.quantidade_var.get())
        except ValueError:
            messagebox.showerror("Erro", "A quantidade deve ser um número válido.")
            return

        # --- Lógica de Inserção ---
        id_composicoes_selecionadas = []
        for i in selected_indices:
            # Extrai o ID da composição do texto do listbox
            id_comp = int(self.itens_listbox.get(i).split(':')[0])
            id_composicoes_selecionadas.append(id_comp)

        to_insert_list = self.build_insertion_list(id_composicoes_selecionadas)

        if not to_insert_list:
            messagebox.showinfo("Informação", "Nenhum item novo para inserir.")
            return
        
        # --- Execução no Banco de Dados ---
        inserted_count = 0
        for entry in to_insert_list:
            id_comp = entry['comp_id']
            # A quantidade final já vem calculada corretamente do build_insertion_list
            quantidade_prod_final = entry['final_quantity'] 

            comp_info = self.all_composicoes.get(id_comp)
            if not comp_info:
                continue

            id_item_filho = comp_info['id_item_filho']
            
            # Monta o caminho completo
            # O caminho agora é uma lista de IDs, então juntamos com '>'
            path_full = '>'.join(map(str, entry['path']))

            current_timestamp = datetime.datetime.now()
            sql_insert = """
                INSERT INTO cliente_item 
                (idpedido, id_item_fk, id_composicao, quantidade_prod, caminho, item_raiz_id, status_producao, data_engenharia)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """
            params = (
                id_pedido, id_item_filho, id_comp, quantidade_prod_final, path_full, 
                id_item_raiz_selecionado, 'Aguardando Programação', current_timestamp
            )

            if self._execute_query(sql_insert, params):
                inserted_count += 1

        messagebox.showinfo("Sucesso", f"Operação concluída. {inserted_count} registros inseridos.")
        self.on_pedido_selected() # Recarrega a lista de vínculos

    def build_insertion_list(self, id_composicoes_selecionadas):
        """Constrói a lista de itens para inserção, calculando a quantidade cumulativa."""
        to_insert = []
        include_desc = self.include_desc_var.get()
        quantidade_base = float(self.quantidade_var.get() or 1.0)

        for id_comp_raiz in id_composicoes_selecionadas:
            comp_raiz_info = self.all_composicoes.get(id_comp_raiz)
            if not comp_raiz_info:
                continue
            
            id_item_filho_raiz = comp_raiz_info['id_item_filho']
            quantidade_filho_raiz = comp_raiz_info['quantidade']

            # Adiciona o próprio item selecionado
            to_insert.append({
                'comp_id': id_comp_raiz,
                'path': [id_item_filho_raiz],
                'final_quantity': quantidade_base * quantidade_filho_raiz
            })

            if include_desc:
                # Se for para incluir descendentes, faz a busca em árvore (BFS)
                # A fila agora carrega a quantidade acumulada
                queue = [{
                    'item_id': id_item_filho_raiz, 
                    'path': [id_item_filho_raiz],
                    'cumulative_quantity': quantidade_base * quantidade_filho_raiz
                }]
                
                while queue:
                    node = queue.pop(0)
                    current_item_id = node['item_id']
                    current_path = node['path']
                    current_cumulative_qty = node['cumulative_quantity']

                    if current_item_id in self.comps_by_pai:
                        for child_comp in self.comps_by_pai[current_item_id]:
                            child_item_id = child_comp['id_item_filho']
                            new_path = current_path + [child_item_id]
                            new_cumulative_qty = current_cumulative_qty * child_comp['quantidade']
                            
                            to_insert.append({'comp_id': child_comp['id'], 'path': new_path, 'final_quantity': new_cumulative_qty})
                            queue.append({'item_id': child_item_id, 'path': new_path, 'cumulative_quantity': new_cumulative_qty})
        return to_insert

    def show_vinculo_context_menu(self, event):
        """Exibe o menu de contexto para um item vinculado."""
        selected_iid = self.vinculos_tree.identify_row(event.y)
        if not selected_iid:
            return

        self.vinculos_tree.selection_set(selected_iid)
        # Armazena o ID do vínculo (primeira coluna) do item selecionado
        self.selected_vinculo_id = self.vinculos_tree.item(selected_iid, 'values')[0]
        
        # Exibe o menu na posição do cursor
        self.vinculo_context_menu.post(event.x_root, event.y_root)

    def alterar_quantidade_vinculo(self):
        """Abre um diálogo para alterar a quantidade de um item vinculado."""
        if not self.selected_vinculo_id:
            return

        item_values = self.vinculos_tree.item(self.vinculos_tree.selection()[0], 'values')
        descricao = item_values[2]
        quantidade_atual = item_values[3]

        nova_quantidade = simpledialog.askfloat(
            "Alterar Quantidade",
            f"Digite a nova quantidade para:\n{descricao}",
            initialvalue=quantidade_atual,
            parent=self.main_frame
        )

        if nova_quantidade is not None and nova_quantidade >= 0:
            sql = "UPDATE cliente_item SET quantidade_prod = %s WHERE id_item = %s"
            if self._execute_query(sql, (nova_quantidade, self.selected_vinculo_id)):
                messagebox.showinfo("Sucesso", "Quantidade atualizada com sucesso.")
                self.on_pedido_selected() # Recarrega a lista
            else:
                messagebox.showerror("Erro", "Não foi possível atualizar a quantidade.")

    def excluir_vinculo(self):
        """Exclui um item vinculado do pedido."""
        if not self.selected_vinculo_id:
            return

        item_values = self.vinculos_tree.item(self.vinculos_tree.selection()[0], 'values')
        descricao = item_values[2]

        if messagebox.askyesno("Confirmar Exclusão", f"Tem certeza que deseja excluir o vínculo para o item:\n{descricao}?"):
            sql = "DELETE FROM cliente_item WHERE id_item = %s"
            if self._execute_query(sql, (self.selected_vinculo_id,)):
                messagebox.showinfo("Sucesso", "Vínculo excluído com sucesso.")
                self.on_pedido_selected() # Recarrega a lista
            else:
                messagebox.showerror("Erro", "Não foi possível excluir o vínculo.")