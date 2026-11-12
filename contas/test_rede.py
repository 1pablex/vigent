"""Testes unitários do IP de origem (contas/rede.py). Não usam banco."""
from django.conf import settings
from django.test import RequestFactory, SimpleTestCase, override_settings

from contas.rede import ip_do_cliente


def com_proxies(quantidade):
    return override_settings(VIGENT={**settings.VIGENT, "PROXIES_CONFIAVEIS": quantidade})


class IpDoClienteTest(SimpleTestCase):

    def setUp(self):
        self.fabrica = RequestFactory()

    def requisicao(self, remote_addr="203.0.113.10", encaminhado=None):
        extra = {"REMOTE_ADDR": remote_addr}
        if encaminhado is not None:
            extra["HTTP_X_FORWARDED_FOR"] = encaminhado
        return self.fabrica.get("/", **extra)

    @com_proxies(0)
    def test_sem_proxy_usa_o_ip_da_conexao(self):
        self.assertEqual(ip_do_cliente(self.requisicao()), "203.0.113.10")

    @com_proxies(0)
    def test_sem_proxy_ignora_o_x_forwarded_for_escrito_pelo_cliente(self):
        requisicao = self.requisicao(encaminhado="10.0.0.1")
        self.assertEqual(ip_do_cliente(requisicao), "203.0.113.10")

    @com_proxies(1)
    def test_com_um_proxy_usa_o_ip_que_o_proxy_acrescentou(self):
        requisicao = self.requisicao(remote_addr="10.1.1.1", encaminhado="198.51.100.7")
        self.assertEqual(ip_do_cliente(requisicao), "198.51.100.7")

    @com_proxies(1)
    def test_com_um_proxy_ignora_o_que_o_cliente_escreveu_a_esquerda(self):
        # O cliente mandou "1.2.3.4"; o proxy acrescentou o IP real no fim.
        requisicao = self.requisicao(remote_addr="10.1.1.1",
                                     encaminhado="1.2.3.4, 198.51.100.7")
        self.assertEqual(ip_do_cliente(requisicao), "198.51.100.7")

    @com_proxies(2)
    def test_com_dois_proxies_usa_o_penultimo_da_lista(self):
        requisicao = self.requisicao(remote_addr="10.1.1.1",
                                     encaminhado="1.2.3.4, 198.51.100.7, 10.2.2.2")
        self.assertEqual(ip_do_cliente(requisicao), "198.51.100.7")

    @com_proxies(2)
    def test_lista_menor_que_o_numero_de_proxies_usa_o_ip_da_conexao(self):
        requisicao = self.requisicao(remote_addr="10.1.1.1", encaminhado="198.51.100.7")
        self.assertEqual(ip_do_cliente(requisicao), "10.1.1.1")

    @com_proxies(1)
    def test_sem_cabecalho_com_proxy_configurado_usa_o_ip_da_conexao(self):
        self.assertEqual(ip_do_cliente(self.requisicao()), "203.0.113.10")

    @com_proxies(1)
    def test_valor_que_nao_e_ip_e_descartado(self):
        # Gravar texto qualquer no campo de IP do log quebraria no PostgreSQL.
        for invalido in ("abc", "<script>", "999.1.1.1"):
            with self.subTest(invalido=invalido):
                requisicao = self.requisicao(remote_addr="10.1.1.1", encaminhado=invalido)
                self.assertIsNone(ip_do_cliente(requisicao))

    @com_proxies(1)
    def test_cabecalho_vazio_usa_o_ip_da_conexao(self):
        requisicao = self.requisicao(remote_addr="10.1.1.1", encaminhado=" , ")
        self.assertEqual(ip_do_cliente(requisicao), "10.1.1.1")

    @com_proxies(0)
    def test_aceita_ipv6(self):
        self.assertEqual(ip_do_cliente(self.requisicao(remote_addr="2001:db8::1")), "2001:db8::1")

    @com_proxies(0)
    def test_remote_addr_ausente_devolve_none(self):
        requisicao = self.requisicao()
        del requisicao.META["REMOTE_ADDR"]
        self.assertIsNone(ip_do_cliente(requisicao))
