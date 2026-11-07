"""Filtros de template para exibir o conteúdo dos cursos com segurança."""
from django import template
from django.utils.safestring import mark_safe

from treinamentos.seguranca import sanitizar_html

register = template.Library()


@register.filter
def html_seguro(texto):
    """RN-40 - sanitiza na exibição também, cobrindo textos gravados antes da regra
    ou alterados sem passar pelo save() (ex.: update em massa)."""
    return mark_safe(sanitizar_html(texto or ""))
