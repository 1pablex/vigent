"""Contratos de saída da API de indicadores.

Os indicadores são calculados em core/services.py; os serializers só descrevem e
validam o formato da resposta (e alimentam a documentação OpenAPI gerada).
"""
from rest_framework import serializers


class IndiceConformidadeSerializer(serializers.Serializer):
    percentual = serializers.IntegerField(help_text="(em dia + vencendo) ÷ total, em %")
    meta = serializers.IntegerField(help_text="Meta interna de conformidade, em %")
    total = serializers.IntegerField(help_text="Pares colaborador ativo × curso exigido")
    em_dia = serializers.IntegerField()
    vencendo = serializers.IntegerField(help_text="Vence em até 30 dias")
    vencido = serializers.IntegerField()
    pendente = serializers.IntegerField(help_text="Sem certificado emitido")


class ConformidadeGrupoSerializer(serializers.Serializer):
    percentual = serializers.IntegerField()
    total = serializers.IntegerField()
    conformes = serializers.IntegerField()


class ConformidadeDepartamentoSerializer(ConformidadeGrupoSerializer):
    departamento = serializers.CharField()


class ConformidadeCursoSerializer(ConformidadeGrupoSerializer):
    curso = serializers.CharField()


class VencimentoFaixaSerializer(serializers.Serializer):
    faixa = serializers.CharField()
    de_dias = serializers.IntegerField()
    ate_dias = serializers.IntegerField()
    quantidade = serializers.IntegerField()


class ReacaoCursoSerializer(serializers.Serializer):
    curso = serializers.CharField()
    media_didatica = serializers.FloatField()
    media_entendimento = serializers.FloatField()
    respostas = serializers.IntegerField()


class QualidadePercebidaSerializer(serializers.Serializer):
    taxa_conclusao = serializers.IntegerField(help_text="Pares que já têm certificado, em %")
    nota_media_prova = serializers.FloatField()
    media_reacao = serializers.FloatField()
