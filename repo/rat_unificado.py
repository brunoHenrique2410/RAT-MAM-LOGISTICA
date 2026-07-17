import os
import sys
from io import BytesIO
from datetime import datetime, date

from PIL import Image, ImageOps

THIS_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(THIS_DIR)
PDF_BASE_PATH = os.path.join(
    PROJECT_ROOT,
    "pdf_templates",
    "RAT_MAM_UNIFICADA.pdf",
)


for path in [THIS_DIR, PROJECT_ROOT]:
    if path not in sys.path:
        sys.path.insert(0, path)

import streamlit as st
import fitz  # PyMuPDF

from common.state import init_defaults
from common.pdf import (
    open_pdf_template,
    insert_right_of,
    insert_textbox,
    mark_X_left_of,
    insert_signature_png,
)

import ui_unificado


# =============== PATHS / CONSTANTES ===============

PROJECT_ROOT = os.path.dirname(THIS_DIR)


# =============== STATE DEFAULTS ===============


def _init_rat_defaults() -> None:
    """
    Inicializa todos os campos usados pela UI + geração de PDF.
    """
    init_defaults(
        {
            # --------- BLOCO 1 – Dados do Relatório & Local ---------
            "num_relatorio": "",
            "num_chamado": "",
            "operadora_contrato": "",
            "cliente_razao": "",
            "cnpj_cpf": "",
            "contato_nome": "",
            "contato_telefone_email": "",
            "endereco_completo": "",
            "distancia_km": "",
            "inicio_atend": "",   # "10:00"
            "termino_atend": "",  # "11:15"
            "data_atendimento": datetime.now().date().isoformat(),
            # --------- BLOCO 2 – Atendimento & Testes ---------
            "analista_suporte": "",
            "analista_integradora": "",
            "analista_validador": "",
            "tipo_atendimento": "",          # ex.: "Instalação", "Ativação"...
            "anormalidade_flags": [],        # ex.: ["Interrupção total", "Lentidão"]
            "motivo_chamado": "",            # fallback texto livre
            # checklist técnico – dicionário {item: "Sim"/"Não"}
            "checklist_tecnico": {},
            # --------- BLOCO 3 – Materiais & Equipamentos ---------
            "material_utilizado": "",
            "equip_instalados": "",
            "equip_retirados": "",
            # --------- BLOCO 4 – Observações ---------
            "testes_realizados": [],
            "descricao_atendimento": "",
            "observacoes_pendencias": "",
            # --------- BLOCO 5 – Aceite & Assinaturas ---------
            "nome_tecnico": "",
            "doc_tecnico": "",
            "tel_tecnico": "",
            "dt_tecnico": "",
            "nome_cliente": "",
            "doc_cliente": "",
            "tel_cliente": "",
            "dt_cliente": "",
            "sig_tec_png": None,
            "sig_cli_png": None,
            # --------- FOTOS DO CHAMADO ---------
            "fotos_chamado": [],
            "fotos_chamado_hashes": set(),
            "fotos_upload_version": 0,
            # --------- CONTROLE ---------
            "trigger_generate": False,
        }
    )


# =============== HELPERS ===============


def _safe_date_to_str(value) -> str:
    try:
        if isinstance(value, date):
            d = value
        else:
            d = date.fromisoformat(str(value))
        # formato separado, com mais espaço entre dia/mes/ano
        return f"{d.day:02d}   {d.month:02d}   {d.year:04d}"
    except Exception:
        return str(value or "")


def _safe_distancia_txt(ss) -> str:
    """
    Converte distancia_km para string com 1 casa e vírgula.
    Aceita '12,5', '12.5', '12', etc. Se não conseguir, retorna o valor cru.
    """
    try:
        raw = str(getattr(ss, "distancia_km", "")).strip()
        val = float(raw.replace(",", "."))
        return f"{val:.1f}".replace(".", ",")
    except Exception:
        return str(getattr(ss, "distancia_km", ""))


def _mark_tipo_atendimento(page: fitz.Page, tipo: str) -> None:
    """
    Marca X no checkbox do Tipo de Atendimento, de acordo com o valor vindo da UI.
    """
    if not tipo:
        return

    t = tipo.strip().lower()

    def mx(label: str):
        mark_X_left_of(page, label, dx=-10, dy=0, fontsize=11)

    if "instala" in t:
        mx("Instalação")
    elif "ativ" in t:
        mx("Ativação")
    elif "manut" in t and "corre" in t:
        mx("Manut. Corretiva")
    elif "manut" in t and "preven" in t:
        mx("Manut. Preventiva")
    elif "verif" in t:
        mx("Verificação")
    elif "retir" in t:
        mx("Retirada")
    elif "pass" in t and "cabo" in t:
        mx("Passagem de cabo")
    elif "outro" in t:
        mx("Outros")


def _mark_anormalidades(page: fitz.Page, flags) -> None:
    """
    Marca X nas opções de "Anormalidade / Motivo do Chamado"
    se receber uma lista de strings (flags).
    """
    if not flags or not isinstance(flags, (list, tuple, set)):
        return

    norm = [str(f).strip().lower() for f in flags]

    def mx(label: str):
        mark_X_left_of(page, label, dx=-10, dy=0, fontsize=11)

    for f in norm:
        if "interrup" in f or "total" in f:
            mx("Interrupção total")
        if "sincron" in f:
            mx("Sem sincronismo")
        if "mensagem" in f or "erro" in f:
            mx("Mensagem com erro")
        if "intermit" in f or "queda" in f:
            mx("Intermitência / Quedas")
        if "taxa" in f:
            mx("Taxa de erro")
        if "portadora" in f:
            mx("Sem portadora")
        if "lentidao" in f or "lentidão" in f:
            mx("Lentidão")
        if "ruido" in f or "ruído" in f:
            mx("Ruído")
        if "outro" in f:
            mx("Outros")


def _mark_checklist_tecnico(page: fitz.Page, checklist_dict) -> None:
    """
    Marca X no 5. Checklist Técnico (SIM / NÃO) em cima dos quadradinhos
    de SIM ou NÃO, de acordo com o dicionário vindo da UI.

    checklist_dict = {
        "Circuito corretamente instalado": "Sim",
        "Teste de circuito normal": "Não",
        ...
    }

    Estratégia:
    - Procura o retângulo do texto do item.
    - Procura todos os "Sim" e "Não" na página.
    - Para cada item, pega o "Sim"/"Não" que estiver na mesma linha (y parecido)
      e mais à direita do texto do item.
    - Desenha o X um pouco à esquerda da palavra "Sim"/"Não" (onde fica a caixinha).
    """
    if not isinstance(checklist_dict, dict) or not checklist_dict:
        return

    # pré-busca de todos os "Sim" e "Não" da página
    try:
        sim_rects = page.search_for("Sim")
    except Exception:
        sim_rects = []

    try:
        nao_rects = page.search_for("Não")
    except Exception:
        nao_rects = []

    page_w = page.rect.width

    def _closest_on_line(label_rect, rects):
        """
        Pega o retângulo em `rects` que:
        - está na mesma "linha" (y +- pequena faixa)
        - tem x0 > label_rect.x1 (à direita do texto)
        - é o mais próximo em x (menor x0)
        """
        if not rects:
            return None
        ly = (label_rect.y0 + label_rect.y1) / 2.0
        candidates = []
        for r in rects:
            ry = (r.y0 + r.y1) / 2.0
            if abs(ry - ly) <= 6 and r.x0 > label_rect.x1:
                candidates.append(r)
        if not candidates:
            return None
        # pega o mais próximo do texto (menor x0)
        candidates.sort(key=lambda rr: rr.x0)
        return candidates[0]

    for item, resp in checklist_dict.items():
        if str(resp) not in ("Sim", "Não"):
            continue

        try:
            item_rects = page.search_for(item)
        except Exception:
            item_rects = []

        if not item_rects:
            continue

        label_rect = item_rects[0]

        if resp == "Sim":
            r = _closest_on_line(label_rect, sim_rects)
        else:
            r = _closest_on_line(label_rect, nao_rects)

        if not r:
            continue

        # posição do X: um pouco à esquerda da palavra "Sim"/"Não"
        y = (r.y0 + r.y1) / 2.0
        x = r.x0 - 12  # 10 pontos à esquerda deve cair na caixinha
        page.insert_text((x, y), "X", fontsize=11)



# =============== PREENCHIMENTO POR COORDENADAS FIXAS ===============


def _write_box(
    page: fitz.Page,
    rect,
    value,
    fontsize: float = 8,
    align: int = 0,
) -> None:
    """Escreve texto em uma área fixa do template."""
    text = str(value or "").strip()

    if not text:
        return

    page.insert_textbox(
        fitz.Rect(*rect),
        text,
        fontsize=fontsize,
        fontname="helv",
        color=(0, 0, 0),
        align=align,
        overlay=True,
    )


def _draw_x(
    page: fitz.Page,
    x: float,
    y: float,
    fontsize: float = 8.5,
) -> None:
    """Desenha um X centralizado dentro de uma caixa de seleção."""
    page.insert_text(
        (x, y),
        "X",
        fontsize=fontsize,
        fontname="helv",
        color=(0, 0, 0),
        overlay=True,
    )


def _insert_signature_fixed(
    page: fitz.Page,
    rect,
    png_bytes,
) -> None:
    """Insere assinatura PNG em uma área fixa."""
    if not png_bytes:
        return

    page.insert_image(
        fitz.Rect(*rect),
        stream=png_bytes,
        keep_proportion=True,
        overlay=True,
    )


def _mark_tipo_atendimento_fixed(
    page: fitz.Page,
    tipo: str,
) -> None:
    value = str(tipo or "").strip().lower()

    positions = {
        "instala": (38, 301),
        "verif": (38, 317),
        "ativ": (159, 301),
        "retir": (159, 317),
        "corret": (279, 301),
        "passagem": (279, 317),
        "preven": (419, 301),
        "outro": (419, 317),
    }

    for key, position in positions.items():
        if key in value:
            _draw_x(page, *position)
            break


def _mark_anormalidades_fixed(
    page: fitz.Page,
    flags,
) -> None:
    """Marca as anormalidades no centro exato das caixas."""
    if not isinstance(flags, (list, tuple, set)):
        return

    positions = {
        "interrup": (41.5, 420.0),
        "sincron": (41.5, 436.0),
        "mensagem": (41.5, 452.0),
        "intermit": (211.5, 420.0),
        "queda": (211.5, 420.0),
        "taxa": (211.5, 436.0),
        "portadora": (211.5, 452.0),
        "lent": (401.5, 420.0),
        "ru": (401.5, 436.0),
        "outro": (401.5, 452.0),
    }

    marked = set()

    for item in flags:
        normalized = str(item or "").strip().lower()

        for key, position in positions.items():
            if key in normalized and position not in marked:
                _draw_x(page, *position)
                marked.add(position)


def _mark_checklist_fixed(
    page: fitz.Page,
    checklist,
) -> None:
    """
    Marca Sim/Não por coordenadas fixas e centralizadas.
    """
    if not isinstance(checklist, dict):
        return

    aliases = {
        "Teste de circuito comutado": "Teste de circuito normal",
    }

    rows = {
        "Circuito corretamente instalado": {
            "sim": (269.0, 518.5),
            "nao": (309.5, 518.5),
        },
        "Teste de circuito normal": {
            "sim": (269.0, 534.3),
            "nao": (309.5, 534.3),
        },
        "Alimentação adequada": {
            "sim": (269.0, 550.0),
            "nao": (309.5, 550.0),
        },
        "Aterramento adequado": {
            "sim": (269.0, 565.8),
            "nao": (309.5, 565.8),
        },
        "Mensagem com erro": {
            "sim": (269.0, 581.5),
            "nao": (309.5, 581.5),
        },
        "Sem portadora": {
            "sim": (519.0, 520.2),
            "nao": (560.5, 520.2),
        },
        "Fiação interna adequada": {
            "sim": (519.0, 536.0),
            "nao": (560.5, 536.0),
        },
        "Cabo de rede adequado": {
            "sim": (519.0, 551.8),
            "nao": (560.5, 551.8),
        },
        "Equipamentos em condições": {
            "sim": (519.0, 567.5),
            "nao": (560.5, 567.5),
        },
        "Ambiente/infra adequada": {
            "sim": (519.0, 583.3),
            "nao": (560.5, 583.3),
        },
    }

    for original_item, answer in checklist.items():
        item = aliases.get(original_item, original_item)

        if item not in rows:
            continue

        normalized_answer = str(answer or "").strip().lower()

        if normalized_answer == "sim":
            _draw_x(page, *rows[item]["sim"])
        elif normalized_answer in ("não", "nao"):
            _draw_x(page, *rows[item]["nao"])


def _mark_tests_fixed(
    page: fitz.Page,
    tests,
) -> None:
    """Marca os testes nas caixas corretas da página 2."""
    if not isinstance(tests, (list, tuple, set)):
        return

    positions = {
        "autenticação": (305.5, 315.5),
        "autenticacao": (305.5, 315.5),
        "navegação": (305.5, 329.0),
        "navegacao": (305.5, 329.0),
        "sincronismo": (305.5, 342.5),
        "ping": (305.5, 356.0),
        "latência": (305.5, 356.0),
        "latencia": (305.5, 356.0),
        "throughput": (305.5, 369.5),
        "velocidade": (305.5, 369.5),
        "teste de dados": (305.5, 369.5),
    }

    marked = set()
    extras = []

    for test in tests:
        normalized = str(test or "").strip().lower()
        found = False

        for key, position in positions.items():
            if key in normalized:
                if position not in marked:
                    _draw_x(page, *position)
                    marked.add(position)
                found = True
                break

        if not found and normalized:
            extras.append(str(test))

    if extras:
        _write_box(
            page,
            (390, 312, 565, 378),
            "Outros: " + " | ".join(extras),
            fontsize=7,
        )


# =============== PÁGINA 1 ===============


def _fill_page1(page: fitz.Page, ss) -> None:
    """
    Preenche a página 1 com os valores abaixo dos títulos originais.
    """

    generated_at = datetime.now()
    generated_date = generated_at.strftime("%d / %m / %Y")
    generated_time = generated_at.strftime("%H:%M")

    # 1. Identificação do Atendimento
    _write_box(page, (40, 91, 205, 103), ss.num_chamado, fontsize=9)
    _write_box(page, (220, 91, 388, 103), ss.num_relatorio, fontsize=9)
    _write_box(page, (402, 91, 565, 103), ss.operadora_contrato, fontsize=9)

    _write_box(page, (40, 129, 565, 142), ss.cliente_razao, fontsize=9)

    _write_box(page, (40, 167, 176, 180), ss.cnpj_cpf, fontsize=9)
    _write_box(page, (192, 167, 312, 180), ss.contato_nome, fontsize=9)
    _write_box(
        page,
        (325, 167, 565, 180),
        ss.contato_telefone_email,
        fontsize=9,
    )

    _write_box(
        page,
        (40, 205, 565, 218),
        ss.endereco_completo,
        fontsize=8,
    )

    # 2. Dados Operacionais
    _write_box(page, (40, 256, 205, 270), ss.analista_suporte, fontsize=8.5)
    _write_box(
        page,
        (220, 256, 388, 270),
        ss.analista_integradora,
        fontsize=8.5,
    )
    _write_box(
        page,
        (402, 256, 565, 270),
        ss.analista_validador,
        fontsize=8.5,
    )

    _mark_tipo_atendimento_fixed(
        page,
        getattr(ss, "tipo_atendimento", ""),
    )

    # 3. Horários e Deslocamento
    _write_box(
        page,
        (48, 359, 142, 374),
        _safe_date_to_str(ss.data_atendimento),
        fontsize=10,
        align=1,
    )
    _write_box(
        page,
        (160, 359, 238, 374),
        ss.inicio_atend,
        fontsize=10,
        align=1,
    )
    _write_box(
        page,
        (255, 359, 334, 374),
        ss.termino_atend,
        fontsize=10,
        align=1,
    )
    _write_box(
        page,
        (352, 359, 565, 374),
        _safe_distancia_txt(ss),
        fontsize=10,
        align=1,
    )

    # 4. Anormalidade / Motivo
    _mark_anormalidades_fixed(
        page,
        getattr(ss, "anormalidade_flags", []),
    )

    # 5. Checklist Técnico
    _mark_checklist_fixed(
        page,
        getattr(ss, "checklist_tecnico", {}),
    )

    # 6. Aceite do Cliente
    _write_box(page, (40, 630, 205, 645), ss.nome_cliente, fontsize=9)
    _write_box(page, (224, 630, 388, 645), ss.doc_cliente, fontsize=9)
    _write_box(page, (402, 630, 565, 645), ss.tel_cliente, fontsize=9)

    # Data e hora automáticas da geração.
    _write_box(
        page,
        (46, 699, 126, 718),
        generated_date,
        fontsize=9,
        align=1,
    )
    _write_box(
        page,
        (131, 699, 178, 718),
        generated_time,
        fontsize=9,
        align=1,
    )

    _insert_signature_fixed(
        page,
        (310, 673, 560, 716),
        getattr(ss, "sig_cli_png", None),
    )


# =============== PÁGINA 2 ===============


def _fill_page2(page: fitz.Page, ss) -> None:
    """
    Preenche a página 2 dentro das áreas úteis do template.
    """

    generated_at = datetime.now()
    generated_date = generated_at.strftime("%d / %m / %Y")
    generated_time = generated_at.strftime("%H:%M")

    # 7. Equipamentos instalados / existentes
    _write_box(
        page,
        (38, 103, 560, 191),
        ss.equip_instalados,
        fontsize=8,
    )

    # 8. Equipamentos retirados
    _write_box(
        page,
        (38, 239, 560, 278),
        ss.equip_retirados,
        fontsize=8,
    )

    # 9. Material utilizado
    _write_box(
        page,
        (38, 322, 292, 380),
        ss.material_utilizado,
        fontsize=8,
    )

    # 10. Testes realizados
    _mark_tests_fixed(
        page,
        getattr(ss, "testes_realizados", []),
    )

    # 11. Descrição do Atendimento
    _write_box(
        page,
        (38, 405, 560, 526),
        ss.descricao_atendimento,
        fontsize=8,
    )

    # 12. Observações / Pendências
    _write_box(
        page,
        (38, 555, 560, 641),
        ss.observacoes_pendencias,
        fontsize=8,
    )

    # 13. Encerramento do Técnico
    _write_box(page, (40, 679, 205, 694), ss.nome_tecnico, fontsize=9)
    _write_box(page, (224, 679, 388, 694), ss.doc_tecnico, fontsize=9)
    _write_box(page, (404, 679, 565, 694), ss.tel_tecnico, fontsize=9)

    # Data e hora automáticas da geração.
    _write_box(
        page,
        (46, 748, 126, 767),
        generated_date,
        fontsize=9,
        align=1,
    )
    _write_box(
        page,
        (132, 748, 179, 767),
        generated_time,
        fontsize=9,
        align=1,
    )

    _insert_signature_fixed(
        page,
        (310, 721, 560, 765),
        getattr(ss, "sig_tec_png", None),
    )


# =============== FOTOS DO CHAMADO ===============


def _get_photo_bytes(photo) -> bytes:
    """
    Aceita foto armazenada como:
    - dict com a chave 'conteudo';
    - UploadedFile;
    - bytes/bytearray.
    """
    if isinstance(photo, dict):
        raw = photo.get("conteudo", b"")
    elif hasattr(photo, "getvalue"):
        raw = photo.getvalue()
    elif isinstance(photo, (bytes, bytearray)):
        raw = bytes(photo)
    else:
        raw = b""

    return bytes(raw) if raw else b""


def _normalize_photo_for_pdf(raw: bytes) -> bytes:
    """
    Corrige orientação EXIF, redimensiona e comprime a imagem.

    Regras:
    - lado maior limitado a 1600 px;
    - conversão para RGB;
    - JPEG com qualidade 82;
    - otimização e modo progressivo ativados.
    """
    max_dimension = 1600
    jpeg_quality = 82

    with Image.open(BytesIO(raw)) as image:
        image = ImageOps.exif_transpose(image)

        if image.mode not in ("RGB", "L"):
            background = Image.new("RGB", image.size, "white")

            if "A" in image.getbands():
                background.paste(image, mask=image.getchannel("A"))
            else:
                background.paste(image)

            image = background
        elif image.mode == "L":
            image = image.convert("RGB")

        width, height = image.size
        largest_side = max(width, height)

        if largest_side > max_dimension:
            scale = max_dimension / largest_side
            new_size = (
                max(1, int(width * scale)),
                max(1, int(height * scale)),
            )

            image = image.resize(
                new_size,
                Image.Resampling.LANCZOS,
            )

        output = BytesIO()
        image.save(
            output,
            format="JPEG",
            quality=jpeg_quality,
            optimize=True,
            progressive=True,
        )

        return output.getvalue()


def _fit_rect_keep_aspect(
    source_width: float,
    source_height: float,
    target: fitz.Rect,
) -> fitz.Rect:
    """
    Calcula um retângulo centralizado dentro de target,
    preservando a proporção original da foto.
    """
    if source_width <= 0 or source_height <= 0:
        return target

    source_ratio = source_width / source_height
    target_ratio = target.width / target.height

    if source_ratio > target_ratio:
        width = target.width
        height = width / source_ratio
    else:
        height = target.height
        width = height * source_ratio

    x0 = target.x0 + (target.width - width) / 2
    y0 = target.y0 + (target.height - height) / 2

    return fitz.Rect(
        x0,
        y0,
        x0 + width,
        y0 + height,
    )


def _clean_metadata_value(value) -> str:
    """
    Converte qualquer valor em uma linha segura para extração futura.
    """
    if isinstance(value, (list, tuple, set)):
        value = " | ".join(str(item) for item in value)

    elif isinstance(value, dict):
        value = " | ".join(
            f"{key}:{item}"
            for key, item in value.items()
        )

    cleaned = str(value or "")
    cleaned = cleaned.replace("\r", " ")
    cleaned = cleaned.replace("\n", " ")
    cleaned = " ".join(cleaned.split())

    return cleaned


def _build_hidden_metadata(ss) -> str:
    """
    Monta o bloco estruturado que ficará em texto branco na página 3.

    Cada linha começa com &&&, facilitando a extração pelo sistema
    de fechamento.
    """
    metadata = {
        "VERSAO": "1",
        "TIPO_DOCUMENTO": "RAT_MAM_UNIFICADA",
        "NUM_CHAMADO": getattr(ss, "num_chamado", ""),
        "NUM_RELATORIO": getattr(ss, "num_relatorio", ""),
        "OPERADORA_CONTRATO": getattr(
            ss,
            "operadora_contrato",
            "",
        ),
        "CLIENTE_RAZAO": getattr(ss, "cliente_razao", ""),
        "CNPJ_CPF": getattr(ss, "cnpj_cpf", ""),
        "CONTATO_NOME": getattr(ss, "contato_nome", ""),
        "CONTATO_TELEFONE_EMAIL": getattr(
            ss,
            "contato_telefone_email",
            "",
        ),
        "ENDERECO_COMPLETO": getattr(
            ss,
            "endereco_completo",
            "",
        ),
        "DISTANCIA_KM": getattr(ss, "distancia_km", ""),
        "DATA_ATENDIMENTO": getattr(
            ss,
            "data_atendimento",
            "",
        ),
        "INICIO_ATENDIMENTO": getattr(
            ss,
            "inicio_atend",
            "",
        ),
        "TERMINO_ATENDIMENTO": getattr(
            ss,
            "termino_atend",
            "",
        ),
        "ANALISTA_SUPORTE": getattr(
            ss,
            "analista_suporte",
            "",
        ),
        "ANALISTA_INTEGRADORA": getattr(
            ss,
            "analista_integradora",
            "",
        ),
        "ANALISTA_VALIDADOR": getattr(
            ss,
            "analista_validador",
            "",
        ),
        "TIPO_ATENDIMENTO": getattr(
            ss,
            "tipo_atendimento",
            "",
        ),
        "ANORMALIDADES": getattr(
            ss,
            "anormalidade_flags",
            [],
        ),
        "MOTIVO_CHAMADO": getattr(
            ss,
            "motivo_chamado",
            "",
        ),
        "CHECKLIST_TECNICO": getattr(
            ss,
            "checklist_tecnico",
            {},
        ),
        "MATERIAL_UTILIZADO": getattr(
            ss,
            "material_utilizado",
            "",
        ),
        "EQUIPAMENTOS_INSTALADOS": getattr(
            ss,
            "equip_instalados",
            "",
        ),
        "EQUIPAMENTOS_RETIRADOS": getattr(
            ss,
            "equip_retirados",
            "",
        ),
        "TESTES_REALIZADOS": getattr(
            ss,
            "testes_realizados",
            [],
        ),
        "DESCRICAO_ATENDIMENTO": getattr(
            ss,
            "descricao_atendimento",
            "",
        ),
        "OBSERVACOES_PENDENCIAS": getattr(
            ss,
            "observacoes_pendencias",
            "",
        ),
        "NOME_TECNICO": getattr(ss, "nome_tecnico", ""),
        "DOCUMENTO_TECNICO": getattr(ss, "doc_tecnico", ""),
        "TELEFONE_TECNICO": getattr(ss, "tel_tecnico", ""),
        "DATA_HORA_TECNICO": getattr(ss, "dt_tecnico", ""),
        "NOME_CLIENTE_RESPONSAVEL": getattr(
            ss,
            "nome_cliente",
            "",
        ),
        "DOCUMENTO_CLIENTE": getattr(ss, "doc_cliente", ""),
        "TELEFONE_CLIENTE": getattr(ss, "tel_cliente", ""),
        "DATA_HORA_CLIENTE": getattr(ss, "dt_cliente", ""),
        "TOTAL_FOTOS": len(
            getattr(ss, "fotos_chamado", []) or []
        ),
    }

    lines = [
        "&&&RAT_METADATA_BEGIN"
    ]

    for key, value in metadata.items():
        lines.append(
            f"&&&{key}={_clean_metadata_value(value)}"
        )

    lines.append("&&&RAT_METADATA_END")

    return "\n".join(lines)


def _insert_hidden_metadata(
    page: fitz.Page,
    ss,
) -> None:
    """
    Insere os metadados em branco na página 3.

    O texto é inserido antes das fotos. As fotos ficam visualmente
    por cima, mas o conteúdo continua extraível com PyMuPDF.
    """
    metadata_text = _build_hidden_metadata(ss)

    metadata_rect = fitz.Rect(
        28,
        48,
        page.rect.width - 28,
        page.rect.height - 28,
    )

    page.insert_textbox(
        metadata_rect,
        metadata_text,
        fontsize=4,
        fontname="helv",
        color=(1, 1, 1),
        align=0,
        overlay=False,
    )


def _add_photo_pages(doc: fitz.Document, ss) -> None:
    """
    Adiciona páginas de fotos após as páginas principais da RAT.

    Layout:
    - 4 fotos por página;
    - grade 2 x 2;
    - legenda simples abaixo de cada foto;
    - cria quantas páginas forem necessárias.
    """
    photos = getattr(ss, "fotos_chamado", [])

    if not isinstance(photos, (list, tuple)):
        photos = []

    valid_photos = []

    for index, photo in enumerate(photos, start=1):
        raw = _get_photo_bytes(photo)

        if not raw:
            continue

        if isinstance(photo, dict):
            name = str(photo.get("nome") or f"Foto {index}")
        else:
            name = str(getattr(photo, "name", f"Foto {index}"))

        try:
            normalized = _normalize_photo_for_pdf(raw)

            with Image.open(BytesIO(normalized)) as image:
                width, height = image.size

            valid_photos.append(
                {
                    "name": name,
                    "bytes": normalized,
                    "width": width,
                    "height": height,
                }
            )
        except Exception:
            # Uma imagem inválida não interrompe a geração da RAT.
            continue

    # Página A4 em pontos.
    page_width = 595
    page_height = 842

    margin_x = 32
    margin_top = 55
    margin_bottom = 30
    gap_x = 18
    gap_y = 28
    caption_height = 18

    usable_width = page_width - (2 * margin_x) - gap_x
    usable_height = (
        page_height
        - margin_top
        - margin_bottom
        - gap_y
        - (2 * caption_height)
    )

    cell_width = usable_width / 2
    image_height = usable_height / 2

    total_pages = max(
        1,
        (len(valid_photos) + 3) // 4,
    )

    for page_number in range(total_pages):
        page_start = page_number * 4
        page_photos = valid_photos[page_start:page_start + 4]

        page = doc.new_page(
            width=page_width,
            height=page_height,
        )

        # O bloco &&& fica sempre na primeira página de fotos,
        # ou seja, na página 3 do PDF final.
        if page_number == 0:
            _insert_hidden_metadata(page, ss)

        page.insert_text(
            (margin_x, 30),
            "REGISTRO FOTOGRÁFICO DO CHAMADO",
            fontsize=14,
            fontname="helv",
            color=(0, 0, 0),
        )

        for local_index, photo in enumerate(page_photos):
            row = local_index // 2
            column = local_index % 2

            x0 = margin_x + column * (cell_width + gap_x)
            y0 = margin_top + row * (
                image_height + caption_height + gap_y
            )

            cell_rect = fitz.Rect(
                x0,
                y0,
                x0 + cell_width,
                y0 + image_height,
            )

            photo_rect = _fit_rect_keep_aspect(
                photo["width"],
                photo["height"],
                cell_rect,
            )

            # Moldura leve ao redor da área da foto.
            page.draw_rect(
                cell_rect,
                color=(0.65, 0.65, 0.65),
                width=0.6,
            )

            page.insert_image(
                photo_rect,
                stream=photo["bytes"],
                keep_proportion=True,
                overlay=True,
            )

            global_index = page_start + local_index + 1
            caption = f"Foto {global_index:02d} - {photo['name']}"

            caption_rect = fitz.Rect(
                x0,
                y0 + image_height + 3,
                x0 + cell_width,
                y0 + image_height + caption_height,
            )

            page.insert_textbox(
                caption_rect,
                caption,
                fontsize=8,
                fontname="helv",
                color=(0, 0, 0),
                align=1,
            )


# =============== GERAÇÃO DO PDF ===============


def generate_pdf_from_state(ss) -> bytes:
    """
    Abre o template RAT_MAM_UNIFICADA_VF.pdf (2 páginas),
    preenche e retorna os bytes do PDF.
    """
    doc, page1 = open_pdf_template(PDF_BASE_PATH, hint="RAT_MAM_UNIFICADA")

    _fill_page1(page1, ss)

    if doc.page_count >= 2:
        page2 = doc[1]
        _fill_page2(page2, ss)

    # Adiciona as páginas de fotos após as páginas principais.
    _add_photo_pages(doc, ss)

    out = BytesIO()
    doc.save(out)
    doc.close()
    return out.getvalue()


# =============== ENTRYPOINT PARA O APP ===============


def render():
    """
    Função principal chamada pelo app.py
    """
    _init_rat_defaults()

    # UI em abas / passos (modo escuro) – definido em ui_unificado.py
    ui_unificado.render_layout()

    ss = st.session_state

    # Gatilho do botão "Gerar RAT" vindo da UI
    if ss.get("trigger_generate"):
        try:
            pdf_bytes = generate_pdf_from_state(ss)
            st.success("RAT gerada com sucesso! ✅")

            nome_base = (
                ss.num_relatorio
                or ss.num_chamado
                or ss.cliente_razao
                or "RAT_MAM"
            )
            nome_base = (
                str(nome_base)
                .strip()
                .replace(" ", "_")
                .replace("/", "-")
            )

            st.download_button(
                "⬇️ Baixar RAT (PDF)",
                data=pdf_bytes,
                file_name=f"{nome_base}.pdf",
                mime="application/pdf",
            )
        except Exception as e:
            st.error("Falha ao gerar o PDF da RAT.")
            st.exception(e)
        finally:
            ss.trigger_generate = False
