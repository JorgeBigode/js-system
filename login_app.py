import customtkinter as ctk
from tkinter import messagebox
import pymysql
from werkzeug.security import check_password_hash
import datetime
from config import DB_HOST, DB_USER, DB_PASS, DB_NAME
from main_app import MainApp  # Importa a MainApp do novo arquivo
import configparser
import os
import sys
import base64

def resource_path(relative_path):
    """ Obtém o caminho absoluto para o recurso, funciona para dev e para PyInstaller """
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

class LoginApp:
    def __init__(self):
        # Janela principal
        self.root = ctk.CTk()
        self.root.title("Sistema de Login")
        self.root.iconbitmap(resource_path('img/icon-SILO.ico'))
        self.root.resizable(False, False)

        # Define o tema do CustomTkinter
        ctk.set_appearance_mode("light")  # "light", "dark", "system"
        ctk.set_default_color_theme("blue") # "blue", "green", "dark-blue"
        
        self.config_file = 'remember.ini'
        
        self.create_widgets()
        self.load_remembered_credentials()
        self.center_window(self.root, 400, 400)

    def center_window(self, window, width, height):
        """Centraliza uma janela na tela."""
        # Assegura que as dimensões da janela foram atualizadas
        window.update_idletasks()
        screen_width = window.winfo_screenwidth()
        screen_height = window.winfo_screenheight()
        x = (screen_width / 2) - (width / 2)
        y = (screen_height / 2) - (height / 2)
        window.geometry(f'{width}x{height}+{int(x)}+{int(y)}')

    def create_widgets(self):
        # Frame principal
        frame = ctk.CTkFrame(self.root, corner_radius=10)
        frame.pack(padx=20, pady=20, fill="both", expand=True)
        
        # Título
        label = ctk.CTkLabel(frame, text="Sistema de Login", font=ctk.CTkFont(size=20, weight="bold"))
        label.pack(pady=(20, 10))
        
        # Campo de usuário
        self.username_entry = ctk.CTkEntry(frame, placeholder_text="Usuário", width=250)
        self.username_entry.pack(pady=10, padx=20)
        
        # Campo de senha
        self.password_entry = ctk.CTkEntry(frame, placeholder_text="Senha", show="*", width=250)
        self.password_entry.pack(pady=10, padx=20)
        
        # Checkbox lembrar-me
        self.remember_var = ctk.BooleanVar()
        self.remember_check = ctk.CTkCheckBox(frame, text="Lembrar-me", variable=self.remember_var)
        self.remember_check.pack(pady=10, padx=20)
        
        # Botão de login
        button = ctk.CTkButton(frame, text="Login", command=self.login, width=250)
        button.pack(pady=20, padx=20)
        
        # Label de status
        self.status_label = ctk.CTkLabel(frame, text="")
        self.status_label.pack(pady=(0, 10))
        
        # Bind Enter key to login
        self.root.bind('<Return>', lambda event: self.login())
        
    def get_db_connection(self):
        """Estabelece conexão com o banco de dados"""
        try:
            connection = pymysql.connect(
                host=DB_HOST,
                user=DB_USER,
                password=DB_PASS,
                database=DB_NAME,
                charset='utf8mb4',
                cursorclass=pymysql.cursors.DictCursor
            )
            return connection
        except Exception as e:
            messagebox.showerror("Erro", f"Erro ao conectar com o banco: {str(e)}")
            return None

    def save_credentials(self, username, password):
        """Salva as credenciais no arquivo de configuração."""
        config = configparser.ConfigParser()
        config['Credentials'] = {
            'username': username,
            'password': base64.b64encode(password.encode('utf-8')).decode('utf-8') # Ofusca a senha
        }
        with open(self.config_file, 'w') as configfile:
            config.write(configfile)

    def load_remembered_credentials(self):
        """Carrega as credenciais salvas, se existirem."""
        if not os.path.exists(self.config_file):
            return

        config = configparser.ConfigParser()
        config.read(self.config_file)

        if 'Credentials' in config:
            username = config['Credentials'].get('username')
            encoded_password = config['Credentials'].get('password')

            if username and encoded_password:
                try:
                    password = base64.b64decode(encoded_password.encode('utf-8')).decode('utf-8')
                    self.username_entry.insert(0, username)
                    self.password_entry.insert(0, password)
                    self.remember_var.set(True)
                except Exception:
                    # Se houver erro na decodificação, limpa o arquivo corrompido
                    self.clear_saved_credentials()

    def clear_saved_credentials(self):
        """Limpa as credenciais salvas."""
        if os.path.exists(self.config_file):
            try:
                os.remove(self.config_file)
            except OSError as e:
                print(f"Erro ao remover o arquivo de configuração: {e}")

    def login(self):
        username = self.username_entry.get()
        password = self.password_entry.get()
        
        if not username or not password:
            self.status_label.configure(text="Preencha todos os campos!", text_color="red")
            return
            
        try:
            # Conecta ao banco
            connection = self.get_db_connection()
            if not connection:
                return
                
            with connection.cursor() as cursor:
                # Busca usuário no banco
                sql = "SELECT * FROM usuarios WHERE username = %s"
                cursor.execute(sql, (username,))
                user = cursor.fetchone()
                
                if user and check_password_hash(user['password'], password):
                    # Lógica do "Lembrar-me"
                    if self.remember_var.get():
                        self.save_credentials(username, password)
                    else:
                        self.clear_saved_credentials()

                    # Atualiza último acesso e status
                    now = datetime.datetime.now()
                    update_sql = "UPDATE usuarios SET ultimo_acesso = %s, status = 'online' WHERE id = %s"
                    cursor.execute(update_sql, (now, user['id']))
                    connection.commit()
                    
                    self.status_label.configure(text="Login bem-sucedido!", text_color="green")
                    messagebox.showinfo("Sucesso", f"Bem-vindo, {user['username']}!")
                    self.open_main_app(user)
                else:
                    self.status_label.configure(text="Credenciais inválidas!", text_color="red")
                    messagebox.showerror("Erro", "Usuário ou senha incorretos!")
                    
        except Exception as e:
            self.status_label.configure(text="Erro de conexão!", text_color="red")
            messagebox.showerror("Erro", f"Erro ao autenticar: {str(e)}")
        finally:
            if connection:
                connection.close()
    
    def open_main_app(self, user):
        # Fecha a janela de login
        self.root.destroy()
        
        # Abre a aplicação principal
        app = MainApp(user)
        app.run()
    
    def run(self):
        self.root.mainloop()

if __name__ == "__main__":
    app = LoginApp()
    app.run()