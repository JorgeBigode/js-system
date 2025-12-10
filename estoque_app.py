import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
import pymysql
from config import DB_HOST, DB_USER, DB_PASS, DB_NAME
from datetime import datetime
from select2_tkinter import Select2Tkinter

class EstoqueApp:
    def __init__(self, parent, user):
        self.parent = parent
        self.user = user
        self.main_frame = ttk.Frame(self.parent, padding="10")
        self.main_frame.pack(fill=tk.BOTH, expand=True)

        self.all_itens_data = [] # Para popular o combobox de adição
        self.stock_data = [] # Para a lista principal

        self.create_widgets()
        self.load_all_itens() # Carrega itens para o modal
        self.load_stock_data() # Carrega o estoque para a tabela

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
                    return cursor.lastrowid if "INSERT" in query.upper() else True
        except pymysql.Error as e:
            messagebox.showerror("Erro de Banco de Dados", f"Erro: {e}")
            if conn: conn.rollback()
            return None
        finally:
            if conn: conn.close()

    def create_widgets(self):
        # --- Frame de Filtros e Ações ---
        top_frame = ttk.LabelFrame(self.main_frame, text="Ações e Filtros", padding=10)
        top_frame.pack(fill=tk.X, pady=(0, 10))

        ttk.Button(top_frame, text="Adicionar Produto ao Estoque", command=self.open_add_modal).pack(side=tk.LEFT, padx=(0, 20))

        ttk.Label(top_frame, text="Buscar por Código/Descrição:").pack(side=tk.LEFT, padx=5)
        self.search_var = tk.StringVar()
        search_entry = ttk.Entry(top_frame, textvariable=self.search_var, width=40)
        search_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        search_entry.bind("<KeyRelease>", lambda e: self.load_stock_data())

        ttk.Button(top_frame, text="Limpar Busca", command=self.clear_search).pack(side=tk.LEFT, padx=5)

        # --- Tabela de Estoque ---
        list_frame = ttk.LabelFrame(self.main_frame, text="Produtos em Estoque", padding=10)
        list_frame.pack(fill=tk.BOTH, expand=True)

        columns = ('id', 'codigo', 'descricao', 'quantidade', 'localizacao', 'atualizacao')
        self.tree = ttk.Treeview(list_frame, columns=columns, show='headings')

        headings = {
            'id': 'ID', 'codigo': 'Código', 'descricao': 'Descrição (Conjunto)',
            'quantidade': 'Qtd.', 'localizacao': 'Localização', 'atualizacao': 'Última Atualização'
        }
        widths = {
            'id': 50, 'codigo': 100, 'descricao': 350,
            'quantidade': 80, 'localizacao': 150, 'atualizacao': 150
        }

        for col, text in headings.items():
            self.tree.heading(col, text=text, anchor='w')
            self.tree.column(col, width=widths[col], anchor='w')

        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar = ttk.Scrollbar(list_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.tree.bind("<Double-1>", self.open_update_modal)

        # Configurar tags de cor
        self.tree.tag_configure('estoque-baixo', background='#ffe6e6')
        self.tree.tag_configure('estoque-medio', background='#fff9e6')
        self.tree.tag_configure('estoque-alto', background='#e6ffe6')

    def load_all_itens(self):
        """Carrega todos os itens para o modal de adição."""
        self.all_itens_data = self._execute_query("SELECT id, codigo, descricao FROM itens ORDER BY descricao ASC", fetch='all') or []

    def load_stock_data(self):
        """Carrega os dados do estoque do banco de dados, aplicando o filtro de busca."""
        search_term = self.search_var.get().strip()
        
        if search_term:
            sql = """
                SELECT i.id, i.codigo, i.descricao, e.quantidade, e.localizacao, e.data_atualizacao 
                FROM itens i
                LEFT JOIN estoque e ON i.id = e.id_produto
                WHERE i.descricao LIKE %s OR i.codigo LIKE %s
                ORDER BY i.descricao ASC
            """
            params = (f"%{search_term}%", f"%{search_term}%")
        else:
            sql = """
                SELECT i.id, i.codigo, i.descricao, e.quantidade, e.localizacao, e.data_atualizacao 
                FROM itens i
                INNER JOIN estoque e ON i.id = e.id_produto
                WHERE e.quantidade > 0
                ORDER BY i.descricao ASC
            """
            params = None

        self.stock_data = self._execute_query(sql, params, fetch='all') or []
        self.populate_treeview()

    def populate_treeview(self):
        """Preenche a Treeview com os dados do estoque."""
        for i in self.tree.get_children():
            self.tree.delete(i)

        for item in self.stock_data:
            quantidade = int(item.get('quantidade') or 0)
            
            tag = ''
            if quantidade <= 5: tag = 'estoque-baixo'
            elif quantidade <= 20: tag = 'estoque-medio'
            else: tag = 'estoque-alto'

            data_att = item.get('data_atualizacao')
            data_formatada = data_att.strftime('%d/%m/%Y %H:%M') if data_att else 'Nunca'

            values = (
                item['id'],
                item.get('codigo', ''),
                item.get('descricao', ''),
                quantidade,
                item.get('localizacao', 'Não definida'),
                data_formatada
            )
            self.tree.insert('', 'end', values=values, tags=(tag,))

    def clear_search(self):
        self.search_var.set("")
        self.load_stock_data()

    def open_add_modal(self):
        """Abre o modal para adicionar um novo produto ao estoque."""
        self.show_edit_modal(title="Adicionar Produto ao Estoque", item_data=None)

    def open_update_modal(self, event=None):
        """Abre o modal para atualizar um produto existente no estoque."""
        selected_iid = self.tree.focus()
        if not selected_iid:
            return
        
        item_values = self.tree.item(selected_iid, 'values')
        item_id = item_values[0]

        # Busca o item completo para passar ao modal
        item_data = next((item for item in self.stock_data if str(item['id']) == str(item_id)), None)
        if item_data:
            self.show_edit_modal(title=f"Atualizar Estoque - {item_data['descricao']}", item_data=item_data)

    def show_edit_modal(self, title, item_data):
        """Função genérica para mostrar o modal de adição/edição."""
        modal = tk.Toplevel(self.main_frame)
        modal.title(title)
        modal.transient(self.main_frame)
        modal.grab_set()
        modal.geometry("450x300")

        frame = ttk.Frame(modal, padding=20)
        frame.pack(fill=tk.BOTH, expand=True)

        # Configura o grid para que a coluna 1 (dos campos de entrada) se expanda
        frame.columnconfigure(1, weight=1)


        # --- Campos do Modal ---
        # Campo de Produto (Select2 para adicionar, Label para editar)
        ttk.Label(frame, text="Produto:").grid(row=0, column=0, sticky='w', pady=5)
        item_id_var = tk.StringVar()

        if item_data: # Modo Edição
            item_id_var.set(item_data['id'])
            ttk.Label(frame, text=f"({item_data['codigo']}) {item_data['descricao']}", font=('Arial', 10, 'bold'), wraplength=250).grid(row=0, column=1, sticky='ew', pady=5)
        else: # Modo Adição
            select_values = [(item['id'], f"({item['codigo']}) {item['descricao']}") for item in self.all_itens_data]
            select_produto = Select2Tkinter(frame, select_mode="single", list_of_values=select_values, width=250)
            select_produto.grid(row=0, column=1, sticky='ew', pady=5)

        # Campo Quantidade
        ttk.Label(frame, text="Quantidade:").grid(row=1, column=0, sticky='w', pady=5)
        quant_var = tk.StringVar(value=item_data.get('quantidade', '0') if item_data else '0')
        quant_entry = ttk.Entry(frame, textvariable=quant_var)
        quant_entry.grid(row=1, column=1, sticky='ew', pady=5)

        # Campo Localização
        ttk.Label(frame, text="Localização:").grid(row=2, column=0, sticky='w', pady=5)
        loc_var = tk.StringVar(value=item_data.get('localizacao', '') if item_data else '')
        loc_entry = ttk.Entry(frame, textvariable=loc_var)
        loc_entry.grid(row=2, column=1, sticky='ew', pady=5)

        def on_save():
            try:
                quantidade = int(quant_var.get())
                localizacao = loc_var.get().strip()
                
                if item_data: # Edição
                    item_id = item_data['id']
                else: # Adição
                    selected = select_produto.get_value()
                    if not selected:
                        messagebox.showerror("Erro", "Selecione um produto.", parent=modal)
                        return
                    item_id = selected[0]

                if quantidade < 0:
                    messagebox.showerror("Erro", "A quantidade não pode ser negativa.", parent=modal)
                    return

                self.save_stock_update(item_id, quantidade, localizacao, modal)

            except ValueError:
                messagebox.showerror("Erro de Formato", "A quantidade deve ser um número inteiro.", parent=modal)
            except Exception as e:
                messagebox.showerror("Erro", f"Ocorreu um erro: {e}", parent=modal)

        # --- Botões do Modal ---
        btn_frame = ttk.Frame(frame)
        btn_frame.grid(row=3, column=0, columnspan=2, pady=20)
        ttk.Button(btn_frame, text="Salvar", command=on_save).pack(side=tk.LEFT, padx=5)

        # Adiciona o botão de excluir apenas no modo de edição
        if item_data:
            def on_delete():
                self.delete_stock_item(item_data['id'], modal)

            ttk.Button(btn_frame, text="Excluir", command=on_delete).pack(side=tk.LEFT, padx=5)

        ttk.Button(btn_frame, text="Cancelar", command=modal.destroy).pack(side=tk.LEFT, padx=5)

        quant_entry.focus_set()
        quant_entry.selection_range(0, 'end')

    def save_stock_update(self, item_id, quantidade, localizacao, modal_window):
        """Verifica se o item já está no estoque e decide entre INSERT e UPDATE."""
        
        # Verificar se já existe registro para este produto
        check_sql = "SELECT id FROM estoque WHERE id_produto = %s"
        existing_record = self._execute_query(check_sql, (item_id,), fetch='one')

        if existing_record:
            # Atualizar registro existente
            sql = "UPDATE estoque SET quantidade = %s, localizacao = %s, data_atualizacao = NOW() WHERE id_produto = %s"
            params = (quantidade, localizacao, item_id)
        else:
            # Inserir novo registro
            sql = "INSERT INTO estoque (id_produto, quantidade, localizacao, data_atualizacao) VALUES (%s, %s, %s, NOW())"
            params = (item_id, quantidade, localizacao)

        if self._execute_query(sql, params) is not None:
            messagebox.showinfo("Sucesso", "Estoque atualizado com sucesso!", parent=modal_window)
            modal_window.destroy()
            self.load_stock_data() # Recarrega a lista principal
        else:
            messagebox.showerror("Erro", "Falha ao atualizar o estoque.", parent=modal_window)

    def delete_stock_item(self, item_id, modal_window):
        """Exclui um item do estoque."""
        if not messagebox.askyesno("Confirmar Exclusão", "Tem certeza que deseja excluir este item do estoque? Esta ação não pode ser desfeita.", parent=modal_window):
            return

        sql = "DELETE FROM estoque WHERE id_produto = %s"
        if self._execute_query(sql, (item_id,)):
            messagebox.showinfo("Sucesso", "Item removido do estoque com sucesso!", parent=modal_window)
            modal_window.destroy()
            self.load_stock_data()
        else:
            messagebox.showerror("Erro", "Falha ao remover o item do estoque.", parent=modal_window)