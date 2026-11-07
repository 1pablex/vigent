"""RN-40 - Segurança do conteúdo dos cursos: imagens enviadas e texto dos slides."""
import shutil
import tempfile
from io import BytesIO
from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from PIL import Image

from treinamentos import seguranca
from treinamentos.models import Aula, Curso, SlideAula

PAYLOAD = b"<script>alert('xss')</script><?php system($_GET['c']); ?>"


def imagem(formato="PNG", tamanho=(20, 20), nome=None, exif=None, sufixo=b""):
    buffer = BytesIO()
    opcoes = {"exif": exif} if exif else {}
    Image.new("RGB", tamanho, (47, 78, 143)).save(buffer, format=formato, **opcoes)
    nome = nome or f"arquivo.{formato.lower()}"
    return SimpleUploadedFile(nome, buffer.getvalue() + sufixo,
                              content_type=f"image/{formato.lower()}")


class ValidacaoDeImagemTest(TestCase):

    def test_aceita_jpg_png_e_webp(self):
        for formato in ("JPEG", "PNG", "WEBP"):
            with self.subTest(formato=formato):
                seguranca.validar_imagem(imagem(formato))

    def test_recusa_formato_fora_da_lista_mesmo_sendo_imagem_valida(self):
        for formato in ("GIF", "BMP", "TIFF"):
            with self.subTest(formato=formato):
                with self.assertRaisesMessage(ValidationError, "JPG, PNG ou WEBP"):
                    seguranca.validar_imagem(imagem(formato, nome="disfarce.png"))

    def test_recusa_arquivo_que_nao_e_imagem(self):
        falsa = SimpleUploadedFile("capa.png", b"<?php echo 'x'; ?>", content_type="image/png")
        with self.assertRaisesMessage(ValidationError, "não é uma imagem válida"):
            seguranca.validar_imagem(falsa)

    def test_recusa_arquivo_acima_do_limite_de_tamanho(self):
        grande = SimpleUploadedFile("grande.png", b"0" * (5 * 1024 * 1024 + 1))
        with self.assertRaisesMessage(ValidationError, "no máximo 5 MB"):
            seguranca.validar_imagem(grande)

    def test_recusa_resolucao_grande_demais(self):
        with patch.object(seguranca, "PIXELS_MAXIMOS", 100):
            with self.assertRaisesMessage(ValidationError, "resolução grande demais"):
                seguranca.validar_imagem(imagem(tamanho=(20, 20)))

    def test_model_recusa_imagem_invalida_tambem_fora_do_painel(self):
        # O validador está no campo do model: vale para o painel do RH e para o admin.
        curso = Curso(nome="X", categoria="Y", imagem_capa=imagem("GIF"))
        with self.assertRaises(ValidationError) as erro:
            curso.full_clean()
        self.assertIn("imagem_capa", erro.exception.message_dict)


class RegravacaoDeImagemTest(TestCase):

    def setUp(self):
        self.media = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.media, ignore_errors=True)
        configuracao = override_settings(MEDIA_ROOT=self.media)
        configuracao.enable()
        self.addCleanup(configuracao.disable)

    def salvar_capa(self, arquivo):
        curso = Curso.objects.create(nome="LGPD", categoria="Compliance", imagem_capa=arquivo)
        curso.imagem_capa.open("rb")
        self.addCleanup(curso.imagem_capa.close)
        return curso.imagem_capa

    def test_conteudo_escondido_apos_a_imagem_e_descartado(self):
        # Arquivo "poliglota": é uma imagem válida, mas carrega script no final.
        capa = self.salvar_capa(imagem("PNG", sufixo=PAYLOAD))
        self.assertNotIn(b"<script>", capa.read())

    def test_metadados_exif_sao_removidos(self):
        exif = Image.Exif()
        exif[0x013B] = "Autor da foto"          # Artist
        exif[0x8825] = {2: (23, 33, 0)}          # GPSInfo
        capa = self.salvar_capa(imagem("JPEG", exif=exif.tobytes()))
        with Image.open(capa) as salva:
            self.assertEqual(len(salva.getexif()), 0)

    def test_nome_e_aleatorio_e_extensao_segue_o_formato_real(self):
        capa = self.salvar_capa(imagem("JPEG", nome="relatorio-financeiro.png"))
        self.assertNotIn("relatorio", capa.name)
        self.assertRegex(capa.name, r"^capas/[0-9a-f]{32}\.jpg$")

    def test_imagem_ja_salva_nao_e_regravada_ao_editar_o_curso(self):
        capa = self.salvar_capa(imagem("PNG"))
        curso = Curso.objects.get()
        curso.nome = "LGPD na Prática"
        curso.save()
        self.assertEqual(curso.imagem_capa.name, capa.name)

    def test_imagem_do_slide_tambem_e_regravada(self):
        curso = Curso.objects.create(nome="NR-35", categoria="Segurança")
        aula = Aula.objects.create(curso=curso, ordem=1, titulo="Aula 1")
        slide = SlideAula.objects.create(aula=aula, ordem=1, titulo="S1",
                                         imagem=imagem("PNG", sufixo=PAYLOAD))
        with slide.imagem.open("rb") as arquivo:
            self.assertNotIn(b"<script>", arquivo.read())
        self.assertRegex(slide.imagem.name, r"^slides/[0-9a-f]{32}\.png$")


class SanitizacaoDoTextoDoSlideTest(TestCase):

    def test_remove_script_e_atributos_perigosos(self):
        sujo = ('<p onclick="roubar()">Oi</p><script>alert(1)</script>'
                '<img src=x onerror="alert(1)"><a href="javascript:alert(1)">link</a>')
        limpo = seguranca.sanitizar_html(sujo)
        for perigoso in ("<script", "alert(1)", "onclick", "onerror", "<img", "javascript:"):
            with self.subTest(perigoso=perigoso):
                self.assertNotIn(perigoso, limpo)

    def test_mantem_a_formatacao_simples(self):
        texto = "<p>Use <strong>EPI</strong> e <em>cinto</em>:</p><ul><li>Item</li></ul><br>"
        self.assertEqual(seguranca.sanitizar_html(texto), texto)

    def test_texto_e_sanitizado_ao_salvar_o_slide(self):
        curso = Curso.objects.create(nome="NR-35", categoria="Segurança")
        aula = Aula.objects.create(curso=curso, ordem=1, titulo="Aula 1")
        slide = SlideAula.objects.create(aula=aula, ordem=1, titulo="S1",
                                         corpo="<p>Texto</p><script>alert(1)</script>")
        slide.refresh_from_db()
        self.assertEqual(slide.corpo, "<p>Texto</p>")
