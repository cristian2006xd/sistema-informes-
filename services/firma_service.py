import fitz  # PyMuPDF


def validar_pdf_firmado(ruta_pdf):
    """
    Validación básica institucional:
    detecta estructura real de firma digital en PDF.
    """

    try:
        doc = fitz.open(ruta_pdf)
        metadata = doc.metadata or {}
        doc.close()

        with open(ruta_pdf, "rb") as f:
            contenido = f.read()

        tiene_byte_range = b"/ByteRange" in contenido
        tiene_sig = b"/Type/Sig" in contenido or b"/Type /Sig" in contenido
        tiene_adbe = (
            b"adbe.pkcs7.detached" in contenido or
            b"ETSI.CAdES.detached" in contenido or
            b"ETSI.RFC3161" in contenido
        )

        if tiene_byte_range and (tiene_sig or tiene_adbe):
            return {
                "valido": True,
                "mensaje": "El PDF contiene estructura compatible con firma digital.",
                "firmante": "Firma digital detectada",
                "metadata": metadata
            }

        return {
            "valido": False,
            "mensaje": "No se detectó una firma digital válida en el PDF.",
            "firmante": None,
            "metadata": metadata
        }

    except Exception as e:
        return {
            "valido": False,
            "mensaje": f"Error al validar el PDF: {str(e)}",
            "firmante": None,
            "metadata": {}
        }