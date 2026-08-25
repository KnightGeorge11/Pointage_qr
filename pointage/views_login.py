# pointage/views_login.py
from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.views.decorators.http import require_http_methods

@require_http_methods(["GET", "POST"])
def login_view(request):
    """
    Connexion unifiée :
    - admin / superuser  → Django admin (/admin/)
    - utilisateur normal → dashboard
    """

    if request.user.is_authenticated:
        return _redirect_after_login(request.user)

    error = None

    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        password = request.POST.get('password', '')

        user = authenticate(request, username=username, password=password)

        if user is not None:
            if user.is_active:
                login(request, user)
                return _redirect_after_login(user)
            else:
                error = "Ce compte est désactivé."
        else:
            error = "Nom d'utilisateur ou mot de passe incorrect."

    return render(request, 'pointage/login.html', {
        'error': error,
    })


def logout_view(request):
    """Déconnexion et retour à la page de login."""
    logout(request)
    return redirect('login')


def _redirect_after_login(user):
    """Redirige selon le rôle du compte."""
    if user.role == 'admin'or user.is_superuser:
        return redirect('/admin/')
    return redirect('dashboard')