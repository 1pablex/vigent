"""Identidade, organização e credenciais de acesso."""
import secrets

from django.conf import settings
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.db import models, transaction
from django.utils import timezone
from django.utils.crypto import salted_hmac


class Departamento(models.Model):
    nome = models.CharField(max_length=80, unique=True)

    class Meta:
        ordering = ["nome"]
        verbose_name_plural = "departamentos"

    def __str__(self):
        return self.nome

class UsuarioManager(BaseUserManager):
    """RN-17 - o endereço é sempre normalizado antes de gravar."""

    """normaliza o email para minusculo e remove espaços em branco antes de gravar no banco de dados."""
    def normalize_email(self, email):
        return (email or "").strip().lower()

    @transaction.atomic
    def create_user(self, email, nome, password=None, aceite_termo_vigente=False, **extra):
        """Com aceite_termo_vigente=True, a conta já nasce com o aceite da versão vigente do
        termo de uso (usado pela carga de demonstração e pelos testes)."""
        if not email:
            raise ValueError("O endereço de correio eletrônico é obrigatório.")
        email = self.normalize_email(email)
        usuario = self.model(email=email, nome=nome, **extra)
        usuario.set_password(password)
        usuario.save(using=self._db)
        if aceite_termo_vigente:
            termo = TermoUso.vigente()
            if termo is not None:
                AceiteTermo.objects.create(usuario=usuario, termo=termo)
        return usuario

    def create_superuser(self, email, nome, password=None, **extra):
        extra.setdefault("is_staff", True)
        extra.setdefault("is_superuser", True)
        extra.setdefault("grupo", Usuario.Grupo.RH)
        extra.setdefault("senha_provisoria", False)
        return self.create_user(email, nome, password, **extra)


class Usuario(AbstractBaseUser, PermissionsMixin):
    class Grupo(models.TextChoices):
        COLABORADOR = "COLABORADOR", "Colaborador"
        RH = "RH", "RH"

    matricula = models.CharField(max_length=10, unique=True, editable=False)
    nome = models.CharField(max_length=120)
    email = models.EmailField(unique=True)
    cargo = models.CharField(max_length=80, blank=True)
    departamento = models.ForeignKey(
        Departamento, on_delete=models.PROTECT, related_name="colaboradores",
        null=True, blank=True,
    )
    grupo = models.CharField(max_length=12, choices=Grupo.choices, default=Grupo.COLABORADOR)

    senha_provisoria = models.BooleanField(default=True)
    pseudonimizado = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    data_cadastro = models.DateTimeField(default=timezone.now, editable=False)
    # Sessão única: só a sessão do último login vale; as outras são encerradas no próximo acesso.
    sessao_ativa = models.CharField(max_length=40, blank=True, editable=False)
    # O aceite do termo de uso fica em AceiteTermo, um registro por versão aceita (RN-33).

    objects = UsuarioManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["nome"]

    class Meta:
        ordering = ["matricula"]
        verbose_name_plural = "usuários"

    def __str__(self):
        return f"{self.matricula} - {self.nome}"

    def save(self, *args, **kwargs):
        self.email = (self.email or "").strip().lower()
        if not self.matricula:
            self.matricula = self._proxima_matricula()
        super().save(*args, **kwargs)

    @staticmethod
    def _proxima_matricula():
        ultima = (
            Usuario.objects.order_by("-matricula")
            .values_list("matricula", flat=True)
            .first()
        )
        proxima = (int(ultima) + 1) if ultima else 1
        return f"{proxima:04d}"

    @property
    def e_rh(self):
        return self.grupo == self.Grupo.RH

    def get_short_name(self):
        return self.nome.split(" ")[0]

    @property
    def aceite_vigente(self):
        """Aceite da versão vigente do termo, ou None se ainda falta aceitar (RN-33)."""
        termo = TermoUso.vigente()
        if termo is None:
            return None
        return self.aceites_termo.filter(termo=termo).select_related("termo").first()

    @property
    def precisa_aceitar_termo(self):
        """Há termo publicado e a pessoa ainda não aceitou a versão vigente."""
        return TermoUso.vigente() is not None and self.aceite_vigente is None

    @property
    def ultimo_aceite(self):
        return self.aceites_termo.select_related("termo").order_by("-data_hora").first()


class TermoUso(models.Model):
    """RN-33 - cada versão publicada do termo de uso e política de privacidade.

    Vigente é a versão publicada mais recente. Uma versão publicada não é editada nem apagada:
    para mudar o texto, publica-se uma versão nova (Django Admin), e todos precisam aceitá-la
    no próximo acesso. Assim fica comprovado qual texto cada pessoa aceitou.
    """

    versao = models.CharField(max_length=10, unique=True, help_text="Ex.: 1.1")
    conteudo = models.TextField(
        help_text="Texto completo em HTML simples: títulos (h3), parágrafos, listas e tabelas.")
    resumo_alteracoes = models.TextField(
        blank=True, help_text="O que mudou em relação à versão anterior. Aparece para quem "
                              "precisa aceitar de novo.")
    publicado_em = models.DateTimeField(default=timezone.now, editable=False)
    publicado_por = models.ForeignKey(
        Usuario, on_delete=models.PROTECT, null=True, blank=True, editable=False,
        related_name="termos_publicados")

    class Meta:
        ordering = ["-publicado_em", "-id"]
        verbose_name = "termo de uso"
        verbose_name_plural = "termos de uso"

    def __str__(self):
        return f"Versão {self.versao} ({timezone.localtime(self.publicado_em):%d/%m/%Y})"

    def save(self, *args, **kwargs):
        if self.pk is not None:
            raise ValueError("Versão publicada não pode ser alterada: publique uma versão nova.")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValueError("Versão publicada não pode ser apagada.")

    @classmethod
    def vigente(cls):
        return cls.objects.order_by("-publicado_em", "-id").first()


class AceiteTermo(models.Model):
    """RN-33 - registro de que a pessoa aceitou uma versão do termo (prova do aceite, LGPD)."""

    usuario = models.ForeignKey(Usuario, on_delete=models.CASCADE, related_name="aceites_termo")
    termo = models.ForeignKey(TermoUso, on_delete=models.PROTECT, related_name="aceites")
    data_hora = models.DateTimeField(default=timezone.now, editable=False)
    ip = models.GenericIPAddressField(null=True, blank=True, editable=False)

    class Meta:
        unique_together = [("usuario", "termo")]
        ordering = ["-data_hora"]
        verbose_name = "aceite do termo"
        verbose_name_plural = "aceites do termo"

    def __str__(self):
        return f"{self.usuario} - versão {self.termo.versao}"

class Reidentificacao(models.Model):
    """Cofre de dados originais de colaboradores desligados (RN-35)."""

    usuario = models.OneToOneField(Usuario, on_delete=models.CASCADE, related_name="reidentificacao")
    matricula = models.CharField(max_length=10)
    pseudonimo = models.CharField(max_length=20)
    nome_original = models.CharField(max_length=120)
    email_original = models.EmailField()
    cargo_original = models.CharField(max_length=80, blank=True)
    data_desligamento = models.DateField(default=timezone.localdate)
    registrado_por = models.ForeignKey(
        Usuario, on_delete=models.PROTECT, related_name="desligamentos_registrados"
    )
    data_exclusao = models.DateField()

    class Meta:
        verbose_name = "reidentificação"
        verbose_name_plural = "reidentificações"

    def __str__(self):
        return f"{self.pseudonimo} (expurgo em {self.data_exclusao:%d/%m/%Y})"


class CodigoVerificacao(models.Model):
    """Segundo fator enviado por api brevo (RN-25).

    O código não é gravado: fica só o HMAC-SHA256 dele, com chave derivada da SECRET_KEY
    Sem a SECRET_KEY, que não fica no banco, não dá para ficar testando n codigos.
    """

    SAL_HMAC = "vigent.contas.CodigoVerificacao"

    usuario = models.ForeignKey(Usuario, on_delete=models.CASCADE, related_name="codigos")
    codigo_hash = models.CharField(max_length=64, editable=False)
    data_geracao = models.DateTimeField(auto_now_add=True)
    data_expiracao = models.DateTimeField()
    utilizado = models.BooleanField(default=False)
    tentativas_erradas = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["-data_geracao"]
        verbose_name = "código de verificação"
        verbose_name_plural = "códigos de verificação"

    def __str__(self):
        # O código em si não aparece: é o segundo fator do login.
        return f"Código de verificação de {self.usuario}"

    @property
    def bloqueado(self):
        return self.tentativas_erradas >= settings.VIGENT["MAX_TENTATIVAS_CODIGO"]

    @property
    def valido(self):
        return (not self.utilizado and not self.bloqueado
                and timezone.now() < self.data_expiracao)

    @classmethod
    def calcular_hash(cls, usuario_id, codigo):
        # O id do usuário entra na mensagem: o mesmo código para duas pessoas gera hashes diferentes.
        return salted_hmac(cls.SAL_HMAC, f"{usuario_id}:{codigo}", algorithm="sha256").hexdigest()

    def confere(self, digitado):
        """Compara os HMACs em tempo constante; o código digitado nunca é comparado em texto."""
        return secrets.compare_digest(self.calcular_hash(self.usuario_id, digitado or ""),
                                      self.codigo_hash)

    def registrar_erro(self):
        """Conta um erro de forma atômica; ao atingir o limite o código deixa de valer."""
        (CodigoVerificacao.objects
         .filter(pk=self.pk, tentativas_erradas__lt=settings.VIGENT["MAX_TENTATIVAS_CODIGO"])
         .update(tentativas_erradas=models.F("tentativas_erradas") + 1))
        self.refresh_from_db(fields=["tentativas_erradas"])
