from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

from config import settings

urlpatterns = [
    path('admin/', admin.site.urls),
    path('conta/', include('contas.urls')),
    path('treinamentos/', include('treinamentos.urls')),
    path('avaliacoes/', include('avaliacoes.urls')),
    path('relatorios/', include('relatorios.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)