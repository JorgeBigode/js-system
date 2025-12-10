import tkinter as tk
from tkinter import ttk, messagebox
import os
import platform
import subprocess

# Defina o caminho UNC para a pasta de PDFs.
# O 'r' antes da string é importante para tratar as barras invertidas corretamente.
PDF_SHARE_UNC = r'\\smasrv2\SMA_PROJETOS\PCP2\1-PDFs'

class BuscarPDFApp:
    def __init__(self, parent, user):
        self.parent = parent
        self.user = user
        self.frame = ttk.Frame(parent)
        self.frame.pack(fill=tk.BOTH, expand=True)

        self.create_widgets()

    def create_widgets(self):
        # Frame principal para o formulário de busca
        form_frame = ttk.Frame(self.frame, padding="20")
        form_frame.pack(expand=True, fill=tk.BOTH)

        ttk.Label(form_frame, text="Digite o nome do arquivo (sem .pdf):", font=('Arial', 10)).pack(anchor='w')
        self.pdf_name_entry = ttk.Entry(form_frame, font=('Arial', 10))
        self.pdf_name_entry.pack(fill=tk.X, pady=(5, 10))
        self.pdf_name_entry.bind("<Return>", self.buscar_pdf) # Permite buscar com a tecla Enter
        self.pdf_name_entry.focus_set() # Coloca o foco no campo de texto ao abrir

        search_button = ttk.Button(form_frame, text="Buscar", command=self.buscar_pdf)
        search_button.pack(fill=tk.X)

    def buscar_pdf(self, event=None):
        pdf_base_name = self.pdf_name_entry.get().strip()
        if not pdf_base_name:
            messagebox.showwarning("Aviso", "Por favor, digite o nome do arquivo PDF.")
            return

        pdf_filename = f"{pdf_base_name}.pdf"
        pdf_full_path = os.path.join(PDF_SHARE_UNC, pdf_filename)

        # Verifica se o arquivo existe no caminho de rede
        if os.path.exists(pdf_full_path):
            try:
                # Abre o arquivo com o programa padrão do sistema operacional
                if platform.system() == "Windows":
                    os.startfile(pdf_full_path)
                elif platform.system() == "Darwin":  # macOS
                    subprocess.call(["open", pdf_full_path])
                else:  # Linux
                    subprocess.call(["xdg-open", pdf_full_path])
                
                messagebox.showinfo("Sucesso", f"Abrindo o arquivo:\n{pdf_filename}")

            except Exception as e:
                messagebox.showerror("Erro ao Abrir", f"Não foi possível abrir o arquivo PDF.\n\nCaminho: {pdf_full_path}\nErro: {e}")
        else:
            messagebox.showerror("Não Encontrado", 
                                 f"O arquivo '{pdf_filename}' não foi encontrado no diretório de projetos.\n\n"
                                 f"Verifique o nome do arquivo e sua conexão com a rede.")