from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, render

from .models import Certificado


@login_required
def meus_certificados(request):
    certificados = (Certificado.objects
                    .filter(usuario=request.user)
                    .select_related("curso")
                    .order_by("-data_emissao"))
    return render(request, "certificacao/certificado.html", {"certificados": certificados})


@login_required
def ver_certificado(request, certificado_id):
    certificado = get_object_or_404(Certificado, pk=certificado_id, usuario=request.user)
    return render(request, "certificacao/ver_certificado.html", {"certificado": certificado})