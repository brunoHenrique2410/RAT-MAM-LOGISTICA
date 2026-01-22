import fitz
from io import BytesIO
from datetime import datetime
from zoneinfo import ZoneInfo

from common.pdf import open_pdf_template

PDF_PATH = "pdf_templates/RAT_MAM_UNIFICADA_VF.pdf"

def gerar_pdf(ss):
    doc, page1 = open_pdf_template(PDF_PATH)

    # Preencher campos usando ss (session state)
    page1.insert_text((120, 150), ss.cliente)
    page1.insert_text((420, 150), ss.numero_chamado)

    # TODO: completar todos os campos...

    out = BytesIO()
    doc.save(out)
    return out.getvalue()

