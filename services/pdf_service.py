import os
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import cm
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_JUSTIFY
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image
)
from reportlab.lib.styles import ParagraphStyle

# ─── Constantes de página ──────────────────────────────────────────────────────
PAGE_W, PAGE_H = A4
ML = 2.5 * cm   # margen izquierdo
MR = 2.0 * cm   # margen derecho
MT = 3.2 * cm   # margen superior (deja espacio al encabezado)
MB = 2.8 * cm   # margen inferior  (deja espacio al pie)
CW = PAGE_W - ML - MR   # ancho del área de contenido ≈ 16.5 cm

AZUL  = colors.HexColor("#003b73")
NEGRO = colors.black

MESES = [
    "enero","febrero","marzo","abril","mayo","junio",
    "julio","agosto","septiembre","octubre","noviembre","diciembre"
]

# ─── Plantillas de texto fijo por tipo de informe ─────────────────────────────
PLANTILLAS = {
    "A": {
        "asunto": "Revisión de equipo tecnológico disponible para asignación.",
        "antecedentes": (
            "Mediante requerimiento institucional, se solicitó la entrega y configuración "
            "de un equipo de cómputo para <b>{NOMBRES}</b>, con C.I. <b>{CEDULA}</b>, "
            "quien desempeña el cargo de <b>{CARGO}</b> en la <b>{DIRECCION}</b>, a fin "
            "de contar con las herramientas tecnológicas necesarias para el cumplimiento "
            "de sus actividades y responsabilidades institucionales."
        ),
        "desarrollo": [
            "En atención al requerimiento realizado, se efectuó la revisión física y "
            "funcional del equipo tecnológico destinado al personal asignado, verificando "
            "el estado adecuado y funcional del equipo tecnológico.",
            "Como parte del proceso de preparación del equipo, se realizaron las "
            "validaciones necesarias del sistema tecnológico requeridas para el desarrollo "
            "de las actividades laborales.",
            "Se verificó la identificación de los bienes tecnológicos mediante la "
            "validación de sus respectivas etiquetas institucionales y códigos de control interno.",
            "Durante las pruebas y verificaciones efectuadas, se constató que los equipos "
            "presentan un funcionamiento estable y adecuado, cumpliendo con las condiciones "
            "técnicas necesarias para su entrega, asignación y uso dentro de las actividades "
            "institucionales del personal asignado.",
            "Una vez concluidas las verificaciones técnicas y configuraciones "
            "correspondientes, se confirmó que el equipo se encuentra en buenas "
            "condiciones para su utilización.",
        ],
        "conclusiones": [
            "Como resultado de las validaciones efectuadas, se realizó la entrega y "
            "configuración de los bienes tecnológicos a favor de <b>{NOMBRES}</b>, en "
            "su calidad de <b>{CARGO}</b> de la <b>{DIRECCION}</b>, quedando apto "
            "para el desempeño de sus funciones institucionales."
        ]
    },
    "D": {
        "asunto": "Descargo de bien tecnológico.",
        "antecedentes": (
            "Mediante requerimiento institucional, se solicitó la revisión técnica y "
            "documental de un bien tecnológico asociado a <b>{NOMBRES}</b>, con C.I. "
            "<b>{CEDULA}</b>, quien desempeña el cargo de <b>{CARGO}</b> en la "
            "<b>{DIRECCION}</b>, con la finalidad de sustentar el procedimiento de "
            "descargo correspondiente, de acuerdo con las disposiciones administrativas "
            "y de control institucional vigentes."
        ),
        "desarrollo": [
            "En atención al requerimiento realizado, se efectuó el levantamiento de "
            "información técnica y documental del bien objeto de análisis, revisando "
            "los registros institucionales, códigos patrimoniales y demás elementos "
            "de identificación correspondientes.",
            "Durante la inspección se evaluó la condición actual del bien tecnológico, "
            "recopilando los antecedentes necesarios para determinar su situación dentro "
            "del inventario institucional y sustentar el procedimiento administrativo "
            "correspondiente.",
            "Adicionalmente, se documentaron las características relevantes del bien y "
            "su estado de conservación, generando la evidencia técnica requerida para "
            "el trámite de descargo.",
        ],
        "conclusiones": [
            "El análisis efectuado permitió determinar la condición actual del bien "
            "tecnológico y recopilar la información necesaria para sustentar el "
            "procedimiento administrativo correspondiente.",
            "Como resultado de las actividades realizadas, se gestionó el proceso de "
            "descargo del bien tecnológico asociado a <b>{NOMBRES}</b>, en su calidad "
            "de <b>{CARGO}</b> de la <b>{DIRECCION}</b>, de conformidad con la normativa "
            "y procedimientos institucionales vigentes."
        ]
    },
    "RE": {
        "asunto": "Revisión de estado de bien tecnológico.",
        "antecedentes": (
            "Mediante requerimiento institucional, se solicitó la revisión del estado "
            "físico y operativo de un bien tecnológico asignado a <b>{NOMBRES}</b>, con "
            "C.I. <b>{CEDULA}</b>, quien desempeña el cargo de <b>{CARGO}</b> en la "
            "<b>{DIRECCION}</b>, con el propósito de determinar sus condiciones actuales "
            "de uso y conservación dentro de las actividades institucionales."
        ),
        "desarrollo": [
            "En atención al requerimiento realizado, se efectuó una inspección técnica "
            "del bien tecnológico asignado, con el propósito de determinar sus condiciones "
            "físicas, operativas y de conservación.",
            "Durante la revisión se evaluó el estado general del bien, considerando "
            "aspectos relacionados con su utilización, integridad y desempeño dentro "
            "de las actividades institucionales.",
            "Asimismo, se corroboró la información de identificación patrimonial mediante "
            "la revisión de etiquetas institucionales, números de serie y registros de "
            "control correspondientes.",
        ],
        "conclusiones": [
            "La inspección realizada permitió determinar las condiciones físicas y "
            "operativas del bien tecnológico, evidenciando su estado actual para el "
            "desarrollo de las actividades institucionales.",
            "Como resultado de las acciones efectuadas, se registró el estado del bien "
            "tecnológico asignado a <b>{NOMBRES}</b>, en su calidad de <b>{CARGO}</b> "
            "de la <b>{DIRECCION}</b>, para los fines administrativos y de control "
            "institucional correspondientes."
        ]
    },
    "CA": {
        "asunto": "Cambio y actualización de bien tecnológico.",
        "antecedentes": (
            "Mediante requerimiento institucional, se solicitó la ejecución de actividades "
            "de cambio y actualización de un bien tecnológico asignado a <b>{NOMBRES}</b>, "
            "con C.I. <b>{CEDULA}</b>, quien desempeña el cargo de <b>{CARGO}</b> en la "
            "<b>{DIRECCION}</b>, con el fin de optimizar su desempeño y garantizar la "
            "continuidad de las actividades institucionales."
        ),
        "desarrollo": [
            "En atención al requerimiento realizado, se ejecutaron actividades de cambio "
            "y actualización sobre el bien tecnológico asignado, con la finalidad de "
            "mejorar su desempeño y garantizar la continuidad de las labores institucionales.",
            "Como parte del proceso, se realizaron ajustes técnicos, configuraciones y "
            "adecuaciones orientadas a optimizar las condiciones de uso del equipo de "
            "acuerdo con las necesidades identificadas.",
            "Posteriormente, se efectuaron las pruebas operativas necesarias para "
            "garantizar la correcta implementación de las mejoras realizadas y su "
            "disponibilidad para el usuario asignado.",
        ],
        "conclusiones": [
            "Las actividades ejecutadas permitieron optimizar las condiciones de uso y "
            "desempeño del bien tecnológico, asegurando su adecuada utilización dentro "
            "del entorno institucional.",
            "Como resultado de las acciones efectuadas, se realizó la actualización y "
            "configuración del bien tecnológico asignado a <b>{NOMBRES}</b>, en su "
            "calidad de <b>{CARGO}</b> de la <b>{DIRECCION}</b>, quedando disponible "
            "para el cumplimiento de sus funciones institucionales."
        ]
    },
    "I": {
        "asunto": "Instalación de bien tecnológico.",
        "antecedentes": (
            "Mediante requerimiento institucional, se solicitó la instalación y "
            "configuración de un bien tecnológico para <b>{NOMBRES}</b>, con C.I. "
            "<b>{CEDULA}</b>, quien desempeña el cargo de <b>{CARGO}</b> en la "
            "<b>{DIRECCION}</b>, a fin de contar con los recursos tecnológicos necesarios "
            "para el cumplimiento de sus actividades y responsabilidades institucionales."
        ),
        "desarrollo": [
            "En atención al requerimiento realizado, se llevó a cabo la instalación del "
            "bien tecnológico solicitado, considerando los parámetros técnicos y operativos "
            "requeridos para su incorporación al entorno institucional.",
            "Como parte del procedimiento, se efectuaron las configuraciones necesarias "
            "para su puesta en marcha, así como la integración de los recursos asociados "
            "para garantizar su disponibilidad y uso adecuado.",
            "Finalmente, se realizó el registro e identificación del bien mediante la "
            "comprobación de los datos patrimoniales y controles institucionales "
            "correspondientes.",
        ],
        "conclusiones": [
            "Una vez concluido el proceso de instalación, el bien tecnológico quedó "
            "integrado al entorno de trabajo institucional y disponible para su "
            "utilización conforme a los requerimientos del área solicitante.",
            "Como resultado de las actividades realizadas, se efectuó la instalación y "
            "configuración del bien tecnológico a favor de <b>{NOMBRES}</b>, en su "
            "calidad de <b>{CARGO}</b> de la <b>{DIRECCION}</b>, quedando apto para "
            "el desempeño de sus funciones institucionales."
        ]
    },
    "OT": {
        "asunto": "Orden de trabajo de mantenimiento de bien tecnológico.",
        "antecedentes": (
            "Mediante requerimiento institucional, se solicitó la atención técnica de "
            "un bien tecnológico asignado a <b>{NOMBRES}</b>, con C.I. <b>{CEDULA}</b>, "
            "quien desempeña el cargo de <b>{CARGO}</b> en la <b>{DIRECCION}</b>, con "
            "el fin de asegurar el correcto funcionamiento de los recursos tecnológicos "
            "institucionales."
        ),
        "desarrollo": [
            "En atención al requerimiento realizado, se ejecutaron las actividades "
            "técnicas necesarias sobre el bien tecnológico, verificando su estado y "
            "realizando las intervenciones correspondientes.",
            "Durante el proceso se evaluaron las condiciones operativas del equipo, "
            "documentando las acciones realizadas y confirmando la resolución de los "
            "requerimientos identificados.",
        ],
        "conclusiones": [
            "Como resultado de las actividades realizadas, se atendió el requerimiento "
            "técnico del bien tecnológico asignado a <b>{NOMBRES}</b>, en su calidad "
            "de <b>{CARGO}</b> de la <b>{DIRECCION}</b>, quedando operativo para el "
            "cumplimiento de sus funciones institucionales."
        ]
    }
}


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _fmt_fecha(f):
    if not f:
        return "___"
    try:
        if hasattr(f, 'day'):
            return f"{f.day:02d} de {MESES[f.month - 1]} de {f.year}"
        from datetime import datetime
        d = datetime.strptime(str(f), "%Y-%m-%d")
        return f"{d.day:02d} de {MESES[d.month - 1]} de {d.year}"
    except Exception:
        return str(f)


def _sustituir(texto, vars_dict):
    for k, v in vars_dict.items():
        texto = texto.replace(k, str(v) if v else "___")
    return texto


def _img_elemento(ruta_relativa, max_ancho=10 * cm, max_alto=8 * cm):
    if not ruta_relativa:
        return None
    ruta = os.path.join("static", ruta_relativa) if not os.path.isabs(ruta_relativa) else ruta_relativa
    if os.path.exists(ruta):
        img = Image(ruta)
        img._restrictSize(max_ancho, max_alto)
        return img
    return None


def _imagen_centrada(ruta_relativa):
    img = _img_elemento(ruta_relativa)
    if not img:
        return None
    t = Table([[img]], colWidths=[CW])
    t.setStyle(TableStyle([
        ("ALIGN",  (0, 0), (-1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]))
    return t


# ─── Encabezado y pie de página en cada hoja ──────────────────────────────────

def _dibujar_pagina(canvas, config):
    canvas.saveState()

    # ── Encabezado ──────────────────────────────────────────────────────────
    y_linea_sup = PAGE_H - 2.3 * cm

    logo_rep = os.path.join("static", "img", "logo_republica.png")
    if os.path.exists(logo_rep):
        canvas.drawImage(
            logo_rep,
            ML, PAGE_H - 2.1 * cm,
            width=1.6 * cm, height=2.0 * cm,
            preserveAspectRatio=True, mask="auto"
        )
        canvas.setFont("Helvetica-Bold", 5.5)
        canvas.setFillColor(AZUL)
        canvas.drawString(ML + 1.8 * cm, PAGE_H - 0.85 * cm, "REPÚBLICA")
        canvas.drawString(ML + 1.8 * cm, PAGE_H - 1.25 * cm, "DEL ECUADOR")
    else:
        canvas.setFont("Helvetica-Bold", 6.5)
        canvas.setFillColor(AZUL)
        canvas.drawString(ML, PAGE_H - 0.85 * cm, "REPÚBLICA")
        canvas.drawString(ML, PAGE_H - 1.25 * cm, "DEL ECUADOR")

    canvas.setFont("Helvetica-BoldOblique", 8.5)
    canvas.setFillColor(AZUL)
    canvas.drawRightString(
        PAGE_W - MR, PAGE_H - 1.3 * cm,
        "Instituto Nacional de Meteorología e Hidrología - INAMHI"
    )

    canvas.setStrokeColor(AZUL)
    canvas.setLineWidth(0.6)
    canvas.line(ML, y_linea_sup, PAGE_W - MR, y_linea_sup)

    # ── Pie de página ────────────────────────────────────────────────────────
    y_linea_inf = 2.3 * cm
    canvas.setStrokeColor(AZUL)
    canvas.line(ML, y_linea_inf, PAGE_W - MR, y_linea_inf)

    canvas.setFont("Helvetica", 6)
    canvas.setFillColor(NEGRO)
    dir_texto = config.get("footer_direccion", "Dirección: Núñez de Vela N36-15 y Corea")
    tel_texto  = config.get("footer_telefono",  "Teléfono: +593-2 397 1100")
    web_texto  = config.get("footer_web",        "www.inamhi.gob.ec")
    canvas.drawString(ML, 1.95 * cm, f"{dir_texto}    Código postal: 170507 / Quito-Ecuador")
    canvas.drawString(ML, 1.55 * cm, f"{tel_texto}    {web_texto}")

    logo_ec = os.path.join("static", "img", "logo_nuevo_ecuador.png")
    if os.path.exists(logo_ec):
        canvas.drawImage(
            logo_ec,
            PAGE_W - MR - 2.8 * cm, 0.9 * cm,
            width=2.8 * cm, height=1.4 * cm,
            preserveAspectRatio=True, mask="auto"
        )
    else:
        canvas.setFont("Helvetica-Bold", 7)
        canvas.setFillColor(colors.HexColor("#cc3300"))
        canvas.drawRightString(PAGE_W - MR, 1.6 * cm, "EL NUEVO ECUADOR")

    canvas.restoreState()


# ─── Función principal ────────────────────────────────────────────────────────

def generar_pdf_informe(informe, bienes_asignados, fotografias, ruta_salida, config=None):
    config = config or {}
    os.makedirs(os.path.dirname(ruta_salida), exist_ok=True)

    doc = SimpleDocTemplate(
        ruta_salida,
        pagesize=A4,
        leftMargin=ML, rightMargin=MR,
        topMargin=MT, bottomMargin=MB
    )

    # ── Estilos ──────────────────────────────────────────────────────────────
    sTitulo = ParagraphStyle("Titulo",
        fontName="Helvetica-Bold", fontSize=20,
        alignment=TA_CENTER, textColor=NEGRO,
        spaceAfter=3, spaceBefore=4
    )
    sNumero = ParagraphStyle("Numero",
        fontName="Helvetica-Bold", fontSize=12,
        alignment=TA_CENTER, textColor=NEGRO,
        spaceAfter=10
    )
    sCampo = ParagraphStyle("Campo",
        fontName="Helvetica", fontSize=10,
        alignment=TA_LEFT, spaceAfter=4, spaceBefore=1
    )
    sSeccion = ParagraphStyle("Seccion",
        fontName="Helvetica-Bold", fontSize=10,
        alignment=TA_LEFT, spaceAfter=4, spaceBefore=10
    )
    sBody = ParagraphStyle("Body",
        fontName="Helvetica", fontSize=10,
        alignment=TA_JUSTIFY, leading=14,
        spaceAfter=8
    )
    sCaracTitulo = ParagraphStyle("CaracTitulo",
        fontName="Helvetica-Bold", fontSize=11,
        spaceAfter=6, spaceBefore=12
    )
    sBienTipo = ParagraphStyle("BienTipo",
        fontName="Helvetica-Bold", fontSize=10,
        textColor=AZUL, spaceAfter=3, spaceBefore=8
    )
    sBienCampo = ParagraphStyle("BienCampo",
        fontName="Helvetica-Bold", fontSize=10,
        spaceAfter=2, spaceBefore=1
    )
    sEstado = ParagraphStyle("Estado",
        fontName="Helvetica-Bold", fontSize=10,
        alignment=TA_CENTER
    )
    sFirma = ParagraphStyle("Firma",
        fontName="Helvetica", fontSize=10,
        alignment=TA_CENTER, leading=14,
        textColor=AZUL
    )
    sFirmaTitulo = ParagraphStyle("FirmaTitulo",
        fontName="Helvetica-Bold", fontSize=10,
        alignment=TA_CENTER
    )

    # ── Variables de sustitución ─────────────────────────────────────────────
    nombres   = f"{informe.get('nombres','') or ''} {informe.get('apellidos','') or ''}".strip()
    cedula    = informe.get('cedula') or '___'
    cargo     = informe.get('cargo') or '___'
    direccion = informe.get('dependencia') or '___'
    fecha_str = _fmt_fecha(informe.get('fecha_informe'))
    numero    = informe.get('numero_informe') or '___'

    vars_dict = {
        "{NOMBRES}":   nombres,
        "{CEDULA}":    cedula,
        "{CARGO}":     cargo,
        "{DIRECCION}": direccion,
        "{DIRECCIÓN}": direccion,
        "{FECHA}":     fecha_str,
    }

    # ── Plantilla del tipo ───────────────────────────────────────────────────
    codigo_tipo = (informe.get('codigo_tipo') or 'OT').upper().strip()
    plantilla = PLANTILLAS.get(codigo_tipo, PLANTILLAS["OT"])

    # ── Agrupar fotografías ──────────────────────────────────────────────────
    fotos_generales = [f for f in fotografias if not f.get('bien_id')]
    fotos_por_bien  = {}
    for f in fotografias:
        bid = f.get('bien_id')
        if bid:
            fotos_por_bien.setdefault(bid, []).append(f)

    # ── Construcción del documento ───────────────────────────────────────────
    elems = []

    # Título centrado
    elems.append(Paragraph("INFORME TÉCNICO", sTitulo))
    elems.append(Paragraph(numero, sNumero))

    # Asunto y fecha
    elems.append(Paragraph(f"<b>Asunto:</b> {plantilla['asunto']}", sCampo))
    elems.append(Paragraph(f"<b>Fecha:</b> {fecha_str}", sCampo))
    elems.append(Spacer(1, 8))

    # ANTECEDENTES
    elems.append(Paragraph("ANTECEDENTES", sSeccion))
    antec = _sustituir(plantilla.get("antecedentes", ""), vars_dict)
    elems.append(Paragraph(antec, sBody))

    # DESARROLLO
    elems.append(Paragraph("DESARROLLO", sSeccion))
    dev_parrafos = plantilla.get("desarrollo", [])
    split_en = min(2, len(dev_parrafos))

    for i, p in enumerate(dev_parrafos):
        elems.append(Paragraph(_sustituir(p, vars_dict), sBody))
        # Insertar fotos generales después del 2° párrafo del desarrollo
        if i == split_en - 1 and fotos_generales:
            for foto in fotos_generales[:3]:
                img_t = _imagen_centrada(foto.get('ruta_archivo', ''))
                if img_t:
                    elems.append(Spacer(1, 6))
                    elems.append(img_t)
                    elems.append(Spacer(1, 6))

    # CARACTERÍSTICAS POR BIEN
    if bienes_asignados:
        elems.append(Spacer(1, 4))
        elems.append(Paragraph("Características e identificación del bien tecnológico", sCaracTitulo))

        for b in bienes_asignados:
            tipo_nombre = (b.get('tipo') or 'BIEN').upper()
            estado_val  = (b.get('estado_bien') or '').upper()

            # Nombre del tipo subrayado y en azul
            elems.append(Paragraph(f"<u>{tipo_nombre}</u>", sBienTipo))

            # MARCA + ESTADO (en tabla de dos columnas)
            t_marca_estado = Table(
                [[
                    Paragraph(f"<b>MARCA:</b> {b.get('marca') or ''}",  sBienCampo),
                    Paragraph(f"<b>ESTADO: {estado_val}</b>", sEstado)
                ]],
                colWidths=[CW * 0.70, CW * 0.30]
            )
            t_marca_estado.setStyle(TableStyle([
                ("VALIGN",         (0, 0), (-1, -1), "MIDDLE"),
                ("BOX",            (1, 0), (1, 0),   0.8, NEGRO),
                ("LEFTPADDING",    (0, 0), (0, 0),   0),
                ("RIGHTPADDING",   (0, 0), (0, 0),   4),
                ("LEFTPADDING",    (1, 0), (1, 0),   4),
                ("RIGHTPADDING",   (1, 0), (1, 0),   4),
                ("TOPPADDING",     (1, 0), (1, 0),   4),
                ("BOTTOMPADDING",  (1, 0), (1, 0),   4),
            ]))
            elems.append(t_marca_estado)

            # Resto de campos
            elems.append(Paragraph(f"<b>MODELO:</b> {b.get('modelo') or ''}",           sBienCampo))
            elems.append(Paragraph(f"<b>CÓDIGO ESBYE:</b> {b.get('codigo_esbye') or ''}",  sBienCampo))
            elems.append(Paragraph(f"<b>NÚMERO DE SERIE:</b> {b.get('serie') or ''}",     sBienCampo))
            elems.append(Paragraph(f"<b>CÓDIGO ANTERIOR:</b> {b.get('codigo_anterior') or ''}",  sBienCampo))

            # Fotos específicas del bien
            for foto in fotos_por_bien.get(b.get('id'), []):
                img_t = _imagen_centrada(foto.get('ruta_archivo', ''))
                if img_t:
                    elems.append(Spacer(1, 6))
                    elems.append(img_t)
                    elems.append(Spacer(1, 4))

    # CONCLUSIONES
    elems.append(Spacer(1, 4))
    elems.append(Paragraph("CONCLUSIONES", sSeccion))
    for p in plantilla.get("conclusiones", []):
        elems.append(Paragraph(_sustituir(p, vars_dict), sBody))

    # ELABORADO / APROBADO
    elems.append(Spacer(1, 40))

    elab_nombre = config.get("elaborado_nombre") or "______________________________"
    elab_cargo  = config.get("elaborado_cargo")  or "Técnico TICS"
    apro_nombre = config.get("aprobado_nombre")  or "______________________________"
    apro_cargo  = config.get("aprobado_cargo")   or "Responsable / Jefe TICS"

    t_firmas = Table(
        [
            [Paragraph("<b>ELABORADO</b>", sFirmaTitulo),
             Paragraph("<b>APROBADO</b>",  sFirmaTitulo)],
            [Paragraph(f"<br/><br/><br/><br/>{elab_nombre}<br/>{elab_cargo}", sFirma),
             Paragraph(f"<br/><br/><br/><br/>{apro_nombre}<br/>{apro_cargo}", sFirma)],
        ],
        colWidths=[CW / 2, CW / 2],
        rowHeights=[None, 4.2 * cm]
    )
    t_firmas.setStyle(TableStyle([
        ("BOX",         (0, 0), (-1, -1), 0.7, NEGRO),
        ("INNERGRID",   (0, 0), (-1, -1), 0.7, NEGRO),
        ("ALIGN",       (0, 0), (-1, -1), "CENTER"),
        ("VALIGN",      (0, 0), (-1, 0),  "MIDDLE"),
        ("VALIGN",      (0, 1), (-1, 1),  "BOTTOM"),
        ("TOPPADDING",  (0, 0), (-1, 0),  6),
        ("BOTTOMPADDING",(0,0), (-1, 0),  6),
        ("BOTTOMPADDING",(0,1), (-1, 1),  10),
    ]))
    elems.append(t_firmas)

    # ── Build ────────────────────────────────────────────────────────────────
    on_page = lambda c, _: _dibujar_pagina(c, config)
    doc.build(elems, onFirstPage=on_page, onLaterPages=on_page)

    return ruta_salida
