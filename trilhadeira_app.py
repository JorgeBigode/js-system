import tkinter as tk
from tkinter import messagebox
import pymysql
from config import DB_HOST, DB_USER, DB_PASS, DB_NAME
from datetime import datetime
from collections import Counter 
import customtkinter as ctk
from select2_tkinter import Select2Tkinter
from PIL import Image, ImageTk
import os
import sys
import threading

def resource_path(relative_path):
    """ Obtém o caminho absoluto para o recurso, funciona para dev e para PyInstaller """
    try:
        # PyInstaller cria uma pasta temp e armazena o caminho em _MEIPASS
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

class TrilhadeiraApp:

    def __init__(self, parent, user):
        self.parent = parent
        self.user = user
        self.main_frame = ctk.CTkFrame(self.parent, fg_color="transparent")
        self.main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # self.apply_styles() # Estilos agora são tratados pelo CustomTkinter

        self.status_class_map = {
            'em-programacao': 'status-em-programacao',
            'aguardando-programacao': 'status-em-programacao',
            'a-iniciar-producao': 'status-a-iniciar-producao',
            'aguardando-pcp': 'status-a-iniciar-producao',
            'em-producao': 'status-produzindo',
            'produzindo': 'status-produzindo',
            'producao-finalizada': 'status-esperando-qualidade',
            'esperando-qualidade': 'status-esperando-qualidade',
            'liberado-para-expedicao': 'status-patio',
            'patio': 'status-patio',
            'entregue': 'status-entregue',
            'cancelada': 'status-cancelada',
        }

        self.modelos_tr = ["TR-60", "TR-80", "TR-80 BD", "TR-100", "TR-120", "TR-120s", "TR-150s"]

        self.create_widgets()
        self.load_tr_images()
        self.start_loading_data()
        self.parent.bind("<Configure>", self.on_resize, add="+")

    def get_db_connection(self):
        return pymysql.connect(
            host=DB_HOST, user=DB_USER, password=DB_PASS,
            database=DB_NAME, charset='utf8mb4',
            cursorclass=pymysql.cursors.DictCursor
        )

    def normalize_status_key(self, s):
        if not s: return ''
        s = str(s).strip().lower()
        # Simple normalization, can be expanded
        replacements = {'á': 'a', 'ã': 'a', 'ç': 'c', 'é': 'e', 'ê': 'e', 'í': 'i', 'ó': 'o', 'õ': 'o', 'ú': 'u'}
        for old, new in replacements.items():
            s = s.replace(old, new)
        s = s.replace(' ', '-')
        return s

    def create_widgets(self):
        # --- Filtros de Status ---
        filter_bar = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        filter_bar.pack(fill=tk.X, pady=5)

        ctk.CTkButton(filter_bar, text="ADICIONAR TR", command=self.open_equip_search_modal).pack(side=tk.LEFT, padx=10)
        
        self.status_buttons_frame = ctk.CTkFrame(filter_bar, fg_color="transparent")
        self.status_buttons_frame.pack(side=tk.LEFT, expand=True, fill=tk.X)

        # --- Canvas e Scrollbar para os Cards ---
        canvas_frame = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        canvas_frame.pack(fill=tk.BOTH, expand=True, pady=10)

        self.canvas = tk.Canvas(canvas_frame, background='#1f1f1f', highlightthickness=0)
        scrollbar = ctk.CTkScrollbar(canvas_frame, command=self.canvas.yview)
        self.scrollable_frame = ctk.CTkFrame(self.canvas, fg_color="transparent")

        self.scrollable_frame.bind(
            "<Configure>",
            lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        )

        self.canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
        self.canvas.configure(yscrollcommand=scrollbar.set)

        self.canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        self.canvas.bind("<MouseWheel>", self._on_mousewheel)

        # --- Menu de Contexto ---
        self.context_menu = tk.Menu(self.main_frame, tearoff=0)
        self.context_menu.add_command(label="Marcar como Entregue", command=lambda: self.update_context_status('ENTREGUE'))
        self.context_menu.add_command(label="Marcar como Cancelada", command=lambda: self.update_context_status('CANCELADA'))

        # --- Loading Spinner ---
        self.loading_frame = ctk.CTkFrame(self.canvas, fg_color="#1f1f1f")
        self.loading_label = ctk.CTkLabel(self.loading_frame, text="Carregando...", font=ctk.CTkFont(size=14))
        self.loading_label.pack(pady=(0, 10))
        self.loading_spinner = ctk.CTkProgressBar(self.loading_frame, mode="indeterminate")
        self.loading_spinner.pack()

    def _show_loading(self):
        self.loading_frame.place(relx=0.5, rely=0.5, anchor="center")
        self.loading_spinner.start()

    def _on_mousewheel(self, event):
        self.canvas.yview_scroll(int(-1*(event.delta/120)), "units")

    def on_resize(self, event=None):
        """Agenda a reorganização dos cards após um redimensionamento para evitar chamadas excessivas."""
        # Usar um único job de redimensionamento para todos os componentes
        if hasattr(self, '_resize_job'):
            self.main_frame.after_cancel(self._resize_job)
        self._resize_job = self.main_frame.after(250, self.rearrange_components)

    def rearrange_components(self):
        """Chama todas as funções de reorganização da UI."""
        self.rearrange_status_buttons()
        self.rearrange_cards()

    def rearrange_status_buttons(self):
        """Reorganiza os botões de filtro de status."""
        if not hasattr(self, 'status_buttons') or not self.status_buttons_frame.winfo_exists():
            return

        container_width = self.status_buttons_frame.winfo_width() - 20 # Subtrai um padding
        if container_width < 150: return

        # Estima a largura de cada botão e calcula quantas colunas cabem
        avg_button_width = 160  # Largura média estimada de um botão de status
        num_columns = max(1, container_width // avg_button_width)

        # Limpa a configuração de grid anterior para evitar que colunas antigas mantenham peso
        for i in range(self.status_buttons_frame.grid_size()[1]):
            self.status_buttons_frame.grid_columnconfigure(i, weight=0)

        for i, btn in enumerate(self.status_buttons):
            row = i // num_columns
            col = i % num_columns
            btn.grid(row=row, column=col, pady=2, padx=5, sticky="ew")
        
        # Configura as colunas atuais para se expandirem igualmente
        for i in range(num_columns):
            self.status_buttons_frame.grid_columnconfigure(i, weight=1)
        
    def rearrange_cards(self):
        """Reorganiza os cards na tela com base na largura atual."""
        if not hasattr(self, 'scrollable_frame') or not self.scrollable_frame.winfo_exists() or not hasattr(self, 'cards'):
            return

        # Garante que o frame tenha uma largura válida antes de calcular as colunas
        # CORREÇÃO: Usar a largura do canvas, não do scrollable_frame
        self.canvas.update_idletasks()
        container_width = self.canvas.winfo_width()
        if container_width < 10: return

        min_card_width = 380  # Largura mínima de um card + padding
        
        num_columns = max(1, int(container_width / min_card_width))
        
        # Reseta os pesos para todas as colunas potencialmente usadas para 0
        # Assumindo um número máximo razoável de colunas (ex: 5)
        for i in range(5): # Máximo de 5 colunas para cards
            self.scrollable_frame.grid_columnconfigure(i, weight=0)

        # Define os pesos para o número real de colunas necessárias
        for i in range(num_columns):
            self.scrollable_frame.grid_columnconfigure(i, weight=1)

        visible_cards = [card for card in self.cards if card.winfo_ismapped()]
        
        for i, card in enumerate(visible_cards):
            row = i // num_columns
            col = i % num_columns
            card.grid(row=row, column=col, padx=10, pady=10, sticky='nsew')

    def load_status_counts(self):
        for widget in self.status_buttons_frame.winfo_children():
            widget.destroy()

        try:
            conn = self.get_db_connection()
            with conn.cursor() as cursor:
                cursor.execute("SELECT status, COUNT(*) as count FROM pedidos_tr GROUP BY status")
                rows = cursor.fetchall()
        finally:
            conn.close()

        status_counts = {
            'AGUARDANDO': 0, 'EM PROGRAMAÇÃO': 0, 'A INICIAR PRODUÇÃO': 0,
            'PRODUZINDO': 0, 'ESPERANDO QUALIDADE': 0, 'PATIO': 0,
            'ENTREGUE': 0, 'CANCELADA': 0
        }
        for row in rows:
            if row['status'] and row['status'].upper() in status_counts:
                status_counts[row['status'].upper()] = row['count']

        status_map_display = {
            'AGUARDANDO': ('#cccccc', 'black'), 'EM PROGRAMAÇÃO': ('#e06666', 'black'),
            'A INICIAR PRODUÇÃO': ('#e69138', 'black'), 'PRODUZINDO': ('#f1c232', 'black'),
            'ESPERANDO QUALIDADE': ('#ffff00', 'black'), 'PATIO': ('#056b27', 'black'),
            'ENTREGUE': ('#48dfa0', 'black'), 'CANCELADA': ('#A64D79', 'black')
        }
        
        self.status_buttons = []
        
        all_btn = ctk.CTkButton(self.status_buttons_frame, text="TODOS", command=lambda: self.filter_cards('all'))
        self.status_buttons.append(all_btn)
        
        for status, (bg, fg) in status_map_display.items():
            count = status_counts.get(status, 0)
            norm_status = self.normalize_status_key(status)
            btn_text = f"{status.replace('_', ' ')} ({count})"
            btn = ctk.CTkButton(self.status_buttons_frame, text=btn_text, fg_color=bg, text_color=fg,
                                command=lambda s=norm_status: self.filter_cards(s))
            self.status_buttons.append(btn)
        
        self.rearrange_status_buttons()

    def start_loading_data(self):
        """Inicia o carregamento de todos os dados em uma thread para não bloquear a UI."""
        self._show_loading()
        # Limpa os cards antigos antes de carregar novos
        for widget in self.scrollable_frame.winfo_children():
            widget.destroy()
        self.cards = []
        
        threading.Thread(target=self._load_data_thread, daemon=True).start()

    def _load_data_thread(self):
        """Função executada na thread para carregar dados do banco."""
        self.update_all_statuses() # Atualiza status no início
        
        try:
            conn = self.get_db_connection()
            with conn.cursor() as cursor:
                sql = """
                    SELECT 
                        p.idpedido, p.numero_pedido AS pedido, ac.cliente, ac.endereco, p.data_entrega,
                        pt.idpedidos_tr, pt.status, pt.modelo, pt.montagem, pt.frete, 
                        pt.frequencia, pt.bica, pt.n_serie, pt.observacao
                    FROM pedidos_tr AS pt
                    JOIN pedido AS p ON pt.id_pedido = p.idpedido
                    JOIN add_cliente AS ac ON p.idcliente = ac.idcliente
                    ORDER BY p.idpedido DESC
                """
                cursor.execute(sql)
                pedidos = cursor.fetchall()
        finally:
            conn.close()
        
        # Agenda a atualização da UI na thread principal
        self.main_frame.after(0, self.display_loaded_data, pedidos)

    def load_pedidos_tr(self):
        for widget in self.scrollable_frame.winfo_children():
            widget.destroy()

        try:
            conn = self.get_db_connection()
            with conn.cursor() as cursor:
                sql = """
                    SELECT 
                        p.idpedido, p.numero_pedido AS pedido, ac.cliente, ac.endereco, p.data_entrega,
                        pt.idpedidos_tr, pt.status, pt.modelo, pt.montagem, pt.frete, 
                        pt.frequencia, pt.bica, pt.n_serie, pt.observacao
                    FROM pedidos_tr AS pt
                    JOIN pedido AS p ON pt.id_pedido = p.idpedido
                    JOIN add_cliente AS ac ON p.idcliente = ac.idcliente
                    ORDER BY p.idpedido DESC
                """
                cursor.execute(sql)
                pedidos = cursor.fetchall()
        finally:
            conn.close()

        self.cards = []
        for i, pedido in enumerate(pedidos):
            self.create_pedido_card(pedido, i)

    def display_loaded_data(self, pedidos):
        """Atualiza a UI com os dados carregados."""
        self.loading_spinner.stop()
        self.loading_frame.place_forget()

        self.load_status_counts() # Atualiza contadores
        
        # Limpa os cards antigos da lista e da tela
        self.cards = []
        
        for i, pedido in enumerate(pedidos):
            self.create_pedido_card(pedido, i)

    def create_pedido_card(self, pedido, index):
        raw_status = pedido.get('status', '')
        norm_key = self.normalize_status_key(raw_status)
        css_suffix = self.status_class_map.get(norm_key, 'status-default')
        bg_color, fg_color = self.get_status_colors(css_suffix)

        card = ctk.CTkFrame(self.scrollable_frame, fg_color=bg_color, border_width=2, corner_radius=8)
        # A posição será definida pela função rearrange_cards
        card.grid(row=0, column=0, padx=10, pady=10, sticky='nsew')
        card.status_tag = css_suffix
        self.cards.append(card)

        # --- Imagem da TR ---
        modelo = pedido.get('modelo')
        if modelo and modelo in self.tr_images:
            img_label = ctk.CTkLabel(card, image=self.tr_images[modelo], text="")
            img_label.pack(side=tk.LEFT, padx=10, pady=10)

        # Frame para o conteúdo à direita da imagem
        main_content_frame = ctk.CTkFrame(card, fg_color="transparent")
        main_content_frame.pack(side=tk.LEFT, fill=tk.X, expand=True)

        # --- Header ---
        header = ctk.CTkFrame(main_content_frame, fg_color="transparent")
        header.pack(fill=tk.X)

        header_content = ctk.CTkFrame(header, fg_color="transparent")
        header_content.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=10, pady=10)

        # --- Toggle Button ---
        toggle_button = ctk.CTkButton(header, text="▼", width=30)
        toggle_button.pack(side=tk.RIGHT, padx=5)

        # --- Content (collapsible) ---
        content = ctk.CTkFrame(main_content_frame, fg_color="transparent")

        # Ação do botão de toggle
        toggle_button.configure(command=lambda c=content, b=toggle_button: self.toggle_content(c, b))

        # --- Detalhes no Header ---
        ctk.CTkLabel(header_content, text=pedido['cliente'], text_color=fg_color, font=('Arial', 12, 'bold')).pack(anchor='w')
        ctk.CTkLabel(header_content, text=f"Pedido: {pedido['pedido']}", text_color=fg_color).pack(anchor='w')
        
        data_entrega = pedido['data_entrega']
        if data_entrega:
            data_formatada = data_entrega.strftime('%d/%m/%Y')
            ctk.CTkLabel(header_content, text=f"Entrega: {data_formatada}", text_color=fg_color).pack(anchor='w')

        ctk.CTkLabel(header_content, text=f"Endereço: {pedido['endereco']}", text_color=fg_color).pack(anchor='w')
        ctk.CTkLabel(header_content, text=f"Modelo: {pedido['modelo']}", text_color=fg_color).pack(anchor='w')

        details = {
            "Montagem": pedido.get('montagem'), "Frete": pedido.get('frete'),
            "Status": pedido.get('status'), "Frequência": pedido.get('frequencia'),
            "Bica": pedido.get('bica'), "N° de Série": pedido.get('n_serie'),
            "Observação": pedido.get('observacao')
        }

        for i, (label, value) in enumerate(details.items()):
            ctk.CTkLabel(content, text=f"{label}:", font=('Arial', 9, 'bold'), text_color=fg_color).grid(row=i, column=0, sticky='w', pady=2)
            val_label = ctk.CTkLabel(content, text=value or 'N/A', wraplength=250, text_color=fg_color)
            val_label.grid(row=i, column=1, sticky='w', padx=5)
            if label == "Status":
                val_label.bind("<Button-3>", lambda e, p=pedido: self.show_context_menu(e, p))

        # Botão de editar, agora dentro do frame de conteúdo
        edit_button_frame = ctk.CTkFrame(content, fg_color="transparent")
        edit_button_frame.grid(row=len(details), columnspan=2, pady=10)

        # --- Edit Link ---
        ctk.CTkButton(edit_button_frame, text="Editar", command=lambda p=pedido: self.open_edit_modal(p)).pack()

    def open_edit_modal(self, pedido_data):
        """Abre uma janela modal para editar os detalhes de um pedido da trilhadeira."""
        modal = ctk.CTkToplevel(self.main_frame)
        modal.title(f"Editar TR - Pedido {pedido_data['pedido']}")
        self.center_window(modal, 500, 480) # Aumentei um pouco a altura
        modal.grab_set()

        frame = ctk.CTkFrame(modal)
        frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        entries = {}
        fields_to_edit = {
            "modelo": {"label": "Modelo:", "type": "combo", "values": self.modelos_tr},
            "n_serie": {"label": "N° de Série:", "type": "entry"},
            "montagem": {"label": "Montagem:", "type": "combo", "values": ["SMA", "CLIENTE"]},
            "frete": {"label": "Frete:", "type": "combo", "values": ["SMA", "CLIENTE"]},
            "frequencia": {"label": "Frequência:", "type": "combo", "values": ["50Hz", "60Hz"]},
            "bica": {"label": "Bica:", "type": "combo", "values": ["BICA SIMPLES", "BICA DUPLA"]},
            "observacao": {"label": "Observação:", "type": "entry"},
        }

        # Adiciona o status (apenas leitura)
        ctk.CTkLabel(frame, text="Status (Automático):").grid(row=len(fields_to_edit), column=0, sticky='w', padx=10, pady=5)
        status_entry = ctk.CTkEntry(frame, width=250, state="disabled")
        status_entry.insert(0, str(pedido_data.get('status') or ''))
        status_entry.grid(row=len(fields_to_edit), column=1, sticky='ew', padx=10, pady=5)

        for i, (field_name, config) in enumerate(fields_to_edit.items()):
            ctk.CTkLabel(frame, text=config["label"]).grid(row=i, column=0, sticky='w', padx=10, pady=5)
            
            current_value = pedido_data.get(field_name)

            if config["type"] == "combo":
                combo = ctk.CTkComboBox(frame, values=config.get("values", []), width=250, state="readonly")
                # Garante que o valor atual esteja na lista antes de setar
                if current_value and current_value in config.get("values", []):
                    combo.set(current_value)
                else:
                    combo.set('') # Deixa em branco se não for um valor válido
                combo.grid(row=i, column=1, sticky='ew', padx=10, pady=5)
                entries[field_name] = combo
            else:
                entry = ctk.CTkEntry(frame, width=250)
                entry.insert(0, str(current_value or ''))
                entry.grid(row=i, column=1, sticky='ew', padx=10, pady=5)
                entries[field_name] = entry

        def save_changes():
            # Coleta os dados na ordem correta para a query SQL
            updated_data_list = []
            sql_field_order = ["modelo", "montagem", "frete", "frequencia", "bica", "n_serie", "observacao"]
            
            for field_name in sql_field_order:
                widget = entries[field_name]
                value = widget.get()
                # Trata campos vazios como NULL no banco
                if isinstance(widget, ctk.CTkComboBox) and not value:
                    updated_data_list.append(None)
                else:
                    updated_data_list.append(value)

            id_tr = pedido_data['idpedidos_tr']

            try:
                conn = self.get_db_connection()
                with conn.cursor() as cursor:
                    sql = """
                        UPDATE pedidos_tr SET
                        modelo = %s, montagem = %s, frete = %s, frequencia = %s,
                        bica = %s, n_serie = %s, observacao = %s
                        WHERE idpedidos_tr = %s
                    """
                    params = updated_data_list + [id_tr]
                    cursor.execute(sql, params)
                conn.commit()
                messagebox.showinfo("Sucesso", "Dados da TR atualizados com sucesso!", parent=modal)
                modal.destroy()
                self.start_loading_data() # Recarrega os cards com spinner
            except Exception as e:
                messagebox.showerror("Erro", f"Falha ao salvar alterações: {e}", parent=modal)
            finally:
                if conn:
                    conn.close()

        button_frame = ctk.CTkFrame(frame, fg_color="transparent")
        button_frame.grid(row=len(fields_to_edit) + 1, column=0, columnspan=2, pady=20)
        ctk.CTkButton(button_frame, text="Salvar Alterações", command=save_changes).pack(side=tk.LEFT, padx=10)
        ctk.CTkButton(button_frame, text="Cancelar", command=modal.destroy).pack(side=tk.LEFT, padx=10)
        
    def load_tr_images(self):
        """Carrega as imagens dos modelos de TR da pasta img/."""
        self.tr_images = {}
        # Tenta com .png e .jpg
        extensions = ['.png', '.jpg', '.jpeg']
        
        for modelo in self.modelos_tr:
            final_img_path = None
            # Transforma 'TR-80 BD' em 'TR-80_BD' para o nome do arquivo
            filename_base = modelo.replace(' ', '_')
            for ext in extensions:
                # Usa resource_path para encontrar a imagem
                img_path = resource_path(os.path.join('img', f"{filename_base}{ext}"))
                if os.path.exists(img_path):
                    final_img_path = img_path
                    break
            
            if final_img_path:
                pil_image = Image.open(final_img_path)
                self.tr_images[modelo] = ctk.CTkImage(light_image=pil_image, size=(100, 100))

    def toggle_content(self, content_frame, button):
        if content_frame.winfo_ismapped():
            content_frame.pack_forget()
            button.configure(text="▼")
        else:
            content_frame.pack(fill=tk.X, padx=5, pady=5)
            button.configure(text="▲")

    def filter_cards(self, status_to_show):
        visible_cards_count = 0
        for card in self.cards:
            if status_to_show == 'all' or card.status_tag == f'status-{status_to_show}':
                card.grid()
            else:
                card.grid_remove()

        self.rearrange_cards()

    def show_context_menu(self, event, pedido):
        self.context_menu_pedido_id = pedido['idpedidos_tr']
        self.context_menu.post(event.x_root, event.y_root)

    def update_context_status(self, new_status):
        if not self.context_menu_pedido_id:
            return
        
        if not messagebox.askyesno("Confirmar", f"Deseja alterar o status para '{new_status}'?"):
            return

        try:
            conn = self.get_db_connection()
            with conn.cursor() as cursor:
                cursor.execute("UPDATE pedidos_tr SET status = %s WHERE idpedidos_tr = %s", 
                               (new_status, self.context_menu_pedido_id))
            conn.commit()
            messagebox.showinfo("Sucesso", "Status atualizado com sucesso!")
            self.start_loading_data() # Recarrega tudo
        except Exception as e:
            messagebox.showerror("Erro", f"Falha ao atualizar status: {e}")
        finally:
            if conn:
                conn.close()

    def update_all_statuses(self):
        """Port da lógica de atualização automática de status do PHP."""
        try:
            conn = self.get_db_connection()
            with conn.cursor() as cursor:
                # 1. Obter todos os pedidos_tr com seus vinculos e status de produção dos itens em uma única query
                sql = """
                    SELECT 
                        pt.idpedidos_tr, 
                        pt.status AS current_tr_status,
                        ci.status_producao
                    FROM pedidos_tr pt
                    JOIN cliente_item ci 
                        ON FIND_IN_SET(ci.id_item, REPLACE(pt.vinculos_item, ';', ','))
                    WHERE pt.vinculos_item IS NOT NULL AND pt.vinculos_item != ''
                """
                cursor.execute(sql)
                results = cursor.fetchall()

            # 2. Agrupar os status de produção por idpedidos_tr
            statuses_by_pedido = {}
            for row in results:
                pedido_id = row['idpedidos_tr']
                if pedido_id not in statuses_by_pedido:
                    statuses_by_pedido[pedido_id] = {
                        'current_status': row['current_tr_status'],
                        'item_statuses': []
                    }
                if row['status_producao']:
                    statuses_by_pedido[pedido_id]['item_statuses'].append(row['status_producao'])

            # 3. Determinar o novo status para cada pedido e preparar updates
            updates_to_perform = []
            for pedido_id, data in statuses_by_pedido.items():
                # Se não houver itens com status, não faz nada com este pedido.
                # Isso evita que um pedido sem itens vinculados tenha seu status alterado indevidamente.
                if not data.get('item_statuses'):
                    continue

                # Normaliza os status dos itens para comparação
                norm_statuses = {self.normalize_status_key(s) for s in data['item_statuses']}

                # Padrão é manter o status atual, a menos que uma regra seja atendida.
                novo_status_tr = data['current_status']

                # --- Nova Lógica de Prioridade ---
                # A ordem dos 'if/elif' define a prioridade.
                # Se qualquer item estiver 'Aguardando Programação', o status da TR é 'EM PROGRAMAÇÃO'.
                if 'aguardando-programacao' in norm_statuses:
                    novo_status_tr = 'EM PROGRAMAÇÃO'
                # Se não houver nenhum 'Aguardando Programação', mas houver algum 'Aguardando PCP',
                # o status da TR é 'A INICIAR PRODUÇÃO'.
                elif 'aguardando-pcp' in norm_statuses:
                    novo_status_tr = 'A INICIAR PRODUÇÃO'
                # E assim por diante, seguindo a hierarquia do processo de produção.
                elif 'em-producao' in norm_statuses or 'produzindo' in norm_statuses:
                    novo_status_tr = 'PRODUZINDO'
                elif 'producao-finalizada' in norm_statuses or 'esperando-qualidade' in norm_statuses:
                    novo_status_tr = 'ESPERANDO QUALIDADE'
                elif 'liberado-para-expedicao' in norm_statuses or 'patio' in norm_statuses:
                    novo_status_tr = 'PATIO'
                # Se todos os itens estiverem 'Entregue', o status da TR se torna 'ENTREGUE'.
                elif norm_statuses == {'entregue'}:
                    novo_status_tr = 'ENTREGUE'
                # Se todos os itens estiverem 'Cancelada', o status da TR se torna 'CANCELADA'.
                elif norm_statuses == {'cancelada'}:
                    novo_status_tr = 'CANCELADA'
                else:
                    # Se nenhuma das condições acima for atendida (ex: status mistos em fases avançadas),
                    # o status da TR não é alterado.
                    pass

                # Adicionar à lista de updates se o status mudou
                # e se o novo status não for nulo ou vazio.
                if novo_status_tr and (data['current_status'] is None or novo_status_tr.strip().upper() != data['current_status'].strip().upper()):
                    updates_to_perform.append((novo_status_tr, pedido_id))

            # 4. Executar todos os updates de uma vez
            if updates_to_perform:
                with conn.cursor() as cursor_update:
                    cursor_update.executemany("UPDATE pedidos_tr SET status = %s WHERE idpedidos_tr = %s", updates_to_perform)
            conn.commit()
        except Exception as e:
            print(f"Erro ao atualizar status em lote: {e}")
        finally:
            if conn:
                conn.close()

    def center_window(self, window, width, height):
        window.update_idletasks()
        screen_width = window.winfo_screenwidth()
        screen_height = window.winfo_screenheight()
        x = (screen_width / 2) - (width / 2)
        y = (screen_height / 2) - (height / 2)
        window.geometry(f'{width}x{height}+{int(x)}+{int(y)}')

    # --- Funcionalidade do Modal de Busca por Equipamento ---
    def open_equip_search_modal(self):
        self.modal = ctk.CTkToplevel(self.main_frame)
        self.modal.title("Adicionar TR por Equipamento")
        self.center_window(self.modal, 1200, 800)
        self.modal.grab_set()

        modal_main_frame = ctk.CTkFrame(self.modal, fg_color="transparent")
        modal_main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # --- Widgets do Modal ---
        top_frame = ctk.CTkFrame(modal_main_frame, fg_color="transparent")
        top_frame.pack(fill=tk.X, pady=(0, 10))

        ctk.CTkLabel(top_frame, text="Equipamentos:").pack(side=tk.LEFT, padx=5)
        
        # Carregar equipamentos
        try:
            conn = self.get_db_connection()
            with conn.cursor() as cursor:
                # Alterado para buscar da tabela 'itens' que são pais em 'item_composicao'
                sql = """
                    SELECT DISTINCT i.id, i.descricao FROM itens i
                    JOIN item_composicao ic ON i.id = ic.id_item_pai
                    ORDER BY i.descricao ASC
                """
                cursor.execute(sql)
                equipamentos_data = cursor.fetchall()
        finally:
            conn.close()

        # --- NOVO: Listbox para seleção de equipamentos ---
        listbox_frame = ctk.CTkFrame(top_frame)
        listbox_frame.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)

        list_scrollbar = ctk.CTkScrollbar(listbox_frame)
        list_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.equip_listbox = tk.Listbox(
            listbox_frame,
            selectmode=tk.EXTENDED,  # Permite seleção múltipla
            yscrollcommand=list_scrollbar.set,
            height=5,  # Altura da lista em número de itens
            bg="#2b2b2b", fg="white", selectbackground="#00529B", highlightthickness=0, borderwidth=0
        )
        self.equip_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        list_scrollbar.configure(command=self.equip_listbox.yview)

        # Guarda um mapa do texto para o ID para facilitar a busca
        self.equip_listbox_map = {}
        for e in equipamentos_data:
            display_text = f"({e['id']}) {e['descricao']}"
            self.equip_listbox.insert(tk.END, display_text)
            self.equip_listbox_map[display_text] = e['id']

        ctk.CTkButton(top_frame, text="Buscar", command=self.search_by_equip).pack(side=tk.LEFT, padx=10)
        ctk.CTkButton(top_frame, text="Limpar", command=self.clear_equip_search).pack(side=tk.LEFT, padx=5)

        self.search_status_label = ctk.CTkLabel(top_frame, text="")
        self.search_status_label.pack(side=tk.LEFT, padx=10)

        # --- Resultados da Busca ---
        results_canvas_frame = ctk.CTkFrame(modal_main_frame)
        results_canvas_frame.pack(fill=tk.BOTH, expand=True)

        self.results_canvas = tk.Canvas(results_canvas_frame, background='#1f1f1f', highlightthickness=0)
        results_scrollbar = ctk.CTkScrollbar(results_canvas_frame, command=self.results_canvas.yview)
        self.results_scrollable_frame = ctk.CTkFrame(self.results_canvas, fg_color="transparent")

        self.results_scrollable_frame.bind(
            "<Configure>",
            lambda e: self.results_canvas.configure(scrollregion=self.results_canvas.bbox("all"))
        )

        self.results_canvas.create_window((0, 0), window=self.results_scrollable_frame, anchor="nw")
        self.results_canvas.configure(yscrollcommand=results_scrollbar.set)

        self.results_canvas.pack(side="left", fill="both", expand=True)
        results_scrollbar.pack(side="right", fill="y")

    def search_by_equip(self):
        # Obtém os IDs dos itens selecionados na Listbox
        selected_indices = self.equip_listbox.curselection()
        selected_texts = [self.equip_listbox.get(i) for i in selected_indices]
        selected_ids = [self.equip_listbox_map[text] for text in selected_texts]

        if not selected_ids:
            messagebox.showwarning("Aviso", "Selecione ao menos um equipamento.", parent=self.modal)
            return

        self.search_status_label.configure(text="Buscando...")
        self.main_frame.update_idletasks()

        try: # type: ignore
            conn = self.get_db_connection()
            with conn.cursor() as cursor:
                placeholders = ','.join(['%s'] * len(selected_ids))
                sql = f"""
                    SELECT
                        p.idpedido,
                        p.numero_pedido AS pedido,
                        ac.idcliente,
                        ac.cliente,
                        ac.endereco,
                        pi.id AS equipamento_id,
                        pi.descricao AS equipamento_pai,
                        si.descricao AS conjunto,
                        ci.id_item AS id_vinculo,
                        ci.quantidade_prod
                    FROM cliente_item ci
                    JOIN pedido p ON ci.idpedido = p.idpedido
                    JOIN add_cliente ac ON p.idcliente = ac.idcliente
                    JOIN itens pi ON ci.item_raiz_id = pi.id
                    JOIN itens si ON ci.id_item_fk = si.id
                    WHERE ci.item_raiz_id IN ({placeholders})
                    ORDER BY p.idpedido DESC, pi.descricao
                """
                cursor.execute(sql, selected_ids)
                results = cursor.fetchall()
        finally:
            conn.close()

        # Agrupar resultados
        clientes = {}
        for row in results:
            idcliente = row['idcliente']
            if idcliente not in clientes:
                clientes[idcliente] = {
                    'idcliente': idcliente, 'pedido': row['pedido'], 'cliente': row['cliente'], 'idpedido': row['idpedido'],
                    'equipamentos': {}
                }
            
            equipamento_id = row['equipamento_id']
            if equipamento_id not in clientes[idcliente]['equipamentos']:
                clientes[idcliente]['equipamentos'][equipamento_id] = {
                    'equipamento_id': equipamento_id, 'equipamento_pai': row['equipamento_pai'],
                    'itens': []
                }
            
            clientes[idcliente]['equipamentos'][equipamento_id]['itens'].append(row)

        self.display_equip_search_results(list(clientes.values()))
        self.search_status_label.configure(text=f"{len(clientes)} clientes encontrados.")

    def display_equip_search_results(self, clientes_data):
        for widget in self.results_scrollable_frame.winfo_children():
            widget.destroy()

        if not clientes_data:
            ctk.CTkLabel(self.results_scrollable_frame, text="Nenhum resultado encontrado.").pack(pady=20)
            return

        # Configura o grid para os cards
        self.results_scrollable_frame.columnconfigure(0, weight=1)

        for cliente in clientes_data:
            cliente_card = ctk.CTkFrame(self.results_scrollable_frame, border_width=1)
            cliente_card.pack(fill=tk.X, pady=5, expand=True)
            ctk.CTkLabel(cliente_card, text=f"{cliente['cliente']} (Pedido: {cliente['pedido']})", font=('Arial', 12, 'bold')).pack(anchor='w', padx=10, pady=(5,0))
            
            for equip_id, equip in cliente['equipamentos'].items():
                equip_frame = ctk.CTkFrame(cliente_card, fg_color="transparent")
                equip_frame.pack(fill=tk.X, pady=5)

                top_row = ctk.CTkFrame(equip_frame, fg_color="transparent")
                top_row.pack(fill=tk.X)

                ctk.CTkLabel(top_row, text=f"Equipamento: {equip['equipamento_pai']}", font=('Arial', 10, 'bold')).pack(side=tk.LEFT, padx=(10,0))

                # Modelo e botão de registro
                action_frame = ctk.CTkFrame(top_row, fg_color="transparent")
                action_frame.pack(side=tk.RIGHT)
                
                modelo_combo = ctk.CTkComboBox(action_frame, values=self.modelos_tr, width=150, state="readonly")
                modelo_combo.pack(side=tk.LEFT, padx=5)

                reg_btn = ctk.CTkButton(action_frame, text="Registrar", 
                                        command=lambda p=cliente['idpedido'], e=equip_id, m=modelo_combo: self.register_model_for_equip(p, e, m))
                reg_btn.pack(side=tk.LEFT)

                # Itens (conjuntos)
                itens_frame = ctk.CTkFrame(equip_frame, fg_color="transparent")
                itens_frame.pack(fill=tk.X)
                for item in equip['itens']: 
                    ctk.CTkLabel(itens_frame, text=f"- {item['conjunto']} (Qtd: {item['quantidade_prod']})").pack(anchor='w', padx=(30,0))

    def register_model_for_equip(self, pedido_id, equip_id, modelo_combo):
        modelo = modelo_combo.get()
        if not modelo:
            messagebox.showwarning("Aviso", "Selecione um modelo para registrar.", parent=self.modal)
            return

        if not messagebox.askyesno("Confirmar", f"Registrar o modelo '{modelo}' para este equipamento?", parent=self.modal):
            return

        conn = self.get_db_connection()
        try:
            with conn.cursor() as cursor:
                # 1. Encontrar todos os id_vinculo para este pedido e equipamento (item_raiz)
                sql_find_vinculos = """
                    SELECT ci.id_item FROM cliente_item ci
                    WHERE ci.idpedido = %s AND ci.item_raiz_id = %s
                """
                cursor.execute(sql_find_vinculos, (pedido_id, equip_id))
                vinculos = cursor.fetchall()
                if not vinculos:
                    messagebox.showerror("Erro", "Nenhum item (vínculo) encontrado para este cliente e equipamento.", parent=self.modal)
                    return

                todos_vinculos_ids = [v['id_item'] for v in vinculos]
                id_vinculo_principal = todos_vinculos_ids[0]
                vinculos_item_string = ';'.join(map(str, todos_vinculos_ids))

                # 2. Verificar se algum vínculo já existe
                check_conditions = " OR ".join([f"FIND_IN_SET(%s, REPLACE(vinculos_item, ';', ','))" for _ in todos_vinculos_ids])
                sql_check = f"SELECT idpedidos_tr FROM pedidos_tr WHERE {check_conditions}"
                cursor.execute(sql_check, todos_vinculos_ids)
                if cursor.fetchone():
                    messagebox.showerror("Erro", "Um ou mais itens deste equipamento já foram inseridos na trilhadeira.", parent=self.modal)
                    return

                # 3. Inserir
                sql_insert = "INSERT INTO pedidos_tr (id_pedido, modelo, id_vinculo, vinculos_item) VALUES (%s, %s, %s, %s)"
                cursor.execute(sql_insert, (pedido_id, modelo, id_vinculo_principal, vinculos_item_string))
                conn.commit()

                messagebox.showinfo("Sucesso", "Registro inserido com sucesso!", parent=self.modal)
                self.modal.destroy()
                # Recarregar tela principal com spinner
                self.start_loading_data()

        except Exception as e:
            messagebox.showerror("Erro", f"Falha ao registrar: {e}", parent=self.modal)
        finally:
            conn.close()

    def clear_equip_search(self):
        self.equip_listbox.selection_clear(0, tk.END)
        for widget in self.results_scrollable_frame.winfo_children():
            widget.destroy()
        self.search_status_label.configure(text="")

    def get_status_colors(self, status_name):
        """Retorna um par de cores (background, foreground) para um status."""
        status_styles = {
            'status-em-programacao': ('#e06666', 'black'),
            'status-a-iniciar-producao': ('#e69138', 'black'),
            'status-produzindo': ('#f1c232', 'black'),
            'status-esperando-qualidade': ('#ffff00', 'black'),
            'status-patio': ('#056b27', 'white'),
            'status-entregue': ('#48dfa0', 'black'),
            'status-cancelada': ('#A64D79', 'black'),
            'status-default': ('#cccccc', 'black')
        }
        return status_styles.get(status_name, ('#cccccc', 'black'))

if __name__ == '__main__':
    root = tk.Tk()
    root.title("Teste Trilhadeira App")
    # Mock user object for testing
    mock_user = {'id': 1, 'username': 'test', 'role': 'admin'}
    app = TrilhadeiraApp(root, mock_user)
    root.mainloop()