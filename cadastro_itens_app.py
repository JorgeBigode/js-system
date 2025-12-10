import tkinter as tk
from tkinter import ttk, messagebox, font
import customtkinter as ctk
import pymysql
from config import DB_HOST, DB_USER, DB_PASS, DB_NAME
from select2_tkinter import Select2Tkinter

class CadastroItensApp:
    def __init__(self, parent, user):
        self.parent = parent
        self.user = user
        self.main_frame = ctk.CTkFrame(self.parent, fg_color="transparent")
        self.main_frame.pack(fill=tk.BOTH, expand=True)

        self.itens_data = []
        self.select_values = []
        self.child_selectors = []
        self.create_widgets()
        self.full_text_map = {} # Dicionário para guardar o texto completo dos itens da árvore
        self.load_all_data()

    def get_db_connection(self):
        """Retorna uma conexão com o banco de dados."""
        return pymysql.connect(
            host=DB_HOST, user=DB_USER, password=DB_PASS,
            database=DB_NAME, charset='utf8mb4',
            cursorclass=pymysql.cursors.DictCursor
        )

    def create_widgets(self):
        """Cria os widgets da interface gráfica."""
        # Frame principal que conterá todos os widgets
        main_container = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        main_container.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # --- Widgets do Formulário (Topo) ---
        
        # 1. Lista de Itens
        ctk.CTkLabel(main_container, text="Itens Cadastrados", font=ctk.CTkFont(weight="bold")).pack(anchor="w")
        items_list_frame = ctk.CTkFrame(main_container)
        items_list_frame.pack(fill=tk.X, expand=False, pady=(5, 10))

        search_item_frame = ctk.CTkFrame(items_list_frame, fg_color="transparent")
        search_item_frame.pack(fill=tk.X, pady=5)
        ctk.CTkLabel(search_item_frame, text="Buscar Item:").pack(side=tk.LEFT)
        self.search_item_entry = ctk.CTkEntry(search_item_frame)
        self.search_item_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        self.search_item_entry.bind("<KeyRelease>", self.filter_items_list)

        self.items_listbox = tk.Listbox(items_list_frame, height=6, bg="#2b2b2b", fg="white", selectbackground="#00529B", highlightthickness=0, borderwidth=0)
        self.items_listbox.pack(fill=tk.BOTH, expand=True)
        
        ctk.CTkButton(main_container, text="Adicionar Novo Item", command=self.open_add_item_modal).pack(fill=tk.X, pady=5)

        # 2. Formulário de Vínculo
        ctk.CTkLabel(main_container, text="Criar Vínculo Hierárquico", font=ctk.CTkFont(weight="bold")).pack(anchor="w", pady=(10,0))
        link_frame = ctk.CTkFrame(main_container)
        link_frame.pack(fill=tk.X, pady=(5,0))
        self.link_frame = link_frame # Salva a referência para recriar os widgets

        # Frame para o seletor do Pai
        self.parent_selector_frame = ctk.CTkFrame(link_frame, fg_color="transparent")
        self.parent_selector_frame.pack(fill=tk.X, pady=5)

        # Frame para os seletores de filhos dinâmicos
        self.child_selectors_frame = ctk.CTkFrame(link_frame, fg_color="transparent")
        self.child_selectors_frame.pack(fill=tk.X, pady=5)

        # Botões de ação
        action_frame = ctk.CTkFrame(main_container, fg_color="transparent")
        action_frame.pack(fill=tk.X, pady=(0, 5))
        ctk.CTkButton(action_frame, text="Ver Vínculos do Pai", command=self.show_parent_links).pack(side=tk.LEFT, padx=(0, 5), expand=True, fill=tk.X)
        ctk.CTkButton(action_frame, text="Criar Vínculo", command=self.create_link).pack(side=tk.LEFT, padx=(5, 0), expand=True, fill=tk.X)

        # --- Visualização da Hierarquia (Abaixo do formulário) ---
        ctk.CTkLabel(main_container, text="Visualizar Vínculos (Estrutura Hierárquica)", font=ctk.CTkFont(weight="bold")).pack(anchor="w", pady=(15, 0))
        hierarchy_frame = ctk.CTkFrame(main_container)
        hierarchy_frame.pack(fill=tk.BOTH, expand=True, pady=5)

        search_tree_frame = ctk.CTkFrame(hierarchy_frame, fg_color="transparent")
        search_tree_frame.pack(fill=tk.X, pady=5)
        ctk.CTkLabel(search_tree_frame, text="Buscar na Estrutura:").pack(side=tk.LEFT)
        self.search_tree_entry = ctk.CTkEntry(search_tree_frame)
        self.search_tree_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        self.search_tree_entry.bind("<KeyRelease>", self.filter_hierarchy_tree)

        self.tree = ttk.Treeview(hierarchy_frame, columns=("quantidade"), show="tree headings")
        self.tree.heading("#0", text="Item")
        self.tree.heading("quantidade", text="Quantidade")
        self.tree.column("quantidade", width=100, anchor='center', stretch=False)
        self.tree.column("#0", stretch=True)
        
        # Estilo da Treeview para combinar com o tema
        style = ttk.Style()
        style.theme_use("default")
        style.configure("Treeview", background="#2b2b2b", foreground="white", fieldbackground="#2b2b2b", borderwidth=0)
        style.configure("Treeview.Heading", background="#171717", foreground="white", relief="flat", font=('Arial', 10, 'bold'))
        style.map("Treeview.Heading", background=[('active', '#333333')])
        style.map("Treeview", background=[('selected', '#00529B')])

        tree_scrollbar = ctk.CTkScrollbar(hierarchy_frame, command=self.tree.yview)
        self.tree.configure(yscrollcommand=tree_scrollbar.set)
        
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        tree_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.tree_menu = tk.Menu(self.tree, tearoff=0)
        self.tree.bind("<Button-3>", self.popup_tree_menu) # Liga o clique direito

        # Liga o evento de redimensionamento para atualizar os textos
        self.main_frame.bind("<Configure>", self.on_tree_configure)

    def popup_tree_menu(self, event):
        """Mostra o menu de contexto no clique direito do mouse."""
        try:
            # Pega o item que foi clicado
            selected_item_iid = self.tree.identify_row(event.y)
            if not selected_item_iid:
                return

            self.tree.selection_set(selected_item_iid)
            self.tree_menu.delete(0, tk.END) # Limpa o menu

            # Verifica se o item clicado é um PAI (IID = ID do item, ex: '10') ou FILHO (IID = '10-20')
            is_parent = '-' not in selected_item_iid
            
            if is_parent:
                self.tree_menu.add_command(
                    label="❌ Excluir Vínculos do Item Pai", 
                    command=lambda: self.delete_parent_link(selected_item_iid)
                )
            else:
                self.tree_menu.add_command(
                    label="✏️ Editar Vínculo do Item Filho", 
                    command=lambda: self.open_edit_child_modal(selected_item_iid)
                )
                self.tree_menu.add_command(
                    label="🗑️ Excluir Vínculo do Item Filho", 
                    command=lambda: self.delete_child_link(selected_item_iid)
                )

            # Exibe o menu na posição do clique
            self.tree_menu.tk_popup(event.x_root, event.y_root)
        finally:
            self.tree_menu.grab_release()

    def load_all_data(self):
        """Carrega todos os dados iniciais do banco de dados."""
        self.load_items()
        self.load_hierarchy()

    def load_items(self):
        """Carrega os itens do banco e atualiza a Listbox e os Select2."""
        try:
            conn = self.get_db_connection()
            with conn.cursor() as cursor:
                cursor.execute("SELECT id, codigo, descricao FROM itens ORDER BY descricao ASC")
                self.itens_data = cursor.fetchall()
        except Exception as e:
            messagebox.showerror("Erro de Banco de Dados", f"Não foi possível carregar os itens: {e}")
            self.itens_data = []
        finally:
            if conn:
                conn.close()

        # Atualiza a Listbox
        self.items_listbox.delete(0, tk.END)
        for item in self.itens_data:
            self.items_listbox.insert(tk.END, f"({item['codigo']}) {item['descricao']}")

        # Atualiza os dropdowns Select2
        select_values = [(item['id'], f"({item['codigo']}) {item['descricao']}") for item in self.itens_data]
        self.select_values = select_values # Armazena para uso posterior
        self._create_or_update_parent_select(self.select_values)
        self._reset_child_selectors()

    def _create_or_update_parent_select(self, values):
        """Cria ou atualiza o seletor de Item Pai."""
        if hasattr(self, 'parent_select_label'):
            self.parent_select_label.destroy()
            self.parent_select.destroy()

        self.parent_select_label = ctk.CTkLabel(self.parent_selector_frame, text="Item Pai:")
        self.parent_select_label.pack(fill=tk.X)
        self.parent_select = Select2Tkinter(self.parent_selector_frame, width=350, list_of_values=values)
        self.parent_select.pack(fill=tk.X)

    def _reset_child_selectors(self):
        """Limpa e reinicia os seletores de Item Filho."""
        for widget in self.child_selectors_frame.winfo_children():
            widget.destroy()
        self.child_selectors = []
        self._add_child_selector()

    def _add_child_selector(self):
        """Adiciona um novo campo de seleção para Item Filho."""
        # Remove o botão '+' do seletor anterior, se existir
        if self.child_selectors:
            last_selector_info = self.child_selectors[-1]
            if 'add_button' in last_selector_info and last_selector_info['add_button'].winfo_exists():
                last_selector_info['add_button'].destroy()

        row_frame = ctk.CTkFrame(self.child_selectors_frame, fg_color="transparent")
        row_frame.pack(fill=tk.X, pady=2)

        label = ctk.CTkLabel(row_frame, text=f"Filho {len(self.child_selectors) + 1}:")
        label.pack(side=tk.LEFT, padx=(0, 5))

        # Botão de adicionar '+' vai para a direita primeiro
        add_button = ctk.CTkButton(row_frame, text="+", width=28, command=self._add_child_selector)
        add_button.pack(side=tk.RIGHT, padx=(2, 0))

        # Botão de remover '-' fica à esquerda do '+'
        remove_button = ctk.CTkButton(row_frame, text="-", width=28)
        remove_button.pack(side=tk.RIGHT)

        # Entry para quantidade (substituindo Spinbox)
        quantity_entry = ctk.CTkEntry(row_frame, width=50)
        quantity_entry.insert(0, "1")
        quantity_entry.pack(side=tk.RIGHT, padx=(2, 2))
        ctk.CTkLabel(row_frame, text="Qtd:").pack(side=tk.RIGHT)

        # O seletor de filho preenche o espaço restante
        child_select = Select2Tkinter(row_frame, list_of_values=self.select_values)
        child_select.pack(side=tk.LEFT, fill=tk.X, expand=True)

        remove_button['command'] = lambda rf=row_frame, cs=child_select: self._remove_child_selector(rf, cs)

        if len(self.child_selectors) == 0:
            remove_button.configure(state=tk.DISABLED) # Desabilita o '-' na primeira linha

        self.child_selectors.append({
            'frame': row_frame, 'selector': child_select, 
            'add_button': add_button, 'quantity_entry': quantity_entry
        })

    def _remove_child_selector(self, frame_to_remove, selector_to_remove):
        """Remove uma linha de seleção de Item Filho."""
        if len(self.child_selectors) <= 1:
            return

        frame_to_remove.destroy()
        self.child_selectors = [s for s in self.child_selectors if s['selector'] != selector_to_remove]

    def load_hierarchy(self):
        """Carrega e constrói a árvore de hierarquia."""
        for i in self.tree.get_children():
            self.tree.delete(i)
        
        try:
            conn = self.get_db_connection()
            with conn.cursor() as cursor:
                sql = """
                    SELECT 
                        ic.id_item_pai, 
                        p.codigo AS pai_codigo,
                        p.descricao AS pai_desc, 
                        ic.id_item_filho, 
                        f.codigo AS filho_codigo,
                        f.descricao AS filho_desc,
                        ic.quantidade
                    FROM item_composicao ic
                    JOIN itens p ON ic.id_item_pai = p.id
                    JOIN itens f ON ic.id_item_filho = f.id
                    ORDER BY p.descricao, f.descricao
                """
                cursor.execute(sql)
                self.hierarchy_data = cursor.fetchall()
        except Exception as e:
            messagebox.showerror("Erro de Banco de Dados", f"Não foi possível carregar a hierarquia: {e}")
            self.hierarchy_data = []
        finally:
            if conn:
                conn.close()

        # Constrói a árvore
        self.full_text_map.clear() # Limpa o mapa de textos
        nodes = {}
        for link in self.hierarchy_data:
            id_pai = str(link['id_item_pai'])
            id_filho = str(link['id_item_filho'])

            if id_pai not in nodes:
                parent_text = f"({link['pai_codigo']}) {link['pai_desc']}"
                self.full_text_map[id_pai] = parent_text # Guarda o texto completo
                nodes[id_pai] = self.tree.insert("", "end", iid=id_pai, text=parent_text) # Insere o texto completo
            
            # Insere o filho sob o pai
            child_iid = f"{id_pai}-{id_filho}"
            if not self.tree.exists(child_iid): # Garante que o item filho não seja inserido duas vezes
                child_text = f"({link['filho_codigo']}) {link['filho_desc']}"
                self.full_text_map[child_iid] = child_text # Guarda o texto completo
                self.tree.insert(nodes[id_pai], "end", iid=child_iid, text=child_text, values=(f"x{link['quantidade']}",))
        
        self.main_frame.after(100, self.update_all_tree_text) # Atualiza o texto após um pequeno delay

    def _truncate_text(self, text, max_width, font_obj, margin=20):
        """Trunca o texto com '...' se exceder a largura máxima e substitui espaços para evitar quebra de linha."""
        if not isinstance(text, str):
            return text

        text_width = font_obj.measure(text)
        
        # Se o texto não couber, trunca
        if text_width > max_width - margin:
            temp_text = text
            # Reduz o texto até que ele (com '...') caiba na largura
            while font_obj.measure(temp_text + '...') > max_width - margin and len(temp_text) > 0:
                temp_text = temp_text[:-1]
            final_text = temp_text + '...'
        else:
            final_text = text
        
        # Substitui espaços por 'non-breaking spaces' para forçar uma única linha no Treeview
        return final_text.replace(' ', '\u00A0')
    
    def on_tree_configure(self, event=None):
        """Chamado quando a árvore é redimensionada. Atualiza os textos."""
        # Usamos 'after' para garantir que o redimensionamento da janela já tenha sido processado
        # antes de tentarmos calcular as novas larguras.
        self.main_frame.after(50, self._resize_and_update_text)

    def _resize_and_update_text(self):
        """Calcula a largura das colunas e atualiza o texto."""
        if not self.tree.winfo_exists():
            return
        
        total_width = self.tree.winfo_width()
        qty_width = 100
        self.tree.column("quantidade", width=qty_width, stretch=False)
        main_col_width = total_width - qty_width - 5
        self.tree.column("#0", width=main_col_width)
        self.update_all_tree_text()

    def update_all_tree_text(self):
        """Percorre todos os itens da árvore e atualiza o texto truncado com base na largura atual da coluna."""
        if not self.tree.winfo_exists():
            return
            
        col_width = self.tree.column('#0', 'width')
        default_font = font.nametofont("TkDefaultFont")

        for iid in self.full_text_map:
            if self.tree.exists(iid):
                full_text = self.full_text_map[iid]
                # A margem aqui é importante para compensar ícones e padding interno da Treeview
                truncated_text = self._truncate_text(full_text, col_width, default_font, margin=35)
                self.tree.item(iid, text=truncated_text)

    def filter_items_list(self, event=None):
        """Filtra a lista de itens com base na busca."""
        search_term = self.search_item_entry.get().lower()
        self.items_listbox.delete(0, tk.END)
        for item in self.itens_data:
            if search_term in item['descricao'].lower() or search_term in item['codigo'].lower():
                self.items_listbox.insert(tk.END, f"({item['codigo']}) {item['descricao']}")

    def filter_hierarchy_tree(self, event=None):
        """Filtra a visualização da árvore de hierarquia."""
        search_term = self.search_tree_entry.get().lower()
        
        for parent_id in self.tree.get_children():
            # Torna todos visíveis primeiro para reavaliar
            self.tree.item(parent_id, open=False)
            self.tree.reattach(parent_id, '', 'end')

            parent_text = self.tree.item(parent_id, "text").lower()
            parent_match = search_term in parent_text
            child_matches = False

            for child_id in self.tree.get_children(parent_id):
                child_text = self.tree.item(child_id, "text").lower()
                if search_term in child_text:
                    child_matches = True
                    break
            
            if search_term == "":
                self.tree.item(parent_id, open=False)
            elif parent_match or child_matches:
                self.tree.item(parent_id, open=True)
            else:
                self.tree.detach(parent_id)

    def open_add_item_modal(self):
        """Abre uma janela modal para adicionar um novo item."""
        modal = ctk.CTkToplevel(self.main_frame)
        modal.title("Adicionar Novo Item")
        modal.transient(self.parent)
        modal.grab_set()
        
        frame = ctk.CTkFrame(modal)
        frame.pack(expand=True, fill=tk.BOTH)

        ctk.CTkLabel(frame, text="Código:").grid(row=0, column=0, sticky="w", pady=5, padx=10)
        code_entry = ctk.CTkEntry(frame, width=300)
        code_entry.grid(row=0, column=1, sticky="ew", pady=5, padx=10)

        ctk.CTkLabel(frame, text="Descrição (obrigatório):").grid(row=1, column=0, sticky="w", pady=5, padx=10)
        desc_entry = ctk.CTkEntry(frame, width=300)
        desc_entry.grid(row=1, column=1, sticky="ew", pady=5, padx=10)
        
        button_frame = ctk.CTkFrame(frame, fg_color="transparent")
        button_frame.grid(row=2, columnspan=2, pady=20)
        
        def save_item():
            codigo = code_entry.get().strip()
            descricao = desc_entry.get().strip()
            if not descricao:
                messagebox.showwarning("Campo Obrigatório", "A descrição do item é obrigatória.", parent=modal)
                return

            try:
                conn = self.get_db_connection()
                with conn.cursor() as cursor:
                    cursor.execute("INSERT INTO itens (codigo, descricao) VALUES (%s, %s)", (codigo, descricao))
                conn.commit()
                messagebox.showinfo("Sucesso", "Item adicionado com sucesso!", parent=modal)
                modal.destroy()
                self.load_items() # Recarrega a lista de itens
            except Exception as e:
                messagebox.showerror("Erro de Banco de Dados", f"Falha ao salvar o item: {e}", parent=modal)
            finally:
                if conn:
                    conn.close()
        
        ctk.CTkButton(button_frame, text="Salvar", command=save_item).pack(side=tk.LEFT, padx=10)
        ctk.CTkButton(button_frame, text="Cancelar", command=modal.destroy).pack(side=tk.LEFT, padx=10)
        
        modal.update_idletasks()
        x = self.parent.winfo_x() + (self.parent.winfo_width() // 2) - (modal.winfo_width() // 2)
        y = self.parent.winfo_y() + (self.parent.winfo_height() // 2) - (modal.winfo_height() // 2)
        modal.geometry(f"+{x}+{y}")
        desc_entry.focus_set()

    def _coerce_int(self, v):
        """Tenta converter v para int, retorna None se falhar."""
        try:
            return int(v)
        except Exception:
            return None

    def _get_id_from_selection(self, selection):
        """Safely extracts the ID from a Select2Tkinter selection in many possible formats."""
        if selection is None:
            return None

        # Caso: Select2 retorna lista com tupla [(id, label)] ou está vazio
        if isinstance(selection, list) and selection:
            first = selection[0]
            if isinstance(first, (list, tuple)) and first:
                return self._coerce_int(first[0])
            return self._coerce_int(first)

        # Caso: recebeu uma tupla/lista diretamente (id, label)
        if isinstance(selection, (tuple, list)) and not selection: # Tupla/lista vazia
            return None
            
        if isinstance(selection, (tuple, list)) and selection:
            return self._coerce_int(selection[0])

        # Caso: string — pode vir "123", "(123) descrição" ou "('123','desc')"
        if isinstance(selection, str):
            # tenta extrair número inicial
            import re
            m = re.search(r'(\d+)', selection)
            if m:
                return int(m.group(1))
            # fallback: tenta converter a string inteira
            return self._coerce_int(selection)

        # Caso: já é número
        return self._coerce_int(selection)

    def create_link(self):
        """Cria vínculos entre um item pai e um ou mais filhos."""
        parent_selection = self.parent_select.get_value()
    
        id_pai = self._get_id_from_selection(parent_selection)
    
        # Validações básicas
        if id_pai is None:
            messagebox.showwarning("Seleção Inválida", "Selecione um item pai.")
            return
        
        # Processa a lista de filhos
        # Coleta IDs e quantidades
        filhos_com_quantidade = []
        for s in self.child_selectors:
            id_filho = self._get_id_from_selection(s['selector'].get_value())
            if id_filho:
                try:
                    # Acessa o entry de quantidade
                    quantidade = int(s['quantity_entry'].get())
                    filhos_com_quantidade.append({'id': id_filho, 'qtd': quantidade})
                except (ValueError, KeyError, AttributeError):
                    continue # Ignora se a quantidade for inválida ou o spinbox não for encontrado
    
        if not filhos_com_quantidade:
            messagebox.showwarning("Seleção Inválida", "Nenhum item filho válido foi selecionado.")
            return
        
        # Verifica se o pai está na lista de filhos
        if id_pai in [f['id'] for f in filhos_com_quantidade]:
            messagebox.showerror("Erro de Lógica", "Um item não pode ser filho de si mesmo.")
            return
    
        # Mensagem de confirmação
        get_item_text = lambda item_id: next((f"({item['codigo']}) {item['descricao']}" for item in self.itens_data if item['id'] == item_id), f"ID {item_id}")
        parent_text = get_item_text(id_pai)
        children_texts = "\n - ".join([f"{get_item_text(f['id'])} (Qtd: {f['qtd']})" for f in filhos_com_quantidade])
        
        msg = f"Deseja vincular o pai:\n - {parent_text}\n\nAos seguintes filhos:\n - {children_texts}"
        if not messagebox.askyesno("Confirmar Vínculos", msg):
            return
    
        try:
            conn = self.get_db_connection()
            with conn.cursor() as cursor:
                # Prepara os dados para inserção em lote
                dados_para_inserir = [(id_pai, f['id'], f['qtd']) for f in filhos_com_quantidade]
                
                # Usar INSERT IGNORE para evitar erros se um vínculo já existir
                sql = "INSERT IGNORE INTO item_composicao (id_item_pai, id_item_filho, quantidade) VALUES (%s, %s, %s)"
                cursor.executemany(sql, dados_para_inserir)
                
            conn.commit()
            messagebox.showinfo("Sucesso", "Vínculos criados com sucesso!")
            self.load_hierarchy()
            self._reset_child_selectors() # Limpa os campos de filho após o sucesso
        except Exception as e:
            messagebox.showerror("Erro de Banco de Dados", f"Falha ao criar os vínculos: {e}")
        finally:
            if conn:
                conn.close()

    def delete_parent_link(self, parent_iid):
        """Exclui TODOS os vínculos (filhos) de um item pai."""
        id_item_pai = self._coerce_int(parent_iid)
        if id_item_pai is None:
            return

        parent_text = self.tree.item(parent_iid, "text")
        msg = f"ATENÇÃO! Você irá excluir TODOS os vínculos do item PAI:\n\n{parent_text}\n\nTem certeza?"
        
        if not messagebox.askyesno("Confirmar Exclusão do Vínculo Pai", msg):
            return

        try:
            conn = self.get_db_connection()
            with conn.cursor() as cursor:
                # Deleta todos os filhos associados a este pai
                sql = "DELETE FROM item_composicao WHERE id_item_pai = %s"
                cursor.execute(sql, (id_item_pai,))
            conn.commit()
            messagebox.showinfo("Sucesso", f"Todos os vínculos de {parent_text} foram excluídos.")
            self.load_hierarchy() # Recarrega a árvore para atualizar
        except Exception as e:
            messagebox.showerror("Erro de Banco de Dados", f"Falha ao excluir os vínculos: {e}")
        finally:
            if conn:
                conn.close()

    def delete_child_link(self, child_iid):
        """Exclui um único vínculo (item filho) de um pai."""
        # IID no formato 'id_pai-id_filho'
        try:
            id_item_pai, id_item_filho = map(int, child_iid.split('-'))
        except ValueError:
            return

        child_text = self.tree.item(child_iid, "text")
        parent_text = self.tree.item(self.tree.parent(child_iid), "text")
        
        msg = f"Deseja realmente excluir o vínculo:\n\nPAI: {parent_text}\nFILHO: {child_text}\n\nEsta ação é irreversível."
        
        if not messagebox.askyesno("Confirmar Exclusão do Vínculo Filho", msg):
            return

        try:
            conn = self.get_db_connection()
            with conn.cursor() as cursor:
                sql = "DELETE FROM item_composicao WHERE id_item_pai = %s AND id_item_filho = %s"
                cursor.execute(sql, (id_item_pai, id_item_filho))
            conn.commit()
            messagebox.showinfo("Sucesso", "Vínculo excluído com sucesso.")
            self.load_hierarchy()
        except Exception as e:
            messagebox.showerror("Erro de Banco de Dados", f"Falha ao excluir o vínculo: {e}")
        finally:
            if conn:
                conn.close()

    def show_parent_links(self):
        """Mostra os vínculos existentes para o item pai selecionado."""
        parent_selection = self.parent_select.get_value()
        id_pai = self._get_id_from_selection(parent_selection)

        if id_pai is None:
            messagebox.showwarning("Seleção Inválida", "Selecione um item pai para ver seus vínculos.")
            return

        # Filtra a árvore para mostrar apenas o pai selecionado e seus filhos
        search_term = self.tree.item(str(id_pai), "text")
        self.search_tree_entry.delete(0, tk.END)
        self.search_tree_entry.insert(0, search_term)
        self.filter_hierarchy_tree()

        # Garante que o item pai esteja visível na árvore
        try:
            self.tree.see(str(id_pai))
            self.tree.selection_set(str(id_pai))
            self.tree.focus(str(id_pai))
        except tk.TclError:
            messagebox.showinfo("Informação", "O item pai selecionado não possui vínculos cadastrados.", parent=self.main_frame)


    def open_edit_child_modal(self, child_iid):
        """Abre uma janela modal para editar a quantidade de um item filho."""
        try:
            id_item_pai, id_item_filho = map(int, child_iid.split('-'))
        except ValueError:
            return
        
        modal = ctk.CTkToplevel(self.main_frame)
        modal.title("Editar Quantidade do Vínculo")
        modal.transient(self.parent)
        modal.grab_set()
        
        frame = ctk.CTkFrame(modal)
        frame.pack(expand=True, fill=tk.BOTH)

        parent_text = self.tree.item(self.tree.parent(child_iid), "text")
        child_text = self.tree.item(child_iid, "text")
        current_qty_str = self.tree.item(child_iid, "values")[0].replace('x', '')
        current_qty = self._coerce_int(current_qty_str) or 1
        
        ctk.CTkLabel(frame, text=f"Item Pai: {parent_text}", text_color='cyan').pack(anchor='w', pady=(10, 5), padx=10)
        ctk.CTkLabel(frame, text=f"Item Filho: {child_text}", text_color='cyan').pack(anchor='w', pady=(0, 10), padx=10)

        ctk.CTkLabel(frame, text="Nova Quantidade:").pack(anchor='w', pady=2, padx=10)
        qty_entry = ctk.CTkEntry(frame, width=150)
        qty_entry.insert(0, str(current_qty))
        qty_entry.pack(fill=tk.X, pady=(0, 10), padx=10)
        
        def save_edit():
            try:
                nova_quantidade = int(qty_entry.get())
                if nova_quantidade < 1:
                    messagebox.showwarning("Valor Inválido", "A quantidade deve ser maior ou igual a 1.", parent=modal)
                    return
            except ValueError:
                messagebox.showwarning("Valor Inválido", "A quantidade deve ser um número inteiro.", parent=modal)
                return

            try:
                conn = self.get_db_connection()
                with conn.cursor() as cursor:
                    sql = "UPDATE item_composicao SET quantidade = %s WHERE id_item_pai = %s AND id_item_filho = %s"
                    cursor.execute(sql, (nova_quantidade, id_item_pai, id_item_filho))
                conn.commit()
                messagebox.showinfo("Sucesso", "Vínculo atualizado com sucesso!", parent=modal)
                modal.destroy()
                self.load_hierarchy() # Recarrega a árvore para mostrar a nova quantidade
            except Exception as e:
                messagebox.showerror("Erro de Banco de Dados", f"Falha ao atualizar o vínculo: {e}", parent=modal)
            finally:
                if conn:
                    conn.close()
        
        button_frame = ctk.CTkFrame(frame, fg_color="transparent")
        button_frame.pack(fill=tk.X, pady=20)
        
        ctk.CTkButton(button_frame, text="Salvar Edição", command=save_edit).pack(side=tk.LEFT, expand=True, padx=10)
        ctk.CTkButton(button_frame, text="Cancelar", command=modal.destroy).pack(side=tk.LEFT, expand=True, padx=10)
        
        modal.update_idletasks()
        # Centraliza a modal
        x = self.parent.winfo_x() + (self.parent.winfo_width() // 2) - (modal.winfo_width() // 2)
        y = self.parent.winfo_y() + (self.parent.winfo_height() // 2) - (modal.winfo_height() // 2)
        modal.geometry(f"+{x}+{y}")
        qty_entry.focus_set()


if __name__ == '__main__':
    root = tk.Tk()
    root.title("Cadastro de Itens e Estrutura")
    root.geometry("1200x700")

    # Mock user object para teste
    mock_user = {'id': 1, 'username': 'test_user', 'role': 'admin'}
    
    app = CadastroItensApp(root, mock_user)
    
    root.mainloop()
