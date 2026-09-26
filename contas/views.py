"""Autenticação, definição de senha e cadastro de colaboradores."""
import secrets
import string

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.utils import timezone

from auditoria.models import LogSistema, RegistroAcesso
from contas.models import Departamento, Usuario
from core.correio import enviar_primeiro_acesso
from core.services import registrar

from core.correio import enviar_codigo_verificacao, enviar_primeiro_acesso, enviar_codigo_redefinicao
from core.services import gerar_codigo_verificacao, registrar
from contas.models import CodigoVerificacao, Departamento, Usuario


def _ip(request):
    encaminhado = request.META.get("HTTP_X_FORWARDED_FOR")
    return (encaminhado.split(",")[0].strip() if encaminhado
            else request.META.get("REMOTE_ADDR"))


def gerar_senha_provisoria(tamanho=10):
    alfabeto = string.ascii_letters + string.digits
    return "".join(secrets.choice(alfabeto) for _ in range(tamanho))

def _bloqueado_por_forca_bruta(email, ip):
    """
    RN-35 — trava temporária contra força bruta.

    Conta tentativas malsucedidas de login para o e-mail informado e para o IP de origem. Basta um dos
    dois exceder o limite para bloquear temporariamente o acesso. O bloqueio é registrado no log de auditoria.
    """
    desde = timezone.now() - timezone.timedelta(
        minutes=settings.VIGENT["JANELA_BLOQUEIO_LOGIN_MIN"])
    limite = settings.VIGENT["MAX_TENTATIVAS_LOGIN"]
    negados = RegistroAcesso.objects.filter(
        data_hora__gte=desde, resultado__in=["Negado", "Conta desativada"])

    por_email = negados.filter(identificacao=email).count() if email else 0
    por_ip = negados.filter(ip=ip).count() if ip else 0
    return por_email >= limite or por_ip >= limite


def tela_login(request):
    if request.user.is_authenticated:
        return redirect("core:inicio")

    erro = None
    if request.method == "POST":
        email = (request.POST.get("email") or "").strip().lower()   # RN-26
        senha = request.POST.get("senha") or ""
        ip = _ip(request)

        if _bloqueado_por_forca_bruta(email, ip):
            erro = ("Muitas tentativas de acesso em pouco tempo. Aguarde alguns "
                    "minutos antes de tentar novamente.")
            RegistroAcesso.objects.create(
                identificacao=email or "—", evento="Bloqueio por força bruta",
                grupo="—", ip=ip, resultado="Bloqueado temporariamente")
            registrar(LogSistema.Nivel.WARN, "Login bloqueado",
                      f"Limite de {settings.VIGENT['MAX_TENTATIVAS_LOGIN']} tentativas "
                      f"excedido para {email or ip}")
            return render(request, "contas/login.html", {"erro": erro})

        usuario = authenticate(request, username=email, password=senha)

        if usuario is None:
            existente = Usuario.objects.filter(email=email).first()
            if existente and not existente.is_active:
                erro = "Conta desativada. Procure o setor de RH."   # RN-16
                RegistroAcesso.objects.create(
                    identificacao=email, evento="Tentativa de login",
                    grupo="—", ip=ip, resultado="Conta desativada")
                registrar(LogSistema.Nivel.WARN, "Login recusado",
                          f"Conta desativada — {email}")
            else:
                erro = "E-mail ou senha inválidos."
                RegistroAcesso.objects.create(
                    identificacao=email or "—", evento="Credencial inválida",
                    grupo="—", ip=ip, resultado="Negado")
        elif usuario.senha_provisoria:
            # Login com senha provisória: pula o 2FA — o código chegaria pelo
            # mesmo e-mail que já entregou a credencial, então não agrega
            # segurança aqui. Vai direto para a troca obrigatória de senha.
            login(request, usuario)
            RegistroAcesso.objects.create(
                identificacao=usuario.email, evento="Login realizado",
                grupo=usuario.get_grupo_display(), ip=ip, resultado="Autorizado")
            registrar(LogSistema.Nivel.INFO, "Login realizado (senha provisória)",
                      f"{usuario.nome} — grupo {usuario.get_grupo_display()}; "
                      f"2FA dispensado no primeiro acesso", usuario, ip)
            return redirect("contas:definir_senha")
        else:
            codigo_obj = gerar_codigo_verificacao(usuario)
            enviar_codigo_verificacao(usuario, codigo_obj)
            request.session["pre_2fa_usuario_id"] = usuario.id
            registrar(LogSistema.Nivel.INFO, "Código de verificação enviado",
                      f"Senha correta para {usuario.email}; aguardando segundo fator", ip=ip)
            return redirect("contas:verificar_codigo")

    return render(request, "contas/login.html", {"erro": erro})

def sair(request):
    logout(request)
    return redirect("contas:login")


def ver_politica_privacidade(request):
    return render(request, "contas/politica_privacidade.html")

#obrigatorio apos o login, para que o usuario troque a senha provisoria
@login_required
def definir_senha(request):
    """RN-27 — troca obrigatória no primeiro acesso."""
    if not request.user.senha_provisoria:
        return redirect("core:inicio")

    erro = None
    if request.method == "POST":
        nova = request.POST.get("nova1") or ""
        repetida = request.POST.get("nova2") or ""
        if len(nova) < 6:
            erro = "A senha deve ter ao menos 6 caracteres."
        elif nova != repetida:
            erro = "As senhas não coincidem."
        elif request.user.check_password(nova):
            erro = "A nova senha deve ser diferente da provisória."
        else:
            request.user.set_password(nova)
            request.user.senha_provisoria = False
            request.user.save()
            update_session_auth_hash(request, request.user)
            registrar(LogSistema.Nivel.INFO, "Senha alterada",
                      "Troca obrigatória concluída", request.user)
            messages.success(request, "Senha definida com sucesso.")
            return redirect("core:inicio")

    return render(request, "contas/definir_senha.html", {"erro": erro})

@login_required
def cadastrar_colaborador(request):
    """RF-14, RF-27, RF-32, RN-15, RN-32, RN-33."""
    if not request.user.e_rh:
        return redirect("core:inicio")

    erro = None
    if request.method == "POST":
        nome = (request.POST.get("nome") or "").strip()
        email = (request.POST.get("email") or "").strip().lower()
        cargo = (request.POST.get("cargo") or "").strip()
        dep_id = request.POST.get("departamento")
        grupo = request.POST.get("grupo") or Usuario.Grupo.COLABORADOR

        if len(nome) < 3:
            erro = "Informe o nome completo."
        elif "@" not in email or "." not in email.split("@")[-1]:
            erro = "Endereço de correio eletrônico inválido."
        elif Usuario.objects.filter(email=email).exists():
            erro = "Já existe conta com este endereço."
        elif not cargo:
            erro = "Informe o cargo."
        else:
            senha = gerar_senha_provisoria()
            novo = Usuario.objects.create_user(
                email=email, nome=nome, password=senha, cargo=cargo,
                departamento_id=dep_id or None, grupo=grupo,
                senha_provisoria=True,
            )
            enviar_primeiro_acesso(novo, senha)     # RN-32
            registrar(LogSistema.Nivel.INFO, "Colaborador cadastrado",
                      f"Matrícula {novo.matricula} — {nome} · {email} · grupo {grupo} · "
                      f"credenciais enviadas ao titular", request.user)
            messages.success(
                request,
                f"Matrícula {novo.matricula} atribuída. "
                f"As credenciais foram enviadas para {email}.")
            return redirect("core:rh_colaboradores")

    return render(request, "contas/cadastrar.html", {
        "erro": erro,
        "departamentos": Departamento.objects.all(),
        "grupos": Usuario.Grupo.choices,
        "valores": request.POST,
    })

def verificar_codigo(request):
    usuario_id = request.session.get("pre_2fa_usuario_id")
    if not usuario_id:
        return redirect("contas:login")
    usuario = Usuario.objects.filter(pk=usuario_id).first()
    if usuario is None:
        del request.session["pre_2fa_usuario_id"]
        return redirect("contas:login")

    erro = None
    if request.method == "POST":
        if "reenviar" in request.POST:
            codigo_obj = gerar_codigo_verificacao(usuario)
            enviar_codigo_verificacao(usuario, codigo_obj)
            messages.success(request, "Um novo código foi enviado.")
        else:
            digitado = (request.POST.get("codigo") or "").strip()
            pendente = (CodigoVerificacao.objects
                        .filter(usuario=usuario, utilizado=False)
                        .order_by("-data_geracao").first())
            if pendente and pendente.valido and digitado == pendente.codigo:
                pendente.utilizado = True
                pendente.save()
                del request.session["pre_2fa_usuario_id"]
                login(request, usuario)
                ip = _ip(request)
                RegistroAcesso.objects.create(
                    identificacao=usuario.email, evento="Login realizado",
                    grupo=usuario.get_grupo_display(), ip=ip, resultado="Autorizado")
                registrar(LogSistema.Nivel.INFO, "Login realizado",
                          f"{usuario.nome} — grupo {usuario.get_grupo_display()}",
                          usuario, ip)
                if usuario.senha_provisoria:
                    return redirect("contas:definir_senha")
                return redirect("core:inicio")
            else:
                erro = "Código inválido ou expirado."

    return render(request, "contas/verificar_codigo.html", {"erro": erro, "email": usuario.email})

def esqueci_senha(request):
    erro = None
    if request.method == "POST":
        email = (request.POST.get("email") or "").strip().lower()
        if not email:
            erro = "Informe seu e-mail corporativo."
        else:
            usuario = Usuario.objects.filter(email=email, is_active=True).first()
            if usuario:
                codigo_obj = gerar_codigo_verificacao(usuario)
                enviar_codigo_redefinicao(usuario, codigo_obj)
                registrar(LogSistema.Nivel.INFO, "Código de redefinição enviado",
                          f"Solicitação de redefinição para {email}", ip=_ip(request))
            request.session["reset_email"] = email
            messages.success(request, "Se o e-mail informado estiver cadastrado, um código foi enviado.")
            return redirect("contas:redefinir_senha")

    return render(request, "contas/esqueci_senha.html", {"erro": erro})


def redefinir_senha(request):
    email = request.session.get("reset_email")
    if not email:
        return redirect("contas:esqueci_senha")

    erro = None
    if request.method == "POST":
        codigo_digitado = (request.POST.get("codigo") or "").strip()
        nova = request.POST.get("nova1") or ""
        repetida = request.POST.get("nova2") or ""

        usuario = Usuario.objects.filter(email=email, is_active=True).first()
        pendente = None
        if usuario:
            pendente = (CodigoVerificacao.objects
                        .filter(usuario=usuario, utilizado=False)
                        .order_by("-data_geracao").first())

        if len(nova) < 6:
            erro = "A senha deve ter ao menos 6 caracteres."
        elif nova != repetida:
            erro = "As senhas não coincidem."
        elif not usuario or not pendente or not pendente.valido or codigo_digitado != pendente.codigo:
            erro = "Código inválido ou expirado."
        else:
            pendente.utilizado = True
            pendente.save()
            usuario.set_password(nova)
            usuario.senha_provisoria = False
            usuario.save()
            del request.session["reset_email"]
            registrar(LogSistema.Nivel.INFO, "Senha redefinida",
                      "Redefinição via 'esqueci minha senha' concluída", usuario)
            messages.success(request, "Senha redefinida com sucesso. Faça login com a nova senha.")
            return redirect("contas:login")

    return render(request, "contas/redefinir_senha.html", {"erro": erro, "email": email})
@login_required
def aceitar_termo(request):
    if request.user.aceitou_termos:
        return redirect("core:inicio")

    erro = None
    if request.method == "POST":
        if request.POST.get("aceito") == "on":
            request.user.aceitou_termos = True
            request.user.data_aceite_termos = timezone.now()
            request.user.save()
            registrar(LogSistema.Nivel.INFO, "Termo de uso aceito",
                      "Aceite registrado no primeiro acesso pós-definição de senha",
                      request.user)
            return redirect("core:inicio")
        erro = "É necessário marcar a caixa de aceite para continuar."

    return render(request, "contas/aceitar_termo.html", {"erro": erro})