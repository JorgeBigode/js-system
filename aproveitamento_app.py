import tkinter as tk
from tkinter import ttk, messagebox
import customtkinter as ctk
import copy
import random
import math

class EditorChapaWindow(tk.Toplevel):
    """
    Uma janela de edição separada para uma única chapa, permitindo uma visão ampliada.
    Permite arrastar, soltar e rotacionar as peças manualmente.
    """
    def __init__(self, master, app, chapa_data, chapa_index):
        super().__init__(master)
        self.app = app
        self.chapa_data = chapa_data
        self.chapa_index = chapa_index

        self.title(f"Editando Chapa {self.chapa_index + 1}")
        self.geometry("1000x700")

        # Calcula uma nova escala para a janela do editor
        padding = 50 
        scale_w = (1000 - padding) / self.app.chapa_w_val
        scale_h = (700 - padding) / self.app.chapa_h_val
        self.scale = min(scale_w, scale_h, 1)

        canvas_w = int(self.app.chapa_w_val * self.scale)
        canvas_h = int(self.app.chapa_h_val * self.scale)

        # Frame para centralizar o canvas
        center_frame = ttk.Frame(self)
        center_frame.pack(fill=tk.BOTH, expand=True)

        self.editor_canvas = tk.Canvas(center_frame, width=canvas_w, height=canvas_h, bg="#f0f0f0", relief=tk.SOLID, borderwidth=1)
        self.editor_canvas.place(in_=center_frame, anchor="c", relx=.5, rely=.5)

        self.drag_data = None

        self._redraw_canvas()

        # Associa os eventos
        self.editor_canvas.bind("<ButtonPress-1>", self._start_drag)
        self.editor_canvas.bind("<B1-Motion>", self._do_drag)
        self.editor_canvas.bind("<ButtonRelease-1>", self._stop_drag)
        self.editor_canvas.bind("<ButtonPress-3>", self._rotate_piece)

        # Lida com o fechamento da janela
        self.protocol("WM_DELETE_WINDOW", self.on_close)

        # Torna a janela modal
        self.transient(master)
        self.grab_set()
        master.wait_window(self)

    def on_close(self):
        # Atualiza a visualização do aplicativo principal antes de fechar
        self.app.atualizar_desenho_principal(self.chapa_index)
        self.destroy()

    def _redraw_canvas(self):
        self.editor_canvas.delete("all")
        
        drag_info = self.drag_data
        peca_sendo_arrastada = (drag_info or {}).get('peca')

        for peca in self.chapa_data['pecas_colocadas']:
            x1 = peca['x'] * self.scale
            y1 = peca['y'] * self.scale
            x2 = (peca['x'] + peca['largura']) * self.scale
            y2 = (peca['y'] + peca['altura']) * self.scale

            # MODIFICAÇÃO: Usa a cor fixa da peça
            cor_peca = peca.get('cor', "#cccccc")
            
            outline_color = "black"
            if peca is peca_sendo_arrastada:
                # Se a peça estiver sendo arrastada, verifica colisão para mudar o contorno
                if self._check_collision(peca) or self._is_out_of_bounds(peca):
                    outline_color = "red"
                else:
                    outline_color = "#33FF57" # Verde para indicar posição válida
            
            self.editor_canvas.create_rectangle(x1, y1, x2, y2, fill=cor_peca, outline=outline_color, width=2)
            self.editor_canvas.create_text((x1 + x2) / 2, (y1 + y2) / 2, text=f"P{peca['id']}", font=('Arial', 10, 'bold'))

    def _start_drag(self, event):
        orig_x = event.x / self.scale
        orig_y = event.y / self.scale

        for peca in reversed(self.chapa_data['pecas_colocadas']):
            if (peca['x'] <= orig_x <= peca['x'] + peca['largura'] and
                peca['y'] <= orig_y <= peca['y'] + peca['altura']):
                
                self.drag_data = {
                    'peca': peca,
                    'offset_x': orig_x - peca['x'],
                    'offset_y': orig_y - peca['y'],
                    'original_x': peca['x'],
                    'original_y': peca['y']
                }
                return

    def _do_drag(self, event):
        if not self.drag_data:
            return

        peca = self.drag_data['peca']
        
        peca['x'] = (event.x / self.scale) - self.drag_data['offset_x']
        peca['y'] = (event.y / self.scale) - self.drag_data['offset_y']
        
        self._clamp_position(peca)
        self._redraw_canvas()

    def _stop_drag(self, event):
        if not self.drag_data:
            return
            
        peca = self.drag_data['peca']

        self._clamp_position(peca)

        # Checa colisão ou fora dos limites
        if self._check_collision(peca) or self._is_out_of_bounds(peca):
            # Reverte para a posição original se houver colisão
            peca['x'] = self.drag_data['original_x']
            peca['y'] = self.drag_data['original_y']

        self.drag_data = None
        self._redraw_canvas()

    def _rotate_piece(self, event):
        x = event.x / self.scale
        y = event.y / self.scale

        for peca in reversed(self.chapa_data['pecas_colocadas']):
            if (peca['x'] <= x <= peca['x'] + peca['largura'] and
                peca['y'] <= y <= peca['y'] + peca['altura']):

                largura_original = peca['largura']
                altura_original = peca['altura']
                x_original = peca['x']
                y_original = peca['y']

                peca['largura'] = altura_original
                peca['altura'] = largura_original

                self._clamp_position(peca)

                if self._check_collision(peca) or self._is_out_of_bounds(peca):
                    peca['largura'] = largura_original
                    peca['altura'] = altura_original
                    peca['x'] = x_original
                    peca['y'] = y_original
                    messagebox.showwarning("Rotação Inválida", "A peça não pode ser rotacionada pois colidiria com outra peça ou sairia da chapa.", parent=self)
                else:
                    self._redraw_canvas()
                
                return

    def _clamp_position(self, peca):
        """Ajusta a posição da peça para mantê-la dentro dos limites da chapa."""
        max_x = self.app.chapa_w_val - peca['largura']
        max_y = self.app.chapa_h_val - peca['altura']
        peca['x'] = max(0, min(peca['x'], max_x))
        peca['y'] = max(0, min(peca['y'], max_y))

    def _check_collision(self, peca_a_verificar):
        for outra_peca in self.chapa_data['pecas_colocadas']:
            if peca_a_verificar is outra_peca:
                continue
            if (peca_a_verificar['x'] < outra_peca['x'] + outra_peca['largura'] and
                peca_a_verificar['x'] + peca_a_verificar['largura'] > outra_peca['x'] and
                peca_a_verificar['y'] < outra_peca['y'] + outra_peca['altura'] and
                peca_a_verificar['y'] + peca_a_verificar['altura'] > outra_peca['y']):
                return True
        return False

    def _is_out_of_bounds(self, peca):
        return (peca['x'] < 0 or 
                peca['y'] < 0 or
                peca['x'] + peca['largura'] > self.app.chapa_w_val or
                peca['y'] + peca['altura'] > self.app.chapa_h_val)


class AproveitamentoApp:
    """
    Uma aplicação para calcular o aproveitamento de chapas e barras, baseada em um algoritmo de encaixe,
    com gerenciamento de múltiplas páginas (Notebook) para as funcionalidades 2D e 1D.
    """
    def __init__(self, master, user):
        self.master = master
        self.user = user
        self.frame = ttk.Frame(self.master)
        self.frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # --- Variáveis Comuns (Cores) ---
        self.cores = ["#FFC300", "#FF5733", "#C70039", "#900C3F", "#581845", "#DAF7A6", "#33FF57", "#33D4FF", "#A569BD", "#F08080", "#ADD8E6", "#90EE90"]

        # --- Variáveis para Corte de Chapa (2D) ---
        self.pecas_entries = []
        self.chapa_width_var = tk.StringVar(value="3000")
        self.chapa_height_var = tk.StringVar(value="1200")
        self.espaco_var = tk.StringVar(value="5")
        self.chapas_geradas = [] 
        self.canvas_chapas = {} 
        self.chapa_w_val = 3000
        self.chapa_h_val = 1200
        
        # --- Variáveis para Corte de Barra (1D) ---
        self.barra_entries = []
        self.barra_length_var = tk.StringVar(value="6000")
        self.kerf_var = tk.StringVar(value="3")
        self.barras_geradas = {} # Armazena o resultado da otimização 1D

        self._setup_notebook()

        # Inicialização das listas de peças
        self.adicionar_peca() # 2D
        self.adicionar_barra_peca() # 1D

    def _setup_notebook(self):
        """Configura o Notebook (abas) para a mudança de página."""
        
        # O Notebook será o principal widget de navegação
        self.notebook = ctk.CTkTabview(self.frame)
        self.notebook.pack(fill=tk.BOTH, expand=True)

        # --- Página 1: Corte de Chapa (Placas 2D) ---
        self.chapa_page = self.notebook.add("Corte de Chapa (Placas)")
        self.chapa_page.configure(fg_color="transparent")
        self.create_chapa_widgets(self.chapa_page)
        
        # --- Página 2: Aproveitamento de Barra (Linear 1D) ---
        self.barra_page = self.notebook.add("Aproveitamento de Barra (Linear)")
        self.barra_page.configure(fg_color="transparent")
        self.create_barra_widgets(self.barra_page)
        
    def create_barra_widgets(self, parent_frame):
        """Cria e organiza todos os widgets da página de Aproveitamento de Barra (1D)."""
        
        # Frame de Configurações (Esquerda)
        config_frame = ttk.LabelFrame(parent_frame, text="Configurações da Barra", padding=10)
        config_frame.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 10))

        # Dimensões da Barra e Kerf
        barra_config_frame = ttk.Frame(config_frame)
        barra_config_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(barra_config_frame, text="Comprimento Padrão (mm):").grid(row=0, column=0, sticky="w", padx=5)
        ttk.Entry(barra_config_frame, textvariable=self.barra_length_var, width=10).grid(row=0, column=1, padx=5)
        
        ttk.Label(barra_config_frame, text="Perda de Corte (Kerf - mm):").grid(row=1, column=0, sticky="w", padx=5)
        ttk.Entry(barra_config_frame, textvariable=self.kerf_var, width=10).grid(row=1, column=1, padx=5)

        ttk.Separator(config_frame, orient='horizontal').pack(fill=tk.X, pady=10)

        # Container para as peças de barra com scroll
        ttk.Label(config_frame, text="Peças a Cortar:").pack(anchor="w")
        pecas_container = ttk.Frame(config_frame)
        pecas_container.pack(fill=tk.BOTH, expand=True)
        
        pecas_canvas = tk.Canvas(pecas_container, borderwidth=0)
        self.barra_pecas_frame = ttk.Frame(pecas_canvas)
        scrollbar = ttk.Scrollbar(pecas_container, orient="vertical", command=pecas_canvas.yview)
        pecas_canvas.configure(yscrollcommand=scrollbar.set)

        scrollbar.pack(side="right", fill="y")
        pecas_canvas.pack(side="left", fill=tk.BOTH, expand=True)
        pecas_canvas.create_window((0, 0), window=self.barra_pecas_frame, anchor="nw")

        self.barra_pecas_frame.bind("<Configure>", lambda e: pecas_canvas.configure(scrollregion=pecas_canvas.bbox("all")))
        pecas_canvas.bind_all("<MouseWheel>", lambda e, c=pecas_canvas: self._on_mousewheel_pecas(e, c))
        pecas_canvas.bind_all("<Button-4>", lambda e, c=pecas_canvas: self._on_mousewheel_pecas(e, c))
        pecas_canvas.bind_all("<Button-5>", lambda e, c=pecas_canvas: self._on_mousewheel_pecas(e, c))

        # Botões de Ação
        botoes_frame = ttk.Frame(config_frame)
        botoes_frame.pack(fill=tk.X, pady=10, side=tk.BOTTOM)
        ttk.Button(botoes_frame, text="Adicionar Peça", command=self.adicionar_barra_peca).pack(fill=tk.X, pady=2)
        ttk.Button(botoes_frame, text="Calcular Corte 1D", command=self.gerar_encaixe_barra, style="Accent.TButton").pack(fill=tk.X, pady=2)

        # --- Frame de Resultados (Direita) ---
        self.barra_result_frame = ttk.LabelFrame(parent_frame, text="Plano de Corte Linear", padding=10)
        self.barra_result_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)
        
        # Adicionando um Canvas com Scrollbars para os resultados da barra
        self.barra_draw_canvas = tk.Canvas(self.barra_result_frame, bg='white')
        self.barra_draw_canvas.pack(fill=tk.BOTH, expand=True)
        
        self.barra_draw_frame = ttk.Frame(self.barra_draw_canvas)
        v_scroll = ttk.Scrollbar(self.barra_result_frame, orient='vertical', command=self.barra_draw_canvas.yview)
        v_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.barra_draw_canvas.configure(yscrollcommand=v_scroll.set)
        
        self.barra_draw_canvas.create_window((0,0), window=self.barra_draw_frame, anchor='nw')
        self.barra_draw_frame.bind("<Configure>", lambda e: self.barra_draw_canvas.configure(scrollregion=self.barra_draw_canvas.bbox("all")))
        self.barra_draw_canvas.bind_all("<MouseWheel>", lambda e, c=self.barra_draw_canvas: self._on_mousewheel_resultados(e, c))
        self.barra_draw_canvas.bind_all("<Button-4>", lambda e, c=self.barra_draw_canvas: self._on_mousewheel_resultados(e, c))
        self.barra_draw_canvas.bind_all("<Button-5>", lambda e, c=self.barra_draw_canvas: self._on_mousewheel_resultados(e, c))

    def adicionar_barra_peca(self, comprimento="500", quantidade="1"):
        """Adiciona uma nova linha para entrada de peças de corte 1D."""
        peca_id = len(self.barra_entries)
        frame = ttk.Frame(self.barra_pecas_frame, relief=tk.GROOVE, borderwidth=1, padding=5)
        frame.pack(fill=tk.X, pady=5, padx=5)

        ttk.Label(frame, text=f"Peça {peca_id + 1}").grid(row=0, column=0, columnspan=3, sticky="w")

        ttk.Label(frame, text="Comprimento:").grid(row=1, column=0)
        comprimento_var = tk.StringVar(value=comprimento)
        ttk.Entry(frame, textvariable=comprimento_var, width=8).grid(row=1, column=1)

        ttk.Label(frame, text="Qtd:").grid(row=2, column=0)
        quantidade_var = tk.StringVar(value=quantidade)
        ttk.Entry(frame, textvariable=quantidade_var, width=8).grid(row=2, column=1)

        remover_btn = ttk.Button(frame, text="Remover", command=lambda f=frame: self.remover_barra_peca(f), width=8)
        remover_btn.grid(row=1, column=2, rowspan=2, padx=5)

        self.barra_entries.append({'frame': frame, 'comprimento': comprimento_var, 'quantidade': quantidade_var})

    def remover_barra_peca(self, frame_to_remove):
        """Remove uma linha de peça de corte 1D."""
        self.barra_entries = [p for p in self.barra_entries if p['frame'] != frame_to_remove]
        frame_to_remove.destroy()
        for i, peca_info in enumerate(self.barra_entries):
            label = peca_info['frame'].winfo_children()[0]
            label.config(text=f"Peça {i + 1}")
    
    def gerar_encaixe_barra(self):
        """Coleta dados e executa a otimização de corte 1D."""
        try:
            barra_length = float(self.barra_length_var.get())
            kerf = float(self.kerf_var.get())
            if barra_length <= 0 or kerf < 0:
                 raise ValueError("Valores devem ser positivos ou zero para Kerf.")
        except ValueError:
            messagebox.showerror("Erro de Entrada", "O comprimento da barra e o Kerf devem ser números válidos.", parent=self.master)
            return

        pecas_necessarias = []
        pecas_validas = True
        
        for peca_info in self.barra_entries:
            try:
                c = float(peca_info['comprimento'].get())
                qtd = int(peca_info['quantidade'].get())
                if c <= 0 or qtd <= 0:
                     raise ValueError()
                if c > barra_length:
                     messagebox.showwarning("Peça Grande", f"A peça de {c}mm é maior que a barra de {barra_length}mm e será ignorada.", parent=self.master)
                     continue
                pecas_necessarias.append((c, qtd))
            except ValueError:
                pecas_validas = False
                break

        if not pecas_validas:
             messagebox.showerror("Erro de Entrada", "Comprimentos e quantidades das peças devem ser números inteiros/flutuantes válidos e positivos.", parent=self.master)
             return

        if not pecas_necessarias:
            self.barras_geradas = {}
            self.desenhar_resultados_barra()
            return

        self.barras_geradas = self.otimizar_corte_barras(barra_length, pecas_necessarias, kerf)
        self.desenhar_resultados_barra()
    
    def otimizar_corte_barras(self, comprimento_barra: float, pecas_necessarias: list[tuple[float, int]], perda_corte: float) -> dict:
        """Implementação do algoritmo First-Fit Decreasing (FFD) para corte 1D."""
        
        pecas_para_cortar = []
        for comprimento, quantidade in pecas_necessarias:
            pecas_para_cortar.extend([comprimento] * quantidade)
        
        pecas_para_cortar.sort(reverse=True)

        barras = []
        total_comprimento_util = 0

        for peca in pecas_para_cortar:
            colocado = False
            
            for barra in barras:
                required_space = peca
                # Adiciona Kerf se não for a primeira peça na barra
                if barra['pecas']:
                    required_space += perda_corte

                if barra['comprimento_restante'] >= required_space:
                    barra['pecas'].append(peca)
                    barra['comprimento_restante'] -= required_space
                    colocado = True
                    break
            
            if not colocado:
                # Nova barra (não precisa de Kerf no primeiro corte)
                comprimento_restante = comprimento_barra - peca
                barras.append({
                    'comprimento_total': comprimento_barra,
                    'comprimento_restante': comprimento_restante,
                    'pecas': [peca]
                })
            
            total_comprimento_util += peca

        total_desperdicio_final = 0
        total_perda_corte = 0
        
        for barra in barras:
            barra['sobra_final'] = round(barra['comprimento_restante'], 2)
            total_desperdicio_final += barra['sobra_final']
            
            num_cortes = len(barra['pecas']) - 1
            perda_kerf_barra = num_cortes * perda_corte
            barra['perda_corte_kerf'] = round(perda_kerf_barra, 2)
            total_perda_corte += perda_kerf_barra
            
            barra['pecas'] = [round(p, 2) for p in barra['pecas']] # Arredonda o comprimento das peças

        total_material_usado = comprimento_barra * len(barras)
        
        eficiencia = 0
        if total_material_usado > 0:
            eficiencia = (total_comprimento_util / total_material_usado) * 100

        return {
            'barras': barras,
            'resumo': {
                'barras_necessarias': len(barras),
                'comprimento_util_total': round(total_comprimento_util, 2),
                'desperdicio_final_total': round(total_desperdicio_final, 2),
                'perda_corte_total': round(total_perda_corte, 2),
                'material_total_usado': round(total_material_usado, 2),
                'eficiencia': round(eficiencia, 2)
            }
        }
    
    def desenhar_resultados_barra(self):
        """Desenha o plano de corte e exibe o resumo para a otimização 1D."""
        for widget in self.barra_draw_frame.winfo_children():
            widget.destroy()
        
        if not self.barras_geradas:
            ttk.Label(self.barra_draw_frame, text="Nenhum resultado para exibir. Preencha a lista de peças e clique em 'Calcular Corte 1D'.").pack(padx=20, pady=20)
            return
            
        resumo = self.barras_geradas['resumo']
        barras_data = self.barras_geradas['barras']
        barra_w = barras_data[0]['comprimento_total'] if barras_data else 0
        
        # --- Resumo Estatístico (Topo) ---
        resumo_frame = ttk.LabelFrame(self.barra_draw_frame, text="Estatísticas", padding=10)
        resumo_frame.pack(fill=tk.X, padx=10, pady=10)
        
        ttk.Label(resumo_frame, text=f"Barras Necessárias: {resumo['barras_necessarias']}", font=('Arial', 10, 'bold')).grid(row=0, column=0, sticky='w', padx=5, pady=2)
        ttk.Label(resumo_frame, text=f"Eficiência de Corte: {resumo['eficiencia']}%", font=('Arial', 10, 'bold')).grid(row=0, column=1, sticky='w', padx=5, pady=2)
        ttk.Label(resumo_frame, text=f"Desperdício Final (Sobra): {resumo['desperdicio_final_total']} mm").grid(row=1, column=0, sticky='w', padx=5, pady=2)
        ttk.Label(resumo_frame, text=f"Perda por Kerf Total: {resumo['perda_corte_total']} mm").grid(row=1, column=1, sticky='w', padx=5, pady=2)

        # --- Desenho das Barras ---
        CANVAS_WIDTH = 700  # Tamanho fixo em pixels para a visualização da barra
        BAR_HEIGHT = 40     # Altura da barra visual
        
        if barra_w > 0:
            scale_factor = CANVAS_WIDTH / barra_w
        else:
            scale_factor = 0

        for i, barra in enumerate(barras_data):
            barra_frame = ttk.Frame(self.barra_draw_frame, padding=5)
            barra_frame.pack(fill=tk.X, padx=10, pady=5)
            
            ttk.Label(barra_frame, text=f"Barra {i + 1} ({barra_w} mm)", font=('Arial', 10, 'bold')).pack(anchor='w')
            
            details_frame = ttk.Frame(barra_frame)
            details_frame.pack(anchor='w', pady=2)
            ttk.Label(details_frame, text=f"Sobra Final: {barra['sobra_final']} mm | Perda Kerf: {barra['perda_corte_kerf']} mm").pack(side=tk.LEFT)
            
            # Canvas de desenho da barra
            canvas = tk.Canvas(barra_frame, width=CANVAS_WIDTH, height=BAR_HEIGHT, bg="#f0f0f0", relief=tk.SOLID, borderwidth=1)
            canvas.pack(fill=tk.X)
            
            current_x = 0
            
            for piece_index, peca_length in enumerate(barra['pecas']):
                visual_length = peca_length * scale_factor
                
                # Cor da peça (pode usar o mesmo ciclo de cores do 2D)
                cor_peca = self.cores[piece_index % len(self.cores)]
                
                # Desenha a peça
                x1 = current_x
                x2 = current_x + visual_length
                canvas.create_rectangle(x1, 0, x2, BAR_HEIGHT, fill=cor_peca, outline="#1f2937", width=1)
                
                # Texto da peça
                canvas.create_text((x1 + x2) / 2, BAR_HEIGHT / 2, text=f"{peca_length}mm", font=('Arial', 8, 'bold'), fill='white')
                
                current_x = x2
                
                # Desenha a perda de corte (Kerf), se não for a última peça
                kerf = float(self.kerf_var.get())
                if piece_index < len(barra['pecas']) - 1:
                    kerf_visual_length = kerf * scale_factor
                    
                    # Desenha o Kerf (linha fina e escura)
                    canvas.create_line(current_x, 0, current_x, BAR_HEIGHT, fill='red', width=max(1, math.ceil(kerf_visual_length)))
                    
                    current_x += kerf_visual_length

            # Desenha a sobra final (Desperdício)
            sobra_length = barra['sobra_final'] * scale_factor
            if sobra_length > 0.1: # Desenha apenas se a sobra for visualmente significativa
                x1_sobra = current_x
                x2_sobra = current_x + sobra_length
                
                canvas.create_rectangle(x1_sobra, 0, x2_sobra, BAR_HEIGHT, fill="#ef4444", outline="#1f2937", width=1)
                
                # Texto da sobra
                if sobra_length > 50:
                    canvas.create_text((x1_sobra + x2_sobra) / 2, BAR_HEIGHT / 2, text=f"Sobra: {barra['sobra_final']}mm", font=('Arial', 8, 'bold'), fill='white')

        self.barra_draw_frame.update_idletasks()
        self.barra_draw_canvas.config(scrollregion=self.barra_draw_canvas.bbox("all"))

    # O restante dos métodos (adicionar_peca, remover_peca, inverter_medidas, gerar_encaixe, 
    # algoritmo_shelf_bin_packing, _tentar_colocar_na_chapa_shelf, desenhar_resultados, 
    # _redraw_chapa_canvas, toggle_edit_mode, atualizar_desenho_principal, 
    # _on_mousewheel_pecas, _on_mousewheel_resultados) permanece essencialmente o mesmo.
    
    def create_chapa_widgets(self, parent_frame):
        """Cria e organiza todos os widgets da página de Corte de Chapa (funcionalidade original)."""
        
        # --- Frame de Configurações (Esquerda) ---
        config_frame = ttk.LabelFrame(parent_frame, text="Configurações", padding=10)
        config_frame.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 10))

        # Dimensões da Chapa
        chapa_frame = ttk.Frame(config_frame)
        chapa_frame.pack(fill=tk.X, pady=5)
        ttk.Label(chapa_frame, text="Largura da Chapa:").grid(row=0, column=0, sticky="w", padx=5)
        ttk.Entry(chapa_frame, textvariable=self.chapa_width_var, width=10).grid(row=0, column=1, padx=5)
        ttk.Label(chapa_frame, text="Altura da Chapa:").grid(row=1, column=0, sticky="w", padx=5)
        ttk.Entry(chapa_frame, textvariable=self.chapa_height_var, width=10).grid(row=1, column=1, padx=5)
        ttk.Label(chapa_frame, text="Espaço entre Peças:").grid(row=2, column=0, sticky="w", padx=5)
        ttk.Entry(chapa_frame, textvariable=self.espaco_var, width=10).grid(row=2, column=1, padx=5)

        ttk.Separator(config_frame, orient='horizontal').pack(fill=tk.X, pady=10)

        # Container para as peças com scroll
        pecas_container = ttk.Frame(config_frame)
        pecas_container.pack(fill=tk.BOTH, expand=True)
        
        pecas_canvas = tk.Canvas(pecas_container, borderwidth=0)
        self.pecas_frame = ttk.Frame(pecas_canvas)
        scrollbar = ttk.Scrollbar(pecas_container, orient="vertical", command=pecas_canvas.yview)
        pecas_canvas.configure(yscrollcommand=scrollbar.set)

        scrollbar.pack(side="right", fill="y")
        pecas_canvas.pack(side="left", fill="both", expand=True)
        pecas_canvas.create_window((0, 0), window=self.pecas_frame, anchor="nw")

        self.pecas_frame.bind("<Configure>", lambda e: pecas_canvas.configure(scrollregion=pecas_canvas.bbox("all")))

        # Adiciona o scroll do mouse ao canvas das peças
        pecas_canvas.bind_all("<MouseWheel>", lambda e, c=pecas_canvas: self._on_mousewheel_pecas(e, c))
        pecas_canvas.bind_all("<Button-4>", lambda e, c=pecas_canvas: self._on_mousewheel_pecas(e, c))
        pecas_canvas.bind_all("<Button-5>", lambda e, c=pecas_canvas: self._on_mousewheel_pecas(e, c))

        # Botões de Ação
        botoes_frame = ttk.Frame(config_frame)
        botoes_frame.pack(fill=tk.X, pady=10, side=tk.BOTTOM)
        ttk.Button(botoes_frame, text="Adicionar Peça", command=self.adicionar_peca).pack(fill=tk.X, pady=2)
        ttk.Button(botoes_frame, text="Gerar Encaixe", command=self.gerar_encaixe, style="Accent.TButton").pack(fill=tk.X, pady=2)

        # --- Frame de Resultados (Direita) ---
        self.result_frame = ttk.LabelFrame(parent_frame, text="Resultados", padding=10)
        self.result_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)
        
        # Adicionando um Canvas com Scrollbars para os resultados
        self.result_canvas = tk.Canvas(self.result_frame, bg='white')
        h_scroll = ttk.Scrollbar(self.result_frame, orient='horizontal', command=self.result_canvas.xview)
        v_scroll = ttk.Scrollbar(self.result_frame, orient='vertical', command=self.result_canvas.yview)
        self.result_canvas.configure(xscrollcommand=h_scroll.set, yscrollcommand=v_scroll.set)

        h_scroll.pack(side=tk.BOTTOM, fill=tk.X)
        v_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.result_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # Frame interno para desenhar
        self.draw_frame = ttk.Frame(self.result_canvas)
        self.result_canvas.create_window((0,0), window=self.draw_frame, anchor='nw')

        self.draw_frame.bind("<Configure>", lambda e: self.result_canvas.configure(scrollregion=self.result_canvas.bbox("all")))

        # Adiciona o scroll do mouse ao canvas de resultados
        self.result_canvas.bind_all("<MouseWheel>", lambda e, c=self.result_canvas: self._on_mousewheel_resultados(e, c))
        self.result_canvas.bind_all("<Button-4>", lambda e, c=self.result_canvas: self._on_mousewheel_resultados(e, c))
        self.result_canvas.bind_all("<Button-5>", lambda e, c=self.result_canvas: self._on_mousewheel_resultados(e, c))

    def adicionar_peca(self, largura="100", altura="100", quantidade="1"):
        peca_id = len(self.pecas_entries)
        frame = ttk.Frame(self.pecas_frame, relief=tk.GROOVE, borderwidth=1, padding=5)
        frame.pack(fill=tk.X, pady=5, padx=5)

        ttk.Label(frame, text=f"Peça {peca_id + 1}").grid(row=0, column=0, columnspan=3, sticky="w")

        ttk.Label(frame, text="Largura:").grid(row=1, column=0)
        largura_var = tk.StringVar(value=largura)
        ttk.Entry(frame, textvariable=largura_var, width=6).grid(row=1, column=1)

        ttk.Label(frame, text="Altura:").grid(row=2, column=0)
        altura_var = tk.StringVar(value=altura)
        ttk.Entry(frame, textvariable=altura_var, width=6).grid(row=2, column=1)

        ttk.Label(frame, text="Qtd:").grid(row=3, column=0)
        quantidade_var = tk.StringVar(value=quantidade)
        ttk.Entry(frame, textvariable=quantidade_var, width=6).grid(row=3, column=1)

        btn_frame = ttk.Frame(frame)
        btn_frame.grid(row=1, column=2, rowspan=3, padx=5)

        remover_btn = ttk.Button(btn_frame, text="X", command=lambda f=frame: self.remover_peca(f), width=3)
        remover_btn.pack(pady=1)

        inverter_btn = ttk.Button(btn_frame, text="↻", command=lambda l=largura_var, a=altura_var: self.inverter_medidas(l, a), width=3)
        inverter_btn.pack(pady=1)

        self.pecas_entries.append({'frame': frame, 'largura': largura_var, 'altura': altura_var, 'quantidade': quantidade_var})

    def remover_peca(self, frame_to_remove):
        self.pecas_entries = [p for p in self.pecas_entries if p['frame'] != frame_to_remove]
        frame_to_remove.destroy()
        for i, peca_info in enumerate(self.pecas_entries):
            label = peca_info['frame'].winfo_children()[0]
            label.config(text=f"Peça {i + 1}")

    def inverter_medidas(self, largura_var, altura_var):
        largura_val = largura_var.get()
        altura_val = altura_var.get()
        largura_var.set(altura_val)
        altura_var.set(largura_val)

    def gerar_encaixe(self):
        try:
            self.chapa_w_val = int(self.chapa_width_var.get())
            self.chapa_h_val = int(self.chapa_height_var.get())
            espaco = int(self.espaco_var.get())
        except ValueError:
            messagebox.showerror("Erro de Entrada", "As dimensões da chapa e o espaçamento devem ser números inteiros.")
            return

        pecas_para_cortar = []
        try:
            for i, peca_info in enumerate(self.pecas_entries):
                w = int(peca_info['largura'].get())
                h = int(peca_info['altura'].get())
                qtd = int(peca_info['quantidade'].get())
                for _ in range(qtd):
                    # Adiciona o ID da peça de entrada (i+1)
                    pecas_para_cortar.append({'id': i + 1, 'largura': w, 'altura': h, 'area': w * h})
        except ValueError:
            messagebox.showerror("Erro de Entrada", "As dimensões e quantidades das peças devem ser números inteiros.")
            return

        def sort_key(p):
            is_full_width = (p['largura'] == self.chapa_w_val or p['altura'] == self.chapa_w_val)
            return (not is_full_width, -max(p['largura'], p['altura']))
        pecas_para_cortar.sort(key=sort_key)

        self.chapas_geradas = self.algoritmo_shelf_bin_packing(pecas_para_cortar, self.chapa_w_val, self.chapa_h_val, espaco)
        self.desenhar_resultados()

    def algoritmo_shelf_bin_packing(self, pecas, chapa_w, chapa_h, espaco):
        chapas = []
        for peca in pecas:
            peca_colocada = False
            for chapa in chapas:
                if self._tentar_colocar_na_chapa_shelf(peca, chapa, chapa_w, chapa_h, espaco):
                    peca_colocada = True
                    break
            
            if not peca_colocada:
                nova_chapa = {'pecas_colocadas': [], 'shelves': []}
                if self._tentar_colocar_na_chapa_shelf(peca, nova_chapa, chapa_w, chapa_h, espaco):
                    chapas.append(nova_chapa)
                else:
                    print(f"Atenção: Peça ID {peca['id']} não coube em uma nova chapa.")
        
        return chapas

    def _tentar_colocar_na_chapa_shelf(self, peca, chapa, chapa_w, chapa_h, espaco):
        orientacoes = [
            {'w': peca['largura'], 'h': peca['altura'], 'rot': False},
            {'w': peca['altura'], 'h': peca['largura'], 'rot': True}
        ]
        best_fit = None

        for shelf in chapa['shelves']:
            for o in orientacoes:
                # Inclui o espaçamento na largura do fit
                if o['h'] <= shelf['height'] and (shelf['current_w'] + o['w'] + espaco) <= chapa_w:
                    waste = shelf['height'] - o['h']
                    if best_fit is None or waste < best_fit['waste']:
                        best_fit = {'waste': waste, 'shelf': shelf, 'w': o['w'], 'h': o['h']}

        if best_fit:
            shelf = best_fit['shelf']
            w, h = best_fit['w'], best_fit['h']
            x, y = shelf['current_w'], shelf['y']
            
            # Atribui uma cor fixa com base no ID da peça
            peca_cor = self.cores[(peca['id'] - 1) % len(self.cores)]
            peca_pos = {'id': peca['id'], 'x': x, 'y': y, 'largura': w, 'altura': h, 'cor': peca_cor}
            
            chapa['pecas_colocadas'].append(peca_pos)
            shelf['current_w'] += w + espaco
            shelf['max_piece_height'] = max(shelf['max_piece_height'], h)
            return True
            
        # Tenta criar uma nova "shelf" na parte superior
        last_y = max([s['y'] + s['max_piece_height'] for s in chapa['shelves']], default=0) + (espaco if chapa['shelves'] else 0)

        # Tenta encaixar a peça na orientação original
        w, h = peca['largura'], peca['altura']
        if last_y + h <= chapa_h:
            chapa['shelves'].append({'y': last_y, 'height': h, 'current_w': 0, 'max_piece_height': h})
            # Chama a função novamente para colocar na nova prateleira (shelf)
            return self._tentar_colocar_na_chapa_shelf(peca, chapa, chapa_w, chapa_h, espaco)
        
        # Tenta encaixar a peça rotacionada
        w, h = peca['altura'], peca['largura']
        if last_y + h <= chapa_h:
            chapa['shelves'].append({'y': last_y, 'height': h, 'current_w': 0, 'max_piece_height': h})
            # Chama a função novamente para colocar na nova prateleira (shelf)
            return self._tentar_colocar_na_chapa_shelf(peca, chapa, chapa_w, chapa_h, espaco)
            
        return False

    def desenhar_resultados(self):
        for widget in self.draw_frame.winfo_children():
            widget.destroy()
        
        self.canvas_chapas.clear()

        if not self.chapas_geradas:
            ttk.Label(self.draw_frame, text="Nenhum resultado para exibir.").pack()
            return

        max_display_w, max_display_h = 800, 500
        scale_w = max_display_w / self.chapa_w_val
        scale_h = max_display_h / self.chapa_h_val
        self.scale = min(scale_w, scale_h, 1)

        canvas_w = int(self.chapa_w_val * self.scale)
        canvas_h = int(self.chapa_h_val * self.scale)
        
        for i, chapa_data in enumerate(self.chapas_geradas):
            chapa_frame = ttk.Frame(self.draw_frame, padding=10)
            chapa_frame.pack(pady=10, anchor='w')

            ttk.Label(chapa_frame, text=f"Chapa {i + 1}", font=('Arial', 12, 'bold')).pack(anchor='w')
            
            canvas = tk.Canvas(chapa_frame, width=canvas_w, height=canvas_h, bg="#f0f0f0", relief=tk.SOLID, borderwidth=1)
            canvas.pack()
            canvas.chapa_index = i
            
            self.canvas_chapas[i] = canvas

            aproveitamento_label = ttk.Label(chapa_frame, text="Aproveitamento: 0.00%")
            aproveitamento_label.pack(anchor='w')
            chapa_frame.aproveitamento_label = aproveitamento_label

            self._redraw_chapa_canvas(canvas, chapa_data)
            
            # Associa o clique duplo para abrir o editor
            canvas.bind("<Double-1>", self.toggle_edit_mode)

        self.draw_frame.update_idletasks()
        self.result_canvas.config(scrollregion=self.result_canvas.bbox("all"))

    def _redraw_chapa_canvas(self, canvas, chapa_data):
        canvas.delete("all")
        area_pecas_total = 0

        for peca in chapa_data['pecas_colocadas']:
            x1 = peca['x'] * self.scale
            y1 = peca['y'] * self.scale
            x2 = (peca['x'] + peca['largura']) * self.scale
            y2 = (peca['y'] + peca['altura']) * self.scale

            cor_peca = peca.get('cor', "#cccccc")
            
            canvas.create_rectangle(x1, y1, x2, y2, fill=cor_peca, outline="black", width=1)
            canvas.create_text((x1 + x2) / 2, (y1 + y2) / 2, text=f"P{peca['id']}", font=('Arial', 8, 'bold'))

            area_pecas_total += peca['largura'] * peca['altura']

        aproveitamento = (area_pecas_total / (self.chapa_w_val * self.chapa_h_val)) * 100
        canvas.master.aproveitamento_label.config(text=f"Aproveitamento: {aproveitamento:.2f}%")

    def toggle_edit_mode(self, event):
        """Abre a janela de edição para a chapa selecionada."""
        canvas = event.widget
        chapa_index = canvas.chapa_index
        chapa_data = self.chapas_geradas[chapa_index]
        
        # Abre a nova janela de edição
        EditorChapaWindow(self.master, self, chapa_data, chapa_index)

    def atualizar_desenho_principal(self, chapa_index):
        """Atualiza o canvas da chapa especificada na janela principal."""
        if chapa_index in self.canvas_chapas:
            canvas = self.canvas_chapas[chapa_index]
            chapa_data = self.chapas_geradas[chapa_index]
            self._redraw_chapa_canvas(canvas, chapa_data)

    def _on_mousewheel_pecas(self, event, canvas):
        if canvas.winfo_containing(event.x_root, event.y_root) == canvas:
            if event.num == 4 or event.delta > 0:
                canvas.yview_scroll(-1, "units")
            elif event.num == 5 or event.delta < 0:
                canvas.yview_scroll(1, "units")

    def _on_mousewheel_resultados(self, event, canvas):
        if canvas.winfo_containing(event.x_root, event.y_root) == canvas:
            if event.num == 4 or event.delta > 0:
                canvas.yview_scroll(-1, "units")
            elif event.num == 5 or event.delta < 0:
                canvas.yview_scroll(1, "units")

if __name__ == "__main__":
    root = tk.Tk()
    root.title("Sistema de Aproveitamento de Materiais")
    
    # Adicionando um estilo para o botão de destaque
    style = ttk.Style(root)
    style.configure("Accent.TButton", foreground="white", background="blue")
    
    app = AproveitamentoApp(root, user="DefaultUser")
    root.mainloop()
