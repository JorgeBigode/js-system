import customtkinter as ctk
from tkinter import messagebox, ttk
import pymysql
from passlib.context import CryptContext # Importa o passlib
from config import DB_HOST, DB_USER, DB_PASS, DB_NAME
from itertools import cycle
import threading
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure
import numpy as np
from obras_app import ObrasApp # Importe a nova classe
from pedidos_app import PedidosApp
from trilhadeira_app import TrilhadeiraApp
from cadastro_itens_app import CadastroItensApp
from vincular_app import VincularApp # Importe a nova classe
from material_app import MaterialApp # Importe a nova classe de material
from relatorio_app import RelatorioApp # Importe a nova classe de relatório
from galeria_app import GaleriaApp # Importe a nova classe de galeria
from buscar_pdf_app import BuscarPDFApp # Importe a nova classe de busca de PDF
from aproveitamento_app import AproveitamentoApp # Importe a nova classe de aproveitamento
from programacao_app import ProgramacaoApp 
from estoque_app import EstoqueApp # Importe a nova classe de estoque
import os
import sys

def resource_path(relative_path):
    """ Obtém o caminho absoluto para o recurso, funciona para dev e para PyInstaller """
    try:
        # PyInstaller cria uma pasta temp e armazena o caminho em _MEIPASS
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

# Configura o contexto do passlib para ser compatível com a aplicação web
pwd_context = CryptContext(
    schemes=["bcrypt", "phpass", "md5_crypt", "pbkdf2_sha256"],
    deprecated="auto"
)

class MainApp:
    def __init__(self, user):
        self.user = user
        self.root = ctk.CTk()
        self.root.title("Sistema Principal")
        self.root.iconbitmap(resource_path('img/icon-SILO.ico'))
        self.root.geometry("1200x700")
        self.root.state('zoomed')  # Abre em tela cheia
        
        # Define o tema do CustomTkinter
        # NOTA: A aparência "light" foi definida, mas o código usa cores para modo "dark".
        # Se a intenção é um tema escuro, use set_appearance_mode("dark").
        # Vou manter "light" conforme o código, mas os componentes podem parecer inconsistentes.
        ctk.set_appearance_mode("light")  # "light", "dark", "system"
        ctk.set_default_color_theme("blue") # "blue", "green", "dark-blue"

        # Dados para o slide show
        self.slide_data = []
        self.slide_cycle = None
        self.current_slide_index = 0
        self.status_counts = {}
        self.animating = False # Flag para controlar a animação
        self.is_running = True  # Flag para controlar se a aplicação está rodando        

        # --- Lógica de Verificação de Atualização ---
        self.update_check_paused = False
        # try:
        #     self.initial_mtime = os.path.getmtime(sys.argv[0])
        # except (OSError, IndexError):
        #     self.initial_mtime = 0 # Se não conseguir obter, desativa a verificação
        self.initial_mtime = 0 # Desativa a verificação de atualização por enquanto
        
        # Configurar o layout principal
        self.create_widgets()
        
        self.fetch_slide_data()
        
        # Configurar o fechamento da janela
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        
    def on_closing(self):
        """Método chamado quando a janela é fechada"""
        # Adiciona a mesma confirmação do botão "SAIR"
        if messagebox.askyesno("Confirmar Saída", "Tem certeza que deseja sair do sistema?"):
            self.logout()

        # Inicia a verificação de atualizações (desativado temporariamente)
        # self.root.after(300000, self.check_for_updates) # 300000ms = 5 minutos
        
    def create_widgets(self):
        # Frame principal
        main_frame = ctk.CTkFrame(self.root, corner_radius=0, fg_color="#1f1f1f")
        main_frame.pack(fill="both", expand=True)
        
        # Barra lateral (menu)
        self.sidebar = ctk.CTkFrame(main_frame, width=250, corner_radius=10, fg_color="#171717")
        self.sidebar.pack(side="left", fill="y", padx=10, pady=10)
        
        # Área de conteúdo
        self.content = ctk.CTkFrame(main_frame, corner_radius=10, fg_color="#1f1f1f")
        self.content.pack(side="right", fill="both", expand=True, padx=10, pady=10)
        
        # Adicionar itens ao menu lateral
        self.add_menu_items()
        
        # Exibir conteúdo inicial
        self.show_home()
        
    def add_menu_items(self):
        # Perfil do usuário
        profile_frame = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        profile_frame.pack(pady=10, padx=10, fill="x")
        
        ctk.CTkLabel(profile_frame, text=f"Usuário: {self.user['username']}", 
                     font=ctk.CTkFont(size=14, weight="bold"), text_color="white").pack(anchor="w")
        ctk.CTkLabel(profile_frame, text=f"Cargo: {self.user['role']}", 
                     font=ctk.CTkFont(size=12), text_color="white").pack(anchor="w")
        
        # Separador
        ctk.CTkFrame(self.sidebar, height=2, fg_color="gray").pack(fill="x", padx=10, pady=10)
        
        # Frame rolável para os itens do menu
        menu_scroll_frame = ctk.CTkScrollableFrame(self.sidebar, fg_color="transparent", corner_radius=0)
        menu_scroll_frame.pack(fill="both", expand=True)
        
        # Itens do menu
        menu_items = [
            "INICIO",
            "PEDIDOS",
            "TRILHADEIRA",
            "CADASTRO",
            "MATERIAL",
            "VINCULAR PRODUTO x CLIENTE",
            "OBRAS",
            "GERAR RELATORIO",
            "GALERIA",            
            "BUSCAR PDF",
            "FERRAMENTAS",
            "PROGRAMAÇÃO",
            "PRODUÇÃO",
            "ESTOQUE",
            "EXPEDIÇÃO",
            "APONTAMENTO",
            "ADMIN",
            "SAIR"
        ]
        
        for item in menu_items:
            btn = ctk.CTkButton(
                menu_scroll_frame, 
                text=item, 
                command=lambda i=item: self.menu_action(i),
                corner_radius=8,
                text_color="white",
                anchor="w",
                fg_color="transparent",
                border_color="gray50",
                border_width=1
            )
            btn.pack(fill="x", padx=0, pady=3)
            
    def menu_action(self, item):
        if item == "SAIR":
            if messagebox.askyesno("Confirmar Saída", "Tem certeza que deseja sair do sistema?"):
                self.logout()
        elif item == "INICIO":
            self.show_home()
        elif item == "OBRAS":
            self.show_obras()
        elif item == "PEDIDOS":
            self.show_pedidos()
        elif item == "TRILHADEIRA":
            self.show_trilhadeira()
        elif item == "MATERIAL":
            self.show_material()
        elif item == "CADASTRO":
            self.show_cadastro()
        elif item == "VINCULAR PRODUTO x CLIENTE":
            self.show_vincular()
        elif item == "GERAR RELATORIO":
            self.show_relatorio()
        elif item == "GALERIA":
            self.show_galeria()
        elif item == "BUSCAR PDF":
            self.show_buscar_pdf()
        elif item == "FERRAMENTAS":
            self.show_aproveitamento()
        elif item == "ESTOQUE":
            self.show_estoque()
        elif item == "PROGRAMAÇÃO":
            self.show_programacao()
        else:
            self.show_content(item)
            
    def fetch_slide_data(self):
        """Busca dados para o slide show em uma thread separada"""
        def fetch_data():
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
                    sql = """
                        SELECT 
                            p.idpedido,
                            p.numero_pedido AS pedido,
                            ac.cliente AS nome_cliente,
                            ac.endereco,
                            ci.id_item AS id_vinculo,
                            ci.status_producao,
                            pai.descricao AS equipamento_pai,
                            filho.descricao AS conjunto
                        FROM cliente_item ci
                        JOIN pedido p ON ci.idpedido = p.idpedido
                        JOIN add_cliente ac ON p.idcliente = ac.idcliente
                        JOIN itens pai ON ci.item_raiz_id = pai.id
                        JOIN itens filho ON ci.id_item_fk = filho.id
                        ORDER BY p.idpedido DESC
                    """
                    cursor.execute(sql)
                    self.slide_data = cursor.fetchall()
                    
                    # Contar status para o gráfico de pizza
                    self.status_counts = {}
                    for item in self.slide_data:
                        status = item['status_producao']
                        self.status_counts[status] = self.status_counts.get(status, 0) + 1
                    
                    # Agrupar em grupos de 3
                    grouped_data = []
                    for i in range(0, len(self.slide_data), 3):
                        grouped_data.append(self.slide_data[i:i+3])
                    
                    self.slide_cycle = cycle(grouped_data)
                    
                    # Iniciar o slide show e atualizar gráfico
                    if self.is_running:
                        self.root.after(0, self.start_slide_transition)
                        self.root.after(0, self.update_pie_chart)
                    
            except Exception as e:
                print(f"Erro ao buscar dados do slide: {str(e)}")
            finally:
                if connection:
                    connection.close()
        
        # Executar em thread separada para não travar a interface
        thread = threading.Thread(target=fetch_data)
        thread.daemon = True
        thread.start()
    
    def get_status_color(self, status):
        """Retorna a cor com base no status de produção"""
        colors = {
            'Aguardando Programação': {'bg': '#ff4444', 'fg': '#ffffff'},
            'Aguardando PCP': {'bg': '#2196F3', 'fg': '#ffffff'},
            'Em Produção': {'bg': '#ffa000', 'fg': '#ffffff'},
            'Liberado para Expedição': {'bg': '#4CAF50', 'fg': '#ffffff'},  # Verde
        }
        return colors.get(status, {'bg': '#757575', 'fg': '#ffffff'})
    
    def start_slide_transition(self):
        """Inicia a transição do slide, preparando o próximo e chamando a animação."""
        if self.animating or not self.is_running or not hasattr(self, 'slide_container') or not self.slide_container.winfo_exists():
            return

        self.animating = True

        # Remove o label de carregamento se existir
        if hasattr(self, 'slide_loading_label') and self.slide_loading_label.winfo_exists():
            self.slide_loading_label.destroy()

        # Prepara o próximo slide no frame oculto
        next_items = next(self.slide_cycle)
        self.populate_slide_frame(self.hidden_frame, next_items)

        # Inicia a animação
        self.animate_slide(0)

    def animate_slide(self, step):
        """Executa um passo da animação de deslizamento."""
        if not self.is_running: return
        
        # Adiciona uma verificação para garantir que o widget ainda existe
        if not hasattr(self, 'slide_container') or not self.slide_container.winfo_exists():
            return
            
        duration = 25  # Número de passos para a animação
        width = self.slide_container.winfo_width()

        if step <= duration:
            # Calcula a posição para um efeito de "ease-in-out"
            progress = step / duration
            ease_progress = (1 - np.cos(progress * np.pi)) / 2

            # Move o frame visível para a esquerda (sai de 0 para -width)
            visible_x = -int(width * ease_progress)
            self.visible_frame.place(x=visible_x, y=0, relwidth=1, relheight=1)

            # Move o frame oculto para o centro (sai de width para 0)
            hidden_x = width - int(width * ease_progress)
            self.hidden_frame.place(x=hidden_x, y=0, relwidth=1, relheight=1)

            self.root.after(15, lambda: self.animate_slide(step + 1))
        else:
            # Fim da animação: troca os frames
            self.visible_frame, self.hidden_frame = self.hidden_frame, self.visible_frame
            # Posiciona o novo frame oculto fora da tela, pronto para a próxima
            self.hidden_frame.place_forget()
            
            self.animating = False
            # Agenda a próxima transição
            self.root.after(5000, self.start_slide_transition)

    def populate_slide_frame(self, frame, items):
        """Preenche um frame com os dados de um slide."""
        # Limpa o frame antes de adicionar novos widgets
        for widget in frame.winfo_children():
            widget.destroy()

        frame.columnconfigure(0, weight=1)
        frame.columnconfigure(1, weight=1)
        frame.columnconfigure(2, weight=1)

        # Exibe cada item
        for i, item in enumerate(items):
            colors = self.get_status_color(item['status_producao'])

            # Cria o card com CustomTkinter
            card_outer_frame = ctk.CTkFrame(
                frame, 
                corner_radius=10, 
                fg_color=colors['bg'],
                border_width=1,
                border_color="gray70"
            )
            card_outer_frame.grid(row=0, column=i, padx=10, pady=5, sticky="nsew")

            # Informações do item
            ctk.CTkLabel(
                card_outer_frame,
                text=f"Cliente: {item['nome_cliente']}", 
                text_color=colors['fg'],
                font=ctk.CTkFont(family='Segoe UI', size=13, weight='bold'),
                anchor='w'
            ).pack(pady=(10, 0), padx=10, fill='x')
            
            ctk.CTkLabel(
                card_outer_frame,
                text=f"Endereço: {item['endereco']}", 
                text_color=colors['fg'],
                font=ctk.CTkFont(family='Segoe UI', size=12),
                anchor='w'
            ).pack(pady=2, padx=10, fill='x')
            
            ctk.CTkLabel(
                card_outer_frame,
                text=f"Equipamento: {item['equipamento_pai']}", 
                text_color=colors['fg'],
                font=ctk.CTkFont(family='Segoe UI', size=12),
                anchor='w'
            ).pack(pady=2, padx=10, fill='x')
            
            ctk.CTkLabel(
                card_outer_frame,
                text=f"Conjunto: {item['conjunto']}", 
                text_color=colors['fg'],
                font=ctk.CTkFont(family='Segoe UI', size=12),
                anchor='w'
            ).pack(pady=2, padx=10, fill='x')
            
            ctk.CTkLabel(
                card_outer_frame,
                text=f"Status: {item['status_producao']}", 
                text_color=colors['fg'],
                font=ctk.CTkFont(family='Segoe UI', size=13, weight='bold'),
                anchor='w'
            ).pack(pady=(5, 10), padx=10, fill='x')
    
    def update_pie_chart(self):
        """Atualiza o gráfico de pizza com a distribuição de status"""
        # Verifica se a aplicação ainda está rodando e se o frame ainda existe
        if not self.is_running or not hasattr(self, 'pie_frame') or not self.pie_frame.winfo_exists():
            return
            
        # Remove o label de carregamento se existir
        if hasattr(self, 'pie_loading_label') and self.pie_loading_label.winfo_exists():
            self.pie_loading_label.destroy()
            
        # Limpa o frame do gráfico
        for widget in self.pie_frame.winfo_children():
            widget.destroy()
            
        # Cria um frame para conter o gráfico e a legenda
        chart_container = ctk.CTkFrame(self.pie_frame, fg_color="transparent")
        chart_container.pack(fill="both", expand=True)
        
        # Frame para o gráfico
        chart_frame = ctk.CTkFrame(chart_container, fg_color="transparent")
        chart_frame.pack(side="left", fill="both", expand=True)
        
        # Frame para a legenda
        legend_frame = ctk.CTkFrame(chart_container, fg_color="transparent")
        legend_frame.pack(side="right", fill="y", padx=20)
        
        # Cria a figura do matplotlib
        fig = Figure(figsize=(5, 4), dpi=80)
        ax = fig.add_subplot(111)
        
        # Prepara os dados para o gráfico
        labels = list(self.status_counts.keys())
        sizes = list(self.status_counts.values())
        
        # Cores para cada status
        colors = [self.get_status_color(label)['bg'] for label in labels]
        
        # Cria o gráfico de pizza sem labels
        wedges, texts = ax.pie(
            sizes, 
            colors=colors,
            startangle=90
        )
        
        # Adiciona porcentagens no gráfico
        total = sum(sizes)
        for i, wedge in enumerate(wedges):
            angle = (wedge.theta2 - wedge.theta1) / 2.0 + wedge.theta1
            x = 0.7 * np.cos(np.radians(angle))
            y = 0.7 * np.sin(np.radians(angle))
            percentage = 100. * sizes[i] / total
            ax.text(x, y, f'{percentage:.1f}%', ha='center', va='center', fontweight='bold', color='white')
        
        ax.axis('equal')  # Garante que o gráfico seja circular
        
        # Adiciona título
        ax.set_title('Distribuição de Status', fontsize=12, fontweight='bold', color='white')
        
        # Adiciona a figura ao Tkinter
        canvas = FigureCanvasTkAgg(fig, chart_frame)
        # Usa a mesma cor de fundo da página para o gráfico
        fig.patch.set_facecolor("#1f1f1f")
        canvas.draw()
        canvas.get_tk_widget().pack(fill="both", expand=True)
        
        # Cria a legenda ao lado do gráfico
        ctk.CTkLabel(legend_frame, text="Legenda:", font=ctk.CTkFont(size=12, weight="bold"), text_color='white').pack(pady=(0, 10))
        
        for i, (status, count) in enumerate(self.status_counts.items()):
            color = self.get_status_color(status).get('bg', '#757575')
            
            # Frame para cada item da legenda
            legend_item = ctk.CTkFrame(legend_frame, fg_color="transparent")
            legend_item.pack(fill="x", pady=2)
            
            # Quadrado colorido
            color_label = ctk.CTkLabel(legend_item, text="", width=15, height=15, fg_color=color, corner_radius=4)
            color_label.pack(side="left", padx=(0, 5))
            
            # Texto da legenda
            percentage = 100. * count / total
            text = f"{status} ({count} - {percentage:.1f}%)"
            ctk.CTkLabel(legend_item, text=text, font=ctk.CTkFont(size=11), text_color="white").pack(side="left")
        
    def show_home(self):
        # Limpa o conteúdo atual
        for widget in self.content.winfo_children():
            widget.destroy()

        # Conteúdo da página inicial
        title = ctk.CTkLabel(self.content, text="Página Inicial", font=ctk.CTkFont(size=24, weight="bold"), text_color="white")
        title.pack(pady=20)
        
        # Informações do usuário
        user_frame = ctk.CTkFrame(self.content, fg_color="transparent")
        user_frame.pack(pady=10)
        
        ctk.CTkLabel(user_frame, text=f"Bem-vindo, {self.user['username']}!",
                     font=ctk.CTkFont(size=16), text_color="white").pack()
        ctk.CTkLabel(user_frame, text=f"Seu cargo: {self.user['role']}",
                     font=ctk.CTkFont(size=14), text_color="white").pack()
        ctk.CTkLabel(user_frame, text=f"Último acesso: {self.user['ultimo_acesso']}",
                     font=ctk.CTkFont(size=12), text_color="white").pack()
        
        # Separador
        ctk.CTkFrame(self.content, height=1, fg_color="gray").pack(fill="x", padx=20, pady=20)
        
        # Título do slide show
        ctk.CTkLabel(self.content, text="Status de Produção - Itens em Andamento",
                     font=ctk.CTkFont(size=16, weight="bold"), text_color="white").pack()
        
        # Frame para o slide show
        self.slide_container = ctk.CTkFrame(self.content, fg_color="transparent")
        self.slide_container.pack(pady=10, padx=10, fill="x", expand=False)
        self.slide_container.configure(height=150) # Altura fixa para o container

        # Frames para a animação
        self.visible_frame = ctk.CTkFrame(self.slide_container, fg_color="transparent")
        self.hidden_frame = ctk.CTkFrame(self.slide_container, fg_color="transparent")
        self.visible_frame.place(x=0, y=0, relwidth=1, relheight=1)
        self.hidden_frame.place(x=self.root.winfo_width(), y=0, relwidth=1, relheight=1) # Começa fora da tela

        # Label de carregamento
        self.slide_loading_label = ctk.CTkLabel(
            self.slide_container, 
            text="Carregando dados...", 
            font=ctk.CTkFont(size=14), text_color="white"
        )
        self.slide_loading_label.place(relx=0.5, rely=0.5, anchor='center')
        
        # Separador
        ctk.CTkFrame(self.content, height=1, fg_color="gray").pack(fill="x", padx=20, pady=20)
        
        # Título do gráfico de pizza
        ctk.CTkLabel(self.content, text="Distribuição de Status",
                     font=ctk.CTkFont(size=16, weight="bold"), text_color="white").pack()
        
        # Frame para o gráfico de pizza
        self.pie_frame = ctk.CTkFrame(self.content, height=300, fg_color="transparent")
        self.pie_frame.pack(pady=10, padx=20, fill="both", expand=True)
        
        # Label de carregamento para o gráfico
        self.pie_loading_label = ctk.CTkLabel( # type: ignore
            self.pie_frame, 
            text="Carregando gráfico...", 
            font=ctk.CTkFont(size=14), text_color="white"
        )
        self.pie_loading_label.pack()
        
        # Buscar dados novamente ao voltar para a home
        self.fetch_slide_data()
        
    def show_content(self, page_name):
        # Limpa o conteúdo atual
        for widget in self.content.winfo_children():
            widget.destroy()
            
        # Exibe o nome da página
        title = ctk.CTkLabel(self.content, text=f"Página: {page_name}", font=ctk.CTkFont(size=24, weight="bold"))
        title.pack(pady=20)
        
        # Aqui você pode adicionar o conteúdo específico de cada página
        content_label = ctk.CTkLabel(self.content, text="Conteúdo em desenvolvimento...")
        content_label.pack(pady=10)
        
    def logout(self):
        # Para a atualização automática
        self.is_running = False
        
        # Atualiza status para offline no banco
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
                update_sql = "UPDATE usuarios SET status = 'offline' WHERE id = %s"
                cursor.execute(update_sql, (self.user['id'],))
                connection.commit()
                
        except Exception as e:
            print(f"Erro ao atualizar status: {str(e)}")
        finally:
            if connection:
                connection.close()
        
        # Fecha a aplicação
        self.root.destroy()

    def show_pedidos(self):
        # Limpa o conteúdo atual
        for widget in self.content.winfo_children():
            widget.destroy()
        
        # Cria e exibe a aplicação de pedidos
        pedidos_app = PedidosApp(self.content, self.user)
        
    def show_obras(self):
        # Limpa o conteúdo atual
        for widget in self.content.winfo_children():
            widget.destroy()
        
        # Cria e exibe a aplicação de obras
        obras_app = ObrasApp(self.content, self.user)

    def show_trilhadeira(self):
        # Limpa o conteúdo atual
        for widget in self.content.winfo_children():
            widget.destroy()
        
        # Cria e exibe a aplicação de trilhadeira
        trilhadeira_app = TrilhadeiraApp(self.content, self.user)

    def show_cadastro(self):
        # Limpa o conteúdo atual
        for widget in self.content.winfo_children():
            widget.destroy()
        
        # Cria e exibe a aplicação de cadastro de itens
        cadastro_app = CadastroItensApp(self.content, self.user)

    def show_material(self):
        # Limpa o conteúdo atual
        for widget in self.content.winfo_children():
            widget.destroy()
        
        # Cria e exibe a aplicação de material
        material_app = MaterialApp(self.content, self.user)

    def show_vincular(self):
        # Limpa o conteúdo atual
        for widget in self.content.winfo_children():
            widget.destroy()
        
        # Cria e exibe a aplicação de vinculação
        vincular_app = VincularApp(self.content, self.user)

    def show_relatorio(self):
        # Limpa o conteúdo atual
        for widget in self.content.winfo_children():
            widget.destroy()
        
        # Cria e exibe a aplicação de relatório
        relatorio_app = RelatorioApp(self.content, self.user)

    def show_galeria(self):
        # Limpa o conteúdo atual
        for widget in self.content.winfo_children():
            widget.destroy()
        
        # Cria e exibe a aplicação de galeria
        galeria_app = GaleriaApp(self.content, self.user)

    def show_buscar_pdf(self):
        """Abre a funcionalidade de busca de PDF em uma nova janela."""
        # Cria uma nova janela (Toplevel) que fica sobre a janela principal.
        pdf_window = ctk.CTkToplevel(self.root)
        pdf_window.title("Buscar PDF")
        pdf_window.geometry("400x150")  # Tamanho mais compacto
        pdf_window.transient(self.root) # Mantém a janela na frente da principal
        pdf_window.grab_set() # Foca na nova janela
        
        # Cria a aplicação de busca de PDF dentro da nova janela.
        buscar_pdf_app = BuscarPDFApp(pdf_window, self.user)

    def show_aproveitamento(self):
        # Limpa o conteúdo atual
        for widget in self.content.winfo_children():
            widget.destroy()
        
        # Cria e exibe a aplicação de aproveitamento
        aproveitamento_app = AproveitamentoApp(self.content, self.user)

    def show_estoque(self):
        # Limpa o conteúdo atual
        for widget in self.content.winfo_children():
            widget.destroy()
        
        # Cria e exibe a aplicação de estoque
        estoque_app = EstoqueApp(self.content, self.user)    
    
    def show_programacao(self):
        # Limpa o conteúdo atual
        for widget in self.content.winfo_children():
            widget.destroy()
        
        # Cria e exibe a aplicação de programação
        programacao_app = ProgramacaoApp(self.content, self.user)
        
    def check_for_updates(self):
        """Verifica periodicamente se o arquivo principal foi modificado."""
        if not self.is_running or self.update_check_paused or self.initial_mtime == 0:
            return

        try:
            current_mtime = os.path.getmtime(sys.argv[0])
            if current_mtime != self.initial_mtime:
                self.update_check_paused = True # Pausa futuras verificações
                self.show_update_notification()
            else:
                # Reagenda a verificação
                self.root.after(300000, self.check_for_updates)
        except (OSError, IndexError):
            # Se o arquivo não for encontrado, para de verificar
            self.update_check_paused = True

    def show_update_notification(self):
        """Exibe uma janela Toplevel com opções para reiniciar."""
        update_win = ctk.CTkToplevel(self.root)
        update_win.title("Atualização Disponível")
        update_win.geometry("350x150")
        update_win.transient(self.root)
        update_win.grab_set()
        update_win.resizable(False, False)

        # Centraliza a janela
        self.root.update_idletasks()
        x = self.root.winfo_x() + (self.root.winfo_width() // 2) - (350 // 2)
        y = self.root.winfo_y() + (self.root.winfo_height() // 2) - (150 // 2)
        update_win.geometry(f"+{x}+{y}")

        main_frame = ctk.CTkFrame(update_win, fg_color="transparent")
        main_frame.pack(expand=True, fill="both", padx=20, pady=20)

        ctk.CTkLabel(main_frame, text="O sistema foi atualizado!", font=ctk.CTkFont(size=16, weight="bold")).pack(pady=(0, 10))
        ctk.CTkLabel(main_frame, text="Recomendamos reiniciar para aplicar as mudanças.").pack()

        btn_frame = ctk.CTkFrame(main_frame, fg_color="transparent")
        btn_frame.pack(pady=(20, 0), fill="x", expand=True)

        def restart_action():
            """Ação para o botão de reiniciar."""
            update_win.destroy()
            self.logout() # Apenas fecha o app, o usuário reabre manualmente.

        ctk.CTkButton(btn_frame, text="Reiniciar Agora", command=restart_action).pack(side="left", expand=True, padx=(0, 5))
        ctk.CTkButton(btn_frame, text="Mais Tarde", command=update_win.destroy, fg_color="gray").pack(side="right", expand=True, padx=(5, 0))

    def restart_app(self):
        """(OBSOLETO) Fecha e reinicia a aplicação."""
        self.is_running = False # Para todas as tarefas em background
        self.root.destroy()
        # Reinicia o processo
        os.execv(sys.executable, ['python'] + sys.argv)

    def run(self):
        self.root.mainloop()