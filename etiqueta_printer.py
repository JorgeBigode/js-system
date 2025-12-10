import platform
from datetime import datetime
import sys
import tempfile
import os

import subprocess
import csv
# Importações condicionais para evitar erros em sistemas não-Windows
WIN32_AVAILABLE = False
if platform.system() == "Windows":
    try:
        import win32api
        import win32print
        import win32con
        import win32ui
        import win32gui
        WIN32_AVAILABLE = True
    except ImportError:
        pass  # A classe lidará com a ausência

try:
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib import colors, units
    from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
    REPORTLAB_AVAILABLE = True
except ImportError:
    REPORTLAB_AVAILABLE = False

def resource_path(relative_path):
    """ Obtém o caminho absoluto para o recurso, funciona para dev e para PyInstaller """
    try:
        # PyInstaller cria uma pasta temp e armazena o caminho em _MEIPASS
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

class EtiquetaPrinter:
    def __init__(self, config, main_window_handle=None):
        self.config = config
        self.config_filepath = resource_path('etiqueta_config.json')
        self.main_window_handle = main_window_handle

    def _mm_to_device_units(self, hDC, mm, is_horizontal=True):
        """Converte milímetros para unidades do dispositivo (pixels)."""
        if is_horizontal:
            pixels_per_mm = win32print.GetDeviceCaps(hDC, win32con.HORZRES) / win32print.GetDeviceCaps(hDC, win32con.HORZSIZE)
            return int(mm * pixels_per_mm)
        else:
            pixels_per_mm = win32print.GetDeviceCaps(hDC, win32con.VERTRES) / win32print.GetDeviceCaps(hDC, win32con.VERTSIZE)
            return int(mm * pixels_per_mm)

    def _pt_to_logical_units(self, hDC, pt):
        """Converte pontos (font size) para unidades lógicas de altura da fonte."""
        return -int(pt * win32print.GetDeviceCaps(hDC, win32con.LOGPIXELSY) / 72)

    def _mm_to_dots(self, mm, dpi=203):
        """Converte milímetros para dots (pontos da impressora). Padrão 203 dpi."""
        INCH_TO_MM = 25.4
        return int((mm / INCH_TO_MM) * dpi)

    def imprimir_direto_windows(self, pedido_info, itens_para_imprimir, printer_name, rotacionar=False):
        if not WIN32_AVAILABLE:
            raise OSError("A biblioteca pywin32 é necessária para impressão direta.")

        dc_obj = None
        try:
            dc_obj = win32ui.CreateDC()
            dc_obj.CreatePrinterDC(printer_name)

            if rotacionar:
                h_printer = win32print.OpenPrinter(printer_name)
                try:
                    # Obtém o DEVMODE atual da impressora
                    devmode = win32print.GetPrinter(h_printer, 2)['pDevMode']
                    
                    # Troca para paisagem (landscape)
                    devmode.Orientation = win32con.DMORIENT_LANDSCAPE
                    
                    # Aplica o DEVMODE modificado ao contexto do dispositivo
                    win32gui.ResetDC(dc_obj.GetSafeHdc(), devmode)
                finally:
                    win32print.ClosePrinter(h_printer)

            h_dc = dc_obj.GetSafeHdc()
            dc_obj.SetMapMode(win32con.MM_TEXT)

            dc_obj.StartDoc("Etiquetas de Obra")

            for item in itens_para_imprimir:
                dc_obj.StartPage()
                
                fonts_to_delete = []
                original_font = None
                original_brush = None
                try:
                    # --- Configurações e Desenho ---
                    largura_mm = self.config['largura_mm']
                    altura_mm = self.config['altura_mm']
                    margem_esq_mm = self.config['margem_esq_mm']
                    margem_sup_mm = self.config['margem_sup_mm']

                    if rotacionar:
                        largura_mm, altura_mm = altura_mm, largura_mm
                        # Quando rotaciona, a margem superior vira a margem esquerda e vice-versa
                        margem_esq_mm, margem_sup_mm = margem_sup_mm, margem_esq_mm

                    width_px = self._mm_to_device_units(h_dc, largura_mm, is_horizontal=True)
                    height_px = self._mm_to_device_units(h_dc, altura_mm, is_horizontal=False)
                    margin_x_px = self._mm_to_device_units(h_dc, margem_esq_mm, is_horizontal=True)
                    margin_y_px = self._mm_to_device_units(h_dc, margem_sup_mm, is_horizontal=False)
                    y_pos = margin_y_px

                    # Define cor e fundo do texto
                    dc_obj.SetTextColor(win32api.RGB(0, 0, 0))
                    dc_obj.SetBkMode(win32con.TRANSPARENT)

                    # --- DESENHA A BORDA PRIMEIRO ---
                    # Seleciona um pincel "nulo" para que o retângulo não seja preenchido
                    hollow_brush = win32ui.CreateBrush(win32con.BS_NULL, 0, 0)
                    original_brush = dc_obj.SelectObject(hollow_brush)
                    # Desenha o retângulo usando as coordenadas corretas
                    dc_obj.Rectangle((margin_x_px, margin_y_px, width_px - margin_x_px, height_px - margin_y_px))
                    # Restaura o pincel original
                    if original_brush: dc_obj.SelectObject(original_brush)

                    # Fontes
                    font_header = win32ui.CreateFont({"name": "Helvetica", "height": self._pt_to_logical_units(h_dc, self.config['fonte_header'])})
                    font_cliente = win32ui.CreateFont({"name": "Helvetica", "height": self._pt_to_logical_units(h_dc, self.config['fonte_cliente'])})
                    font_equip = win32ui.CreateFont({"name": "Helvetica", "height": self._pt_to_logical_units(h_dc, self.config['fonte_equipamento']), "weight": win32con.FW_BOLD})
                    font_conj = win32ui.CreateFont({"name": "Helvetica", "height": self._pt_to_logical_units(h_dc, self.config['fonte_conjunto'])})
                    font_qtde = win32ui.CreateFont({"name": "Helvetica", "height": self._pt_to_logical_units(h_dc, self.config['fonte_quantidade']), "weight": win32con.FW_BOLD})
                    fonts_to_delete = [font_header, font_cliente, font_equip, font_conj, font_qtde]

                    # Salva a fonte original para restaurar depois
                    original_font = dc_obj.SelectObject(font_header)

                    # --- Função auxiliar para desenhar texto ---
                    def _draw_text(text, font, align='center', y_offset_mm=3):
                        nonlocal y_pos
                        dc_obj.SelectObject(font)
                        text_width, text_height = dc_obj.GetTextExtent(text)
                        
                        x = 0
                        if align == 'center':
                            x = (width_px - text_width) // 2
                        elif align == 'left':
                            x = margin_x_px
                        elif align == 'right':
                            x = width_px - margin_x_px - text_width
                        
                        dc_obj.TextOut(x, y_pos, text)
                        y_pos += text_height + self._mm_to_device_units(h_dc, y_offset_mm, False)
                        return text_height # Retorna a altura para uso se necessário

                    if not rotacionar:
                        # --- LÓGICA ORIGINAL (RETRATO) ---
                        # Cabeçalho
                        ped_text = f"PED: {pedido_info['numero_pedido']}"
                        data_text = datetime.now().strftime('%d/%m/%Y %H:%M')
                        dc_obj.SelectObject(font_header)
                        dc_obj.TextOut(margin_x_px, y_pos, ped_text) # Alinhado à esquerda
                        text_width_data, text_height_header = dc_obj.GetTextExtent(data_text)
                        dc_obj.TextOut(width_px - margin_x_px - text_width_data, y_pos, data_text) # Alinhado à direita
                        y_pos += text_height_header + self._mm_to_device_units(h_dc, 3, False)

                        # Conteúdo centralizado usando a função auxiliar
                        _draw_text(pedido_info.get('cliente', ''), font_cliente, y_offset_mm=0)
                        _draw_text(pedido_info.get('endereco', ''), font_cliente)
                        _draw_text(item.get('nome_equipamento', ''), font_equip)
                        _draw_text(item.get('conjunto', ''), font_conj)
                        _draw_text(f"QTDE: {item.get('quantidade_prod', '')}", font_qtde)
                    else:
                        # --- NOVA LÓGICA (PAISAGEM) ---
                        # O conteúdo é desenhado em colunas, da esquerda para a direita.
                        x_pos = margin_x_px
                        
                        # Coluna 1: Cabeçalho e Cliente
                        dc_obj.SelectObject(font_header)
                        ped_text = f"PED: {pedido_info['numero_pedido']}"
                        data_text = datetime.now().strftime('%d/%m/%Y %H:%M')
                        _, text_height = dc_obj.GetTextExtent(ped_text)
                        dc_obj.TextOut(x_pos, margin_y_px, ped_text)
                        dc_obj.TextOut(x_pos, margin_y_px + text_height, data_text)

                        dc_obj.SelectObject(font_cliente)
                        cliente_text = pedido_info.get('cliente', '')
                        endereco_text = pedido_info.get('endereco', '')
                        _, text_height_cliente = dc_obj.GetTextExtent(cliente_text)
                        dc_obj.TextOut(x_pos, margin_y_px + (text_height * 2) + self._mm_to_device_units(h_dc, 5, False), cliente_text)
                        dc_obj.TextOut(x_pos, margin_y_px + (text_height * 2) + text_height_cliente + self._mm_to_device_units(h_dc, 5, False), endereco_text)

                        # Avança a posição X para a próxima "coluna"
                        # Pega a maior largura entre os textos da primeira coluna para definir o avanço
                        w1, _ = dc_obj.GetTextExtent(ped_text)
                        w2, _ = dc_obj.GetTextExtent(data_text)
                        w3, _ = dc_obj.GetTextExtent(cliente_text)
                        w4, _ = dc_obj.GetTextExtent(endereco_text)
                        x_pos += max(w1, w2, w3, w4) + self._mm_to_device_units(h_dc, 5, True)

                        # Coluna 2: Equipamento, Conjunto, Quantidade (centralizados no espaço restante)
                        remaining_width = width_px - x_pos - margin_x_px
                        center_x_of_remaining = x_pos + remaining_width // 2
                        y_pos_col2 = margin_y_px + self._mm_to_device_units(h_dc, 5, False)

                        dc_obj.SelectObject(font_equip)
                        equip_text = item.get('nome_equipamento', '')
                        text_width, text_height = dc_obj.GetTextExtent(equip_text)
                        dc_obj.TextOut(center_x_of_remaining - text_width // 2, y_pos_col2, equip_text)
                        y_pos_col2 += text_height + self._mm_to_device_units(h_dc, 5, False)

                        dc_obj.SelectObject(font_conj)
                        conj_text = item.get('conjunto', '')
                        text_width, text_height = dc_obj.GetTextExtent(conj_text)
                        dc_obj.TextOut(center_x_of_remaining - text_width // 2, y_pos_col2, conj_text)
                        y_pos_col2 += text_height + self._mm_to_device_units(h_dc, 5, False)

                        dc_obj.SelectObject(font_qtde)
                        qtde_text = f"QTDE: {item.get('quantidade_prod', '')}"
                        text_width, _ = dc_obj.GetTextExtent(qtde_text)
                        dc_obj.TextOut(center_x_of_remaining - text_width // 2, y_pos_col2, qtde_text)

                finally:
                    # Limpeza segura dos recursos GDI
                    if original_font:
                        dc_obj.SelectObject(original_font)
                    if original_brush:
                        dc_obj.SelectObject(original_brush)
                    for font in fonts_to_delete: # type: ignore
                        win32gui.DeleteObject(font.GetSafeHandle())
                
                dc_obj.EndPage()

            dc_obj.EndDoc()
        finally:
            if dc_obj:
                dc_obj.DeleteDC()

    def imprimir_direto_ppla(self, pedido_info, itens_para_imprimir, printer_name, rotacionar=False):
        """Gera comandos PPLA e os envia diretamente para a impressora."""
        if not WIN32_AVAILABLE:
            raise OSError("A biblioteca pywin32 é necessária para impressão direta via PPLA.")

        # Configurações da etiqueta em dots (203 dpi)
        largura_dots = self._mm_to_dots(self.config['largura_mm'])
        altura_dots = self._mm_to_dots(self.config['altura_mm'])
        margem_esq_dots = self._mm_to_dots(self.config['margem_esq_mm'])
        margem_sup_dots = self._mm_to_dots(self.config['margem_sup_mm'])

        # Fontes PPLA (mapeamento de pt para tipo de fonte PPLA)
        # PPLA tem fontes bitmap de 1 a 5 e fontes TrueType. Usaremos as bitmap para simplicidade.
        # Tamanhos aproximados em pt: 1(6pt), 2(8pt), 3(10pt), 4(12pt), 5(24pt)
        def map_font_size_to_ppla(pt_size):
            if pt_size <= 7: return '1'
            if pt_size <= 9: return '2'
            if pt_size <= 11: return '3'
            if pt_size <= 18: return '4'
            return '5'

        font_header_ppla = map_font_size_to_ppla(self.config['fonte_header'])
        font_cliente_ppla = map_font_size_to_ppla(self.config['fonte_cliente'])
        font_equip_ppla = map_font_size_to_ppla(self.config['fonte_equipamento'])
        font_conj_ppla = map_font_size_to_ppla(self.config['fonte_conjunto'])
        font_qtde_ppla = map_font_size_to_ppla(self.config['fonte_quantidade'])

        # Mapeia o tamanho da fonte PPLA para suas dimensões em dots (largura, altura)
        PPLA_FONT_DIMS = {
            '1': (8, 12), '2': (10, 16), '3': (12, 20),
            '4': (14, 24), '5': (32, 48)
        }

        def get_text_width_dots(text, font_id):
            """Estima a largura do texto em dots para fontes bitmap PPLA."""
            if font_id not in PPLA_FONT_DIMS:
                font_id = '3' # Padrão
            char_width = PPLA_FONT_DIMS[font_id][0]
            # Multiplicador para compensar o espaçamento entre caracteres
            return int(len(text) * char_width * 1.1)

        # Inicia a comunicação com a impressora
        h_printer = win32print.OpenPrinter(printer_name)
        try:
            for item in itens_para_imprimir:
                # Inicia um novo trabalho de impressão
                job_info = ("Etiqueta PPLA", None, "RAW")
                win32print.StartDocPrinter(h_printer, 1, job_info)
                
                try:
                    # --- Montagem dos comandos PPLA ---
                    # \x02 = STX (Start of Text), \x0D = CR (Carriage Return)
                    # L = Limpa o buffer da imagem
                    # H15 = Define o nível de escuridão (0-19)

                    # Orientação: 1 para normal (retrato), 2 para 90 graus, 3 para 180, 4 para 270
                    orientation = '2' if rotacionar else '1'

                    # Desenha a borda
                    # b{x},{y},{line_w},{line_h},{box_w},{box_h}
                    box_w = largura_dots - (2 * margem_esq_dots)
                    box_h = altura_dots - (2 * margem_sup_dots)
                    
                    # Adiciona o comando de início e limpeza do buffer
                    ppla_commands = b'\x02L\x0DH15\x0D'
                    ppla_commands += f'b{margem_esq_dots},{margem_sup_dots},3,3,{box_w},{box_h}\x0D'.encode('cp850', errors='replace')

                    # --- Funções auxiliares para adicionar texto com alinhamento ---
                    def add_text(x, y, font_id, text, bold=False):
                        text = text.replace('"', '""') # Escapa aspas
                        return f'A,{x},{y},{orientation},{font_id},{font_id},{ "B" if bold else "N"},"{text}"\x0D'.encode('cp850', errors='replace')

                    def add_centered_text(y, font_id, text, bold=False):
                        text_width = get_text_width_dots(text, font_id)
                        printable_width = largura_dots - (2 * margem_esq_dots)
                        x = margem_esq_dots + (printable_width - text_width) // 2
                        return add_text(x, y, font_id, text, bold)

                    def add_right_aligned_text(y, font_id, text, bold=False):
                        text_width = get_text_width_dots(text, font_id)
                        x = largura_dots - margem_esq_dots - text_width - 15 # padding
                        return add_text(x, y, font_id, text, bold)

                    # --- Posicionamento do conteúdo ---
                    # Os eixos x e y são sempre relativos à orientação retrato.
                    y_pos = margem_sup_dots + 20 # Padding interno

                    # Cabeçalho
                    ped_text = f"PED: {pedido_info['numero_pedido']}"
                    data_text = datetime.now().strftime('%d/%m/%Y %H:%M')
                    
                    ppla_commands += add_text(margem_esq_dots + 15, y_pos, font_header_ppla, ped_text)
                    ppla_commands += add_right_aligned_text(y_pos, font_header_ppla, data_text)
                    y_pos += PPLA_FONT_DIMS[font_header_ppla][1] + 20 # Avança com base na altura da fonte + espaçamento

                    # Cliente e Endereço (centralizados)
                    cliente_text = pedido_info.get('cliente', '')
                    endereco_text = pedido_info.get('endereco', '')
                    
                    ppla_commands += add_centered_text(y_pos, font_cliente_ppla, cliente_text)
                    y_pos += PPLA_FONT_DIMS[font_cliente_ppla][1] + 5
                    
                    ppla_commands += add_centered_text(y_pos, font_cliente_ppla, endereco_text)
                    y_pos += PPLA_FONT_DIMS[font_cliente_ppla][1] + 30

                    # Equipamento, Conjunto, Quantidade
                    equip_text = item.get('nome_equipamento', '')
                    ppla_commands += add_centered_text(y_pos, font_equip_ppla, equip_text, bold=True)
                    y_pos += PPLA_FONT_DIMS[font_equip_ppla][1] + 30

                    conj_text = item.get('conjunto', '')
                    ppla_commands += add_centered_text(y_pos, font_conj_ppla, conj_text)
                    y_pos += PPLA_FONT_DIMS[font_conj_ppla][1] + 30

                    qtde_text = f"QTDE: {item.get('quantidade_prod', '')}"
                    ppla_commands += add_centered_text(y_pos, font_qtde_ppla, qtde_text, bold=True)

                    # Fim do comando:
                    # Q1,1 = Imprimir 1 cópia de 1 etiqueta
                    # E = End job e efetivamente imprime
                    ppla_commands += b'Q1,1\x0D'
                    ppla_commands += b'E\x0D'
                    win32print.WritePrinter(h_printer, ppla_commands)
                finally:
                    win32print.EndDocPrinter(h_printer) # Finaliza o trabalho de impressão
        finally:
            win32print.ClosePrinter(h_printer)

    def imprimir_com_bartender(self, pedido_info, itens_para_imprimir, printer_name):
        """
        Gera um arquivo de dados CSV e chama o BarTender via linha de comando para imprimir.
        """
        if not WIN32_AVAILABLE:
            raise OSError("A impressão com BarTender requer um ambiente Windows.")

        # Caminho para o executável do BarTender e para o arquivo de modelo .btw
        # Estes valores devem ser configurados de acordo com sua instalação.
        bartender_exe_path = self.config.get('bartender_exe_path', r"C:\Program Files\Seagull\BarTender Suite\bartend.exe")
        btw_file_path = self.config.get('bartender_btw_path')

        if not btw_file_path or not os.path.exists(btw_file_path):
            raise FileNotFoundError(f"Arquivo de modelo BarTender (.btw) não encontrado em: {btw_file_path}")

        if not os.path.exists(bartender_exe_path):
            raise FileNotFoundError(f"Executável do BarTender não encontrado em: {bartender_exe_path}")

        # Cabeçalhos do CSV - devem corresponder aos nomes dos campos no arquivo .btw
        # Esta lista agora reflete exatamente os campos necessários para a etiqueta de setor.
        csv_headers = [
            'pedido', 'cliente', 'endereco', 'setor', 'conjunto', 'lote', 'quantidade_prod'
        ]

        # Cria um único arquivo CSV com todos os itens (setores) a serem impressos
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.csv', newline='', encoding='utf-8-sig') as tmp_csv:
            csv_filepath = tmp_csv.name
            writer = csv.DictWriter(tmp_csv, fieldnames=csv_headers)
            writer.writeheader()

            for item in itens_para_imprimir:
                # Combina as informações do pedido e do item em um único dicionário
                full_data = {**pedido_info, **item}

                # Cria um novo dicionário contendo APENAS os campos que o CSV espera.
                csv_row_data = {header: full_data.get(header) for header in csv_headers}
                writer.writerow(csv_row_data)

        # Monta o comando para o BarTender
        # /F=caminho_do_btw /D=caminho_do_csv /P=imprimir /PRN=nome_da_impressora /X=fechar_ao_concluir
        command = [
            bartender_exe_path,
            f'/F={btw_file_path}',
            f'/D={csv_filepath}',
            '/P', # Imprime
            '/X'  # Fecha o BarTender ao concluir
        ]
        if printer_name: # Adiciona o nome da impressora apenas se ele for fornecido
            command.append(f'/PRN={printer_name}')

        try:
            # Executa o comando e captura a saída para diagnóstico
            result = subprocess.run(command, check=True, capture_output=True, text=True)
        except subprocess.CalledProcessError as e:
            # Se o BarTender retornar um código de erro, exibe a saída para ajudar a depurar
            error_message = f"O BarTender retornou um erro.\n\nComando: {' '.join(command)}\n\nCódigo de Retorno: {e.returncode}\nSaída: {e.stdout}\nErro: {e.stderr}"
            raise RuntimeError(error_message) from e
        finally:
            # Limpeza do arquivo CSV temporário.
            # É crucial adicionar um atraso aqui. O BarTender.exe retorna o controle
            # para o script Python imediatamente, mas pode levar um momento para
            # realmente ler o arquivo CSV. Sem um atraso, o script pode apagar
            # o arquivo antes que o BarTender o acesse, causando o erro #3260.
            if self.main_window_handle:
                # Usa o loop de eventos do Tkinter para agendar a exclusão para 5 segundos no futuro.
                self.main_window_handle.after(5000, lambda p=csv_filepath: os.path.exists(p) and os.unlink(p))

    def gerar_pdf_e_imprimir(self, pedido_info, itens_para_imprimir, printer_name=None, print_direct=False):
        metodo_impressao = self.config.get('metodo_impressao', 'gdi').lower() # 'gdi', 'ppla' ou 'bartender'

        if print_direct and WIN32_AVAILABLE and printer_name:
            # Se o método é BarTender, chamamos ele diretamente e retornamos.
            if metodo_impressao == 'bartender':
                self.imprimir_com_bartender(pedido_info, itens_para_imprimir, printer_name)
                return
            
            # Se não é BarTender, mas é GDI ou PPLA e um nome de impressora é fornecido,
            # então usamos a impressão direta correspondente e retornamos.
            rotacionar = self.config.get('rotacionar', False)
            if metodo_impressao == 'ppla':
                self.imprimir_direto_ppla(pedido_info, itens_para_imprimir, printer_name, rotacionar=rotacionar)
                return
            elif metodo_impressao == 'gdi': # Padrão para GDI
                self.imprimir_direto_windows(pedido_info, itens_para_imprimir, printer_name, rotacionar=rotacionar)
                return

        # Se o método é BarTender, mas printer_name é None (para usar a impressora padrão do BarTender)
        # ou se print_direct é False, ainda tentamos usar o BarTender se for o método configurado.
        if metodo_impressao == 'bartender' and WIN32_AVAILABLE:
            self.imprimir_com_bartender(pedido_info, itens_para_imprimir, printer_name)
            return

        # Fallback para geração de PDF se nenhuma impressão direta foi executada ou se não é Windows.
        if not REPORTLAB_AVAILABLE:
            raise ImportError("A biblioteca 'reportlab' é necessária para gerar PDF.")

        with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp:
            filepath = tmp.name

        rotacionar = self.config.get('rotacionar', False)
        width, height = self.config['largura_mm'] * units.mm, self.config['altura_mm'] * units.mm
        if rotacionar:
            width, height = height, width # Inverte para o PDF também

        margem_sup, margem_esq = self.config['margem_sup_mm'] * units.mm, self.config['margem_esq_mm'] * units.mm

        doc = SimpleDocTemplate(filepath, pagesize=(width, height), leftMargin=margem_esq, rightMargin=margem_esq, topMargin=margem_sup, bottomMargin=margem_sup)
        styles = getSampleStyleSheet()
        styles.add(ParagraphStyle(name='Center', alignment=TA_CENTER))
        styles.add(ParagraphStyle(name='Right', alignment=TA_RIGHT))
        styles.add(ParagraphStyle(name='Left', alignment=TA_LEFT))
        styles.add(ParagraphStyle(name='Cliente', parent=styles['Normal'], alignment=TA_CENTER, fontSize=self.config['fonte_cliente']))
        styles.add(ParagraphStyle(name='Equipamento', parent=styles['Normal'], alignment=TA_CENTER, fontName='Helvetica-Bold', fontSize=self.config['fonte_equipamento']))
        styles.add(ParagraphStyle(name='Conjunto', parent=styles['Normal'], alignment=TA_CENTER, fontSize=self.config['fonte_conjunto']))
        styles.add(ParagraphStyle(name='Quantidade', parent=styles['Normal'], alignment=TA_CENTER, fontName='Helvetica-Bold', fontSize=self.config['fonte_quantidade']))

        story = []
        for item in itens_para_imprimir:
            # --- Construção do conteúdo da etiqueta para o PDF ---
            
            # Cabeçalho (Pedido e Data)
            header_data = [[
                Paragraph(f"PED: {pedido_info['numero_pedido']}", styles['Left']),
                Paragraph(datetime.now().strftime('%d/%m/%Y %H:%M'), styles['Right'])
            ]]
            header_table = Table(header_data, colWidths=['50%', '50%'])
            header_table.setStyle(TableStyle([('VALIGN', (0, 0), (-1, -1), 'TOP')]))
            story.append(header_table)
            story.append(Spacer(1, 0.2 * units.cm))

            # Cliente e Endereço
            story.append(Paragraph(pedido_info.get('cliente', ''), styles['Cliente']))
            story.append(Paragraph(pedido_info.get('endereco', ''), styles['Cliente']))
            story.append(Spacer(1, 0.3 * units.cm))

            # Equipamento
            story.append(Paragraph(item.get('nome_equipamento', ''), styles['Equipamento']))
            story.append(Spacer(1, 0.3 * units.cm))

            # Conjunto
            story.append(Paragraph(item.get('conjunto', ''), styles['Conjunto']))
            story.append(Spacer(1, 0.3 * units.cm))

            # Quantidade
            story.append(Paragraph(f"QTDE: {item.get('quantidade_prod', '')}", styles['Quantidade']))

            # Adiciona uma quebra de página para a próxima etiqueta
            story.append(PageBreak())

        if story:
            doc.build(story[:-1]) # Remove a última quebra de página

            if WIN32_AVAILABLE and printer_name and print_direct:
                win32api.ShellExecute(0, "printto", filepath, f'"{printer_name}"', ".", 0)
            else:
                # Fallback para outros sistemas
                if platform.system() == "Windows": os.startfile(filepath)
                elif platform.system() == "Darwin": os.system(f"open {filepath}")
                else: os.system(f"xdg-open {filepath}")

        # Limpeza do arquivo temporário
        if self.main_window_handle:
            self.main_window_handle.after(10000, lambda p=filepath: os.path.exists(p) and os.unlink(p))