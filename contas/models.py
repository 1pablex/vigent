"""Identidade, organização e credenciais de acesso."""
from django.conf import settings
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.db import models, transaction
from django.utils import timezone


class Departamento(models.Model):
    nome = models.CharField(max_length=80, unique=True)

    class Meta:
        ordering = ["nome"]
        verbose_name_plural = "departamentos"

    def __str__(self):
        return self.nome

class UsuarioManager(BaseUserManager):
    """RN-26 — o endereço é sempre normalizado antes de gravar."""

    """normaliza o email para minusculo e remove espaços em branco antes de gravar no banco de dados."""
    def normalize_email(self, email):
        return (email or "").strip().lower()

    @transaction.atomic
    def create_user(self, email, nome, password=None, **extra):
        if not email:
            raise ValueError("O endereço de correio eletrônico é obrigatório.")
        email = self.normalize_email(email)
        usuario = self.model(email=email, nome=nome, **extra)
        usuario.set_password(password)
        usuario.save(using=self._db)
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

    objects = UsuarioManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["nome"]

    class Meta:
        ordering = ["matricula"]
        verbose_name_plural = "usuários"

    def __str__(self):
        return f"{self.matricula} — {self.nome}"

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

class Reidentificacao(models.Model):
    """Cofre de dados originais de colaboradores desligados (RN-29)."""

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
    """Segundo fator enviado por api brevo (RN-18)."""

    usuario = models.ForeignKey(Usuario, on_delete=models.CASCADE, related_name="codigos")
    codigo = models.CharField(max_length=6)
    data_geracao = models.DateTimeField(auto_now_add=True)
    data_expiracao = models.DateTimeField()
    utilizado = models.BooleanField(default=False)

    class Meta:
        ordering = ["-data_geracao"]
        verbose_name = "código de verificação"
        verbose_name_plural = "códigos de verificação"

    @property
    def valido(self):
        return not self.utilizado and timezone.now() < self.data_expiracao