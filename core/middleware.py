"""Cabeçalhos de segurança acrescentados a todas as respostas (telas, API e páginas de erro).

O middleware não bloqueia nada no servidor: ele informa ao navegador as regras da página,
e quem as aplica é o navegador.

Content-Security-Policy (CSP): o navegador só executa scripts servidos pelo próprio Vigent.
Não há script inline nem atributo on...= nos templates (static/js/ cuida dos eventos), então
mesmo um XSS que passasse pelas outras proteções não seria executado. Estilos inline seguem
liberados: os templates usam atributos style= e CSS inline tem risco muito menor que script.

Permissions-Policy: recursos do navegador que o Vigent não usa ficam desligados.
"""

CSP = "; ".join([
    "default-src 'self'",
    "script-src 'self'",
    "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com",
    "font-src 'self' https://fonts.gstatic.com",
    "img-src 'self' data: https://res.cloudinary.com",   # imagens dos cursos em produção
    "connect-src 'self'",                                 # fetch do dashboard para a API
    "object-src 'none'",
    "base-uri 'self'",
    "form-action 'self'",
    "frame-ancestors 'none'",                             # ninguém exibe o Vigent em iframe
])

PERMISSIONS_POLICY = "camera=(), microphone=(), geolocation=(), payment=(), usb=()"


class CabecalhosSegurancaMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        resposta = self.get_response(request)
        resposta.headers.setdefault("Content-Security-Policy", CSP)
        resposta.headers.setdefault("Permissions-Policy", PERMISSIONS_POLICY)
        return resposta
