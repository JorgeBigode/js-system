import tkinter as tk
from tkinter import ttk, messagebox, simpledialog, font
import customtkinter as ctk
import pymysql
from config import DB_HOST, DB_USER, DB_PASS, DB_NAME

class MaterialApp:
    def __init__(self, parent, user):
        self.parent = parent
        self.user = user
        self.main_frame = ctk.CTkFrame(self.parent, fg_color="transparent")
        self.main_frame.pack(fill=tk.BOTH, expand=True)
        self.editing_chapa_id = None # Controla se estamos editando ou criando

        # Dados das chapas extraídos do HTML
        # Lista de chapas atualizada e completa
        self.chapa_data = {
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
        self.create_widgets()

    def _execute_query(self, query, params=None, fetch=None):
        """
        Executa uma query no banco de dados usando pymysql.
        fetch: 'one', 'all', ou None para INSERT/UPDATE/DELETE.
        """
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
        """Cria os widgets principais da interface."""
        header_frame = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        header_frame.pack(fill="x")

        self.title_label = ctk.CTkLabel(header_frame, text="Cadastro - Chapa", font=ctk.CTkFont(size=18, weight="bold"), text_color="white")
        self.title_label.pack(side="left", expand=True)

        material_types = ["Chapa", "Retalho", "Ferramentas Maquinas", "Serra"]
        self.material_type_var = tk.StringVar(value=material_types[0])
        
        material_select = ctk.CTkComboBox(header_frame, variable=self.material_type_var, values=material_types, state="readonly", width=200)
        material_select.pack(side="right")
        material_select.configure(command=self.on_material_type_change)
        self.form_container = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        self.form_container.pack(expand=True, fill="both", padx=10, pady=10)

        style = ttk.Style()
        style.theme_use("default")
        style.configure("Custom.Treeview", background="#2b2b2b", foreground="white", fieldbackground="#2b2b2b", borderwidth=0)
        style.configure("Custom.Treeview.Heading", background="#171717", foreground="white", relief="flat", font=('Arial', 10, 'bold'))
        style.map("Custom.Treeview.Heading", background=[('active', '#333333')])
        style.map("Custom.Treeview", background=[('selected', '#00529B')])

        self.update_form_display()

    def on_material_type_change(self, choice):
        selected_type = self.material_type_var.get()
        self.title_label.configure(text=f"Cadastro - {selected_type}")
        self.update_form_display()

    def update_form_display(self):
        for widget in self.form_container.winfo_children():
            widget.destroy()

        selected_type = self.material_type_var.get()
        if selected_type == "Chapa":
            self.create_chapa_form()
        elif selected_type == "Retalho":
            self.create_retalho_form()
        elif selected_type == "Ferramentas Maquinas":
            self.create_ferramentas_form()
        elif selected_type == "Serra":
            self.create_serra_form()
        else:
            ctk.CTkLabel(self.form_container, text=f"Formulário para '{selected_type}' em desenvolvimento.", font=ctk.CTkFont(size=12)).pack(pady=20)

    def create_chapa_form(self):
        ctk.CTkLabel(self.form_container, text="Nova Chapa", font=ctk.CTkFont(weight="bold"), text_color="white").pack(anchor='w', padx=5, pady=(0,5))
        form_frame = ctk.CTkFrame(self.form_container)
        form_frame.pack(fill="x", padx=5, pady=5)

        self.chapa_entries = {}
        
        chapa_select_frame = ctk.CTkFrame(form_frame, fg_color="transparent")
        chapa_select_frame.pack(fill='x', pady=2)
        ctk.CTkLabel(chapa_select_frame, text="Tipo de Chapa:", width=120).pack(side='left')
        self.chapa_select_var = tk.StringVar()
        
        chapa_options = []
        for group, items in self.chapa_data.items():
            chapa_options.extend(list(items.keys()))
        
        # --- CORREÇÃO APLICADA AQUI ---
        # Armazena o combobox em self para poder acessá-lo em outros métodos
        self.chapa_select_combobox = ctk.CTkComboBox(
            chapa_select_frame, 
            variable=self.chapa_select_var, 
            values=chapa_options, 
            state="readonly",
            command=self.on_chapa_selected
        )
        self.chapa_select_combobox.pack(side='left', fill='x', expand=True)

        self.chapa_entries['descricao_material'] = tk.StringVar()

        fields = {"bitola": "Bitola (mm):", "largura": "Largura (mm):", "comprimento": "Comprimento (mm):", "quant_un": "Quant. (un):", "quant_kg": "Quant. (kg):"}
        for name, text in fields.items():
            frame = ctk.CTkFrame(form_frame, fg_color="transparent")
            frame.pack(fill='x', pady=2)
            ctk.CTkLabel(frame, text=text, width=120).pack(side='left')
            entry = ctk.CTkEntry(frame)
            entry.pack(side='left', fill='x', expand=True)
            self.chapa_entries[name] = entry

        for key in ['largura', 'comprimento', 'quant_un']:
            self.chapa_entries[key].bind("<KeyRelease>", self._update_weight_calculation)
            self.chapa_entries[key].bind("<FocusOut>", self._update_weight_calculation)

        action_frame = ctk.CTkFrame(form_frame, fg_color="transparent")
        action_frame.pack(pady=10)

        self.save_button = ctk.CTkButton(action_frame, text="Salvar Nova Chapa", command=self.save_chapa)
        self.save_button.pack(side='left', padx=5)

        clear_button = ctk.CTkButton(action_frame, text="Limpar Formulário", command=self.clear_chapa_form)
        clear_button.pack(side='left', padx=5)

        ctk.CTkLabel(self.form_container, text="Chapas em Estoque", font=ctk.CTkFont(weight="bold"), text_color="white").pack(anchor='w', padx=5, pady=(10,5))
        list_frame = ctk.CTkFrame(self.form_container)
        list_frame.pack(expand=True, fill="both", padx=5, pady=5)

        columns = ('id', 'desc', 'bitola', 'largura', 'comp', 'kg', 'un')
        self.chapa_tree = ttk.Treeview(list_frame, columns=columns, show='headings', style="Custom.Treeview")
        
        headings = {'id': 'ID', 'desc': 'Descrição', 'bitola': 'Bitola', 'largura': 'Largura', 'comp': 'Comprimento', 'kg': 'Kg', 'un': 'Un'}
        widths = {'id': 40, 'desc': 250, 'bitola': 60, 'largura': 80, 'comp': 100, 'kg': 60, 'un': 40}
        for col, text in headings.items():
            self.chapa_tree.heading(col, text=text)
            self.chapa_tree.column(col, width=widths[col])

        self.chapa_tree.pack(expand=True, fill='both', side='left')
        scrollbar = ctk.CTkScrollbar(list_frame, command=self.chapa_tree.yview)
        self.chapa_tree.configure(yscroll=scrollbar.set)
        scrollbar.pack(side='right', fill='y')

        self.chapa_tree.bind("<Double-1>", self.edit_selected_chapa)

        list_action_frame = ctk.CTkFrame(self.form_container, fg_color="transparent")
        list_action_frame.pack(fill='x', pady=5)
        ctk.CTkButton(list_action_frame, text="Deletar Selecionado", command=self.delete_selected_chapa).pack(side='right', padx=5)
        ctk.CTkButton(list_action_frame, text="Editar Selecionado", command=self.edit_selected_chapa).pack(side='right', padx=5)
        ctk.CTkButton(list_action_frame, text="Ler QR Code", command=self.read_qr_code).pack(side='left', padx=5)
        ctk.CTkButton(list_action_frame, text="Recarregar Lista", command=self.reload_current_list).pack(side='right', padx=5)
        self.load_chapas_list()

    def load_chapas_list(self):
        for i in self.chapa_tree.get_children():
            self.chapa_tree.delete(i)
        sql = "SELECT idmateriais, descricao_material, bitola, largura, comprimento, quant_kg, quant_un FROM materiais WHERE tipo_material='chapa' ORDER BY descricao_material ASC"
        chapas = self._execute_query(sql, fetch='all')
        if chapas:
            default_font = font.nametofont("TkDefaultFont")
            desc_width = self.chapa_tree.column('desc', 'width')

            for chapa in chapas:
                values = list(chapa.values())
                # Trunca a descrição
                values[1] = self._truncate_text(values[1], desc_width, default_font)
                self.chapa_tree.insert('', 'end', values=values)

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
        
    def on_chapa_selected(self, selected_desc):
        """Chamado quando um tipo de chapa é selecionado no combobox."""
        
        chapa_info = None
        for group in self.chapa_data.values():
            if selected_desc in group:
                chapa_info = group[selected_desc]
                break
        
        if chapa_info:
            self.chapa_entries['descricao_material'].set(selected_desc)
            
            bitola_entry = self.chapa_entries['bitola']
            bitola_entry.configure(state='normal')
            bitola_entry.delete(0, 'end')
            bitola_entry.insert(0, str(chapa_info['bitola']))
            bitola_entry.configure(state='disabled')
            
            self._update_weight_calculation()

    def _update_weight_calculation(self, event=None):
        """Função centralizada para calcular o peso total em KG."""
        selected_desc = self.chapa_select_var.get()
        if not selected_desc:
            return

        chapa_info = None
        for group in self.chapa_data.values():
            if selected_desc in group:
                chapa_info = group[selected_desc]
                break
        if not chapa_info:
            return

        try:
            largura_mm = float(self.chapa_entries['largura'].get() or 0)
            comprimento_mm = float(self.chapa_entries['comprimento'].get() or 0)
            unidades = int(self.chapa_entries['quant_un'].get() or 0)
            kg_m2 = chapa_info['kg_m2']

            peso_total_kg = (largura_mm * comprimento_mm * kg_m2 / 1000000) * unidades

            self.chapa_entries['quant_kg'].delete(0, 'end')
            self.chapa_entries['quant_kg'].insert(0, f"{peso_total_kg:.2f}")
        except (ValueError, tk.TclError):
            self.chapa_entries['quant_kg'].delete(0, 'end')

    def save_chapa(self):
        data = {name: entry.get() for name, entry in self.chapa_entries.items() if isinstance(entry, ctk.CTkEntry)}
        
        # Obter descrição do StringVar separado
        data['descricao_material'] = self.chapa_entries['descricao_material'].get()

        if not data['descricao_material']:
            messagebox.showerror("Erro", "A descrição é obrigatória. Selecione um tipo de chapa.")
            return

        try:
            bitola_entry = self.chapa_entries['bitola']
            bitola_entry.configure(state='normal')
            bitola = float(bitola_entry.get() or 0)
            bitola_entry.configure(state='disabled')
            
            largura = float(data.get('largura') or 0)
            comprimento = float(data.get('comprimento') or 0)
            quant_kg = float(data.get('quant_kg') or 0)
            quant_un = int(data.get('quant_un') or 0)
        except ValueError:
            messagebox.showerror("Erro de Formato", "Por favor, insira valores numéricos para bitola, largura, etc.")
            return

        if self.editing_chapa_id is None:
            sql = """
                INSERT INTO materiais (descricao_material, tipo_material, bitola, largura, comprimento, un_medida, quant_kg, quant_un)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """
            params = (data['descricao_material'], 'chapa', bitola, largura, comprimento, 'KG', quant_kg, quant_un)
            success_message = "Chapa salva com sucesso!"
        else:
            sql = """
                UPDATE materiais SET descricao_material=%s, bitola=%s, largura=%s, comprimento=%s, quant_kg=%s, quant_un=%s
                WHERE idmateriais=%s
            """
            params = (data['descricao_material'], bitola, largura, comprimento, quant_kg, quant_un, self.editing_chapa_id)
            success_message = "Chapa atualizada com sucesso!"

        if self._execute_query(sql, params):
            messagebox.showinfo("Sucesso", success_message)
            self.clear_chapa_form()
            self.load_chapas_list()

    def delete_selected_chapa(self):
        """Deleta a chapa selecionada na Treeview."""
        selected_item = self.chapa_tree.focus()
        if not selected_item:
            messagebox.showwarning("Atenção", "Nenhuma chapa selecionada.")
            return

        material_id = self.chapa_tree.item(selected_item, 'values')[0]
        if messagebox.askyesno("Confirmar Deleção", f"Tem certeza que deseja deletar a chapa ID {material_id}?"):
            if self._execute_query("DELETE FROM materiais WHERE idmateriais = %s", (material_id,)):
                messagebox.showinfo("Sucesso", "Chapa deletada com sucesso.")
                self.load_chapas_list()
    
    def edit_selected_chapa(self, event=None):
        """Preenche o formulário com os dados da chapa selecionada para edição."""
        selected_item = self.chapa_tree.focus()
        if not selected_item:
            if event: # só mostra o aviso se for chamado por um evento (duplo clique)
                messagebox.showwarning("Atenção", "Nenhuma chapa selecionada para editar.")
            return

        item_values = self.chapa_tree.item(selected_item, 'values')
        self.editing_chapa_id = item_values[0]

        # --- CORREÇÃO APLICADA AQUI ---
        # Desabilita o comando temporariamente para evitar que on_chapa_selected seja acionado ao preencher o form
        self.chapa_select_combobox.configure(command=None)

        self.chapa_select_var.set(item_values[1])
        self.chapa_entries['descricao_material'].set(item_values[1])

        field_map = {
            "bitola": item_values[2], "largura": item_values[3],
            "comprimento": item_values[4], "quant_kg": item_values[5],
            "quant_un": item_values[6]
        }
        
        for name, value in field_map.items():
            entry = self.chapa_entries[name]
            is_disabled = entry.cget('state') == 'disabled'
            if is_disabled:
                entry.configure(state='normal')
            entry.delete(0, 'end')
            entry.insert(0, value)
            if is_disabled:
                entry.configure(state='disabled')

        # Reabilita o comando do combobox após o preenchimento
        self.chapa_select_combobox.configure(command=self.on_chapa_selected)

        self.save_button.configure(text="Atualizar Chapa")
        self.chapa_entries['bitola'].configure(state='disabled')
        self.chapa_entries['quant_un'].focus_set()

    def clear_chapa_form(self):
        """Limpa o formulário e retorna ao modo de inserção."""
        self.chapa_select_var.set('')
        self.chapa_entries['descricao_material'].set('')
        
        for name in ["largura", "comprimento", "quant_un", "quant_kg"]:
            self.chapa_entries[name].delete(0, 'end')
        
        bitola_entry = self.chapa_entries['bitola']
        bitola_entry.configure(state='normal')
        bitola_entry.delete(0, 'end')

        self.editing_chapa_id = None
        self.save_button.configure(text="Salvar Nova Chapa")

    def create_retalho_form(self):
        """Cria o formulário e a lista para cadastro de Retalhos."""
        self.editing_ferramenta_id = None
        ctk.CTkLabel(self.form_container, text="Novo Retalho", font=ctk.CTkFont(weight="bold"), text_color="white").pack(anchor='w', padx=5, pady=(0,5))
        form_frame = ctk.CTkFrame(self.form_container)
        form_frame.pack(fill="x", padx=5, pady=5)

        self.retalho_entries = {}
        self.retalho_vars = {
            'estaleiro': tk.StringVar(),
            'chapa_select': tk.StringVar(),
            'un_medida': tk.StringVar(value='KG'),
            'reserva': tk.BooleanVar()
        }

        # --- Linha 1: Estaleiro, Descrição, Un. Medida, Reserva ---
        row1_frame = ctk.CTkFrame(form_frame, fg_color="transparent")
        row1_frame.pack(fill='x', pady=2)

        # Estaleiro
        ctk.CTkLabel(row1_frame, text="Estaleiro:", width=80).pack(side='left', padx=(0, 5))
        estaleiro_options = [f"EST_RET_GALV_{str(i).zfill(2)}" for i in range(1, 11)] + \
                            [f"EST_RET_PRETA_{str(i).zfill(2)}" for i in range(1, 11)] + \
                            ["EST_RET_DIV"]
        estaleiro_combo = ctk.CTkComboBox(row1_frame, variable=self.retalho_vars['estaleiro'], values=estaleiro_options, state="readonly", width=180)
        estaleiro_combo.pack(side='left', padx=5)

        # Descrição (será preenchida via código)
        ctk.CTkLabel(row1_frame, text="Descrição:", width=80).pack(side='left', padx=(10, 5))
        desc_entry = ctk.CTkEntry(row1_frame, state='readonly')
        desc_entry.pack(side='left', fill='x', expand=True, padx=5)
        self.retalho_entries['descricao_material'] = desc_entry

        # Un. Medida
        ctk.CTkLabel(row1_frame, text="Un.:").pack(side='left', padx=(10, 5))
        un_medida_combo = ctk.CTkComboBox(row1_frame, variable=self.retalho_vars['un_medida'], values=['KG', 'UN'], state="readonly", width=80)
        un_medida_combo.pack(side='left', padx=5)

        # Reserva
        reserva_check = ctk.CTkCheckBox(row1_frame, text="Reserva", variable=self.retalho_vars['reserva'])
        reserva_check.pack(side='left', padx=10)

        # --- Linha 2: Seleção de Chapa e Dimensões ---
        row2_frame = ctk.CTkFrame(form_frame, fg_color="transparent")
        row2_frame.pack(fill='x', pady=5)

        # Seleção de Chapa
        ctk.CTkLabel(row2_frame, text="Chapa Base:", width=80).pack(side='left', padx=(0, 5))
        chapa_options = []
        for group, items in self.chapa_data.items():
            chapa_options.extend(list(items.keys()))

        # --- CORREÇÃO APLICADA AQUI ---
        # Troca do .bind() para o parâmetro 'command', que é o correto para CTkComboBox
        chapa_select_combobox = ctk.CTkComboBox(
            row2_frame,
            variable=self.retalho_vars['chapa_select'],
            values=chapa_options,
            state="readonly",
            width=180,
            command=self._on_retalho_chapa_selected # <-- MUDANÇA PRINCIPAL
        )
        chapa_select_combobox.pack(side='left', padx=5)
        # A linha .bind("<<ComboboxSelected>>", ...) foi removida.

        # Campos de entrada
        fields = {"bitola": "Bitola:", "largura": "Largura:", "comprimento": "Comp.:", "quant_kg": "Qtd(kg):", "quant_un": "Qtd(un):"}
        for name, text in fields.items():
            ctk.CTkLabel(row2_frame, text=text).pack(side='left', padx=(10, 2))
            entry = ctk.CTkEntry(row2_frame, width=80)
            if name == 'bitola':
                entry.configure(state='readonly')
            entry.pack(side='left')
            self.retalho_entries[name] = entry

        # Adiciona eventos para recalcular o peso do retalho
        for key in ['largura', 'comprimento', 'quant_un']:
            self.retalho_entries[key].bind("<KeyRelease>", self._update_retalho_weight_calculation)
            self.retalho_entries[key].bind("<FocusOut>", self._update_retalho_weight_calculation)

        # --- Botões de Ação ---
        action_frame = ctk.CTkFrame(form_frame, fg_color="transparent")
        action_frame.pack(pady=10)
        ctk.CTkButton(action_frame, text="Salvar Novo Retalho", command=self.save_retalho).pack(side='left', padx=5)
        ctk.CTkButton(action_frame, text="Limpar", command=self.clear_retalho_form).pack(side='left', padx=5)

        # --- Lista de Retalhos ---
        ctk.CTkLabel(self.form_container, text="Retalhos em Estoque", font=ctk.CTkFont(weight="bold"), text_color="white").pack(anchor='w', padx=5, pady=(10,5))
        list_frame = ctk.CTkFrame(self.form_container)
        list_frame.pack(expand=True, fill="both", padx=5, pady=5)

        columns = ('id', 'desc', 'bitola', 'largura', 'comp', 'kg', 'un', 'codigo', 'estaleiro', 'reserva')
        self.retalho_tree = ttk.Treeview(list_frame, columns=columns, show='headings', style="Custom.Treeview")

        headings = {'id': 'ID', 'desc': 'Descrição', 'bitola': 'Bitola', 'largura': 'Largura', 'comp': 'Comp.', 'kg': 'Kg', 'un': 'Un', 'codigo': 'Código', 'estaleiro': 'Estaleiro', 'reserva': 'Reserva'}
        widths = {'id': 40, 'desc': 200, 'bitola': 50, 'largura': 60, 'comp': 60, 'kg': 60, 'un': 40, 'codigo': 120, 'estaleiro': 120, 'reserva': 80}
        for col, text in headings.items():
            self.retalho_tree.heading(col, text=text)
            self.retalho_tree.column(col, width=widths[col], anchor='center')

        self.retalho_tree.pack(expand=True, fill='both', side='left')
        scrollbar = ctk.CTkScrollbar(list_frame, command=self.retalho_tree.yview)
        self.retalho_tree.configure(yscroll=scrollbar.set)
        scrollbar.pack(side='right', fill='y')

        # Botão de deletar
        list_action_frame = ctk.CTkFrame(self.form_container, fg_color="transparent")
        list_action_frame.pack(fill='x', pady=5)
        ctk.CTkButton(list_action_frame, text="Deletar Selecionado", command=self.delete_selected_retalho).pack(side='right', padx=5)
        ctk.CTkButton(list_action_frame, text="Ler QR Code", command=self.read_qr_code).pack(side='left', padx=5)
        ctk.CTkButton(list_action_frame, text="Recarregar Lista", command=self.reload_current_list).pack(side='right', padx=5)

        self.load_retalhos_list()

    def _on_retalho_chapa_selected(self, selected_desc):
        """Preenche os campos de descrição e bitola quando uma chapa base é selecionada para o retalho."""
        chapa_info = None
        for group in self.chapa_data.values():
            if selected_desc in group:
                chapa_info = group[selected_desc]
                break

        if chapa_info:
            # Preenche a descrição
            desc_entry = self.retalho_entries['descricao_material']
            desc_entry.configure(state='normal')
            desc_entry.delete(0, 'end')
            desc_entry.insert(0, f"RETALHO {selected_desc}")
            desc_entry.configure(state='readonly')

            # Preenche a bitola
            bitola_entry = self.retalho_entries['bitola']
            bitola_entry.configure(state='normal')
            bitola_entry.delete(0, 'end')
            bitola_entry.insert(0, str(chapa_info['bitola']))
            bitola_entry.configure(state='readonly')
            
            # Dispara o cálculo do peso
            self._update_retalho_weight_calculation()

    def _update_retalho_weight_calculation(self, event=None):
        """Função para calcular o peso do retalho em KG."""
        selected_desc = self.retalho_vars['chapa_select'].get()
        if not selected_desc:
            return

        # Encontra os dados da chapa base selecionada
        chapa_info = None
        for group in self.chapa_data.values():
            if selected_desc in group:
                chapa_info = group[selected_desc]
                break
        if not chapa_info:
            return

        try:
            largura_mm = float(self.retalho_entries['largura'].get() or 0)
            comprimento_mm = float(self.retalho_entries['comprimento'].get() or 0)
            unidades = int(self.retalho_entries['quant_un'].get() or 0)
            kg_m2 = chapa_info['kg_m2']

            peso_total_kg = (largura_mm * comprimento_mm * kg_m2 / 1000000) * unidades

            self.retalho_entries['quant_kg'].delete(0, 'end')
            self.retalho_entries['quant_kg'].insert(0, f"{peso_total_kg:.2f}")
        except (ValueError, tk.TclError):
            self.retalho_entries['quant_kg'].delete(0, 'end') # Limpa o campo se houver erro

    def save_retalho(self):
        """Salva um novo retalho no banco de dados."""
        data = {name: entry.get() for name, entry in self.retalho_entries.items()}
        
        estaleiro = self.retalho_vars['estaleiro'].get()
        if not estaleiro or not data['descricao_material']:
            messagebox.showerror("Erro", "Estaleiro e Chapa Base são obrigatórios.")
            return

        try:
            params = {
                'descricao': data['descricao_material'],
                'tipo': 'retalho',
                'bitola': float(data.get('bitola') or 0),
                'largura': float(data.get('largura') or 0),
                'comprimento': float(data.get('comprimento') or 0),
                'un_medida': self.retalho_vars['un_medida'].get(),
                'quant_kg': float(data.get('quant_kg') or 0),
                'quant_un': int(data.get('quant_un') or 0),
                'estaleiro': estaleiro,
                'reserva': self.retalho_vars['reserva'].get()
            }
        except ValueError:
            messagebox.showerror("Erro de Formato", "Por favor, insira valores numéricos válidos.")
            return

        sql_insert = """
            INSERT INTO materiais (descricao_material, tipo_material, bitola, largura, comprimento, un_medida, quant_kg, quant_un, estaleiro, reserva)
            VALUES (%(descricao)s, %(tipo)s, %(bitola)s, %(largura)s, %(comprimento)s, %(un_medida)s, %(quant_kg)s, %(quant_un)s, %(estaleiro)s, %(reserva)s)
        """
        if self._execute_query(sql_insert, params):
            messagebox.showinfo("Sucesso", "Retalho salvo com sucesso! O código será gerado.")
            self.clear_retalho_form()
            self.load_retalhos_list()

    def load_retalhos_list(self):
        for i in self.retalho_tree.get_children():
            self.retalho_tree.delete(i)
        sql = "SELECT idmateriais, descricao_material, bitola, largura, comprimento, quant_kg, quant_un, codigo_material, estaleiro, reserva, codigo_material FROM materiais WHERE tipo_material='retalho' ORDER BY idmateriais DESC"
        retalhos = self._execute_query(sql, fetch='all')
        if retalhos:
            default_font = font.nametofont("TkDefaultFont")
            desc_width = self.retalho_tree.column('desc', 'width')

            for retalho in retalhos:
                values = list(retalho.values())
                # Trunca a descrição
                # Converte o valor de 'reserva' (índice 9) para "Sim" ou "Não"
                reserva_val = values[9]
                values[9] = "Sim" if reserva_val and int(reserva_val) == 1 else "Não"
                values[1] = self._truncate_text(values[1], desc_width, default_font)
                self.retalho_tree.insert('', 'end', values=values)

    def clear_retalho_form(self):
        """Limpa o formulário de retalhos."""
        for var in self.retalho_vars.values():
            if isinstance(var, tk.BooleanVar):
                var.set(False)
            else:
                var.set('')
        for entry in self.retalho_entries.values():
            is_readonly = entry.cget('state') == 'readonly'
            if is_readonly: entry.configure(state='normal')
            entry.delete(0, 'end')
            if is_readonly: entry.configure(state='readonly')

    def delete_selected_retalho(self):
        """Deleta o retalho selecionado na Treeview."""
        selected_item = self.retalho_tree.focus()
        if not selected_item:
            messagebox.showwarning("Atenção", "Nenhum retalho selecionado.")
            return

        material_id = self.retalho_tree.item(selected_item, 'values')[0]
        if messagebox.askyesno("Confirmar Deleção", f"Tem certeza que deseja deletar o retalho ID {material_id}?"):
            if self._execute_query("DELETE FROM materiais WHERE idmateriais = %s", (material_id,)):
                messagebox.showinfo("Sucesso", "Retalho deletado com sucesso.")
                self.load_retalhos_list()

    def create_ferramentas_form(self):
        """Cria o formulário e a lista para cadastro de Ferramentas de Máquinas."""
        self.editing_ferramenta_id = None
        ctk.CTkLabel(self.form_container, text="Nova Ferramenta/Item", font=ctk.CTkFont(weight="bold")).pack(anchor='w', padx=5, pady=(0,5))
        form_frame = ctk.CTkFrame(self.form_container)
        form_frame.pack(fill="x", padx=5, pady=5)

        self.ferramenta_entries = {}
        self.ferramenta_vars = {'maquina': tk.StringVar()}

        # --- Linha de Formulário ---
        form_row = ctk.CTkFrame(form_frame, fg_color="transparent")
        form_row.pack(fill='x', pady=2)

        # Máquina (Estaleiro no PHP)
        ctk.CTkLabel(form_row, text="Máquina:", width=80).pack(side='left', padx=(0, 5))
        maquina_options = ["LASER 01", "LASER 02", "PUNCIONADEIRA"]
        maquina_combo = ctk.CTkComboBox(form_row, variable=self.ferramenta_vars['maquina'], values=maquina_options, state="readonly", width=180)
        maquina_combo.pack(side='left', padx=5)

        # Descrição
        ctk.CTkLabel(form_row, text="Descrição:", width=80).pack(side='left', padx=(10, 5))
        desc_entry = ctk.CTkEntry(form_row)
        desc_entry.pack(side='left', fill='x', expand=True, padx=5)
        self.ferramenta_entries['descricao_material'] = desc_entry

        # Quantidade
        ctk.CTkLabel(form_row, text="Qtd (un):", width=60).pack(side='left', padx=(10, 5))
        quant_entry = ctk.CTkEntry(form_row, width=80)
        quant_entry.pack(side='left', padx=5)
        self.ferramenta_entries['quant_un'] = quant_entry

        # --- Botões de Ação ---
        action_frame = ctk.CTkFrame(form_frame, fg_color="transparent")
        action_frame.pack(pady=10)
        self.save_ferramenta_button = ctk.CTkButton(action_frame, text="Salvar Item", command=self.save_ferramenta)
        self.save_ferramenta_button.pack(side='left', padx=5)
        ctk.CTkButton(action_frame, text="Limpar", command=self.clear_ferramenta_form).pack(side='left', padx=5)

        # --- Lista de Itens ---
        ctk.CTkLabel(self.form_container, text="Itens Cadastrados", font=ctk.CTkFont(weight="bold"), text_color="white").pack(anchor='w', padx=5, pady=(10,5))
        list_frame = ctk.CTkFrame(self.form_container)
        list_frame.pack(expand=True, fill="both", padx=5, pady=5)
        
        # --- Filtros da Lista ---
        filter_frame = ctk.CTkFrame(list_frame, fg_color="transparent")
        filter_frame.pack(fill='x', pady=5)
        
        self.ferramenta_filter_maquina_var = tk.StringVar(value="Todas as Máquinas")
        maquina_filter_options = ["Todas as Máquinas"] + maquina_options
        maquina_filter_combo = ctk.CTkComboBox(
            filter_frame,
            variable=self.ferramenta_filter_maquina_var,
            values=maquina_filter_options,
            state="readonly",
            command=self.filter_ferramentas_list # <-- MUDANÇA PRINCIPAL
        )
        maquina_filter_combo.pack(side='right', padx=5)
        maquina_filter_combo.bind("<<ComboboxSelected>>", self.filter_ferramentas_list)

        self.ferramenta_filter_desc_var = tk.StringVar()
        desc_filter_entry = ctk.CTkEntry(filter_frame, textvariable=self.ferramenta_filter_desc_var, width=40)
        desc_filter_entry.pack(side='right', fill='x', expand=True, padx=5)
        desc_filter_entry.bind("<KeyRelease>", self.filter_ferramentas_list)
        ctk.CTkLabel(filter_frame, text="Filtrar por Descrição/Código:").pack(side='right')

        # --- Treeview ---
        columns = ('id', 'desc', 'qtd', 'maquina', 'codigo') # Adicionado 'codigo'
        self.ferramenta_tree = ttk.Treeview(list_frame, columns=columns, show='headings', style="Custom.Treeview")

        headings = {'id': 'ID', 'desc': 'Descrição', 'qtd': 'Qtd (un)', 'maquina': 'Máquina', 'codigo': 'Código'}
        widths = {'id': 50, 'desc': 350, 'qtd': 80, 'maquina': 150, 'codigo': 150}
        for col, text in headings.items():
            self.ferramenta_tree.heading(col, text=text)
            self.ferramenta_tree.column(col, width=widths[col], anchor='center')

        self.ferramenta_tree.pack(expand=True, fill='both', side='left')
        scrollbar = ctk.CTkScrollbar(list_frame, command=self.ferramenta_tree.yview)
        self.ferramenta_tree.configure(yscroll=scrollbar.set)
        scrollbar.pack(side='right', fill='y')

        # Evento de duplo clique para editar
        self.ferramenta_tree.bind("<Double-1>", self.edit_selected_ferramenta)


        # Botão de deletar
        list_action_frame = ctk.CTkFrame(self.form_container, fg_color="transparent")
        list_action_frame.pack(fill='x', pady=5)
        ctk.CTkButton(list_action_frame, text="Deletar Selecionado", command=self.delete_selected_ferramenta).pack(side='right', padx=5)
        ctk.CTkButton(list_action_frame, text="Editar Selecionado", command=self.edit_selected_ferramenta).pack(side='right', padx=5)
        ctk.CTkButton(list_action_frame, text="Ler QR Code", command=self.read_qr_code).pack(side='left', padx=5)
        ctk.CTkButton(list_action_frame, text="Recarregar Lista", command=self.reload_current_list).pack(side='right', padx=5)

        self.load_ferramentas_list()

    def save_ferramenta(self):
        """Salva uma nova ferramenta/item ou atualiza uma existente."""
        desc = self.ferramenta_entries['descricao_material'].get()
        maquina = self.ferramenta_vars['maquina'].get()
        quant_un_str = self.ferramenta_entries['quant_un'].get()

        if not desc or not maquina:
            messagebox.showerror("Erro", "Máquina e Descrição são obrigatórios.")
            return

        try:
            quant_un = int(quant_un_str) if quant_un_str else 0
        except ValueError:
            messagebox.showerror("Erro de Formato", "A quantidade deve ser um número inteiro.")
            return

        if self.editing_ferramenta_id is None:
            # Modo de Inserção
            sql = """
                INSERT INTO materiais (descricao_material, tipo_material, quant_un, estaleiro)
                VALUES (%s, %s, %s, %s)
            """
            params = (desc, 'unitario', quant_un, maquina)
            success_message = "Item salvo com sucesso!"
        else:
            # Modo de Atualização
            sql = """
                UPDATE materiais SET descricao_material=%s, quant_un=%s, estaleiro=%s
                WHERE idmateriais=%s
            """
            params = (desc, quant_un, maquina, self.editing_ferramenta_id)
            success_message = "Item atualizado com sucesso!"

        if self._execute_query(sql, params):
            messagebox.showinfo("Sucesso", success_message)
            self.clear_ferramenta_form()
            self.load_ferramentas_list()

    def load_ferramentas_list(self):
        """Carrega e exibe a lista de ferramentas/itens."""
        for i in self.ferramenta_tree.get_children():
            self.ferramenta_tree.delete(i)
        sql = "SELECT idmateriais, descricao_material, quant_un, estaleiro, codigo_material FROM materiais WHERE tipo_material='unitario' ORDER BY idmateriais DESC"
        self.all_ferramentas = self._execute_query(sql, fetch='all') or []
        self.filter_ferramentas_list()

    def filter_ferramentas_list(self, event=None):
        """Filtra os itens na Treeview com base nos campos de filtro."""
        for i in self.ferramenta_tree.get_children():
            self.ferramenta_tree.delete(i)

        filter_text = self.ferramenta_filter_desc_var.get().lower()
        filter_maquina = self.ferramenta_filter_maquina_var.get()

        default_font = font.nametofont("TkDefaultFont")
        desc_width = self.ferramenta_tree.column('desc', 'width')
        codigo_width = self.ferramenta_tree.column('codigo', 'width')

        for item in self.all_ferramentas:
            desc = str(item.get('descricao_material', '')).lower()
            codigo = str(item.get('codigo_material', '')).lower()
            maquina = item.get('estaleiro', '')

            text_match = filter_text in desc or filter_text in codigo
            maquina_match = filter_maquina == "Todas as Máquinas" or maquina == filter_maquina

            if text_match and maquina_match:
                values = list(item.values())
                # Trunca a descrição e o código
                values[1] = self._truncate_text(values[1], desc_width, default_font)
                values[4] = self._truncate_text(values[4], codigo_width, default_font)
                self.ferramenta_tree.insert('', 'end', values=values)

    def clear_ferramenta_form(self):
        """Limpa o formulário de ferramentas e reseta o modo de edição."""
        self.ferramenta_vars['maquina'].set('')
        for entry in self.ferramenta_entries.values():
            entry.delete(0, 'end')
        self.editing_ferramenta_id = None
        if hasattr(self, 'save_ferramenta_button'):
            self.save_ferramenta_button.configure(text="Salvar Item")

    def delete_selected_ferramenta(self):
        """Deleta o item selecionado na Treeview."""
        selected_item = self.ferramenta_tree.focus()
        if not selected_item:
            messagebox.showwarning("Atenção", "Nenhum item selecionado.")
            return

        material_id = self.ferramenta_tree.item(selected_item, 'values')[0]
        if messagebox.askyesno("Confirmar Deleção", f"Tem certeza que deseja deletar o item ID {material_id}?"):
            if self._execute_query("DELETE FROM materiais WHERE idmateriais = %s", (material_id,)):
                messagebox.showinfo("Sucesso", "Item deletado com sucesso.")
                self.load_ferramentas_list()

    def edit_selected_ferramenta(self, event=None):
        """Preenche o formulário com os dados do item selecionado para edição."""
        selected_item = self.ferramenta_tree.focus()
        if not selected_item:
            messagebox.showwarning("Atenção", "Nenhum item selecionado para editar.")
            return

        item_values = self.ferramenta_tree.item(selected_item, 'values')
        self.editing_ferramenta_id = item_values[0]

        # Ordem dos valores: id, desc, qtd, maquina, codigo
        desc = item_values[1]
        qtd = item_values[2]
        maquina = item_values[3]

        # Preenche o formulário
        self.ferramenta_entries['descricao_material'].delete(0, 'end')
        self.ferramenta_entries['descricao_material'].insert(0, desc)
        self.ferramenta_entries['quant_un'].delete(0, 'end')
        self.ferramenta_entries['quant_un'].insert(0, qtd)
        self.ferramenta_vars['maquina'].set(maquina)

        # Altera o texto do botão para indicar modo de edição
        if hasattr(self, 'save_ferramenta_button'):
            self.save_ferramenta_button.configure(text="Atualizar Item")

    def read_qr_code(self):
        code = simpledialog.askstring("Ler QR Code", "Digite ou leia o código do material:")
        if not code: return

        material = self._execute_query("SELECT * FROM materiais WHERE codigo = %s", (code,), fetch='one')
        if material:
            self.show_action_choice_dialog(material)
        else:
            messagebox.showwarning("Não Encontrado", f"Nenhum material encontrado com o código: {code}")

    def show_action_choice_dialog(self, material):
        choice_window = tk.Toplevel(self.parent)
        choice_window.title("O que deseja fazer?")
        choice_window.geometry("300x150")
        choice_window.transient(self.parent)
        choice_window.grab_set()

        ctk.CTkLabel(choice_window, text=f"Código: {material.get('codigo', 'N/A')}", font=ctk.CTkFont(size=12, weight="bold")).pack(pady=10)
        
        ctk.CTkButton(choice_window, text="Dar Baixa no Material", command=lambda: self.dar_baixa(material['idmateriais'], choice_window)).pack(fill="x", padx=20, pady=5)
        ctk.CTkButton(choice_window, text="Alterar Quantidade", command=lambda: self.alterar_quantidade(material['idmateriais'], choice_window)).pack(fill="x", padx=20, pady=5)

    def dar_baixa(self, material_id, parent_window):
        parent_window.destroy()
        if messagebox.askyesno("Confirmar Baixa", "Tem certeza que deseja dar baixa neste material?"):
            if self._execute_query("DELETE FROM materiais WHERE idmateriais = %s", (material_id,)):
                messagebox.showinfo("Sucesso", "Material baixado com sucesso!")
                self.reload_current_list()

    def alterar_quantidade(self, material_id, parent_window):
        parent_window.destroy()
        new_quantity = simpledialog.askfloat("Alterar Quantidade", "Digite a nova quantidade:")
        if new_quantity is not None:
            if self._execute_query("UPDATE materiais SET quant_un = %s WHERE idmateriais = %s", (new_quantity, material_id)):
                messagebox.showinfo("Sucesso", "Quantidade alterada com sucesso!")
                self.reload_current_list()

    def reload_current_list(self):
        """Recarrega a lista de materiais com base na aba atualmente selecionada."""
        current_type = self.material_type_var.get()
        if current_type == "Chapa":
            self.load_chapas_list()
        elif current_type == "Retalho":
            self.load_retalhos_list()
        elif current_type == "Ferramentas Maquinas":
            self.load_ferramentas_list()
        elif current_type == "Serra":
            self.load_serra_list()

    def create_serra_form(self):
        """Cria o formulário e a lista para cadastro de itens de Serra."""
        self.editing_serra_id = None
        ctk.CTkLabel(self.form_container, text="Novo Item de Serra", font=ctk.CTkFont(weight="bold"), text_color="white").pack(anchor='w', padx=5, pady=(0,5))
        form_frame = ctk.CTkFrame(self.form_container)
        form_frame.pack(fill="x", padx=5, pady=5)

        self.serra_entries = {}
        self.serra_vars = {'tipo_serra': tk.StringVar()}

        # --- Linha de Formulário ---
        form_row = ctk.CTkFrame(form_frame, fg_color="transparent")
        form_row.pack(fill='x', pady=2)

        # Tipo (estaleiro no PHP)
        ctk.CTkLabel(form_row, text="Tipo:", width=80).pack(side='left', padx=(0, 8))
        serra_options = [
            "TUBO QUADRADO", "TUBO RETANGULAR", "TUBO REDONDO GALV", "TUBO REDONDO PRETO",
            "BARRA RED TREF 1045", "BARRA RED TREF 1020", "BARRA RED MECANICO 1045",
            "BARRA RED MECANICO 1020", "BARRA QD MECANICO 1045", "BARRA QD MECANICO 1020",
            "BARRA CHATA", "BARRA CHATA ACO 5160", "CANTONEIRA"
        ]
        tipo_combo = ctk.CTkComboBox(form_row, variable=self.serra_vars['tipo_serra'], values=serra_options, state="readonly", width=220)
        tipo_combo.pack(side='left', padx=5)

        # Descrição
        ctk.CTkLabel(form_row, text="Descrição:", width=80).pack(side='left', padx=(10, 5))
        desc_entry = ctk.CTkEntry(form_row)
        desc_entry.pack(side='left', fill='x', expand=True, padx=5)
        self.serra_entries['descricao_material'] = desc_entry

        # Quantidade
        ctk.CTkLabel(form_row, text="Qtd (un):", width=60).pack(side='left', padx=(10, 5))
        quant_entry = ctk.CTkEntry(form_row, width=80)
        quant_entry.pack(side='left', padx=5)
        self.serra_entries['quant_un'] = quant_entry

        # --- Botões de Ação ---
        action_frame = ctk.CTkFrame(form_frame, fg_color="transparent")
        action_frame.pack(pady=10)
        self.save_serra_button = ctk.CTkButton(action_frame, text="Salvar Item", command=self.save_serra)
        self.save_serra_button.pack(side='left', padx=5)
        ctk.CTkButton(action_frame, text="Limpar", command=self.clear_serra_form).pack(side='left', padx=5)

        # --- Lista de Itens ---
        ctk.CTkLabel(self.form_container, text="Itens Cadastrados (Serra)", font=ctk.CTkFont(weight="bold"), text_color="white").pack(anchor='w', padx=5, pady=(10,5))
        list_frame = ctk.CTkFrame(self.form_container)
        list_frame.pack(expand=True, fill="both", padx=5, pady=5)

        # --- Filtros da Lista ---
        filter_frame = ctk.CTkFrame(list_frame, fg_color="transparent")
        filter_frame.pack(fill='x', pady=5)
        
        self.serra_filter_tipo_var = tk.StringVar(value="-- Todos --")
        tipo_filter_options = ["-- Todos --"] + serra_options
        tipo_filter_combo = ctk.CTkComboBox(filter_frame, variable=self.serra_filter_tipo_var, values=tipo_filter_options, state="readonly")
        tipo_filter_combo = ctk.CTkComboBox(
            filter_frame,
            variable=self.serra_filter_tipo_var,
            values=tipo_filter_options,
            state="readonly",
            command=self.filter_serra_list # <-- MUDANÇA PRINCIPAL
        )
        tipo_filter_combo.pack(side='right', padx=20)

        self.serra_filter_desc_var = tk.StringVar()
        desc_filter_entry = ctk.CTkEntry(filter_frame, textvariable=self.serra_filter_desc_var, width=40)
        desc_filter_entry.pack(side='right', fill='x', expand=True, padx=5)
        desc_filter_entry.bind("<KeyRelease>", self.filter_serra_list)
        ctk.CTkLabel(filter_frame, text="Filtrar por Descrição/Código:").pack(side='right')

        # --- Treeview ---
        columns = ('id', 'desc', 'qtd', 'tipo', 'codigo')
        self.serra_tree = ttk.Treeview(list_frame, columns=columns, show='headings', style="Custom.Treeview")

        headings = {'id': 'ID', 'desc': 'Descrição', 'qtd': 'Qtd (un)', 'tipo': 'Tipo', 'codigo': 'Código'}
        widths = {'id': 50, 'desc': 350, 'qtd': 80, 'tipo': 180, 'codigo': 180}
        for col, text in headings.items():
            self.serra_tree.heading(col, text=text)
            self.serra_tree.column(col, width=widths[col], anchor='center')

        self.serra_tree.pack(expand=True, fill='both', side='left')
        scrollbar = ctk.CTkScrollbar(list_frame, command=self.serra_tree.yview)
        self.serra_tree.configure(yscroll=scrollbar.set)
        scrollbar.pack(side='right', fill='y')

        self.serra_tree.bind("<Double-1>", self.edit_selected_serra)

        # Botões de ação da lista
        list_action_frame = ctk.CTkFrame(self.form_container, fg_color="transparent")
        list_action_frame.pack(fill='x', pady=5)
        ctk.CTkButton(list_action_frame, text="Deletar Selecionado", command=self.delete_selected_serra).pack(side='right', padx=5)
        ctk.CTkButton(list_action_frame, text="Editar Selecionado", command=self.edit_selected_serra).pack(side='right', padx=5)
        ctk.CTkButton(list_action_frame, text="Ler QR Code", command=self.read_qr_code).pack(side='left', padx=5)
        ctk.CTkButton(list_action_frame, text="Recarregar Lista", command=self.reload_current_list).pack(side='right', padx=5)

        self.load_serra_list()

    def save_serra(self):
        desc = self.serra_entries['descricao_material'].get()
        tipo_serra = self.serra_vars['tipo_serra'].get()
        quant_un_str = self.serra_entries['quant_un'].get()

        if not desc or not tipo_serra:
            messagebox.showerror("Erro", "Tipo e Descrição são obrigatórios.")
            return

        try:
            quant_un = int(quant_un_str) if quant_un_str else 0
        except ValueError:
            messagebox.showerror("Erro de Formato", "A quantidade deve ser um número inteiro.")
            return

        if self.editing_serra_id is None:
            sql = "INSERT INTO materiais (descricao_material, tipo_material, quant_un, estaleiro) VALUES (%s, %s, %s, %s)"
            params = (desc, 'serra', quant_un, tipo_serra)
            msg = "Item salvo com sucesso!"
        else:
            sql = "UPDATE materiais SET descricao_material=%s, quant_un=%s, estaleiro=%s WHERE idmateriais=%s"
            params = (desc, quant_un, tipo_serra, self.editing_serra_id)
            msg = "Item atualizado com sucesso!"

        if self._execute_query(sql, params):
            messagebox.showinfo("Sucesso", msg)
            self.clear_serra_form()
            self.load_serra_list()

    def load_serra_list(self):
        for i in self.serra_tree.get_children(): self.serra_tree.delete(i)
        sql = "SELECT idmateriais, descricao_material, quant_un, estaleiro, codigo_material FROM materiais WHERE tipo_material='serra' ORDER BY idmateriais DESC"
        self.all_serra_items = self._execute_query(sql, fetch='all') or []
        self.filter_serra_list()

    def filter_serra_list(self, event=None):
        for i in self.serra_tree.get_children(): self.serra_tree.delete(i)
        filter_text = self.serra_filter_desc_var.get().lower()
        filter_tipo = self.serra_filter_tipo_var.get()

        default_font = font.nametofont("TkDefaultFont")
        desc_width = self.serra_tree.column('desc', 'width')
        codigo_width = self.serra_tree.column('codigo', 'width')

        for item in self.all_serra_items:
            codigo = str(item.get('codigo_material', '')).lower()
            desc = str(item.get('descricao_material', '')).lower()
            tipo = item.get('estaleiro', '')
            text_match = filter_text in desc or filter_text in codigo
            tipo_match = filter_tipo == "-- Todos --" or tipo == filter_tipo
            if text_match and tipo_match:
                values = list(item.values())
                values[1] = self._truncate_text(values[1], desc_width, default_font)
                values[4] = self._truncate_text(values[4], codigo_width, default_font)
                self.serra_tree.insert('', 'end', values=values)

    def clear_serra_form(self):
        self.serra_vars['tipo_serra'].set('')
        for entry in self.serra_entries.values(): entry.delete(0, 'end')
        self.editing_serra_id = None
        if hasattr(self, 'save_serra_button'):
            self.save_serra_button.configure(text="Salvar Item")

    def delete_selected_serra(self):
        selected_item = self.serra_tree.focus()
        if not selected_item:
            messagebox.showwarning("Atenção", "Nenhum item selecionado.")
            return
        material_id = self.serra_tree.item(selected_item, 'values')[0]
        if messagebox.askyesno("Confirmar Deleção", f"Tem certeza que deseja deletar o item ID {material_id}?"):
            if self._execute_query("DELETE FROM materiais WHERE idmateriais = %s", (material_id,)):
                messagebox.showinfo("Sucesso", "Item deletado com sucesso.")
                self.load_serra_list()

    def edit_selected_serra(self, event=None):
        selected_item = self.serra_tree.focus()
        if not selected_item:
            messagebox.showwarning("Atenção", "Nenhum item selecionado para editar.")
            return
        item_values = self.serra_tree.item(selected_item, 'values')
        self.editing_serra_id = item_values[0]
        # Ordem: id, desc, qtd, tipo, codigo
        self.serra_entries['descricao_material'].delete(0, 'end')
        self.serra_entries['descricao_material'].insert(0, item_values[1])
        self.serra_entries['quant_un'].delete(0, 'end')
        self.serra_entries['quant_un'].insert(0, item_values[2])
        self.serra_vars['tipo_serra'].set(item_values[3])
        if hasattr(self, 'save_serra_button'):
            self.save_serra_button.configure(text="Atualizar Item")
