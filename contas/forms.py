"""Formulário do RH para lançar uma nova versão do termo de uso (RN-33)."""
import re

from django import forms

from .models import TermoUso

NUMERO_VERSAO = re.compile(r"^\d+(\.\d+)*$")


def numero(versao):
    """"1.10" -> (1, 10), para comparar versões como números; None se não for numérica."""
    if not versao or not NUMERO_VERSAO.match(versao):
        return None
    return tuple(int(parte) for parte in versao.split("."))


def proxima_versao(vigente):
    """Sugestão para a próxima versão: 1.1 -> 1.2. Sem versão numérica, sugere 1.0."""
    atual = numero(vigente.versao) if vigente else None
    if atual is None:
        return "1.0"
    return ".".join(str(p) for p in (*atual[:-1], atual[-1] + 1)) if len(atual) > 1 \
        else f"{atual[0]}.1"


class NovaVersaoTermoForm(forms.Form):
    versao = forms.CharField(
        label="Número da nova versão", max_length=10,
        help_text="Só números e pontos (ex.: 1.2 ou 2.0), maior que a versão vigente.",
        widget=forms.TextInput(attrs={"class": "txt", "style": "max-width:160px"}))
    resumo_alteracoes = forms.CharField(
        label="O que mudou", max_length=1000,
        help_text="Aparece para quem precisa aceitar de novo. Seja direto: o que mudou e por quê.",
        widget=forms.Textarea(attrs={"rows": 3}))
    conteudo = forms.CharField(
        label="Texto do termo",
        help_text="Linha em branco separa parágrafos; \"1. Título\" sozinho na linha vira título; "
                  "linhas com \"- \" viram lista; linhas com \"|\" viram tabela (a primeira linha "
                  "é o cabeçalho). HTML simples também é aceito.",
        widget=forms.Textarea(attrs={"rows": 28, "class": "termo-editor"}))

    def clean_versao(self):
        versao = self.cleaned_data["versao"].strip()
        if numero(versao) is None:
            raise forms.ValidationError("Use só números separados por ponto, como 1.2 ou 2.0.")
        if TermoUso.objects.filter(versao=versao).exists():
            raise forms.ValidationError(f"A versão {versao} já foi publicada.")
        vigente = TermoUso.vigente()
        if vigente and numero(vigente.versao) and numero(versao) <= numero(vigente.versao):
            raise forms.ValidationError(
                f"A nova versão precisa ser maior que a vigente ({vigente.versao}).")
        return versao

    def clean_conteudo(self):
        conteudo = self.cleaned_data["conteudo"].strip()
        vigente = TermoUso.vigente()
        if vigente and conteudo == vigente.conteudo.strip():
            raise forms.ValidationError("O texto está igual ao da versão vigente: não há o que publicar.")
        return conteudo
