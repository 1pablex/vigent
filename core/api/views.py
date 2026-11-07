"""Endpoints de leitura dos indicadores do dashboard do RH (RF-29, RF-30).

Todos são GET, somente leitura e restritos ao RH (permissão padrão da API).
As coleções são pequenas e limitadas por natureza (um item por departamento,
curso ou faixa), por isso não são paginadas.
"""
from drf_spectacular.utils import extend_schema
from rest_framework.response import Response
from rest_framework.views import APIView

from core import services

from . import serializers as s


class IndiceConformidadeView(APIView):
    @extend_schema(summary="Índice de conformidade geral", tags=["Conformidade"],
                   responses=s.IndiceConformidadeSerializer)
    def get(self, request):
        dados = services.indice_conformidade(services.matriz_conformidade())
        return Response(s.IndiceConformidadeSerializer(dados).data)


class ConformidadeDepartamentosView(APIView):
    @extend_schema(summary="Conformidade por departamento", tags=["Conformidade"],
                   responses=s.ConformidadeDepartamentoSerializer(many=True))
    def get(self, request):
        dados = services.conformidade_por_departamento(services.matriz_conformidade())
        return Response(s.ConformidadeDepartamentoSerializer(dados, many=True).data)


class ConformidadeCursosView(APIView):
    @extend_schema(summary="Conformidade por curso", tags=["Conformidade"],
                   responses=s.ConformidadeCursoSerializer(many=True))
    def get(self, request):
        dados = services.conformidade_por_curso(services.matriz_conformidade())
        return Response(s.ConformidadeCursoSerializer(dados, many=True).data)


class VencimentosView(APIView):
    @extend_schema(summary="Vencimentos previstos por faixa (0-30, 31-60, 61-90 dias)",
                   tags=["Conformidade"], responses=s.VencimentoFaixaSerializer(many=True))
    def get(self, request):
        dados = services.vencimentos_por_faixa(services.matriz_conformidade())
        return Response(s.VencimentoFaixaSerializer(dados, many=True).data)


class ReacaoCursosView(APIView):
    @extend_schema(summary="Avaliação de reação por curso (histórico)", tags=["Qualidade"],
                   responses=s.ReacaoCursoSerializer(many=True))
    def get(self, request):
        return Response(s.ReacaoCursoSerializer(services.reacao_por_curso(), many=True).data)


class QualidadePercebidaView(APIView):
    @extend_schema(summary="Qualidade percebida consolidada", tags=["Qualidade"],
                   responses=s.QualidadePercebidaSerializer)
    def get(self, request):
        dados = services.qualidade_percebida(services.matriz_conformidade())
        return Response(s.QualidadePercebidaSerializer(dados).data)
