from django.urls import path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

from . import views

app_name = "api"

urlpatterns = [
    path("indicadores/conformidade/", views.IndiceConformidadeView.as_view(),
         name="conformidade"),
    path("indicadores/conformidade/departamentos/",
         views.ConformidadeDepartamentosView.as_view(), name="conformidade_departamentos"),
    path("indicadores/conformidade/cursos/", views.ConformidadeCursosView.as_view(),
         name="conformidade_cursos"),
    path("indicadores/vencimentos/", views.VencimentosView.as_view(), name="vencimentos"),
    path("indicadores/reacao/", views.ReacaoCursosView.as_view(), name="reacao"),
    path("indicadores/qualidade/", views.QualidadePercebidaView.as_view(), name="qualidade"),
    # Documentação OpenAPI 3 gerada a partir do código (também restrita ao RH)
    path("schema/", SpectacularAPIView.as_view(), name="schema"),
    path("docs/", SpectacularSwaggerView.as_view(url_name="api:schema"), name="docs"),
]
