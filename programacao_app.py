import tkinter as tk
from tkinter import ttk, messagebox
import customtkinter as ctk
import pymysql
from config import DB_HOST, DB_USER, DB_PASS, DB_NAME
from datetime import datetime
from etiqueta_printer import EtiquetaPrinter

class ProgramacaoApp:
    def __init__(self, parent, user):
        self.parent = parent
        self.user = user
        self.frame = ctk.CTkFrame(parent, fg_color="transparent")
        self.frame.pack(fill=tk.BOTH, expand=True)
        self.all_data = []
        self._after_id = None
        self.active_status_filter = None # Para controlar o filtro de status ativo
        self.card_widgets = [] # Armazena apenas os 4 widgets de card reutilizáveis
        
        # --- Paginação ---
        self.items_per_page = 4 # Reduzido para 4 para melhorar a performance percebida
        self.current_page = 0
        self.filtered_cards = []

        self.create_widgets()
        self.load_data()
        self.frame.bind("<Configure>", self.on_resize)

    def create_widgets(self):
        top_frame = ctk.CTkFrame(self.frame, fg_color="transparent")
        top_frame.pack(fill=tk.X, padx=10, pady=5)
        
        self.btn_nao_iniciada = ctk.CTkButton(top_frame, text="Não Iniciada (0)", fg_color='#ffc107', text_color='black', command=lambda: self.filter_by_status('Pendente'))
        self.btn_nao_iniciada.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=5)

        self.btn_em_andamento = ctk.CTkButton(top_frame, text="Em Andamento (0)", command=lambda: self.filter_by_status('Iniciado'))
        self.btn_em_andamento.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=5)
        
        self.btn_concluidos = ctk.CTkButton(top_frame, text="Concluídos (0)", fg_color='#dc3545', command=lambda: self.filter_by_status('Finalizado'))
        self.btn_concluidos.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=5)

        controls_frame = ctk.CTkFrame(self.frame, fg_color="transparent")
        controls_frame.pack(fill=tk.X, padx=10, pady=5)

        btn_mostrar_todos = ctk.CTkButton(controls_frame, text="Mostrar Todos", command=self.clear_all_filters)
        btn_mostrar_todos.pack(side=tk.LEFT, padx=5)

        self.search_var = tk.StringVar()
        search_entry = ctk.CTkEntry(controls_frame, textvariable=self.search_var, width=300, placeholder_text="Digite equipamento ou conjunto")
        search_entry.pack(side=tk.LEFT, padx=5, expand=True, fill=tk.X)
        search_entry.bind('<KeyRelease>', self.filter_data_debounced)

        # Substitui o ComboBox por um campo de texto e um botão de seleção
        self.client_var = tk.StringVar()
        self.client_entry = ctk.CTkEntry(controls_frame, textvariable=self.client_var, state="readonly", width=200)
        self.client_entry.pack(side=tk.LEFT, padx=5)
        ctk.CTkButton(controls_frame, text="Selecionar Cliente", command=self.open_client_selector).pack(side=tk.LEFT)

        # --- Controles de Paginação ---
        self.pagination_frame = ctk.CTkFrame(controls_frame, fg_color="transparent")
        self.pagination_frame.pack(side=tk.LEFT, padx=10)
        self.prev_button = ctk.CTkButton(self.pagination_frame, text="< Anterior", command=self.prev_page, width=100)
        self.prev_button.pack(side=tk.LEFT)
        self.page_label = ctk.CTkLabel(self.pagination_frame, text="Página 1/1")
        self.page_label.pack(side=tk.LEFT, padx=5)
        self.next_button = ctk.CTkButton(self.pagination_frame, text="Próximo >", command=self.next_page, width=100)
        self.next_button.pack(side=tk.LEFT)

        # Substituição do Canvas manual por CTkScrollableFrame para simplicidade e consistência
        self.scrollable_frame = ctk.CTkScrollableFrame(self.frame, fg_color="transparent")
        self.scrollable_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        # Configura o grid para que os cards se expandam horizontalmente
        self.scrollable_frame.grid_columnconfigure(0, weight=1) # Coluna 0
        self.scrollable_frame.grid_columnconfigure(1, weight=1) # Coluna 1

    def on_resize(self, event=None):
        """Agenda a reorganização dos cards após um redimensionamento."""
        if self._after_id:
            self.parent.after_cancel(self._after_id)
        self._after_id = self.parent.after(200, self.rearrange_cards)

    def rearrange_cards(self):
        """Reorganiza os cards na tela com base na largura atual."""
        if not hasattr(self, 'scrollable_frame') or not self.scrollable_frame.winfo_exists() or not self.card_widgets:
            return

        container_width = self.scrollable_frame.winfo_width()
        min_card_width = 500  # Largura mínima de um card + padding
        
        # Decide entre 1 ou 2 colunas
        num_columns = 2 if container_width > (min_card_width * 2 - 100) else 1

        # Reseta os pesos das colunas e define para o número atual de colunas
        for i in range(2): # Máximo de 2 colunas para cards de programação
            self.scrollable_frame.grid_columnconfigure(i, weight=0)
        for i in range(num_columns):
            self.scrollable_frame.grid_columnconfigure(i, weight=1)
        # Re-grida os cards visíveis
        for i, card_widget in enumerate(self.card_widgets):
            if card_widget.winfo_ismapped():
                row = i // num_columns
                col = i % num_columns
                card_widget.grid(row=row, column=col, pady=5, padx=5, sticky="nsew")

    def load_data(self):
        try:
            connection = pymysql.connect(host=DB_HOST, user=DB_USER, password=DB_PASS, database=DB_NAME, charset='utf8mb4', cursorclass=pymysql.cursors.DictCursor)
            with connection.cursor() as cursor:
                sql = """SELECT c.idcliente, c.cliente, ped.numero_pedido AS pedido, c.endereco,
                           parent.codigo AS codigo_equipamento, parent.descricao AS equipamento_pai, 
                           child.codigo AS codigo_conjunto, child.descricao AS conjunto, child.id AS idproduto, 
                           ci.id_item AS id_vinculo, ci.data_engenharia, ci.data_prog_fim, ci.data_programacao,
                           ci.quantidade_prod, ci.link_pastas, ci.tag, ci.obs_programacao, ci.lote, ci.prioridade,
                           COALESCE(SUM(es.quantidade), 0) AS estoque_total
                       FROM cliente_item ci
                       JOIN pedido ped ON ci.idpedido = ped.idpedido
                       JOIN add_cliente c ON ped.idcliente = c.idcliente
                       JOIN item_composicao ic ON ci.id_composicao = ic.id
                       JOIN itens parent ON ic.id_item_pai = parent.id
                       JOIN itens child ON ic.id_item_filho = child.id
                       LEFT JOIN estoque es ON child.id = es.id_produto
                       GROUP BY ci.id_item
                       ORDER BY ci.prioridade DESC, ci.data_engenharia DESC, ci.data_prog_fim DESC"""
                cursor.execute(sql)
                self.all_data = cursor.fetchall()
                self.update_status_counts()
                self.active_status_filter = None # Reseta o filtro de status ao recarregar todos os dados
                
                self.populate_client_order_filter()
                
                # Otimização: Cria os 4 widgets de card reutilizáveis uma única vez
                self.create_reusable_cards()
                
                self.filter_data_immediate() # Aplica os filtros
        except Exception as e:
            messagebox.showerror("Erro", f"Erro ao carregar dados: {e}")
        finally:
            if 'connection' in locals() and connection.open:
                connection.close()

    def filter_data_debounced(self, event=None):
        """Debounces the filter data call to avoid excessive updates."""
        if self._after_id:
            self.parent.after_cancel(self._after_id)
        self._after_id = self.parent.after(300, self._perform_filter)

    def filter_data_immediate(self, event=None):
        """Triggers an immediate filter data call."""
        if self._after_id:
            self.parent.after_cancel(self._after_id)
        self._perform_filter()

    def _perform_filter(self, event=None, status_filter_override=None):
        """
        Performs the actual filtering of items based on current UI states.
        
        Args:
            event: The event that triggered the filter (optional).
            status_filter_override: A specific status to filter by (e.g., 'Pendente', 'Iniciado', 'Finalizado').
                                    If provided, it overrides self.active_status_filter for this call.
        """
        search_term = self.search_var.get().lower()
        selected_client_order = self.client_var.get()

        # Determine the active status filter for this operation
        current_active_status_filter = status_filter_override if status_filter_override is not None else self.active_status_filter

        self.filtered_cards.clear()
        for data in self.all_data:
            current_item_status = self.get_status(data)

            matches = True

            # 1. Apply the current active status filter
            if current_active_status_filter and current_item_status != current_active_status_filter:
                matches = False # Item does not match the specific status filter

            # 2. Apply Client/Order filter
            if matches and selected_client_order:
                # Filtra pelo texto combinado "Pedido - Cliente"
                if f"{data.get('pedido', '')} - {data.get('cliente', '')}" != selected_client_order:
                    matches = False # Item does not match the selected client/order
            
            # 3. Apply Search term filter
            if matches and search_term:
                # Check if search_term is present in any relevant field
                if not (
                    search_term in str(data.get('pedido', '')).lower() or
                    search_term in str(data.get('conjunto', '')).lower() or
                    search_term in str(data.get('lote', '')).lower() or
                    search_term in str(data.get('cliente', '')).lower() or
                    search_term in str(data.get('equipamento_pai', '')).lower() or
                    search_term in str(data.get('tag', '')).lower() or # Adicionado TAG
                    search_term in str(data.get('obs_programacao', '')).lower() # Adicionado Observações
                ):
                    matches = False # Search term not found in relevant fields

            if matches:
                self.filtered_cards.append(data)

        self.current_page = 0
        self._update_display()

    def filter_by_status(self, status_filter):
        """
        Filters items by a specific status.
        """
        self.active_status_filter = status_filter # Define o filtro de status ativo
        self._perform_filter(status_filter_override=status_filter)

    def clear_all_filters(self):
        """Limpa todos os filtros e exibe todos os itens."""
        self.search_var.set("")
        self.client_var.set("")
        self.active_status_filter = None # Limpa o filtro de status ativo
        self._perform_filter() # Reaplica o filtro sem nenhum status específico

    def create_reusable_cards(self):
        """Cria os 4 widgets de card que serão reutilizados."""
        for i in range(self.items_per_page):
            card_widget = self.create_card(self.scrollable_frame)
            self.card_widgets.append(card_widget)
            card_widget.grid_forget() # Esconde todos inicialmente

    def _update_display(self):

        # 2. Calcula a paginação
        total_items = len(self.filtered_cards)
        total_pages = (total_items + self.items_per_page - 1) // self.items_per_page
        total_pages = max(total_pages, 1) # Garante pelo menos 1 página

        start_index = self.current_page * self.items_per_page
        end_index = start_index + self.items_per_page
        cards_to_show = self.filtered_cards[start_index:end_index]
        
        # 3. Otimização: Reutiliza os 4 widgets de card
        for i, card_widget in enumerate(self.card_widgets):
            if i < len(cards_to_show):
                # Se houver dados para este card, atualiza e exibe
                item_data = cards_to_show[i]
                card_widget.grid() # Garante que o card esteja visível antes de reorganizar
                self._update_card_content(card_widget, item_data) # A posição será definida por rearrange_cards
            else:
                # Se não houver dados (ex: última página incompleta), esconde o card
                card_widget.grid_forget()

        # 4. Atualiza os controles de paginação
        self.page_label.configure(text=f"Página {self.current_page + 1}/{total_pages}")
        self.prev_button.configure(state=tk.NORMAL if self.current_page > 0 else tk.DISABLED)
        self.next_button.configure(state=tk.NORMAL if (self.current_page + 1) < total_pages else tk.DISABLED)
        # Esconde a paginação se houver apenas uma página
        if total_pages <= 1:
            self.pagination_frame.pack_forget()
        else:
            self.pagination_frame.pack(side=tk.LEFT, padx=10)
        
        # Chama o rearrange para ajustar o layout inicial
        self.rearrange_cards()

    def next_page(self):
        total_items = len(self.filtered_cards)
        total_pages = (total_items + self.items_per_page - 1) // self.items_per_page
        if self.current_page < total_pages - 1:
            self.current_page += 1
            self._update_display()

    def prev_page(self):
        if self.current_page > 0:
            self.current_page -= 1
            self._update_display()

    def create_card(self, parent):
        card_border_frame = ctk.CTkFrame(parent, border_width=1, corner_radius=8)
        
        # Adiciona um frame interno para criar o padding (borda interna)
        card_frame = ctk.CTkFrame(card_border_frame, fg_color="transparent")
        card_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # --- Pedido Section ---
        pedido_frame = ctk.CTkFrame(card_frame, fg_color="transparent")
        pedido_frame.pack(fill=tk.X, pady=(0, 5))
        
        pedido_header_label = ctk.CTkLabel(pedido_frame, text="PEDIDO:", font=("Arial", 10, "bold"))
        pedido_header_label.pack(side=tk.LEFT, anchor='nw')
        
        pedido_info_label = ctk.CTkLabel(pedido_frame, text="", wraplength=220)
        pedido_info_label.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        card_border_frame.pedido_info_label = pedido_info_label

        # --- Equipamento (Item Pai) Section ---
        equip_frame = ctk.CTkFrame(card_frame, fg_color="transparent")
        equip_frame.pack(fill=tk.X, pady=(0, 5))
        
        ctk.CTkLabel(equip_frame, text="EQUIPAMENTO:", font=("Arial", 10, "bold")).pack(side=tk.LEFT, anchor='nw')
        
        equip_info_label = ctk.CTkLabel(equip_frame, text="", wraplength=220)
        equip_info_label.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        card_border_frame.equip_info_label = equip_info_label

        # --- Conjunto Section ---
        conjunto_frame = ctk.CTkFrame(card_frame, fg_color="transparent")
        conjunto_frame.pack(fill=tk.X, pady=(0, 10))
        
        conjunto_header_label = ctk.CTkLabel(conjunto_frame, text="CONJUNTO:", font=("Arial", 10, "bold"))
        conjunto_header_label.pack(side=tk.LEFT, anchor='nw')

        conjunto_info_label = ctk.CTkLabel(conjunto_frame, text="", wraplength=220)
        conjunto_info_label.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        card_border_frame.conjunto_info_label = conjunto_info_label

        # --- Data/Prioridade Section ---
        date_prio_frame = ctk.CTkFrame(card_frame, fg_color="transparent")
        date_prio_frame.pack(fill=tk.X, pady=(0, 10))

        ctk.CTkLabel(date_prio_frame, text="Data Início:").pack(side=tk.LEFT)
        data_inicio_label = ctk.CTkLabel(date_prio_frame, text="", justify=tk.LEFT)
        data_inicio_label.pack(side=tk.LEFT, padx=5)
        card_border_frame.data_inicio_label = data_inicio_label

        prio_entry = ctk.CTkEntry(date_prio_frame, width=50)
        prio_entry.pack(side=tk.LEFT, padx=10)
        card_border_frame.prio_entry = prio_entry

        # --- Details Section (Link, Obs, Lote) ---
        details_frame = ctk.CTkFrame(card_frame, fg_color="transparent")
        details_frame.pack(fill=tk.X, pady=5)
        
        # Link
        link_frame = ctk.CTkFrame(details_frame, fg_color="transparent")
        link_frame.pack(fill=tk.X, pady=2)
        ctk.CTkLabel(link_frame, text="Link da Pasta:").pack(side=tk.LEFT, anchor='w', padx=(0, 10))
        link_entry = ctk.CTkEntry(link_frame)
        link_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        card_border_frame.link_entry = link_entry
        
        
        # Observações
        obs_frame = ctk.CTkFrame(details_frame, fg_color="transparent")
        obs_frame.pack(fill=tk.X, pady=2)
        ctk.CTkLabel(obs_frame, text="Observações:").pack(side=tk.LEFT, anchor='w', padx=(0, 15))
        obs_entry = ctk.CTkEntry(obs_frame)
        obs_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        card_border_frame.obs_entry = obs_entry

        # Lote
        lote_frame = ctk.CTkFrame(details_frame, fg_color="transparent")
        lote_frame.pack(fill=tk.X, pady=2)
        ctk.CTkLabel(lote_frame, text="Lote:").pack(side=tk.LEFT, anchor='w', padx=(0, 55))
        lote_entry = ctk.CTkEntry(lote_frame)
        lote_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        card_border_frame.lote_entry = lote_entry

        # --- Button Section ---
        button_frame = ctk.CTkFrame(card_frame, fg_color="transparent")
        button_frame.pack(fill=tk.X, pady=10)
        card_border_frame.button_frame = button_frame

        # --- Progress Bar ---
        pbar = ctk.CTkProgressBar(card_frame, progress_color='#800080')
        pbar.set(0) # Inicia em 0
        pbar.pack(fill=tk.X, pady=(10, 5), padx=5)
        card_border_frame.pbar = pbar

        return card_border_frame

    def get_status(self, row):
        if row['data_prog_fim']: return 'Finalizado'
        if row['data_programacao']: return 'Iniciado'
        return 'Pendente'

    def update_status_counts(self):
        nao_iniciada_count = sum(1 for row in self.all_data if self.get_status(row) == 'Pendente')
        em_andamento_count = sum(1 for row in self.all_data if self.get_status(row) == 'Iniciado')
        concluidos_count = sum(1 for row in self.all_data if self.get_status(row) == 'Finalizado')
        self.btn_nao_iniciada.configure(text=f"Não Iniciada ({nao_iniciada_count})")
        self.btn_em_andamento.configure(text=f"Em Andamento ({em_andamento_count})")
        self.btn_concluidos.configure(text=f"Concluídos ({concluidos_count})")

    def populate_client_order_filter(self):
        # Cria uma lista única de "Pedido - Cliente"
        self.client_order_list = sorted(list(set(f"{row.get('pedido', '')} - {row.get('cliente', '')}" for row in self.all_data)))
        self.client_var.set("") # Limpa a seleção

    def open_client_selector(self):
        if not hasattr(self, 'client_order_list'):
            messagebox.showwarning("Aviso", "Lista de clientes não carregada.")
            return

        modal = ctk.CTkToplevel(self.frame)
        modal.title("Selecionar Cliente")
        modal.geometry("400x350")
        modal.transient(self.frame)
        modal.grab_set()

        search_var = tk.StringVar()
        ctk.CTkLabel(modal, text="Buscar Cliente:").pack(padx=10, pady=(10,0), anchor='w')
        search_entry = ctk.CTkEntry(modal, textvariable=search_var)
        search_entry.pack(padx=10, fill='x')

        listbox = tk.Listbox(modal, bg="#2b2b2b", fg="white", selectbackground="#1f6aa5")
        listbox.pack(padx=10, pady=10, fill='both', expand=True)
        
        def update_listbox(data):
            listbox.delete(0, "end")
            # Adiciona a opção "Limpar Filtro" no topo, independentemente da busca
            listbox.insert("end", "LIMPAR FILTRO")
            for item in data:
                listbox.insert("end", item)

        def on_search(*args):
            term = search_var.get().lower()
            if term:
                filtered_items = [item for item in self.client_order_list if term in item.lower()]
                update_listbox(filtered_items)
            else:
                update_listbox(self.client_order_list)

        search_entry.bind("<KeyRelease>", on_search)

        # Adiciona a opção "Limpar Filtro"
        update_listbox(self.client_order_list)

        def on_confirm():
            selected = listbox.get(listbox.curselection())
            self.client_var.set("" if selected == "LIMPAR FILTRO" else selected)
            self.filter_data_immediate()
            modal.destroy()

        ctk.CTkButton(modal, text="Confirmar", command=on_confirm).pack(pady=10)

    def copy_link(self, link_var):
        self.parent.clipboard_clear()
        self.parent.clipboard_append(link_var.get())
        messagebox.showinfo("Copiado", "Link copiado para a área de transferência.")

    def save_data(self, id_vinculo, link_entry, obs_entry, lote_entry, prio_entry):
        # Coleta os novos valores dos campos
        new_link = link_entry.get().strip()
        new_obs = obs_entry.get().strip()
        new_lote = lote_entry.get().strip()
        new_prio = prio_entry.get().strip()

        # Encontra os dados atuais do item em memória para comparação
        item_atual = next((item for item in self.all_data if item['id_vinculo'] == id_vinculo), None)
        if not item_atual:
            messagebox.showerror("Erro", "Não foi possível encontrar o item para salvar.")
            return

        # Monta a query de UPDATE apenas com os campos que mudaram
        update_fields = []
        params = []
        
        if new_link != (item_atual.get('link_pastas') or ''):
            update_fields.append("link_pastas = %s")
            params.append(new_link)
        if new_obs != (item_atual.get('obs_programacao') or ''):
            update_fields.append("obs_programacao = %s")
            params.append(new_obs)
        if new_lote != (item_atual.get('lote') or ''):
            update_fields.append("lote = %s")
            params.append(new_lote)
        if new_prio != str(item_atual.get('prioridade') or '99'):
            update_fields.append("prioridade = %s")
            params.append(int(new_prio) if new_prio.isdigit() else 99)

        if not update_fields:
            messagebox.showinfo("Informação", "Nenhuma alteração para salvar.")
            return

        connection = None
        try:
            connection = pymysql.connect(host=DB_HOST, user=DB_USER, password=DB_PASS, database=DB_NAME, charset='utf8mb4', cursorclass=pymysql.cursors.DictCursor)
            with connection.cursor() as cursor:
                # Constrói a query final
                sql = f"UPDATE cliente_item SET {', '.join(update_fields)} WHERE id_item = %s"
                params.append(id_vinculo)
                cursor.execute(sql, params)
            connection.commit()
            
            messagebox.showinfo("Sucesso", "Dados salvos com sucesso!")
            
            # Recarrega todos os dados para garantir que a UI e a memória estejam em sincronia
            self.load_data()

        except Exception as e:
            messagebox.showerror("Erro de Banco de Dados", f"Não foi possível salvar os dados: {e}")
        finally:
            if connection and connection.open:
                connection.close()

    def finalize_item(self, id_vinculo):
        try:
            connection = pymysql.connect(host=DB_HOST, user=DB_USER, password=DB_PASS, database=DB_NAME, charset='utf8mb4', cursorclass=pymysql.cursors.DictCursor)
            with connection.cursor() as cursor:
                now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                sql = "UPDATE cliente_item SET data_prog_fim = %s WHERE id_item = %s"
                cursor.execute(sql, (now, id_vinculo))
            connection.commit()
            messagebox.showinfo("Sucesso", f"Item {id_vinculo} finalizado.")
            
            # Recarrega todos os dados para garantir que a UI e a memória estejam em sincronia
            # Isso também atualiza os contadores de status e reaplica os filtros.
            self.load_data()
        except Exception as e:
            messagebox.showerror("Erro", f"Erro ao finalizar item: {e}")
        finally:
            if 'connection' in locals() and connection.open:
                connection.close()

    def start_item(self, id_vinculo):
        try:
            connection = pymysql.connect(host=DB_HOST, user=DB_USER, password=DB_PASS, database=DB_NAME, charset='utf8mb4', cursorclass=pymysql.cursors.DictCursor)
            with connection.cursor() as cursor:
                now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                sql = "UPDATE cliente_item SET data_programacao = %s WHERE id_item = %s"
                cursor.execute(sql, (now, id_vinculo))
            connection.commit()            
            messagebox.showinfo("Sucesso", f"Item {id_vinculo} iniciado.")

            # Recarrega todos os dados para garantir que a UI e a memória estejam em sincronia
            # Isso também atualiza os contadores de status e reaplica os filtros.
            self.load_data()
        except Exception as e:
            messagebox.showerror("Erro", f"Erro ao iniciar item: {e}")
        finally:
            if 'connection' in locals() and connection.open:
                connection.close()

    def open_sector_selector(self, item_data):
        """Abre uma janela modal para selecionar setores para impressão de etiquetas."""
        modal = ctk.CTkToplevel(self.frame)
        modal.title("Selecionar Setores para Impressão")
        modal.geometry("350x600")
        modal.transient(self.frame)
        modal.grab_set()

        ctk.CTkLabel(modal, text="Selecione os setores:", font=ctk.CTkFont(weight="bold")).pack(pady=10)

        scrollable_frame = ctk.CTkScrollableFrame(modal)
        scrollable_frame.pack(fill="both", expand=True, padx=15, pady=5)

        setores = [
            "PRODUÇÃO", "EXPEDIÇÃO", "SOLDA", "MONTAGEM", "DOBRA", "CALANDRA",
            "LASER", "SERRA", "USINAGEM", "ALMOXARIFADO", "GUILHOTINA",
            "PUNCIONADEIRA", "ZINCAGEM", "PINTURA", "QUALIDADE", "PRENSA HIDRAULICA"
        ]
        
        self.sector_vars = {}
        for setor in sorted(setores):
            var = tk.BooleanVar()
            chk = ctk.CTkCheckBox(scrollable_frame, text=setor, variable=var)
            chk.pack(anchor='w', padx=10, pady=4)
            self.sector_vars[setor] = var

        def on_confirm():
            selected_sectors = [sector for sector, var in self.sector_vars.items() if var.get()]
            if not selected_sectors:
                messagebox.showwarning("Nenhum Setor", "Por favor, selecione pelo menos um setor para imprimir.", parent=modal)
                return
            
            modal.destroy()
            self.print_labels_for_sectors(item_data, selected_sectors)

        btn_frame = ctk.CTkFrame(modal, fg_color="transparent")
        btn_frame.pack(pady=10, fill='x', padx=15)

        ctk.CTkButton(btn_frame, text="Imprimir Selecionados", command=on_confirm).pack(side='left', expand=True, padx=5)
        ctk.CTkButton(btn_frame, text="Cancelar", command=modal.destroy, fg_color="gray").pack(side='right', expand=True, padx=5)

    def print_labels_for_sectors(self, item_data, sectors):
        """Prepara os dados e chama a classe de impressão para os setores selecionados."""
        try:
            # Configuração da etiqueta (pode ser movida para um arquivo de configuração)
            label_config = {
                'largura_mm': 100,
                'altura_mm': 50,
                'margem_esq_mm': 3,
                'margem_sup_mm': 3,
                'fonte_header': 8,
                'fonte_cliente': 9,
                'fonte_conjunto': 10,
                'fonte_quantidade': 11,
                'fonte_equipamento': 12, # Adicionado para compatibilidade com outros métodos de impressão/PDF
                'metodo_impressao': 'bartender', # Define o método de impressão para BarTender
                'bartender_btw_path': 'C:\\Etiquetas\\modelo_setor.btw', # <--- AJUSTE ESTE CAMINHO PARA O SEU ARQUIVO .BTW
                'bartender_exe_path': r'C:\\Program Files\\Seagull\\BarTender 2022\\bartend.exe' # <--- AJUSTE ESTE CAMINHO PARA O SEU EXECUTÁVEL DO BARTENDER 2022
            }

            # Informações gerais do pedido
            pedido_info = {
                'pedido': item_data.get('pedido', 'N/A'),
                'numero_pedido': item_data.get('pedido', 'N/A'), # Mantém compatibilidade
                'cliente': item_data.get('cliente', 'N/A'), # Cliente
                'endereco': item_data.get('endereco', '') # Endereço
            }

            # Prepara a lista de "itens" para imprimir, um para cada setor
            itens_para_imprimir = []
            for sector in sectors:
                # Cria uma cópia dos dados do item e adiciona/sobrescreve o campo 'setor'
                # Isso garante que todos os dados originais (como nome_equipamento, etc.)
                # sejam preservados e o setor específico seja adicionado para cada etiqueta.
                item_com_setor = item_data.copy()
                item_com_setor['setor'] = sector
                # Garante que 'nome_equipamento' exista para compatibilidade com outros métodos de impressão
                item_com_setor['nome_equipamento'] = item_com_setor.get('equipamento_pai', 'N/A')
                itens_para_imprimir.append(item_com_setor)

            # Instancia e chama a impressora
            printer = EtiquetaPrinter(label_config, self.parent.winfo_toplevel())
            
            # TODO: Obter o nome da impressora de uma configuração ou caixa de diálogo.
            # Se None, o BarTender usará a impressora padrão do Windows.
            printer_name = None # Deixar como None para usar a impressora padrão do BarTender ou especificar uma aqui
            # Chama o método genérico de impressão, que agora usará o BarTender
            printer.gerar_pdf_e_imprimir(pedido_info, itens_para_imprimir, printer_name=printer_name, print_direct=True)
        except Exception as e:
            messagebox.showerror("Erro de Impressão", f"Não foi possível gerar as etiquetas: {e}")

    def _update_card_content(self, card_border_frame, item_data):
        """Preenche um widget de card reutilizável com novos dados."""
        
        # --- Atualiza textos ---
        pedido_info_text = f" {item_data.get('pedido', '')} - {item_data.get('cliente', '')} - {item_data.get('endereco', '')}"[:100]
        card_border_frame.pedido_info_label.configure(text=pedido_info_text)

        codigo_equip = item_data.get('codigo_equipamento', '')
        nome_equip = item_data.get('equipamento_pai', '')
        equip_info_text = (f" {codigo_equip} - {nome_equip}" if codigo_equip else f" {nome_equip}")[:100]
        card_border_frame.equip_info_label.configure(text=equip_info_text)

        codigo_conjunto = item_data.get('codigo_conjunto', '')
        nome_conjunto = item_data.get('conjunto', '')
        conjunto_info_text = (f" {codigo_conjunto} - {nome_conjunto} ({item_data.get('quantidade_prod', 0)} CJ)" if codigo_conjunto else f" {nome_conjunto} ({item_data.get('quantidade_prod', 0)} CJ)")[:100]
        card_border_frame.conjunto_info_label.configure(text=conjunto_info_text)

        data_display_str = "N/A"
        data_fim = item_data.get('data_prog_fim')
        # Verifica se a data_fim existe e não é uma data "zerada" (ano > 1)
        if data_fim and hasattr(data_fim, 'year') and data_fim.year > 1:
            # Se finalizado, mostra a data e hora de finalização
            try:
                dt_obj = datetime.strptime(str(item_data['data_prog_fim']), '%Y-%m-%d %H:%M:%S')
                data_display_str = f"{dt_obj.strftime('%d/%m/%Y')}\n{dt_obj.strftime('%H:%M')}"
            except (ValueError, TypeError):
                data_display_str = str(item_data['data_prog_fim'])
        elif item_data.get('data_programacao'):
            # Se iniciado mas não finalizado, mostra o status
            data_display_str = "Em Programação"
        card_border_frame.data_inicio_label.configure(text=data_display_str)

        card_border_frame.prio_entry.delete(0, 'end')
        card_border_frame.prio_entry.insert(0, str(item_data.get('prioridade', '99')))

        card_border_frame.obs_entry.delete(0, 'end')
        card_border_frame.obs_entry.insert(0, str(item_data.get('obs_programacao', '')))

        card_border_frame.link_entry.delete(0, 'end')
        card_border_frame.link_entry.insert(0, str(item_data.get('link_pastas', '')))

        card_border_frame.lote_entry.delete(0, 'end')
        card_border_frame.lote_entry.insert(0, str(item_data.get('lote', '')))

        # --- Atualiza barra de progresso (exemplo) ---
        progress = 0
        if item_data.get('data_prog_fim'): progress = 1.0
        elif item_data.get('data_programacao'): progress = 0.5
        card_border_frame.pbar.set(progress)

        # --- Reconstrói a seção de botões dinâmicos ---
        button_frame = card_border_frame.button_frame
        for widget in button_frame.winfo_children():
            widget.destroy()

        top_button_frame = ctk.CTkFrame(button_frame, fg_color="transparent")
        top_button_frame.pack(fill=tk.X, pady=2)
        
        # Passa os widgets de entrada para a função de salvar
        save_command = lambda id_v=item_data['id_vinculo'], le=card_border_frame.link_entry, oe=card_border_frame.obs_entry, lote_e=card_border_frame.lote_entry, pe=card_border_frame.prio_entry: \
            self.save_data(id_v, le, oe, lote_e, pe)
        
        ctk.CTkButton(top_button_frame, text="Salvar Dados", command=save_command).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 2))

        
        # Botão de Iniciar/Finalizar
        if item_data.get('data_prog_fim'):
            # Se finalizado, mostra um label
            ctk.CTkLabel(button_frame, text="Item Finalizado", text_color="green", font=ctk.CTkFont(weight="bold")).pack(fill=tk.X, pady=2)
        else:
            # Se não finalizado, mostra botão de Iniciar ou Finalizar
            if item_data.get('data_programacao'):
                ctk.CTkButton(button_frame, text="Finalizar", fg_color='#FF5722', command=lambda id_v=item_data['id_vinculo']: self.finalize_item(id_v)).pack(fill=tk.X, pady=2)
            else:
                ctk.CTkButton(button_frame, text="Iniciar", command=lambda id_v=item_data['id_vinculo']: self.start_item(id_v)).pack(fill=tk.X, pady=2)
        
        # Botões estáticos
        # O comando agora passa os dados completos do item para a função de seleção de setor
        ctk.CTkButton(button_frame, text="Etiquetas", command=lambda data=item_data: self.open_sector_selector(data)).pack(fill=tk.X, pady=2)
        ctk.CTkButton(button_frame, text="Reservar Materiais").pack(fill=tk.X, pady=2)
