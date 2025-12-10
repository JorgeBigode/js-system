# menu_content.py
from flask import session, url_for, render_template
from models import get_session, User

db = get_session()

def is_admin():
    """Verifica se o usuário logado é admin."""
    return session.get('role') == 'admin'

def get_user_html():
    """Retorna o HTML da foto/nome do usuário logado."""
    if session.get('user_id'):
        user_id = session['user_id']
        usuario = db.query(User).filter_by(id=user_id).first()
        if usuario and getattr(usuario, 'foto_perfil', None):
            foto = url_for('static', filename=f'uploads/perfil/{usuario.foto_perfil}')
            return f'<img src="{foto}" alt="Perfil" class="profile-pic-small me-2"> {usuario.username}'
        else:
            # quando não há foto, usuario pode ser None — proteja:
            name = usuario.username if usuario else 'Usuário'
            return f'<i class="fas fa-user-circle me-2"></i> {name}'
    return '<i class="fas fa-user-circle me-2"></i> Usuário'

def get_menu_html():
    """Renderiza e retorna o template do menu como string (útil se usar rota que retorna só o menu)."""
    # Usamos render_template para que Jinja processe as variáveis internas (user_html / is_admin)
    return render_template('menu.html', user_html=get_user_html(), is_admin=is_admin)
