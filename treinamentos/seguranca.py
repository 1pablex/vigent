"""RN-40 - Segurança do conteúdo enviado para os cursos (imagens e texto dos slides).

Imagens: só JPG, PNG e WEBP, identificados pelo conteúdo e não pela extensão, com limite
de tamanho e de pixels. Depois de aceita, a imagem é regravada a partir dos pixels: o que
estiver escondido no arquivo (script anexado, metadados EXIF/GPS) não chega ao disco.

Texto do slide: HTML limitado a parágrafos, listas, negrito, itálico e quebra de linha.
"""
import uuid
from io import BytesIO

import nh3
from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from PIL import Image, ImageOps, UnidentifiedImageError

FORMATOS_PERMITIDOS = {"JPEG": "jpg", "PNG": "png", "WEBP": "webp"}
TAMANHO_MAXIMO_MB = 5
PIXELS_MAXIMOS = 25_000_000   # ~ 5000 x 5000; barra "bombas de descompressão"

TAGS_PERMITIDAS = {"p", "br", "ul", "ol", "li", "strong", "em", "b", "i"}


def validar_imagem(arquivo):
    """Recusa o que não for uma imagem JPG, PNG ou WEBP dentro dos limites."""
    if arquivo.size > TAMANHO_MAXIMO_MB * 1024 * 1024:
        raise ValidationError(f"A imagem deve ter no máximo {TAMANHO_MAXIMO_MB} MB.")
    try:
        arquivo.seek(0)
        with Image.open(arquivo) as imagem:   # lê só o cabeçalho
            formato = imagem.format
            largura, altura = imagem.size
            if formato in FORMATOS_PERMITIDOS and largura * altura <= PIXELS_MAXIMOS:
                imagem.verify()
    except (UnidentifiedImageError, Image.DecompressionBombError, OSError, SyntaxError) as erro:
        raise ValidationError("O arquivo enviado não é uma imagem válida.") from erro
    finally:
        arquivo.seek(0)

    if formato not in FORMATOS_PERMITIDOS:
        raise ValidationError("Envie a imagem em JPG, PNG ou WEBP.")
    if largura * altura > PIXELS_MAXIMOS:
        raise ValidationError("A imagem tem resolução grande demais.")


def regravar_imagem(arquivo):
    """Gera uma imagem nova só com os pixels, com nome aleatório e sem metadados."""
    arquivo.seek(0)
    with Image.open(arquivo) as original:
        formato = original.format
        imagem = ImageOps.exif_transpose(original)   # mantém a orientação da foto
        imagem.load()

    if formato == "JPEG":
        imagem = imagem.convert("RGB")
    elif imagem.mode not in ("RGB", "RGBA", "L", "LA"):
        imagem = imagem.convert("RGBA")

    saida = BytesIO()
    opcoes = {"quality": 90} if formato in ("JPEG", "WEBP") else {}
    imagem.save(saida, format=formato, **opcoes)   # sem exif=, os metadados ficam para trás
    return ContentFile(saida.getvalue(), name=f"{uuid.uuid4().hex}.{FORMATOS_PERMITIDOS[formato]}")


def sanitizar_html(texto):
    """Mantém só a formatação simples do slide; scripts e atributos são removidos."""
    if not texto:
        return texto
    return nh3.clean(texto, tags=TAGS_PERMITIDAS, attributes={})
