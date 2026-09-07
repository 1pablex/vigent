from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect

"""apos login (tela de inicio) """
@login_required
def inicio(request):
    return redirect("treinamentos:inicio")