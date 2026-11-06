"""Testes de segurança dos endpoints do Vigent.

Cobrem autenticação, controle de acesso por perfil (RH x colaborador), acesso a
objetos de terceiros (IDOR), CSRF, ações destrutivas via GET, XSS, upload,
redirecionamento aberto, busca com injeção e cabeçalhos de segurança.

Os testes marcados com @expectedFailure documentam vulnerabilidades conhecidas e
ainda não corrigidas. Quando a correção entrar, o teste passa a dar "unexpected
success" e o decorator deve ser removido.
"""
from unittest import expectedFailure
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase
from django.urls import URLPattern, URLResolver, get_resolver, reverse

from auditoria.models import LogSistema
from avaliacoes.models import Alternativa, AvaliacaoReacao, Prova, Questao
from certificacao.models import Certificado
from contas.models import CodigoVerificacao, Departamento
from treinamentos.models import Aula, Curso, CursoDepartamento, Presenca, ProgressoAula, SlideAula

Usuario = get_user_model()

PUBLICAS = {
    "contas:login", "contas:logout", "contas:esqueci_senha", "contas:redefinir_senha",
    "contas:verificar_codigo", "contas:politica_privacidade",
}

# rota -> quantidade de argumentos inteiros
PROTEGIDAS = {
    "core:inicio": 0, "core:rh_colaboradores": 0, "core:rh_remover": 1,
    "core:rh_auditoria": 0, "core:rh_conformidade": 0, "core:rh_reciclagem": 2,
    "core:rh_dashboard": 0,
    "contas:definir_senha": 0, "contas:cadastrar": 0, "contas:aceitar_termo": 0,
    "contas:meus_dados": 0,
    "treinamentos:inicio": 0, "treinamentos:abrir": 1, "treinamentos:curso": 1,
    "avaliacoes:reacao": 1, "avaliacoes:prova": 1,
    "certificacao:meus": 0, "certificacao:ver": 1,
    "cursos_rh:lista": 0, "cursos_rh:novo": 0, "cursos_rh:editar": 1,
    "cursos_rh:aula_nova": 1, "cursos_rh:aula_editar": 2, "cursos_rh:aula_excluir": 2,
    "cursos_rh:questao_nova": 1, "cursos_rh:questao_editar": 2,
    "cursos_rh:questao_excluir": 2,
}

SOMENTE_RH = [
    "core:rh_colaboradores", "core:rh_remover", "core:rh_auditoria", "core:rh_conformidade",
    "core:rh_reciclagem", "core:rh_dashboard", "contas:cadastrar",
    "cursos_rh:lista", "cursos_rh:novo", "cursos_rh:editar", "cursos_rh:aula_nova",
    "cursos_rh:aula_editar", "cursos_rh:aula_excluir", "cursos_rh:questao_nova",
    "cursos_rh:questao_editar", "cursos_rh:questao_excluir",
]

# API REST (/api/v1/): não redireciona, responde 403 em JSON para anônimo e não RH.
# Os testes de comportamento ficam em core/test_api_indicadores.py.
API_SOMENTE_RH = {
    "api:conformidade", "api:conformidade_departamentos", "api:conformidade_cursos",
    "api:vencimentos", "api:reacao", "api:qualidade", "api:schema", "api:docs",
}

XSS = "<script>alert('xss')</script>"


def rotas_nomeadas(padroes=None, namespace=""):
    """Todas as rotas nomeadas do projeto, como "namespace:nome" (sem o admin)."""
    nomes = set()
    for p in padroes if padroes is not None else get_resolver().url_patterns:
        if isinstance(p, URLResolver):
            if p.app_name == "admin":
                continue
            ns = f"{namespace}{p.namespace}:" if p.namespace else namespace
            nomes |= rotas_nomeadas(p.url_patterns, ns)
        elif isinstance(p, URLPattern) and p.name:
            nomes.add(f"{namespace}{p.name}")
    return nomes


class CenarioSeguranca(TestCase):
    """RH, colaborador de Vendas e um curso publicado com aula, slide, prova e certificado."""

    def setUp(self):
        self.vendas = Departamento.objects.create(nome="Vendas")
        self.rh = Usuario.objects.create_user(
            email="rh@nortex.com.br", nome="Rita RH", password="senha-123",
            grupo=Usuario.Grupo.RH, senha_provisoria=False, aceitou_termos=True)
        self.colaborador = Usuario.objects.create_user(
            email="ana@nortex.com.br", nome="Ana Colaboradora", password="senha-123",
            departamento=self.vendas, senha_provisoria=False, aceitou_termos=True)
        self.outro = Usuario.objects.create_user(
            email="bruno@nortex.com.br", nome="Bruno Colaborador", password="senha-123",
            departamento=self.vendas, senha_provisoria=False, aceitou_termos=True)

        self.curso = Curso.objects.create(nome="LGPD na Prática", categoria="Compliance")
        CursoDepartamento.objects.create(curso=self.curso, departamento=self.vendas)
        self.aula = Aula.objects.create(curso=self.curso, ordem=1, titulo="Introdução")
        SlideAula.objects.create(aula=self.aula, ordem=0, titulo="Boas-vindas")
        self.questao = Questao.objects.create(
            prova=Prova.objects.create(curso=self.curso), ordem=1, enunciado="Q1?")
        Alternativa.objects.create(questao=self.questao, letra="A", texto="Certa", correta=True)
        Alternativa.objects.create(questao=self.questao, letra="B", texto="Errada")
        ProgressoAula.objects.create(usuario=self.outro, aula=self.aula, concluida=True)
        self.certificado_outro = Certificado.objects.create(
            usuario=self.outro, curso=self.curso, nota_prova=9, versao_curso=1,
            data_emissao="2026-01-10", data_validade="2027-01-10")

    def argumentos(self, rota):
        """Ids reais para as rotas que recebem parâmetros."""
        return {
            "core:rh_remover": [self.outro.id],
            "core:rh_reciclagem": [self.outro.id, self.curso.id],
            "treinamentos:abrir": [self.curso.id], "treinamentos:curso": [self.curso.id],
            "avaliacoes:reacao": [self.curso.id], "avaliacoes:prova": [self.curso.id],
            "certificacao:ver": [self.certificado_outro.id],
            "cursos_rh:editar": [self.curso.id], "cursos_rh:aula_nova": [self.curso.id],
            "cursos_rh:aula_editar": [self.curso.id, self.aula.id],
            "cursos_rh:aula_excluir": [self.curso.id, self.aula.id],
            "cursos_rh:questao_nova": [self.curso.id],
            "cursos_rh:questao_editar": [self.curso.id, self.questao.id],
            "cursos_rh:questao_excluir": [self.curso.id, self.questao.id],
        }.get(rota, [])

    def url(self, rota):
        return reverse(rota, args=self.argumentos(rota))

    def estado(self):
        """Retrato do que as ações protegidas poderiam alterar."""
        self.outro.refresh_from_db()
        return {
            "usuarios": Usuario.objects.count(),
            "outro_ativo": self.outro.is_active,
            "cursos": Curso.objects.count(),
            "aulas": Aula.objects.count(),
            "slides": SlideAula.objects.count(),
            "questoes": Questao.objects.count(),
            "progressos": ProgressoAula.objects.count(),
            "nome_curso": Curso.objects.get(pk=self.curso.pk).nome,
        }


class AutenticacaoObrigatoriaTest(CenarioSeguranca):

    def test_todas_as_rotas_estao_classificadas(self):
        # Uma rota nova sem classificação faz este teste falhar até alguém decidir
        # se ela é pública ou exige login.
        self.assertEqual(rotas_nomeadas() - PUBLICAS - set(PROTEGIDAS) - API_SOMENTE_RH, set())

    def test_rotas_protegidas_redirecionam_anonimo_para_login(self):
        for rota in PROTEGIDAS:
            for metodo in ("get", "post"):
                with self.subTest(rota=rota, metodo=metodo):
                    url = self.url(rota)
                    resposta = getattr(self.client, metodo)(url)
                    self.assertEqual(resposta.status_code, 302)
                    self.assertEqual(resposta["Location"],
                                     f"{reverse('contas:login')}?next={url}")

    def test_anonimo_nao_altera_dados(self):
        antes = self.estado()
        for rota in PROTEGIDAS:
            self.client.post(self.url(rota), {"nome": "Invadido", "rodar_rotina": "1"})
        self.assertEqual(self.estado(), antes)

    def test_rotas_publicas_abrem_sem_login(self):
        for rota in ("contas:login", "contas:esqueci_senha", "contas:politica_privacidade"):
            with self.subTest(rota=rota):
                self.assertEqual(self.client.get(reverse(rota)).status_code, 200)

    def test_etapas_do_login_exigem_etapa_anterior(self):
        # Sem senha validada não há 2FA; sem pedido de redefinição não há troca de senha.
        self.assertRedirects(self.client.get(reverse("contas:verificar_codigo")),
                             reverse("contas:login"))
        self.assertRedirects(self.client.get(reverse("contas:redefinir_senha")),
                             reverse("contas:esqueci_senha"))

    def test_admin_recusa_colaborador(self):
        self.client.force_login(self.colaborador)
        resposta = self.client.get("/admin/")
        self.assertRedirects(resposta, "/admin/login/?next=/admin/")


class ControleDeAcessoPorPerfilTest(CenarioSeguranca):

    def test_colaborador_e_barrado_nas_rotas_do_rh(self):
        self.client.force_login(self.colaborador)
        for rota in SOMENTE_RH:
            for metodo in ("get", "post"):
                with self.subTest(rota=rota, metodo=metodo):
                    resposta = getattr(self.client, metodo)(self.url(rota))
                    self.assertEqual(resposta.status_code, 302)
                    self.assertIn(resposta["Location"],
                                  (reverse("treinamentos:inicio"), reverse("core:inicio")))

    def test_colaborador_nao_altera_dados_pelas_rotas_do_rh(self):
        self.client.force_login(self.colaborador)
        antes = self.estado()
        dados = {"nome": "Invadido", "email": "novo@nortex.com.br", "cargo": "X",
                 "grupo": "RH", "categoria": "X", "carga_horaria": "1h", "validade_meses": 1,
                 "nota_minima": 0, "max_tentativas": 9, "rodar_rotina": "1"}
        for rota in SOMENTE_RH:
            self.client.post(self.url(rota), dados)
        self.assertEqual(self.estado(), antes)
        self.assertFalse(Usuario.objects.filter(email="novo@nortex.com.br").exists())

    def test_senha_provisoria_bloqueia_rotas_do_rh(self):
        self.rh.senha_provisoria = True
        self.rh.save()
        self.client.force_login(self.rh)
        for rota in ("cursos_rh:lista", "core:rh_colaboradores", "contas:cadastrar"):
            with self.subTest(rota=rota):
                self.assertRedirects(self.client.get(self.url(rota)),
                                     reverse("contas:definir_senha"))

    def test_termo_nao_aceito_bloqueia_rotas_do_rh(self):
        self.rh.aceitou_termos = False
        self.rh.save()
        self.client.force_login(self.rh)
        self.assertRedirects(self.client.get(self.url("cursos_rh:lista")),
                             reverse("contas:aceitar_termo"))


class AcessoAObjetosDeTerceirosTest(CenarioSeguranca):

    def test_colaborador_nao_abre_certificado_de_outro(self):
        self.client.force_login(self.colaborador)
        self.assertEqual(self.client.get(self.url("certificacao:ver")).status_code, 404)

    def test_colaborador_nao_entra_em_curso_de_outro_departamento(self):
        financeiro = Departamento.objects.create(nome="Financeiro")
        restrito = Curso.objects.create(nome="Fechamento contábil")
        CursoDepartamento.objects.create(curso=restrito, departamento=financeiro)
        self.client.force_login(self.colaborador)
        for rota in ("treinamentos:abrir", "treinamentos:curso",
                     "avaliacoes:reacao", "avaliacoes:prova"):
            with self.subTest(rota=rota):
                resposta = self.client.post(reverse(rota, args=[restrito.id]))
                self.assertRedirects(resposta, reverse("treinamentos:inicio"))
        self.assertFalse(Presenca.objects.filter(usuario=self.colaborador).exists())

    def test_rh_nao_mistura_aula_e_questao_de_outro_curso(self):
        # Ids válidos, mas de cursos diferentes na mesma URL: precisa dar 404 e não apagar.
        outro_curso = Curso.objects.create(nome="NR-10")
        self.client.force_login(self.rh)
        for rota, objeto in (("cursos_rh:aula_editar", self.aula.id),
                             ("cursos_rh:aula_excluir", self.aula.id),
                             ("cursos_rh:questao_editar", self.questao.id),
                             ("cursos_rh:questao_excluir", self.questao.id)):
            with self.subTest(rota=rota):
                resposta = self.client.post(reverse(rota, args=[outro_curso.id, objeto]))
                self.assertEqual(resposta.status_code, 404)
        self.assertTrue(Aula.objects.filter(pk=self.aula.pk).exists())
        self.assertTrue(Questao.objects.filter(pk=self.questao.pk).exists())


class AcoesDestrutivasSoViaPostTest(CenarioSeguranca):

    @patch("core.views.enviar_notificacao_reciclagem")
    def test_get_nao_executa_acoes_destrutivas(self, enviar_notificacao):
        self.client.force_login(self.rh)
        antes = self.estado()
        for rota in ("core:rh_remover", "core:rh_reciclagem",
                     "cursos_rh:aula_excluir", "cursos_rh:questao_excluir"):
            with self.subTest(rota=rota):
                self.assertEqual(self.client.get(self.url(rota)).status_code, 302)
        self.assertEqual(self.estado(), antes)
        enviar_notificacao.assert_not_called()


class ProtecaoCsrfTest(CenarioSeguranca):

    def setUp(self):
        super().setUp()
        self.client = Client(enforce_csrf_checks=True)

    def test_post_sem_token_csrf_e_recusado(self):
        self.client.force_login(self.rh)
        antes = self.estado()
        for rota in ("contas:cadastrar", "core:rh_remover", "core:rh_reciclagem",
                     "core:rh_conformidade", "cursos_rh:novo", "cursos_rh:editar",
                     "cursos_rh:aula_excluir", "cursos_rh:questao_excluir"):
            with self.subTest(rota=rota):
                resposta = self.client.post(self.url(rota), {"nome": "Via CSRF"})
                self.assertEqual(resposta.status_code, 403)
        self.assertEqual(self.estado(), antes)

    def test_login_sem_token_csrf_e_recusado(self):
        resposta = self.client.post(reverse("contas:login"),
                                    {"email": "rh@nortex.com.br", "senha": "senha-123"})
        self.assertEqual(resposta.status_code, 403)
        self.assertFalse(CodigoVerificacao.objects.exists())


class XssTest(CenarioSeguranca):

    def test_nome_do_curso_e_escapado_para_rh_e_colaborador(self):
        self.client.force_login(self.rh)
        self.client.post(self.url("cursos_rh:editar"), {
            "nome": XSS, "categoria": XSS, "carga_horaria": "4 horas", "validade_meses": 12,
            "nota_minima": 7, "max_tentativas": 3, "departamentos": [self.vendas.id]})
        lista_rh = self.client.get(self.url("cursos_rh:lista"))
        self.client.force_login(self.colaborador)
        lista_colaborador = self.client.get(reverse("treinamentos:inicio"))

        for resposta in (lista_rh, lista_colaborador):
            self.assertNotContains(resposta, XSS)
            self.assertContains(resposta, "&lt;script&gt;")

    def test_questao_e_alternativas_sao_escapadas_na_prova(self):
        self.questao.enunciado = XSS
        self.questao.save()
        self.questao.alternativas.filter(letra="B").update(texto=XSS)
        ProgressoAula.objects.create(usuario=self.colaborador, aula=self.aula, concluida=True)
        AvaliacaoReacao.objects.create(usuario=self.colaborador, curso=self.curso,
                                       nota_didatica=8, nota_entendimento=8)
        self.client.force_login(self.colaborador)

        resposta = self.client.get(self.url("avaliacoes:prova"))

        self.assertEqual(resposta.status_code, 200)
        self.assertNotContains(resposta, XSS)

    @expectedFailure
    def test_texto_do_slide_nao_executa_script(self):
        # VULNERÁVEL: curso.html exibe slide.corpo com |safe. Quem tem perfil RH consegue
        # gravar um <script> que roda no navegador de todos os colaboradores do curso.
        self.aula.slides.update(corpo=XSS)
        self.client.force_login(self.colaborador)

        resposta = self.client.get(self.url("treinamentos:curso"))

        self.assertNotContains(resposta, XSS)


class EntradasMaliciosasTest(CenarioSeguranca):

    def test_capa_que_nao_e_imagem_e_recusada(self):
        self.client.force_login(self.rh)
        falsa = SimpleUploadedFile("capa.png", b"<?php echo 'x'; ?>", content_type="image/png")

        resposta = self.client.post(self.url("cursos_rh:novo"), {
            "nome": "Curso com capa falsa", "categoria": "X", "carga_horaria": "1h",
            "validade_meses": 12, "nota_minima": 7, "max_tentativas": 3, "imagem_capa": falsa})

        self.assertEqual(resposta.status_code, 200)
        self.assertTrue(resposta.context["form"].errors.get("imagem_capa"))
        self.assertFalse(Curso.objects.filter(nome="Curso com capa falsa").exists())

    def test_busca_com_injecao_sql_e_tratada_como_texto(self):
        self.client.force_login(self.rh)
        for rota in ("core:rh_colaboradores", "cursos_rh:lista", "core:rh_auditoria",
                     "core:rh_conformidade"):
            with self.subTest(rota=rota):
                resposta = self.client.get(self.url(rota), {"busca": "' OR 1=1 --"})
                self.assertEqual(resposta.status_code, 200)
        resposta = self.client.get(self.url("core:rh_colaboradores"), {"busca": "' OR 1=1 --"})
        self.assertEqual(list(resposta.context["colaboradores"]), [])

    def test_login_ignora_redirecionamento_para_site_externo(self):
        with patch("contas.views.enviar_codigo_verificacao"):
            resposta = self.client.post(
                f"{reverse('contas:login')}?next=https://site-malicioso.example",
                {"email": "rh@nortex.com.br", "senha": "senha-123"})
        self.assertRedirects(resposta, reverse("contas:verificar_codigo"))

    @expectedFailure
    def test_cadastro_recusa_grupo_inexistente(self):
        # VULNERÁVEL: o campo grupo não é validado contra Usuario.Grupo.
        self.client.force_login(self.rh)
        with patch("contas.views.enviar_primeiro_acesso"):
            self.client.post(reverse("contas:cadastrar"), {
                "nome": "Fulano de Tal", "email": "fulano@nortex.com.br", "cargo": "Analista",
                "grupo": "SUPERADMIN"})
        self.assertFalse(Usuario.objects.filter(grupo="SUPERADMIN").exists())


class LimitesDeRequisicaoTest(CenarioSeguranca):

    @expectedFailure
    def test_cabecalho_x_forwarded_for_nao_burla_bloqueio_por_ip(self):
        # VULNERÁVEL: _ip() confia no X-Forwarded-For enviado pelo próprio cliente.
        for i in range(6):
            resposta = self.client.post(
                reverse("contas:login"), {"email": f"x{i}@nortex.com.br", "senha": "errada"},
                HTTP_X_FORWARDED_FOR=f"10.0.0.{i}")
        self.assertContains(resposta, "Muitas tentativas de acesso")

    @expectedFailure
    def test_reenvio_de_codigo_tem_intervalo_minimo(self):
        # VULNERÁVEL: "Reenviar código" gera e envia um e-mail novo a cada clique.
        with patch("contas.views.enviar_codigo_verificacao"):
            self.client.post(reverse("contas:login"),
                             {"email": "rh@nortex.com.br", "senha": "senha-123"})
            for _ in range(5):
                self.client.post(reverse("contas:verificar_codigo"), {"reenviar": "1"})
        self.assertLessEqual(CodigoVerificacao.objects.filter(usuario=self.rh).count(), 2)


class CabecalhosDeSegurancaTest(CenarioSeguranca):

    def test_respostas_trazem_cabecalhos_de_protecao(self):
        resposta = self.client.get(reverse("contas:login"))
        self.assertEqual(resposta["X-Frame-Options"], "DENY")
        self.assertEqual(resposta["X-Content-Type-Options"], "nosniff")
        self.assertEqual(resposta["Referrer-Policy"], "same-origin")

    def test_logout_encerra_a_sessao(self):
        self.client.force_login(self.rh)
        self.client.get(reverse("contas:logout"))
        self.assertRedirects(self.client.get(self.url("cursos_rh:lista")),
                             f"{reverse('contas:login')}?next={self.url('cursos_rh:lista')}")
        self.assertFalse(LogSistema.objects.filter(evento="Curso alterado").exists())
