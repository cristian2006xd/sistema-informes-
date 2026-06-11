USE sistema_informes_tics;

-- ==========================
-- ROLES
-- ==========================
CREATE TABLE roles (
    id INT AUTO_INCREMENT PRIMARY KEY,
    nombre VARCHAR(50) NOT NULL UNIQUE,
    descripcion VARCHAR(255),
    fecha_creacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ==========================
-- USUARIOS
-- ==========================
CREATE TABLE usuarios (
    id INT AUTO_INCREMENT PRIMARY KEY,
    nombres VARCHAR(150) NOT NULL,
    apellidos VARCHAR(150) NOT NULL,
    usuario VARCHAR(100) NOT NULL UNIQUE,
    correo VARCHAR(150),
    password VARCHAR(255) NOT NULL,
    rol_id INT NOT NULL,
    estado ENUM('ACTIVO','INACTIVO') DEFAULT 'ACTIVO',
    fecha_creacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (rol_id) REFERENCES roles(id)
);

-- ==========================
-- FUNCIONARIOS
-- ==========================
CREATE TABLE funcionarios (
    id INT AUTO_INCREMENT PRIMARY KEY,
    cedula VARCHAR(10) UNIQUE,
    nombres VARCHAR(150) NOT NULL,
    apellidos VARCHAR(150) NOT NULL,
    cargo VARCHAR(150),
    dependencia VARCHAR(200),
    ubicacion_fisica VARCHAR(200),
    correo VARCHAR(150),
    telefono VARCHAR(50),
    estado ENUM('ACTIVO','INACTIVO') DEFAULT 'ACTIVO',
    fecha_creacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ==========================
-- TIPOS DE BIEN
-- ==========================
CREATE TABLE tipos_bienes (
    id INT AUTO_INCREMENT PRIMARY KEY,
    nombre VARCHAR(100) NOT NULL UNIQUE
);

-- ==========================
-- MARCAS
-- ==========================
CREATE TABLE marcas (
    id INT AUTO_INCREMENT PRIMARY KEY,
    nombre VARCHAR(100) NOT NULL UNIQUE
);

-- ==========================
-- ESTADOS DE BIEN
-- ==========================
CREATE TABLE estados_bienes (
    id INT AUTO_INCREMENT PRIMARY KEY,
    nombre VARCHAR(100) NOT NULL UNIQUE
);

-- ==========================
-- BIENES
-- ==========================
CREATE TABLE bienes (
    id INT AUTO_INCREMENT PRIMARY KEY,

    tipo_id INT NOT NULL,
    marca_id INT NOT NULL,
    estado_id INT NOT NULL,

    modelo VARCHAR(150),
    serie VARCHAR(150),
    codigo_esbye VARCHAR(150),

    observacion TEXT,

    fecha_creacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (tipo_id) REFERENCES tipos_bienes(id),
    FOREIGN KEY (marca_id) REFERENCES marcas(id),
    FOREIGN KEY (estado_id) REFERENCES estados_bienes(id)
);

-- ==========================
-- TIPOS DE INFORME
-- ==========================
CREATE TABLE tipos_informes (
    id INT AUTO_INCREMENT PRIMARY KEY,
    codigo VARCHAR(10),
    nombre VARCHAR(200)
);

-- ==========================
-- INFORMES
-- ==========================
CREATE TABLE informes (
    id INT AUTO_INCREMENT PRIMARY KEY,

    numero_informe VARCHAR(100) UNIQUE,

    funcionario_id INT NOT NULL,
    tipo_informe_id INT NOT NULL,
    usuario_creador_id INT NOT NULL,

    antecedentes LONGTEXT,
    desarrollo LONGTEXT,
    observaciones LONGTEXT,
    conclusiones LONGTEXT,

    fecha_informe DATE,
    estado ENUM(
        'BORRADOR',
        'GENERADO',
        'FIRMADO',
        'ANULADO'
    ) DEFAULT 'BORRADOR',

    fecha_creacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (funcionario_id)
        REFERENCES funcionarios(id),

    FOREIGN KEY (tipo_informe_id)
        REFERENCES tipos_informes(id),

    FOREIGN KEY (usuario_creador_id)
        REFERENCES usuarios(id)
);

-- ==========================
-- INFORME_BIENES
-- ==========================
CREATE TABLE informe_bienes (
    id INT AUTO_INCREMENT PRIMARY KEY,

    informe_id INT NOT NULL,
    bien_id INT NOT NULL,

    FOREIGN KEY (informe_id)
        REFERENCES informes(id)
        ON DELETE CASCADE,

    FOREIGN KEY (bien_id)
        REFERENCES bienes(id)
        ON DELETE CASCADE
);

-- ==========================
-- FOTOGRAFIAS
-- ==========================
CREATE TABLE fotografias (
    id INT AUTO_INCREMENT PRIMARY KEY,

    informe_id INT NOT NULL,
    bien_id INT NULL,

    nombre_archivo VARCHAR(255),
    ruta_archivo VARCHAR(500),

    fecha_subida TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (informe_id)
        REFERENCES informes(id)
        ON DELETE CASCADE,

    FOREIGN KEY (bien_id)
        REFERENCES bienes(id)
        ON DELETE CASCADE
);

-- ==========================
-- DOCUMENTOS GENERADOS
-- ==========================
CREATE TABLE documentos_generados (
    id INT AUTO_INCREMENT PRIMARY KEY,

    informe_id INT NOT NULL,

    tipo_documento ENUM(
        'PDF',
        'WORD',
        'PDF_FIRMADO'
    ),

    nombre_archivo VARCHAR(255),
    ruta_archivo VARCHAR(500),

    fecha_generacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (informe_id)
        REFERENCES informes(id)
        ON DELETE CASCADE
);

-- ==========================
-- HISTORIAL
-- ==========================
CREATE TABLE historial_informes (
    id INT AUTO_INCREMENT PRIMARY KEY,

    informe_id INT NOT NULL,
    usuario_id INT NOT NULL,

    accion VARCHAR(255),
    detalle TEXT,

    fecha TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (informe_id)
        REFERENCES informes(id)
        ON DELETE CASCADE,

    FOREIGN KEY (usuario_id)
        REFERENCES usuarios(id)
);