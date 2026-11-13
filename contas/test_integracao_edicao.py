"""Testes de integração da edição de colaborador pelo RH (RF-14, RN-02).

Views, middleware e banco de teste são reais. O envio de e-mail pelo Brevo é mock.
"""
from datetime import timedelta
from io import StringIO
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from auditoria.models import LogSistema
from certificacao.models import Certificado
from contas.models import Departamento
from core import services
from treinamentos.models import Curso, CursoDepartamento

Usuario = get_user_model()


class CenarioEdicao(TestCase):
    """RH, colaborador de Financeiro e dois cursos: um só do Financeiro e um geral."""

    def setUp(self):
        self.financeiro = Departamento.objects.create(nome="Financeiro")
        self.ti = Departamento.objects.create(nome="TI")
        self.rh = Usuario.objects.create_user(
            email="rh@nortex.com.br", nome="Rita RH", password="senha-123",
            grupo=Usuario.Grupo.RH, senha_provisoria=False, aceitou_termos=True)
        self.colaborador = Usuario.objects.create_user(
            email="carlos@nortex.com.br", nome="Carlos Pereira", password="senha-123",
            cargo="Analista Financeiro", departamento=self.financeiro,
            senha_provisoria=False, aceitou_termos=True)

        self.fraude = Curso.objects.create(nome="Prevenção a fraude", categoria="Financeiro")
        self.chamados = Curso.objects.create(nome="Abertura de chamados", categoria="Tecnologia")
        CursoDepartamento.objects.create(curso=self.fraude, departamento=self.financeiro)
        for dep in (self.financeiro, self.ti):
            CursoDepartamento.objects.create(curso=self.chamados, departamento=dep)

        self.client.force_login(self.rh)

    def url(self, usuario=None):
        return reverse("contas:editar", args=[(usuario or self.colaborador).pk])

    def dados(self, **alterar):
        dados = {"nome": "Carlos Pereira", "email": "carlos@nortex.com.br",
                 "cargo": "Analista Financeiro", "departamento": self.financeiro.pk,
                 "grupo": Usuario.Grupo.COLABORADOR}
        dados.update(alterar)
        return dados

    def ultimo_log(self):
        return LogSistema.objects.filter(evento="Colaborador alterado").latest("id")


class EdicaoDeColaboradorTest(CenarioEdicao):

    def test_tela_abre_preenchida_com_o_cadastro_atual(self):
        resposta = self.client.get(self.url())
        self.assertContains(resposta, "Editar colaborador")
        self.assertContains(resposta, 'value="carlos@nortex.com.br"')
        self.assertContains(resposta, f'value="{self.financeiro.pk}" selected')

    def test_deve_salvar_nome_cargo_e_email_e_registrar_antes_e_depois(self):
        resposta = self.client.post(self.url(), self.dados(
            nome="Carlos Pereira Lima", cargo="Coordenador", email="  Carlos.Lima@Nortex.com.br "))

        self.assertRedirects(resposta, reverse("core:rh_colaboradores"))
        self.colaborador.refresh_from_db()
        self.assertEqual(self.colaborador.nome, "Carlos Pereira Lima")
        self.assertEqual(self.colaborador.cargo, "Coordenador")
        self.assertEqual(self.colaborador.email, "carlos.lima@nortex.com.br")   # RN-17
        log = self.ultimo_log()
        self.assertEqual(log.nivel, LogSistema.Nivel.INFO)
        self.assertEqual(log.usuario, self.rh)
        self.assertIn("Cargo: Analista Financeiro → Coordenador", log.detalhe)
        self.assertIn("E-mail: carlos@nortex.com.br → carlos.lima@nortex.com.br", log.detalhe)

    def test_mudar_de_departamento_troca_os_cursos_exigidos_e_mantem_o_certificado(self):
        hoje = timezone.localdate()
        Certificado.objects.create(usuario=self.colaborador, curso=self.chamados, nota_prova=9,
                                   versao_curso=1, data_emissao=hoje,
                                   data_validade=hoje + timedelta(days=365))

        resposta = self.client.post(self.url(), self.dados(departamento=self.ti.pk), follow=True)

        self.assertContains(resposta, "passam a ser os do departamento TI")
        self.colaborador.refresh_from_db()
        self.assertEqual(set(services.cursos_do_usuario(self.colaborador)), {self.chamados})  # RN-02
        self.assertEqual(services.situacao(self.colaborador, self.chamados)[0], "EM DIA")
        self.assertIn("Departamento: Financeiro → TI", self.ultimo_log().detalhe)

    def test_mudar_o_perfil_fica_em_destaque_na_auditoria(self):
        self.client.post(self.url(), self.dados(grupo=Usuario.Grupo.RH))

        self.colaborador.refresh_from_db()
        self.assertTrue(self.colaborador.e_rh)
        log = self.ultimo_log()
        self.assertEqual(log.nivel, LogSistema.Nivel.WARN)
        self.assertIn("Perfil: Colaborador → RH", log.detalhe)

    def test_sem_alteracao_nao_grava_nem_registra(self):
        resposta = self.client.post(self.url(), self.dados(), follow=True)
        self.assertContains(resposta, "Nenhuma alteração para salvar.")
        self.assertFalse(LogSistema.objects.filter(evento="Colaborador alterado").exists())

    def test_nome_na_lista_abre_a_edicao(self):
        resposta = self.client.get(reverse("core:rh_colaboradores"))
        self.assertContains(resposta, f'href="{self.url()}"', count=2)   # nome e botão Editar


class ValidacaoDaEdicaoTest(CenarioEdicao):

    def assert_nada_mudou(self, resposta, mensagem):
        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, mensagem)
        antes = (self.colaborador.nome, self.colaborador.email, self.colaborador.cargo,
                 self.colaborador.departamento_id, self.colaborador.grupo)
        self.colaborador.refresh_from_db()
        self.assertEqual((self.colaborador.nome, self.colaborador.email, self.colaborador.cargo,
                          self.colaborador.departamento_id, self.colaborador.grupo), antes)
        self.assertFalse(LogSistema.objects.filter(evento="Colaborador alterado").exists())

    def test_recusa_email_de_outra_conta(self):
        resposta = self.client.post(self.url(), self.dados(email="RH@nortex.com.br"))
        self.assert_nada_mudou(resposta, "Já existe conta com este endereço.")

    def test_recusa_dados_invalidos(self):
        casos = [
            ({"nome": "Ca"}, "Informe o nome completo."),
            ({"email": "carlos@nortex"}, "Endereço de correio eletrônico inválido."),
            ({"cargo": "  "}, "Informe o cargo."),
            ({"departamento": "abc"}, "Selecione um departamento válido."),
            ({"departamento": 9999}, "Selecione um departamento válido."),
            ({"grupo": "SUPERADMIN"}, "Selecione um grupo válido."),
        ]
        for alterar, mensagem in casos:
            with self.subTest(mensagem=mensagem, dados=alterar):
                resposta = self.client.post(self.url(), {**self.dados(nome="Carlos Digitado"), **alterar})
                self.assert_nada_mudou(resposta, mensagem)

    def test_rh_nao_altera_o_proprio_perfil(self):
        resposta = self.client.post(self.url(self.rh), {
            "nome": "Rita RH", "email": "rh@nortex.com.br", "cargo": "Coordenadora",
            "departamento": "", "grupo": Usuario.Grupo.COLABORADOR})

        self.assertContains(resposta, "Você não pode alterar o seu próprio perfil de acesso.")
        self.rh.refresh_from_db()
        self.assertTrue(self.rh.e_rh)
        self.assertEqual(self.rh.cargo, "")

    def test_rh_edita_os_proprios_dados_mantendo_o_perfil(self):
        self.client.post(self.url(self.rh), {
            "nome": "Rita Souza", "email": "rh@nortex.com.br", "cargo": "Coordenadora",
            "departamento": "", "grupo": Usuario.Grupo.RH})
        self.rh.refresh_from_db()
        self.assertEqual((self.rh.nome, self.rh.grupo), ("Rita Souza", Usuario.Grupo.RH))

    def test_conta_desligada_nao_e_editada(self):
        services.remover_colaborador(self.colaborador, self.rh)   # pseudonimiza (RN-34)
        self.colaborador.refresh_from_db()
        pseudonimo = self.colaborador.nome

        for metodo in ("get", "post"):
            with self.subTest(metodo=metodo):
                resposta = getattr(self.client, metodo)(self.url(), self.dados(), follow=True)
                self.assertRedirects(resposta, reverse("core:rh_colaboradores"))
                self.assertContains(resposta, "Conta desligada não pode ser editada.")
        self.colaborador.refresh_from_db()
        self.assertEqual(self.colaborador.nome, pseudonimo)

    def test_colaborador_inexistente_responde_404(self):
        self.assertEqual(self.client.get(reverse("contas:editar", args=[9999])).status_code, 404)

    def test_nome_com_html_e_exibido_como_texto(self):
        self.client.post(self.url(), self.dados(nome="<b>Carlos</b> Pereira"))
        resposta = self.client.get(reverse("core:rh_colaboradores"))
        self.assertContains(resposta, "&lt;b&gt;Carlos&lt;/b&gt; Pereira")
        self.assertNotContains(resposta, "<b>Carlos</b>")


@patch("core.management.commands.verificar_vencimentos.enviar_alerta_vencimento")
class AvisosDeVencimentoAposEdicaoTest(CenarioEdicao):
    """RF-11, RN-02 - o aviso de reciclagem segue o departamento atual e só vai para contas ativas."""

    def setUp(self):
        super().setUp()
        hoje = timezone.localdate()
        self.certificados = {
            curso: Certificado.objects.create(
                usuario=self.colaborador, curso=curso, nota_prova=9, versao_curso=1,
                data_emissao=hoje - timedelta(days=335), data_validade=hoje + timedelta(days=30))
            for curso in (self.fraude, self.chamados)
        }

    def rodar_rotina(self):
        call_command("verificar_vencimentos", stdout=StringIO())

    def cursos_avisados(self, enviar_mock):
        return {chamada.args[1].curso for chamada in enviar_mock.call_args_list}

    def test_avisa_os_cursos_exigidos_pelo_departamento(self, enviar_mock):
        self.rodar_rotina()
        self.assertEqual(self.cursos_avisados(enviar_mock), {self.fraude, self.chamados})

    def test_quem_mudou_de_departamento_so_e_avisado_dos_cursos_do_novo(self, enviar_mock):
        self.client.post(self.url(), self.dados(departamento=self.ti.pk))
        self.rodar_rotina()
        self.assertEqual(self.cursos_avisados(enviar_mock), {self.chamados})
        self.assertTrue(Certificado.objects.filter(pk=self.certificados[self.fraude].pk).exists())

    def test_conta_desligada_nao_recebe_aviso(self, enviar_mock):
        services.remover_colaborador(self.colaborador, self.rh)
        self.rodar_rotina()
        enviar_mock.assert_not_called()
