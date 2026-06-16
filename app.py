import os
from datetime import datetime
from functools import wraps

from flask import (
    Flask, render_template, request, redirect,
    url_for, session, flash, jsonify, send_file
)
from flask_cors import CORS
from werkzeug.utils import secure_filename
import mysql.connector
import bcrypt

from config import Config
from services.word_service import generar_word_informe_tecnico

app = Flask(__name__)
app.config.from_object(Config)
app.secret_key = app.config["SECRET_KEY"]

CORS(app)

# =====================================================
# CONEXION MYSQL
# =====================================================

def get_db_connection():
    return mysql.connector.connect(
        host=app.config["MYSQL_HOST"],
        user=app.config["MYSQL_USER"],
        password=app.config["MYSQL_PASSWORD"],
        database=app.config["MYSQL_DB"]
    )

# =====================================================
# MIGRACIONES AL INICIO
# =====================================================

def init_migrations():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # -- configuracion_sistema
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS configuracion_sistema (
                clave VARCHAR(100) PRIMARY KEY,
                valor TEXT,
                descripcion VARCHAR(255),
                fecha_actualizacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    ON UPDATE CURRENT_TIMESTAMP
            )
        """)

        defaults = [
            ("elaborado_nombre",   "TÉCNICO DE TICS",   "Nombre en sección ELABORADO"),
            ("elaborado_cargo",    "TÉCNICO",            "Cargo en sección ELABORADO"),
            ("aprobado_nombre",    "DIRECTOR/A DAF",     "Nombre en sección APROBADO"),
            ("aprobado_cargo",     "DIRECTOR/A",         "Cargo en sección APROBADO"),
            ("footer_direccion",   "Av. América N34-61 y Av. Colón, Quito - Ecuador",
             "Dirección institucional"),
            ("footer_telefono",    "(02) 2261-408",      "Teléfono institucional"),
            ("footer_web",         "www.inamhi.gob.ec",  "Sitio web institucional"),
            ("imagen_encabezado",  "",                   "Imagen del encabezado del informe Word"),
            ("imagen_pie_pagina",  "",                   "Imagen del pie de página del informe Word"),
        ]
        for clave, valor, desc in defaults:
            cursor.execute("""
                INSERT IGNORE INTO configuracion_sistema (clave, valor, descripcion)
                VALUES (%s, %s, %s)
            """, (clave, valor, desc))

        # -- informes_tecnicos
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS informes_tecnicos (
                id INT AUTO_INCREMENT PRIMARY KEY,
                tipo ENUM('RE_ASIGNACION','DESCARGO','RE_ESTADO',
                          'CAMBIO_ACTUALIZACION','INSTALACION') NOT NULL,
                numero_informe VARCHAR(100),
                fecha DATE NOT NULL,
                nombres VARCHAR(200) NOT NULL,
                cedula VARCHAR(20) NOT NULL,
                cargo VARCHAR(150) NOT NULL,
                direccion VARCHAR(250) NOT NULL,
                usuario_id INT,
                ruta_word VARCHAR(400),
                ruta_firmado VARCHAR(400),
                ruta_pdf_otros VARCHAR(400),
                elaborado_nombre VARCHAR(200),
                elaborado_cargo VARCHAR(150),
                aprobado_nombre VARCHAR(200),
                aprobado_cargo VARCHAR(150),
                fecha_generacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        """)
        # Migración: agregar columnas si ya existe la tabla sin ellas
        for col_sql in [
            "ALTER TABLE informes_tecnicos ADD COLUMN elaborado_nombre VARCHAR(200)",
            "ALTER TABLE informes_tecnicos ADD COLUMN elaborado_cargo VARCHAR(150)",
            "ALTER TABLE informes_tecnicos ADD COLUMN aprobado_nombre VARCHAR(200)",
            "ALTER TABLE informes_tecnicos ADD COLUMN aprobado_cargo VARCHAR(150)",
        ]:
            try:
                cursor.execute(col_sql)
            except Exception:
                pass  # columna ya existe

        # -- it_bienes
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS it_bienes (
                id INT AUTO_INCREMENT PRIMARY KEY,
                informe_id INT NOT NULL,
                tipo_equipo VARCHAR(150),
                marca VARCHAR(100),
                modelo VARCHAR(150),
                codigo_esbye VARCHAR(100),
                serie VARCHAR(100),
                codigo_anterior VARCHAR(100),
                estado_bien VARCHAR(100)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        """)

        # -- it_fotos
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS it_fotos (
                id INT AUTO_INCREMENT PRIMARY KEY,
                informe_id INT NOT NULL,
                bien_idx INT DEFAULT -1,
                nombre_archivo VARCHAR(250),
                ruta_archivo VARCHAR(400)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        """)

        # -- seed CONSULTA role if not present
        try:
            cursor.execute("""
                INSERT IGNORE INTO roles (nombre, descripcion)
                VALUES ('CONSULTA', 'Solo puede visualizar y descargar informes')
            """)
        except Exception:
            pass

        # Extend ENUM to include OTROS
        try:
            cursor.execute("""
                ALTER TABLE informes_tecnicos
                MODIFY COLUMN tipo ENUM('RE_ASIGNACION','DESCARGO','RE_ESTADO',
                                        'CAMBIO_ACTUALIZACION','INSTALACION','OTROS') NOT NULL
            """)
        except Exception:
            pass

        # Columna ruta_pdf_otros para informes tipo OTROS
        try:
            cursor.execute("""
                ALTER TABLE informes_tecnicos
                ADD COLUMN ruta_pdf_otros VARCHAR(400) DEFAULT NULL
            """)
        except Exception:
            pass

        conn.commit()
        cursor.close()
        conn.close()

    except Exception as e:
        print(f"[init_migrations] {e}")

# =====================================================
# AUDITORIA
# =====================================================

def registrar_auditoria(modulo, accion, detalle=None):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO auditoria (usuario_id, usuario, modulo, accion, detalle, ip)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (
            session.get("usuario_id"),
            session.get("usuario"),
            modulo, accion, detalle,
            request.remote_addr
        ))
        conn.commit()
        cursor.close()
        conn.close()
    except Exception as e:
        print(f"[auditoria] {e}")

# =====================================================
# ROL DECORATOR
# =====================================================

def requiere_roles(*roles_permitidos):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if "usuario_id" not in session:
                return redirect(url_for("login"))
            if session.get("rol") not in roles_permitidos:
                flash("No tiene permisos para acceder a este módulo.", "danger")
                return redirect(url_for("dashboard"))
            return f(*args, **kwargs)
        return decorated_function
    return decorator

# =====================================================
# INICIO / LOGIN / LOGOUT
# =====================================================

@app.route("/")
def inicio():
    return redirect(url_for("login"))


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        usuario  = request.form.get("usuario")
        password = request.form.get("password")

        conn   = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("""
            SELECT u.*, r.nombre AS rol
            FROM usuarios u
            INNER JOIN roles r ON u.rol_id = r.id
            WHERE u.usuario = %s AND u.estado = 'ACTIVO'
        """, (usuario,))
        user = cursor.fetchone()
        cursor.close()
        conn.close()

        if user and bcrypt.checkpw(
            password.encode("utf-8"),
            user["password"].encode("utf-8")
        ):
            session["usuario_id"]       = user["id"]
            session["usuario"]          = user["usuario"]
            session["nombres"]          = user["nombres"]
            session["rol"]              = user["rol"]
            session["show_report_modal"] = (user["rol"] == "TECNICO")
            return redirect(url_for("dashboard"))

        flash("Usuario o contraseña incorrectos", "danger")

    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

# =====================================================
# DASHBOARD
# =====================================================

@app.route("/dashboard")
def dashboard():
    if "usuario_id" not in session:
        return redirect(url_for("login"))

    show_modal = session.pop("show_report_modal", False)

    conn   = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("SELECT COUNT(*) total FROM informes_tecnicos")
    total_informes = cursor.fetchone()["total"]

    cursor.execute("""
        SELECT COUNT(*) total FROM informes_tecnicos
        WHERE MONTH(fecha_generacion)=MONTH(CURDATE())
        AND YEAR(fecha_generacion)=YEAR(CURDATE())
    """)
    total_este_mes = cursor.fetchone()["total"]

    cursor.execute("""
        SELECT tipo, COUNT(*) total
        FROM informes_tecnicos
        GROUP BY tipo
    """)
    por_tipo_raw = cursor.fetchall()

    cursor.execute("SELECT COUNT(*) total FROM usuarios")
    total_usuarios = cursor.fetchone()["total"]

    cursor.execute("SELECT COUNT(*) total FROM auditoria")
    total_auditorias = cursor.fetchone()["total"]

    # Últimos 6 meses
    cursor.execute("""
        SELECT DATE_FORMAT(fecha_generacion,'%Y-%m') mes, COUNT(*) total
        FROM informes_tecnicos
        WHERE fecha_generacion >= DATE_SUB(CURDATE(), INTERVAL 6 MONTH)
        GROUP BY mes
        ORDER BY mes
    """)
    por_mes = cursor.fetchall()

    cursor.execute("""
        SELECT id, numero_informe, tipo, nombres, fecha_generacion
        FROM informes_tecnicos
        ORDER BY fecha_generacion DESC
        LIMIT 4
    """)
    ultimos_informes = cursor.fetchall()

    cursor.execute("""
        SELECT COUNT(*) total FROM informes_tecnicos
        WHERE DATE(fecha_generacion) = CURDATE()
    """)
    total_hoy = cursor.fetchone()["total"]

    cursor.close()
    conn.close()

    tipo_labels = {
        "RE_ASIGNACION":       "Revisión Asignación",
        "DESCARGO":            "Descargo",
        "RE_ESTADO":           "Revisión Estado",
        "CAMBIO_ACTUALIZACION":"Cambio / Actualiz.",
        "INSTALACION":         "Instalación",
    }
    grafico_tipo = [{"tipo": tipo_labels.get(r["tipo"], r["tipo"]), "total": r["total"]} for r in por_tipo_raw]
    grafico_mes  = por_mes

    return render_template(
        "dashboard.html",
        show_modal=show_modal,
        total_informes=total_informes,
        total_este_mes=total_este_mes,
        total_usuarios=total_usuarios,
        total_auditorias=total_auditorias,
        total_hoy=total_hoy,
        grafico_tipo=grafico_tipo,
        grafico_mes=grafico_mes,
        ultimos_informes=ultimos_informes,
    )

# =====================================================
# HELPER COMPARTIDO — PROCESAR INFORME
# =====================================================

CARPETA_FOTOS = os.path.join("static", "uploads", "informes_tecnicos")
CARPETA_WORD  = os.path.join("static", "uploads", "word")


def _get_config():
    conn   = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT clave, valor FROM configuracion_sistema")
    config = {r["clave"]: r["valor"] for r in cursor.fetchall()}
    cursor.close()
    conn.close()
    return config


TIPO_ROUTE = {
    "RE_ASIGNACION":       "form_revision_asignacion",
    "DESCARGO":            "form_descargo",
    "RE_ESTADO":           "form_revision_estado",
    "CAMBIO_ACTUALIZACION":"form_cambio_actualizacion",
    "INSTALACION":         "form_instalacion",
}

def _procesar_informe(tipo):
    nombres   = request.form.get("nombres", "").strip()
    cedula    = request.form.get("cedula",  "").strip()
    cargo     = request.form.get("cargo",   "").strip()
    direccion = request.form.get("direccion", "").strip()
    fecha     = request.form.get("fecha", "")
    elab_nombre = request.form.get("elaborado_nombre", "").strip() or None
    elab_cargo  = request.form.get("elaborado_cargo",  "").strip() or None
    apro_nombre = request.form.get("aprobado_nombre",  "").strip() or None
    apro_cargo  = request.form.get("aprobado_cargo",   "").strip() or None

    tipo_equipo_l    = request.form.getlist("tipo_equipo[]")
    marca_l          = request.form.getlist("marca[]")
    modelo_l         = request.form.getlist("modelo[]")
    codigo_esbye_l   = request.form.getlist("codigo_esbye[]")
    serie_l          = request.form.getlist("serie[]")
    codigo_anterior_l= request.form.getlist("codigo_anterior[]")
    estado_bien_l    = request.form.getlist("estado_bien[]")

    n = len(marca_l)
    bienes = []
    for i in range(n):
        bienes.append({
            "tipo_equipo":    tipo_equipo_l[i]     if i < len(tipo_equipo_l)     else "",
            "marca":          marca_l[i],
            "modelo":         modelo_l[i]           if i < len(modelo_l)           else "",
            "codigo_esbye":   codigo_esbye_l[i]     if i < len(codigo_esbye_l)     else "",
            "serie":          serie_l[i]             if i < len(serie_l)             else "",
            "codigo_anterior":codigo_anterior_l[i]  if i < len(codigo_anterior_l)  else "",
            "estado_bien":    estado_bien_l[i]       if i < len(estado_bien_l)       else "",
        })

    os.makedirs(CARPETA_FOTOS, exist_ok=True)

    def _guardar_foto(foto):
        nombre = secure_filename(foto.filename)
        nombre_final = f"it_{tipo.lower()}_{datetime.now().strftime('%H%M%S%f')}_{nombre}"
        ruta_fisica = os.path.join(CARPETA_FOTOS, nombre_final)
        foto.save(ruta_fisica)
        return f"uploads/informes_tecnicos/{nombre_final}"

    if tipo in ("RE_ASIGNACION", "DESCARGO", "RE_ESTADO", "CAMBIO_ACTUALIZACION", "INSTALACION"):
        fotos_generales = [_guardar_foto(f) for f in request.files.getlist("fotos_grupo_1[]") if f and f.filename]
        fotos_grupo_2   = [_guardar_foto(f) for f in request.files.getlist("fotos_grupo_2[]") if f and f.filename]
    else:
        fotos_generales = [_guardar_foto(f) for f in request.files.getlist("fotos_generales[]") if f and f.filename]
        fotos_grupo_2   = []

    fotos_por_bien = {}
    for i in range(n):
        fotos_por_bien[i] = []
        for foto in request.files.getlist(f"fotos_bien_{i}[]"):
            if foto and foto.filename:
                fotos_por_bien[i].append(_guardar_foto(foto))

    conn   = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        anio  = datetime.now().year
        codigo_map = {
            "RE_ASIGNACION":       "A",
            "DESCARGO":            "D",
            "RE_ESTADO":           "RE",
            "CAMBIO_ACTUALIZACION":"CA",
            "INSTALACION":         "I",
        }
        cursor.execute("""
            SELECT COUNT(*) total FROM informes_tecnicos
            WHERE YEAR(fecha_generacion) = %s
        """, (anio,))
        consecutivo = cursor.fetchone()["total"] + 1
        numero = f"INAMHI-DAF-UTICS-{anio}-{str(consecutivo).zfill(3)}-IT-{codigo_map[tipo]}"

        cursor.execute("""
            INSERT INTO informes_tecnicos
                (tipo, numero_informe, fecha, nombres, cedula, cargo, direccion, usuario_id,
                 elaborado_nombre, elaborado_cargo, aprobado_nombre, aprobado_cargo)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (tipo, numero, fecha, nombres, cedula, cargo, direccion, session["usuario_id"],
              elab_nombre, elab_cargo, apro_nombre, apro_cargo))
        informe_id = cursor.lastrowid

        for b in bienes:
            cursor.execute("""
                INSERT INTO it_bienes
                    (informe_id, tipo_equipo, marca, modelo, codigo_esbye, serie, codigo_anterior, estado_bien)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
            """, (informe_id, b["tipo_equipo"], b["marca"], b["modelo"],
                  b["codigo_esbye"], b["serie"], b["codigo_anterior"], b["estado_bien"]))

        for ruta in fotos_generales:
            cursor.execute("""
                INSERT INTO it_fotos (informe_id, bien_idx, nombre_archivo, ruta_archivo)
                VALUES (%s, -1, %s, %s)
            """, (informe_id, os.path.basename(ruta), ruta))

        for ruta in fotos_grupo_2:
            cursor.execute("""
                INSERT INTO it_fotos (informe_id, bien_idx, nombre_archivo, ruta_archivo)
                VALUES (%s, -2, %s, %s)
            """, (informe_id, os.path.basename(ruta), ruta))

        for i, rutas in fotos_por_bien.items():
            for ruta in rutas:
                cursor.execute("""
                    INSERT INTO it_fotos (informe_id, bien_idx, nombre_archivo, ruta_archivo)
                    VALUES (%s, %s, %s, %s)
                """, (informe_id, i, os.path.basename(ruta), ruta))

        # Config base + override con valores del formulario
        cursor.execute("SELECT clave, valor FROM configuracion_sistema")
        config = {r["clave"]: r["valor"] for r in cursor.fetchall()}
        for key in ("elaborado_nombre", "elaborado_cargo",
                    "aprobado_nombre", "aprobado_cargo"):
            val = request.form.get(key, "").strip()
            if val:
                config[key] = val

        # Generar Word
        os.makedirs(CARPETA_WORD, exist_ok=True)
        nombre_word = f"{numero}.docx"
        ruta_word   = os.path.join(CARPETA_WORD, nombre_word)

        generar_word_informe_tecnico(
            tipo=tipo,
            fecha=fecha,
            nombres=nombres,
            cedula=cedula,
            cargo=cargo,
            direccion=direccion,
            bienes=bienes,
            fotos_generales=fotos_generales,
            fotos_por_bien=fotos_por_bien,
            fotos_grupo_2=fotos_grupo_2,
            numero_informe=numero,
            ruta_salida=ruta_word,
            config=config,
        )

        cursor.execute("""
            UPDATE informes_tecnicos SET ruta_word = %s WHERE id = %s
        """, (f"uploads/word/{nombre_word}", informe_id))

        conn.commit()

        registrar_auditoria(
            "Informes",
            f"Generar {tipo}",
            f"Informe {numero} generado"
        )

        if request.headers.get("Accept") == "application/json":
            return jsonify({"ok": True, "id": informe_id})
        return send_file(ruta_word, as_attachment=True, download_name=nombre_word)

    except Exception as e:
        conn.rollback()
        if request.headers.get("Accept") == "application/json":
            return jsonify({"ok": False, "error": str(e)}), 500
        flash(f"Error al generar informe: {str(e)}", "danger")
        return redirect(url_for(TIPO_ROUTE[tipo]))

    finally:
        cursor.close()
        conn.close()

TIPO_TEMPLATES = {
    "RE_ASIGNACION":       "form_re_asignacion.html",
    "DESCARGO":            "form_descargo.html",
    "RE_ESTADO":           "form_re_estado.html",
    "CAMBIO_ACTUALIZACION":"form_cambio_actualizacion.html",
    "INSTALACION":         "form_instalacion.html",
}

def _procesar_edicion_informe(informe_id):
    """Actualiza un informe existente y regenera el Word."""
    conn   = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("SELECT * FROM informes_tecnicos WHERE id = %s", (informe_id,))
        informe_actual = cursor.fetchone()
        if not informe_actual:
            flash("Informe no encontrado.", "danger")
            return redirect(url_for("historial"))

        tipo   = informe_actual["tipo"]
        numero = informe_actual["numero_informe"]

        nombres   = request.form.get("nombres",   "").strip()
        cedula    = request.form.get("cedula",     "").strip()
        cargo     = request.form.get("cargo",      "").strip()
        direccion = request.form.get("direccion",  "").strip()
        fecha     = request.form.get("fecha",      "")

        tipo_equipo_l     = request.form.getlist("tipo_equipo[]")
        marca_l           = request.form.getlist("marca[]")
        modelo_l          = request.form.getlist("modelo[]")
        codigo_esbye_l    = request.form.getlist("codigo_esbye[]")
        serie_l           = request.form.getlist("serie[]")
        codigo_anterior_l = request.form.getlist("codigo_anterior[]")
        estado_bien_l     = request.form.getlist("estado_bien[]")

        n = len(marca_l)
        bienes = []
        for i in range(n):
            bienes.append({
                "tipo_equipo":     tipo_equipo_l[i]     if i < len(tipo_equipo_l)     else "",
                "marca":           marca_l[i],
                "modelo":          modelo_l[i]           if i < len(modelo_l)           else "",
                "codigo_esbye":    codigo_esbye_l[i]     if i < len(codigo_esbye_l)     else "",
                "serie":           serie_l[i]             if i < len(serie_l)             else "",
                "codigo_anterior": codigo_anterior_l[i]  if i < len(codigo_anterior_l)  else "",
                "estado_bien":     estado_bien_l[i]       if i < len(estado_bien_l)       else "",
            })

        os.makedirs(CARPETA_FOTOS, exist_ok=True)

        def _guardar_foto(foto):
            nombre = secure_filename(foto.filename)
            nombre_final = f"it_edit_{datetime.now().strftime('%H%M%S%f')}_{nombre}"
            foto.save(os.path.join(CARPETA_FOTOS, nombre_final))
            return f"uploads/informes_tecnicos/{nombre_final}"

        if tipo in ("RE_ASIGNACION", "DESCARGO"):
            fotos_generales_nuevas = [_guardar_foto(f) for f in request.files.getlist("fotos_grupo_1[]") if f and f.filename]
            fotos_grupo_2_nuevas   = [_guardar_foto(f) for f in request.files.getlist("fotos_grupo_2[]") if f and f.filename]
        else:
            fotos_generales_nuevas = [_guardar_foto(f) for f in request.files.getlist("fotos_generales[]") if f and f.filename]
            fotos_grupo_2_nuevas   = []
        fotos_por_bien = {}
        for i in range(n):
            fotos_por_bien[i] = [_guardar_foto(f) for f in request.files.getlist(f"fotos_bien_{i}[]") if f and f.filename]

        # Actualizar campos principales
        cursor.execute("""
            UPDATE informes_tecnicos
            SET fecha=%s, nombres=%s, cedula=%s, cargo=%s, direccion=%s
            WHERE id=%s
        """, (fecha, nombres, cedula, cargo, direccion, informe_id))

        # Reemplazar bienes
        cursor.execute("DELETE FROM it_bienes WHERE informe_id = %s", (informe_id,))
        for b in bienes:
            cursor.execute("""
                INSERT INTO it_bienes
                    (informe_id, tipo_equipo, marca, modelo, codigo_esbye, serie, codigo_anterior, estado_bien)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
            """, (informe_id, b["tipo_equipo"], b["marca"], b["modelo"],
                  b["codigo_esbye"], b["serie"], b["codigo_anterior"], b["estado_bien"]))

        # Fotos generales: reemplazar solo si se subieron nuevas
        if fotos_generales_nuevas:
            cursor.execute("DELETE FROM it_fotos WHERE informe_id=%s AND bien_idx=-1", (informe_id,))
            for ruta in fotos_generales_nuevas:
                cursor.execute("""
                    INSERT INTO it_fotos (informe_id, bien_idx, nombre_archivo, ruta_archivo)
                    VALUES (%s,-1,%s,%s)
                """, (informe_id, os.path.basename(ruta), ruta))

        if fotos_grupo_2_nuevas:
            cursor.execute("DELETE FROM it_fotos WHERE informe_id=%s AND bien_idx=-2", (informe_id,))
            for ruta in fotos_grupo_2_nuevas:
                cursor.execute("""
                    INSERT INTO it_fotos (informe_id, bien_idx, nombre_archivo, ruta_archivo)
                    VALUES (%s,-2,%s,%s)
                """, (informe_id, os.path.basename(ruta), ruta))

        # Fotos por bien: reemplazar solo las que tienen nuevas subidas
        for i, rutas in fotos_por_bien.items():
            if rutas:
                cursor.execute("DELETE FROM it_fotos WHERE informe_id=%s AND bien_idx=%s", (informe_id, i))
                for ruta in rutas:
                    cursor.execute("""
                        INSERT INTO it_fotos (informe_id, bien_idx, nombre_archivo, ruta_archivo)
                        VALUES (%s,%s,%s,%s)
                    """, (informe_id, i, os.path.basename(ruta), ruta))

        # Config + override firma
        cursor.execute("SELECT clave, valor FROM configuracion_sistema")
        config = {r["clave"]: r["valor"] for r in cursor.fetchall()}
        elab_n = request.form.get("elaborado_nombre", "").strip() or None
        elab_c = request.form.get("elaborado_cargo",  "").strip() or None
        apro_n = request.form.get("aprobado_nombre",  "").strip() or None
        apro_c = request.form.get("aprobado_cargo",   "").strip() or None

        # Guardar por informe
        cursor.execute("""
            UPDATE informes_tecnicos
            SET elaborado_nombre=%s, elaborado_cargo=%s,
                aprobado_nombre=%s,  aprobado_cargo=%s
            WHERE id=%s
        """, (elab_n, elab_c, apro_n, apro_c, informe_id))

        # Actualizar config global solo si se proporcionaron valores
        for key, val in (("elaborado_nombre", elab_n), ("elaborado_cargo", elab_c),
                         ("aprobado_nombre",  apro_n), ("aprobado_cargo",  apro_c)):
            if val:
                config[key] = val
                cursor.execute("""
                    INSERT INTO configuracion_sistema (clave, valor, descripcion)
                    VALUES (%s, %s, %s)
                    ON DUPLICATE KEY UPDATE valor = %s
                """, (key, val, key, val))

        # Recuperar fotos actuales para regenerar
        cursor.execute("SELECT bien_idx, ruta_archivo FROM it_fotos WHERE informe_id=%s ORDER BY id", (informe_id,))
        todas_fotos = cursor.fetchall()
        fotos_gen_final     = [r["ruta_archivo"] for r in todas_fotos if r["bien_idx"] == -1]
        fotos_grupo_2_final = [r["ruta_archivo"] for r in todas_fotos if r["bien_idx"] == -2]
        fotos_bien_final = {}
        for r in todas_fotos:
            if r["bien_idx"] >= 0:
                fotos_bien_final.setdefault(r["bien_idx"], []).append(r["ruta_archivo"])

        # Regenerar Word
        os.makedirs(CARPETA_WORD, exist_ok=True)
        nombre_word = f"{numero}.docx"
        ruta_word   = os.path.join(CARPETA_WORD, nombre_word)

        generar_word_informe_tecnico(
            tipo=tipo, fecha=fecha, nombres=nombres, cedula=cedula,
            cargo=cargo, direccion=direccion, bienes=bienes,
            fotos_generales=fotos_gen_final, fotos_por_bien=fotos_bien_final,
            fotos_grupo_2=fotos_grupo_2_final,
            numero_informe=numero, ruta_salida=ruta_word, config=config,
        )

        cursor.execute("UPDATE informes_tecnicos SET ruta_word=%s WHERE id=%s",
                       (f"uploads/word/{nombre_word}", informe_id))
        conn.commit()

        registrar_auditoria("Informes", f"Editar {tipo}", f"Informe {numero} editado")
        flash("Informe actualizado. El Word ha sido regenerado.", "success")
        return redirect(url_for("historial"))

    except Exception as e:
        conn.rollback()
        flash(f"Error al actualizar informe: {str(e)}", "danger")
        return redirect(url_for("historial"))
    finally:
        cursor.close()
        conn.close()

# =====================================================
# FORMULARIOS DE INFORME
# =====================================================

@app.route("/informe/revision-asignacion")
@requiere_roles("ADMINISTRADOR", "TECNICO")
def form_revision_asignacion():
    return render_template("form_re_asignacion.html",
                           today=datetime.now().strftime("%Y-%m-%d"),
                           config=_get_config())


@app.route("/informe/revision-asignacion/generar", methods=["POST"])
@requiere_roles("ADMINISTRADOR", "TECNICO")
def generar_revision_asignacion():
    return _procesar_informe("RE_ASIGNACION")


@app.route("/informe/descargo")
@requiere_roles("ADMINISTRADOR", "TECNICO")
def form_descargo():
    return render_template("form_descargo.html",
                           today=datetime.now().strftime("%Y-%m-%d"),
                           config=_get_config())


@app.route("/informe/descargo/generar", methods=["POST"])
@requiere_roles("ADMINISTRADOR", "TECNICO")
def generar_descargo():
    return _procesar_informe("DESCARGO")


@app.route("/informe/revision-estado")
@requiere_roles("ADMINISTRADOR", "TECNICO")
def form_revision_estado():
    return render_template("form_re_estado.html",
                           today=datetime.now().strftime("%Y-%m-%d"),
                           config=_get_config())


@app.route("/informe/revision-estado/generar", methods=["POST"])
@requiere_roles("ADMINISTRADOR", "TECNICO")
def generar_revision_estado():
    return _procesar_informe("RE_ESTADO")


@app.route("/informe/cambio-actualizacion")
@requiere_roles("ADMINISTRADOR", "TECNICO")
def form_cambio_actualizacion():
    return render_template("form_cambio_actualizacion.html",
                           today=datetime.now().strftime("%Y-%m-%d"),
                           config=_get_config())


@app.route("/informe/cambio-actualizacion/generar", methods=["POST"])
@requiere_roles("ADMINISTRADOR", "TECNICO")
def generar_cambio_actualizacion():
    return _procesar_informe("CAMBIO_ACTUALIZACION")


@app.route("/informe/instalacion")
@requiere_roles("ADMINISTRADOR", "TECNICO")
def form_instalacion():
    return render_template("form_instalacion.html",
                           today=datetime.now().strftime("%Y-%m-%d"),
                           config=_get_config())


@app.route("/informe/instalacion/generar", methods=["POST"])
@requiere_roles("ADMINISTRADOR", "TECNICO")
def generar_instalacion():
    return _procesar_informe("INSTALACION")


# ── Informe tipo OTROS ────────────────────────────────────────────────────────

def _siguiente_numero_informe():
    """Devuelve el número correlativo que se asignará al próximo informe."""
    try:
        conn   = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        anio   = datetime.now().year
        cursor.execute(
            "SELECT COUNT(*) total FROM informes_tecnicos WHERE YEAR(fecha_generacion) = %s",
            (anio,)
        )
        total = cursor.fetchone()["total"]
        cursor.close()
        conn.close()
        return f"INAMHI-DAF-UTICS-{anio}-{str(total + 1).zfill(3)}-IT-O"
    except Exception:
        return "INAMHI-DAF-UTICS-????-000-IT-O"


@app.route("/informe/otros")
@requiere_roles("ADMINISTRADOR", "TECNICO")
def form_otros():
    return render_template(
        "form_otros.html",
        today=datetime.now().strftime("%Y-%m-%d"),
        numero_preview=_siguiente_numero_informe(),
        config=_get_config()
    )


@app.route("/informe/otros/generar", methods=["POST"])
@requiere_roles("ADMINISTRADOR", "TECNICO")
def generar_otros():
    fecha    = request.form.get("fecha", "").strip()
    nombres  = request.form.get("nombres", "").strip().upper()
    cedula   = request.form.get("cedula", "").strip()
    cargo    = request.form.get("cargo", "").strip().upper()
    direccion = request.form.get("direccion", "").strip().upper()
    archivo  = request.files.get("pdf_otros")

    if not all([fecha, nombres, cedula, cargo, direccion]):
        flash("Todos los campos son obligatorios.", "danger")
        return redirect(url_for("form_otros"))
    if not archivo or not archivo.filename:
        flash("Debe adjuntar un archivo PDF.", "danger")
        return redirect(url_for("form_otros"))

    ext = os.path.splitext(secure_filename(archivo.filename))[1].lower()
    if ext not in (".pdf",):
        flash("Solo se aceptan archivos PDF.", "danger")
        return redirect(url_for("form_otros"))

    conn   = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        anio        = datetime.now().year
        cursor.execute(
            "SELECT COUNT(*) total FROM informes_tecnicos WHERE YEAR(fecha_generacion) = %s",
            (anio,)
        )
        consecutivo = cursor.fetchone()["total"] + 1
        numero      = f"INAMHI-DAF-UTICS-{anio}-{str(consecutivo).zfill(3)}-IT-O"

        # Guardar PDF
        carpeta = os.path.join("static", "uploads", "otros")
        os.makedirs(carpeta, exist_ok=True)
        nombre_archivo = f"otros_{int(datetime.now().timestamp()*1000)}{ext}"
        ruta_pdf = os.path.join(carpeta, nombre_archivo).replace("\\", "/")
        archivo.save(ruta_pdf)

        cursor.execute("""
            INSERT INTO informes_tecnicos
                (tipo, numero_informe, fecha, nombres, cedula, cargo, direccion,
                 usuario_id, ruta_pdf_otros)
            VALUES ('OTROS', %s, %s, %s, %s, %s, %s, %s, %s)
        """, (numero, fecha, nombres, cedula, cargo, direccion,
              session["usuario_id"], ruta_pdf))
        conn.commit()

        registrar_auditoria("Informes", "Subir OTROS",
                            f"Informe {numero} — {nombres}")

        # Calcular el siguiente número para actualizar el preview
        cursor.execute(
            "SELECT COUNT(*) total FROM informes_tecnicos WHERE YEAR(fecha_generacion) = %s",
            (anio,)
        )
        total_nuevo = cursor.fetchone()["total"]
        siguiente   = f"INAMHI-DAF-UTICS-{anio}-{str(total_nuevo + 1).zfill(3)}-IT-O"

        if request.headers.get("Accept") == "application/json":
            cursor.close(); conn.close()
            return jsonify(ok=True, numero=numero, siguiente=siguiente)

        flash(f"Informe registrado correctamente con código {numero}.", "success")
    except Exception as e:
        conn.rollback()
        if request.headers.get("Accept") == "application/json":
            cursor.close(); conn.close()
            return jsonify(ok=False, error=str(e))
        flash(f"Error al registrar el informe: {e}", "danger")
    finally:
        try: cursor.close(); conn.close()
        except Exception: pass

    return redirect(url_for("form_otros"))


# ── Descarga de PDF tipo OTROS ───────────────────────────────────────────────

@app.route("/historial/<int:informe_id>/descargar-otros")
@requiere_roles("ADMINISTRADOR", "TECNICO", "CONSULTA")
def descargar_otros(informe_id):
    conn   = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT ruta_pdf_otros, numero_informe FROM informes_tecnicos WHERE id = %s",
                   (informe_id,))
    row = cursor.fetchone()
    cursor.close()
    conn.close()
    if not row or not row["ruta_pdf_otros"]:
        flash("Archivo no encontrado.", "danger")
        return redirect(url_for("historial"))
    return send_file(row["ruta_pdf_otros"], as_attachment=True,
                     download_name=f"{row['numero_informe']}.pdf")


# ── Edición de informes (solo ADMINISTRADOR) ──────────────────────────────────

@app.route("/historial/<int:informe_id>/editar")
@requiere_roles("ADMINISTRADOR")
def editar_informe(informe_id):
    conn   = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM informes_tecnicos WHERE id = %s", (informe_id,))
    informe = cursor.fetchone()
    if not informe:
        flash("Informe no encontrado.", "danger")
        cursor.close()
        conn.close()
        return redirect(url_for("historial"))
    cursor.execute("SELECT * FROM it_bienes WHERE informe_id = %s ORDER BY id", (informe_id,))
    bienes = cursor.fetchall()
    cursor.execute("SELECT * FROM it_fotos WHERE informe_id = %s ORDER BY id", (informe_id,))
    fotos_all = cursor.fetchall()
    cursor.close()
    conn.close()

    fotos_grupo1 = [f for f in fotos_all if f["bien_idx"] == -1]
    fotos_grupo2 = [f for f in fotos_all if f["bien_idx"] == -2]
    fotos_por_bien = {}
    for f in fotos_all:
        if f["bien_idx"] >= 0:
            fotos_por_bien.setdefault(f["bien_idx"], []).append(f)

    # Convertir fecha a string para el input[type=date]
    if informe.get("fecha"):
        informe["fecha"] = str(informe["fecha"])

    config = _get_config()
    for key in ("elaborado_nombre", "elaborado_cargo", "aprobado_nombre", "aprobado_cargo"):
        if informe.get(key):
            config[key] = informe[key]

    tmpl = TIPO_TEMPLATES.get(informe["tipo"], "form_re_asignacion.html")
    return render_template(tmpl,
                           today=informe["fecha"],
                           config=config,
                           informe=informe,
                           bienes=bienes,
                           fotos_grupo1=fotos_grupo1,
                           fotos_grupo2=fotos_grupo2,
                           fotos_por_bien=fotos_por_bien,
                           modo_edicion=True,
                           informe_id=informe_id)


@app.route("/historial/<int:informe_id>/editar/guardar", methods=["POST"])
@requiere_roles("ADMINISTRADOR")
def guardar_edicion_informe(informe_id):
    return _procesar_edicion_informe(informe_id)

# =====================================================
# HISTORIAL
# =====================================================

@app.route("/historial")
@requiere_roles("ADMINISTRADOR", "CONSULTA")
def historial():
    conn   = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("""
        SELECT
            it.id,
            it.tipo,
            it.numero_informe,
            it.fecha,
            it.nombres,
            it.cargo,
            it.ruta_word,
            it.ruta_firmado,
            it.ruta_pdf_otros,
            it.fecha_generacion,
            u.usuario AS usuario_creador
        FROM informes_tecnicos it
        LEFT JOIN usuarios u ON it.usuario_id = u.id
        ORDER BY it.fecha_generacion DESC
    """)
    registros = cursor.fetchall()
    cursor.close()
    conn.close()

    if session.get("rol") == "CONSULTA":
        registros = [r for r in registros if r.get("ruta_firmado")]

    return render_template("historial.html", registros=registros)


@app.route("/historial/subir-firmado", methods=["POST"])
@requiere_roles("ADMINISTRADOR")
def subir_firmado():
    informe_id = request.form.get("informe_id", "").strip()
    archivo    = request.files.get("archivo_firmado")
    if not informe_id or not archivo or not archivo.filename:
        flash("Seleccione un informe y un archivo.", "danger")
        return redirect(url_for("historial"))

    ext = os.path.splitext(archivo.filename)[1].lower()
    if ext not in (".pdf", ".docx", ".doc"):
        flash("Solo se permiten archivos PDF o Word.", "danger")
        return redirect(url_for("historial"))

    folder = os.path.join("static", "firmados")
    os.makedirs(folder, exist_ok=True)
    nombre   = f"firmado_{informe_id}{ext}"
    ruta_abs = os.path.join(folder, nombre)
    archivo.save(ruta_abs)
    ruta_rel = f"firmados/{nombre}"

    conn   = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE informes_tecnicos SET ruta_firmado = %s WHERE id = %s",
        (ruta_rel, informe_id)
    )
    conn.commit()
    cursor.close()
    conn.close()

    flash("Documento firmado cargado exitosamente.", "success")
    return redirect(url_for("historial"))


@app.route("/historial/<int:informe_id>/descargar-firmado")
@requiere_roles("ADMINISTRADOR", "CONSULTA")
def descargar_firmado(informe_id):
    conn   = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute(
        "SELECT numero_informe, ruta_firmado FROM informes_tecnicos WHERE id = %s",
        (informe_id,)
    )
    row = cursor.fetchone()
    cursor.close()
    conn.close()

    if not row or not row["ruta_firmado"]:
        flash("Documento firmado no disponible.", "danger")
        return redirect(url_for("historial"))

    ruta = os.path.join("static", row["ruta_firmado"])
    if not os.path.exists(ruta):
        flash("El archivo no existe en el servidor.", "danger")
        return redirect(url_for("historial"))

    ext = os.path.splitext(ruta)[1]
    return send_file(ruta, as_attachment=True,
                     download_name=f"{row['numero_informe']}_firmado{ext}")


@app.route("/historial/<int:informe_id>/descargar")
@requiere_roles("ADMINISTRADOR", "TECNICO", "CONSULTA")
def descargar_informe(informe_id):
    conn   = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("""
        SELECT numero_informe, ruta_word
        FROM informes_tecnicos
        WHERE id = %s
    """, (informe_id,))
    row = cursor.fetchone()
    cursor.close()
    conn.close()

    if not row or not row["ruta_word"]:
        flash("Documento no encontrado", "danger")
        return redirect(url_for("historial"))

    ruta_fisica = os.path.join("static", row["ruta_word"])
    if not os.path.exists(ruta_fisica):
        flash("El archivo no existe en el servidor", "danger")
        return redirect(url_for("historial"))

    nombre_descarga = f"{row['numero_informe']}.docx"
    return send_file(ruta_fisica, as_attachment=True, download_name=nombre_descarga)


@app.route("/historial/<int:informe_id>/descargar-pdf")
@requiere_roles("ADMINISTRADOR", "TECNICO", "CONSULTA")
def descargar_pdf_informe(informe_id):
    conn   = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("""
        SELECT numero_informe, ruta_word
        FROM informes_tecnicos WHERE id = %s
    """, (informe_id,))
    row = cursor.fetchone()
    cursor.close()
    conn.close()

    if not row or not row["ruta_word"]:
        flash("Documento no encontrado", "danger")
        return redirect(url_for("historial"))

    ruta_docx = os.path.join("static", row["ruta_word"])
    if not os.path.exists(ruta_docx):
        flash("El archivo no existe en el servidor", "danger")
        return redirect(url_for("historial"))

    numero = row["numero_informe"]

    try:
        from docx2pdf import convert
        ruta_pdf = ruta_docx.replace(".docx", ".pdf")
        if not os.path.exists(ruta_pdf):
            convert(ruta_docx, ruta_pdf)
        return send_file(ruta_pdf, as_attachment=False, download_name=f"{numero}.pdf")
    except Exception:
        return send_file(ruta_docx, as_attachment=False, download_name=f"{numero}.docx")

# =====================================================
# USUARIOS
# =====================================================

@app.route("/usuarios")
@requiere_roles("ADMINISTRADOR")
def usuarios():
    conn   = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("""
        SELECT u.id, u.nombres, u.apellidos, u.usuario, u.correo, u.estado, r.nombre AS rol
        FROM usuarios u
        INNER JOIN roles r ON u.rol_id = r.id
        ORDER BY u.id DESC
    """)
    usuarios_list = cursor.fetchall()
    cursor.execute("SELECT * FROM roles WHERE nombre != 'AUDITOR' ORDER BY nombre")
    roles = cursor.fetchall()
    cursor.close()
    conn.close()
    return render_template("usuarios.html", usuarios=usuarios_list, roles=roles)


@app.route("/usuarios/crear", methods=["POST"])
@requiere_roles("ADMINISTRADOR")
def crear_usuario():
    nombres   = request.form.get("nombres")
    apellidos = request.form.get("apellidos")
    usuario   = request.form.get("usuario")
    correo    = request.form.get("correo")
    password  = request.form.get("password")
    rol_id    = request.form.get("rol_id")

    password_hash = bcrypt.hashpw(
        password.encode("utf-8"), bcrypt.gensalt()
    ).decode("utf-8")

    try:
        conn   = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO usuarios (nombres, apellidos, usuario, correo, password, rol_id, estado)
            VALUES (%s,%s,%s,%s,%s,%s,'ACTIVO')
        """, (nombres, apellidos, usuario, correo, password_hash, rol_id))
        conn.commit()
        cursor.close()
        conn.close()
        flash("Usuario creado correctamente", "success")
    except Exception as e:
        flash(f"Error al crear usuario: {str(e)}", "danger")

    return redirect(url_for("usuarios"))


@app.route("/usuarios/<int:uid>/toggle", methods=["POST"])
@requiere_roles("ADMINISTRADOR")
def toggle_usuario(uid):
    if uid == session.get("usuario_id"):
        flash("No puedes cambiar el estado de tu propia cuenta.", "warning")
        return redirect(url_for("usuarios"))
    conn   = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT estado FROM usuarios WHERE id = %s", (uid,))
    row = cursor.fetchone()
    if row:
        nuevo = "INACTIVO" if row["estado"] == "ACTIVO" else "ACTIVO"
        cursor.execute("UPDATE usuarios SET estado = %s WHERE id = %s", (nuevo, uid))
        conn.commit()
        label = "activado" if nuevo == "ACTIVO" else "inactivado"
        flash(f"Usuario {label} correctamente.", "success")
    cursor.close()
    conn.close()
    return redirect(url_for("usuarios"))

# =====================================================
# AUDITORIA
# =====================================================

@app.route("/auditoria")
@requiere_roles("ADMINISTRADOR")
def auditoria():
    conn   = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("""
        SELECT id, usuario, modulo, accion, detalle, ip, fecha
        FROM auditoria
        ORDER BY fecha DESC
    """)
    registros = cursor.fetchall()
    cursor.close()
    conn.close()
    return render_template("auditoria.html", registros=registros)

# =====================================================
# CONFIGURACION
# =====================================================

CARPETA_CONFIG = os.path.join("static", "uploads", "config")

@app.route("/configuracion", methods=["GET", "POST"])
@requiere_roles("ADMINISTRADOR")
def configuracion():
    conn   = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    if request.method == "POST":
        try:
            # Campos de texto
            for clave in ("elaborado_nombre", "elaborado_cargo",
                          "aprobado_nombre",  "aprobado_cargo"):
                cursor.execute(
                    "UPDATE configuracion_sistema SET valor=%s WHERE clave=%s",
                    (request.form.get(clave, "").strip(), clave)
                )

            # Imágenes
            os.makedirs(CARPETA_CONFIG, exist_ok=True)
            for field in ("imagen_encabezado", "imagen_pie_pagina"):
                f = request.files.get(field)
                if f and f.filename:
                    ext = f.filename.rsplit(".", 1)[-1].lower()
                    filename = f"{field}.{ext}"
                    ruta = os.path.join(CARPETA_CONFIG, filename)
                    f.save(ruta)
                    cursor.execute(
                        "UPDATE configuracion_sistema SET valor=%s WHERE clave=%s",
                        (ruta, field)
                    )

            conn.commit()
            registrar_auditoria("Configuración", "Actualizar",
                                "Se actualizaron imágenes y datos de encabezado/pie de página")
            flash("Configuración actualizada correctamente.", "success")
        except Exception as e:
            flash(f"Error al guardar: {str(e)}", "danger")
        finally:
            cursor.close()
            conn.close()
        return redirect(url_for("configuracion"))

    cursor.execute("SELECT clave, valor FROM configuracion_sistema")
    config = {r["clave"]: r["valor"] for r in cursor.fetchall()}
    cursor.close()
    conn.close()
    return render_template("configuracion.html", config=config)

# =====================================================
# API TEST DB
# =====================================================

@app.route("/api/test-db")
def test_db():
    try:
        conn   = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT DATABASE() AS base_actual")
        resultado = cursor.fetchone()
        cursor.close()
        conn.close()
        return jsonify({"estado": "ok", "base_datos": resultado["base_actual"]})
    except Exception as e:
        return jsonify({"estado": "error", "mensaje": str(e)}), 500

# =====================================================
# MAIN
# =====================================================

with app.app_context():
    init_migrations()

if __name__ == "__main__":
    app.run(debug=True, port=5050, use_reloader=False)
