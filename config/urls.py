from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path('admin/', admin.site.urls),
    path('conta/', include('contas.urls')),
    path('treinamentos/', include('treinamentos.urls')),
    path('avaliacoes/', include('avaliacoes.urls')),
    path('relatorios/', include('relatorios.urls')),
]
