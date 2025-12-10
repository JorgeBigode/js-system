import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import os
import json
from PIL import Image, ImageTk
import shutil
import threading

UPLOADS_DIR = "uploads"

class GaleriaApp:
    def __init__(self, parent, user):
        self.parent = parent
        self.user = user
        self.frame = ttk.Frame(parent)
        self.frame.pack(fill=tk.BOTH, expand=True)

        # Garante que o diretório de uploads exista
        if not os.path.exists(UPLOADS_DIR):
            os.makedirs(UPLOADS_DIR)

        self.image_references = [] # Para manter as referências das imagens

        self.create_widgets()
        self.start_loading_gallery()

    def create_widgets(self):
        # --- Frame Superior (Busca e Upload) ---
        top_frame = ttk.Frame(self.frame)
        top_frame.pack(padx=10, pady=10, fill=tk.X)

        self.search_var = tk.StringVar()
        search_entry = ttk.Entry(top_frame, textvariable=self.search_var, width=50)
        search_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 10))
        search_entry.insert(0, "Pesquisar por Pedido, Cliente ou Conjunto...")
        search_entry.bind("<FocusIn>", lambda e: e.widget.delete(0, tk.END) if e.widget.get() == "Pesquisar por Pedido, Cliente ou Conjunto..." else None)
        search_entry.bind("<FocusOut>", lambda e: e.widget.insert(0, "Pesquisar por Pedido, Cliente ou Conjunto...") if not e.widget.get() else None)

        upload_btn = ttk.Button(top_frame, text="Enviar Fotos", command=self.open_upload_modal)
        upload_btn.pack(side=tk.RIGHT)

        # --- Frame da Galeria (Scrollable) ---
        gallery_container = ttk.Frame(self.frame)
        gallery_container.pack(padx=10, pady=10, fill=tk.BOTH, expand=True)

        self.canvas = tk.Canvas(gallery_container)
        scrollbar = ttk.Scrollbar(gallery_container, orient="vertical", command=self.canvas.yview)
        self.scrollable_frame = ttk.Frame(self.canvas)

        self.scrollable_frame.bind(
            "<Configure>",
            lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        )

        self.canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
        self.canvas.configure(yscrollcommand=scrollbar.set)

        self.canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        self.canvas.bind_all("<MouseWheel>", self._on_mousewheel)

        # Adiciona o trace aqui, depois que todos os widgets foram criados
        self.search_var.trace_add("write", self.filter_gallery)

    def _on_mousewheel(self, event):
        self.canvas.yview_scroll(int(-1*(event.delta/120)), "units")

    def start_loading_gallery(self):
        """Exibe o indicador de carregamento e inicia o carregamento dos dados em uma thread."""
        # Limpa o frame
        for widget in self.scrollable_frame.winfo_children():
            widget.destroy()

        # Mostra o indicador de carregamento
        self.loading_label = ttk.Label(self.scrollable_frame, text="Carregando galeria...", font=('Arial', 12))
        self.loading_label.pack(pady=20)
        self.progress_bar = ttk.Progressbar(self.scrollable_frame, mode='indeterminate')
        self.progress_bar.pack(pady=10, padx=20, fill=tk.X)
        self.progress_bar.start()

        # Inicia o carregamento em uma thread para não travar a UI
        threading.Thread(target=self.load_gallery, daemon=True).start()

    def load_gallery(self):
        """Carrega os dados das imagens e agenda a atualização da UI."""
        all_images = [f for f in os.listdir(UPLOADS_DIR) if f.lower().endswith(('.png', '.jpg', '.jpeg', '.gif'))]
        images_by_pedido = {}

        for img_name in all_images:
            json_path = os.path.join(UPLOADS_DIR, os.path.splitext(img_name)[0] + '.json')
            if os.path.exists(json_path):
                with open(json_path, 'r', encoding='utf-8') as f:
                    info = json.load(f)
                    pedido = info.get('pedido', 'Sem Pedido')
                    if pedido not in images_by_pedido:
                        images_by_pedido[pedido] = []
                    images_by_pedido[pedido].append({'path': os.path.join(UPLOADS_DIR, img_name), 'info': info})

        # Agenda a atualização da interface gráfica na thread principal
        self.frame.after(0, self.update_gallery_ui, images_by_pedido)

    def update_gallery_ui(self, images_by_pedido):
        """Atualiza a interface com os cards da galeria (executado na thread principal)."""
        # Para o indicador de carregamento e o remove
        self.progress_bar.stop()
        self.loading_label.destroy()
        self.progress_bar.destroy()

        # Limpa referências antigas
        self.image_references.clear()

        # Ordena os pedidos
        sorted_pedidos = sorted(images_by_pedido.keys())

        col, row = 0, 0
        max_cols = 4 # 4 cards por linha
        for pedido in sorted_pedidos:
            if images_by_pedido[pedido]:
                self.create_pedido_card(self.scrollable_frame, images_by_pedido[pedido], row, col)
                col = (col + 1) % max_cols
                if col == 0:
                    row += 1

    def create_pedido_card(self, parent, pedido_images, r, c):
        if not pedido_images:
            return

        first_image_data = pedido_images[0]
        info = first_image_data['info']
        pedido = info.get('pedido', 'N/A')
        cliente = info.get('cliente', 'N/A')

        card_frame = ttk.LabelFrame(parent, text=f"Pedido: {pedido}")
        card_frame.grid(row=r, column=c, padx=10, pady=10, sticky="nsew")
        # Atribuindo dados para a busca
        card_frame.data_pedido = pedido
        card_frame.data_cliente = cliente
        card_frame.data_conjuntos = [img['info'].get('conjunto', '') for img in pedido_images]

        try:
            img = Image.open(first_image_data['path'])
            img.thumbnail((200, 200))
            photo = ImageTk.PhotoImage(img)
            self.image_references.append(photo)

            img_label = ttk.Label(card_frame, image=photo)
            img_label.pack(padx=10, pady=10)

        except Exception as e:
            img_label = ttk.Label(card_frame, text="Erro ao carregar imagem")
            img_label.pack(padx=10, pady=10)
            print(f"Erro ao carregar imagem de capa para pedido {pedido}: {e}")

        ttk.Label(card_frame, text=f"Cliente: {cliente}", anchor="center").pack(fill=tk.X, padx=10)
        ttk.Label(card_frame, text=f"{len(pedido_images)} foto(s)", anchor="center").pack(fill=tk.X, padx=10)

        view_btn = ttk.Button(card_frame, text="Ver Galeria", command=lambda p=pedido_images, i=info: self.open_pedido_gallery(p, i))
        view_btn.pack(pady=10, padx=10)

    def open_pedido_gallery(self, images, info):
        win = tk.Toplevel(self.frame)
        win.title(f"Galeria - Pedido: {info.get('pedido')} | Cliente: {info.get('cliente')}")
        win.geometry("800x650")
        win.transient(self.frame)
        win.grab_set()

        # --- Layout do Visualizador ---
        # Frame principal
        main_frame = ttk.Frame(win)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Frame para informações e controles (agora na parte de baixo)
        controls_frame = ttk.Frame(main_frame)
        controls_frame.pack(side=tk.BOTTOM, fill=tk.X, pady=(5, 0))

        # Frame para a imagem
        image_frame = ttk.Frame(main_frame, relief=tk.SUNKEN, borderwidth=2)
        image_frame.pack(fill=tk.BOTH, expand=True)
        image_label = ttk.Label(image_frame)
        image_label.pack(fill=tk.BOTH, expand=True)

        # --- Variáveis de estado ---
        current_index = tk.IntVar(value=0)
        win.image_references = [] # Para evitar que o garbage collector apague a imagem

        # --- Widgets de Controle ---
        prev_btn = ttk.Button(controls_frame, text="<< Anterior")
        info_label = ttk.Label(controls_frame, text="", anchor="center", font=('Arial', 10))
        next_btn = ttk.Button(controls_frame, text="Próxima >>")
        delete_btn = ttk.Button(controls_frame, text="Excluir Foto")

        prev_btn.pack(side=tk.LEFT, padx=10)
        info_label.pack(side=tk.LEFT, fill=tk.X, expand=True)
        delete_btn.pack(side=tk.RIGHT, padx=10)
        next_btn.pack(side=tk.RIGHT)

        def show_image(index):
            # Atualiza o índice
            current_index.set(index)
            
            # Pega os dados da imagem
            img_data = images[index]
            img_path = img_data['path']
            img_info = img_data['info']

            # Carrega e redimensiona a imagem
            try:
                img = Image.open(img_path)
                # Redimensiona mantendo a proporção para caber no frame
                img.thumbnail((image_frame.winfo_width(), image_frame.winfo_height()))
                photo = ImageTk.PhotoImage(img)
                
                image_label.config(image=photo)
                win.image_references.clear()
                win.image_references.append(photo)
            except Exception as e:
                image_label.config(text=f"Erro ao carregar imagem:\n{os.path.basename(img_path)}", image='')
                print(f"Erro ao carregar imagem {img_path}: {e}")

            # Atualiza o label de informações
            info_text = (f"Foto {index + 1} de {len(images)} | "
                         f"Conjunto: {img_info.get('conjunto', 'N/A')} | "
                         f"Lote: {img_info.get('lote', 'N/A')}")
            info_label.config(text=info_text)

            # Atualiza o estado dos botões
            prev_btn.config(state=tk.NORMAL if index > 0 else tk.DISABLED)
            next_btn.config(state=tk.NORMAL if index < len(images) - 1 else tk.DISABLED)

        def navigate(direction):
            new_index = current_index.get() + direction
            if 0 <= new_index < len(images):
                show_image(new_index)

        def delete_current_image():
            index_to_delete = current_index.get()
            img_path_to_delete = images[index_to_delete]['path']
            self.delete_image(img_path_to_delete, win)

        # Configura os comandos dos botões
        prev_btn.config(command=lambda: navigate(-1))
        next_btn.config(command=lambda: navigate(1))
        delete_btn.config(command=delete_current_image)

        # Função para carregar a primeira imagem após a janela ser desenhada
        def initial_load(event=None):
            # Garante que o frame da imagem tenha um tamanho antes de carregar
            win.update_idletasks() 
            show_image(0)

        # Carrega a primeira imagem
        win.bind('<Map>', initial_load, add='+')

    def delete_image(self, img_path, toplevel_to_close):
        if messagebox.askyesno("Confirmar Exclusão", f"Tem certeza que deseja excluir a imagem e suas informações?\n\n{os.path.basename(img_path)}"):
            try:
                json_path = os.path.splitext(img_path)[0] + '.json'
                if os.path.exists(img_path):
                    os.remove(img_path)
                if os.path.exists(json_path):
                    os.remove(json_path)
                
                messagebox.showinfo("Sucesso", "Imagem excluída com sucesso.")
                toplevel_to_close.destroy() # Fecha a janela de detalhes
                self.start_loading_gallery() # Recarrega a galeria principal com indicador
            except Exception as e:
                messagebox.showerror("Erro", f"Não foi possível excluir a imagem: {e}")

    def open_upload_modal(self):
        self.upload_win = tk.Toplevel(self.frame)
        self.upload_win.title("Enviar Novas Fotos")
        self.upload_win.geometry("450x450")
        self.upload_win.transient(self.frame)
        self.upload_win.grab_set()

        main_frame = ttk.Frame(self.upload_win, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Campos do formulário
        ttk.Label(main_frame, text="Pedido:").pack(anchor='w')
        self.pedido_entry = ttk.Entry(main_frame)
        self.pedido_entry.pack(fill=tk.X, pady=(0, 10))

        ttk.Label(main_frame, text="Cliente:").pack(anchor='w')
        self.cliente_entry = ttk.Entry(main_frame)
        self.cliente_entry.pack(fill=tk.X, pady=(0, 10))

        ttk.Label(main_frame, text="Conjunto:").pack(anchor='w')
        self.conjunto_entry = ttk.Entry(main_frame)
        self.conjunto_entry.pack(fill=tk.X, pady=(0, 10))

        ttk.Label(main_frame, text="Lote:").pack(anchor='w')
        self.lote_entry = ttk.Entry(main_frame)
        self.lote_entry.pack(fill=tk.X, pady=(0, 10))

        # Seleção de arquivos
        file_frame = ttk.Frame(main_frame)
        file_frame.pack(fill=tk.X, pady=(10, 10))
        self.file_label = ttk.Label(file_frame, text="Nenhum arquivo selecionado")
        self.file_label.pack(side=tk.LEFT, fill=tk.X, expand=True)
        browse_btn = ttk.Button(file_frame, text="Selecionar Fotos", command=self.browse_files)
        browse_btn.pack(side=tk.RIGHT)
        self.selected_files = []

        # Botões
        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(side=tk.BOTTOM, fill=tk.X, pady=(10, 0))
        
        cancel_btn = ttk.Button(btn_frame, text="Cancelar", command=self.upload_win.destroy)
        cancel_btn.pack(side=tk.RIGHT, padx=(5, 0))
        
        submit_btn = ttk.Button(btn_frame, text="Enviar", command=self.submit_upload)
        submit_btn.pack(side=tk.RIGHT)

    def browse_files(self):
        files = filedialog.askopenfilenames(
            title="Selecione as imagens",
            filetypes=[("Imagens", "*.jpg *.jpeg *.png *.gif"), ("Todos os arquivos", "*.*")]
        )
        if files:
            self.selected_files = files
            self.file_label.config(text=f"{len(files)} arquivo(s) selecionado(s)")

    def submit_upload(self):
        pedido = self.pedido_entry.get().strip()
        cliente = self.cliente_entry.get().strip()
        conjunto = self.conjunto_entry.get().strip()
        lote = self.lote_entry.get().strip()

        if not all([pedido, cliente, conjunto, self.selected_files]):
            messagebox.showwarning("Campos Obrigatórios", "Pedido, Cliente, Conjunto e ao menos uma foto são obrigatórios.", parent=self.upload_win)
            return

        info = {
            "pedido": pedido,
            "cliente": cliente,
            "conjunto": conjunto,
            "lote": lote
        }

        try:
            for file_path in self.selected_files:
                filename = os.path.basename(file_path)
                # Evitar sobreposição de nomes
                base, ext = os.path.splitext(filename)
                new_filename = f"{base}_{pedido}_{conjunto}{ext}"
                dest_path = os.path.join(UPLOADS_DIR, new_filename)
                
                # Copia o arquivo de imagem
                shutil.copy(file_path, dest_path)

                # Cria o arquivo JSON
                json_path = os.path.join(UPLOADS_DIR, os.path.splitext(new_filename)[0] + '.json')
                with open(json_path, 'w', encoding='utf-8') as f:
                    json.dump(info, f, indent=4)
            
            messagebox.showinfo("Sucesso", "Fotos enviadas com sucesso!", parent=self.upload_win)
            self.upload_win.destroy()
            self.start_loading_gallery() # Recarrega a galeria

        except Exception as e:
            messagebox.showerror("Erro no Upload", f"Ocorreu um erro: {e}", parent=self.upload_win)

    def filter_gallery(self, *args):
        search_term = self.search_var.get().lower()
        if search_term == "pesquisar por pedido, cliente ou conjunto...":
            search_term = ""

        for card in self.scrollable_frame.winfo_children():
            if isinstance(card, ttk.LabelFrame):
                # Acessando os dados diretamente dos atributos do widget
                pedido = getattr(card, 'data_pedido', '').lower()
                cliente = getattr(card, 'data_cliente', '').lower()
                conjuntos = [c.lower() for c in getattr(card, 'data_conjuntos', [])]

                matches = (search_term in pedido or 
                           search_term in cliente or 
                           any(search_term in c for c in conjuntos))

                if not matches:
                    card.grid_remove()
                else:
                    card.grid()

    def __del__(self):
        # Desvincula o evento do mousewheel para não afetar outras janelas
        if self.frame.winfo_exists():
            self.canvas.unbind_all("<MouseWheel>")

       