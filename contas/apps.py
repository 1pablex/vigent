from django.apps import AppConfig


class ContasConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'contas'

    def ready(self):
        from contas import sessao  # noqa: F401  (registra o sinal de login)
