from flask import Blueprint, render_template_string
from menu_content import get_menu_html

menu_bp = Blueprint('menu', __name__)

@menu_bp.route('/menu')
def menu():
    menu_html = get_menu_html()
    # Renderiza o HTML do menu diretamente
    return render_template_string(menu_html)
