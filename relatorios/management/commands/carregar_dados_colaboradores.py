"""Popula o banco com dados de demonstração — cenário Nortex Soluções Ltda."""
from django.core.management.base import BaseCommand

from contas.models import Departamento, Usuario


class Command(BaseCommand):
    help = "Cria departamentos e usuários de demonstração."

    def handle(self, *args, **options):
        departamentos = ["Vendas", "Operações", "Sala Limpa"]
        deps = {}
        for nome in departamentos:
            dep, criado = Departamento.objects.get_or_create(nome=nome)
            deps[nome] = dep
            if criado:
                self.stdout.write(f"Departamento criado: {nome}")

        # (email, nome, cargo, departamento, grupo, senha, senha_provisoria)
        usuarios = [
            ("ricardo.lima@nortex.com.br", "Ricardo Lima", "Coordenador de RH",
             "Operações", Usuario.Grupo.RH, "123456", False),
            ("fernanda.lima@nortex.com.br", "Fernanda Lima", "Analista de Vendas",
             "Vendas", Usuario.Grupo.COLABORADOR, "123456", False),
            ("bruno.tavares@nortex.com.br", "Bruno Tavares", "Técnico de Sala Limpa",
             "Sala Limpa", Usuario.Grupo.COLABORADOR, "Nortex@2026", True),
        ]

        for email, nome, cargo, dep_nome, grupo, senha, provisoria in usuarios:
            if Usuario.objects.filter(email=email).exists():
                self.stdout.write(f"Já existe, pulando: {email}")
                continue
            usuario = Usuario.objects.create_user(
                email=email, nome=nome, password=senha, cargo=cargo,
                departamento=deps[dep_nome], grupo=grupo,
                senha_provisoria=provisoria,
            )
            self.stdout.write(self.style.SUCCESS(
                f"Criado: {usuario.matricula} — {nome} ({email})"))

        self.stdout.write(self.style.SUCCESS("Concluído."))