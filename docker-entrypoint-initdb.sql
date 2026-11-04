-- Complete structural schema for legacy entities with managed=False.
-- Safe to run before migrate or import into a new production database:
-- every CREATE is idempotent and existing tables/data are left untouched.

CREATE TABLE IF NOT EXISTS `direcciones` (
    `id_direccion` INT NOT NULL AUTO_INCREMENT,
    `calle` VARCHAR(255) NOT NULL,
    `ciudad` VARCHAR(100) NOT NULL,
    `estado` VARCHAR(100) NOT NULL,
    `referencia` LONGTEXT NULL,
    PRIMARY KEY (`id_direccion`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `usuarios` (
    `id_usuario` INT NOT NULL AUTO_INCREMENT,
    `nombre_usuario` VARCHAR(150) NOT NULL,
    `clave_hash` VARCHAR(255) NOT NULL,
    `email` VARCHAR(254) NOT NULL,
    `rol` VARCHAR(20) NOT NULL DEFAULT 'profesor',
    `activo` TINYINT(1) NOT NULL DEFAULT 1,
    `fecha_creacion` DATETIME(6) NOT NULL,
    PRIMARY KEY (`id_usuario`),
    UNIQUE KEY `usuarios_nombre_usuario_uniq` (`nombre_usuario`),
    UNIQUE KEY `usuarios_email_uniq` (`email`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `periodos_academicos` (
    `id_periodo` INT NOT NULL AUTO_INCREMENT,
    `codigo_periodo` VARCHAR(50) NOT NULL,
    `nombre_periodo` VARCHAR(100) NOT NULL,
    `fecha_inicio` DATE NOT NULL,
    `fecha_fin` DATE NOT NULL,
    `activo` TINYINT(1) NOT NULL DEFAULT 1,
    PRIMARY KEY (`id_periodo`),
    UNIQUE KEY `periodos_academicos_codigo_periodo_uniq` (`codigo_periodo`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `niveles_educativos` (
    `id_nivel` INT NOT NULL AUTO_INCREMENT,
    `nombre_nivel` VARCHAR(100) NOT NULL,
    PRIMARY KEY (`id_nivel`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `turnos` (
    `id_turno` INT NOT NULL AUTO_INCREMENT,
    `nombre_turno` VARCHAR(50) NOT NULL,
    PRIMARY KEY (`id_turno`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `secciones` (
    `id_seccion` INT NOT NULL AUTO_INCREMENT,
    `nombre_seccion` VARCHAR(50) NOT NULL,
    PRIMARY KEY (`id_seccion`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `grados_academicos` (
    `id_grado` INT NOT NULL AUTO_INCREMENT,
    `id_nivel` INT NOT NULL,
    `nombre_grado` VARCHAR(100) NOT NULL,
    `orden` SMALLINT NOT NULL,
    PRIMARY KEY (`id_grado`),
    KEY `grados_academicos_id_nivel_idx` (`id_nivel`),
    CONSTRAINT `fk_grados_nivel` FOREIGN KEY (`id_nivel`)
        REFERENCES `niveles_educativos` (`id_nivel`) ON DELETE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `profesores` (
    `id_profesor` INT NOT NULL AUTO_INCREMENT,
    `id_usuario` INT NULL,
    `primer_nombre` VARCHAR(100) NOT NULL,
    `segundo_nombre` VARCHAR(100) NULL,
    `primer_apellido` VARCHAR(100) NOT NULL,
    `segundo_apellido` VARCHAR(100) NULL,
    `cedula` VARCHAR(20) NOT NULL,
    `telefono` VARCHAR(20) NULL,
    `especialidad` VARCHAR(150) NOT NULL,
    `codigo_cargo` VARCHAR(50) NULL,
    `categoria` VARCHAR(50) NULL,
    `fecha_nacimiento` DATE NULL,
    `talla_zapato` VARCHAR(20) NULL,
    `talla_camisa` VARCHAR(20) NULL,
    `talla_pantalon` VARCHAR(20) NULL,
    `estado_civil` VARCHAR(50) NULL,
    `numero_hijos` INT UNSIGNED NULL,
    `dependencia` VARCHAR(150) NULL,
    `codigo_dependencia` VARCHAR(50) NULL,
    `titulo` VARCHAR(200) NULL,
    `especialidad_campo` VARCHAR(200) NULL,
    `fecha_ingreso_ministerio` DATE NULL,
    `fecha_ingreso_institucion` DATE NULL,
    `correo` VARCHAR(200) NULL,
    `direccion` LONGTEXT NULL,
    PRIMARY KEY (`id_profesor`),
    UNIQUE KEY `profesores_cedula_uniq` (`cedula`),
    UNIQUE KEY `profesores_id_usuario_uniq` (`id_usuario`),
    CONSTRAINT `fk_profesores_usuario` FOREIGN KEY (`id_usuario`)
        REFERENCES `usuarios` (`id_usuario`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `alumnos` (
    `id_alumno` INT NOT NULL AUTO_INCREMENT,
    `id_usuario` INT NULL,
    `id_direccion_residencia` INT NULL,
    `id_profesor_encargado` INT NULL,
    `primer_nombre` VARCHAR(150) NOT NULL,
    `segundo_nombre` VARCHAR(150) NULL,
    `primer_apellido` VARCHAR(150) NOT NULL,
    `segundo_apellido` VARCHAR(150) NULL,
    `tipo_documento_identidad` VARCHAR(50) NOT NULL,
    `numero_documento_identidad` VARCHAR(30) NOT NULL,
    `cedula_escolar` VARCHAR(30) NULL,
    `fecha_nacimiento` DATE NOT NULL,
    `genero` VARCHAR(50) NOT NULL,
    `lugar_nacimiento` VARCHAR(255) NULL,
    `nacionalidad` VARCHAR(100) NULL,
    `carnet_patria_codigo` VARCHAR(50) NULL,
    `carnet_patria_serial` VARCHAR(50) NULL,
    `numero_cuenta` VARCHAR(30) NULL,
    `tipo_cuenta` VARCHAR(20) NULL,
    `banco` VARCHAR(100) NULL,
    `entidad_federal_nacimiento` VARCHAR(100) NULL,
    `municipio_nacimiento` VARCHAR(100) NULL,
    `parroquia_nacimiento` VARCHAR(100) NULL,
    `condicion_fisica` LONGTEXT NULL,
    `grupo_sanguineo` VARCHAR(10) NULL,
    `apoyo_escolar` TINYINT(1) NOT NULL DEFAULT 0,
    `vacunas_completas` TINYINT(1) NOT NULL DEFAULT 0,
    `alergico_a` LONGTEXT NULL,
    `tratamiento_medico` LONGTEXT NULL,
    `peso_kg` DECIMAL(5,2) NULL,
    `talla_cm` DECIMAL(5,2) NULL,
    `talla_camisa` VARCHAR(20) NULL,
    `talla_pantalon` VARCHAR(20) NULL,
    `talla_zapato` VARCHAR(20) NULL,
    `estado_civil_padres` VARCHAR(50) NULL,
    `ingreso_familiar` DECIMAL(10,2) NULL,
    `profesion_madre` VARCHAR(150) NULL,
    `profesion_padre` VARCHAR(150) NULL,
    `tipo_vivienda` VARCHAR(50) NULL,
    `numero_hermanos` INT NULL,
    `numero_en_el_planter` INT NULL,
    `discapacidad` TINYINT(1) NOT NULL DEFAULT 0,
    `tipo_discapacidad` LONGTEXT NULL,
    `observaciones` LONGTEXT NULL,
    `fecha_inscripcion_inicial` DATE NOT NULL,
    `fecha_egreso` DATE NULL,
    `repitiente` TINYINT(1) NOT NULL DEFAULT 0,
    `estatus_general` VARCHAR(50) NOT NULL,
    PRIMARY KEY (`id_alumno`),
    UNIQUE KEY `alumnos_numero_documento_uniq` (`numero_documento_identidad`),
    UNIQUE KEY `alumnos_cedula_escolar_uniq` (`cedula_escolar`),
    KEY `alumnos_id_usuario_idx` (`id_usuario`),
    KEY `alumnos_id_direccion_idx` (`id_direccion_residencia`),
    KEY `alumnos_id_profesor_idx` (`id_profesor_encargado`),
    CONSTRAINT `fk_alumnos_usuario` FOREIGN KEY (`id_usuario`)
        REFERENCES `usuarios` (`id_usuario`) ON DELETE SET NULL,
    CONSTRAINT `fk_alumnos_direccion` FOREIGN KEY (`id_direccion_residencia`)
        REFERENCES `direcciones` (`id_direccion`) ON DELETE SET NULL,
    CONSTRAINT `fk_alumnos_profesor` FOREIGN KEY (`id_profesor_encargado`)
        REFERENCES `profesores` (`id_profesor`) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `grupos_academicos` (
    `id_grupo` INT NOT NULL AUTO_INCREMENT,
    `id_periodo` INT NOT NULL,
    `id_nivel` INT NULL,
    `id_grado` INT NOT NULL,
    `id_seccion` INT NOT NULL,
    `id_turno` INT NOT NULL,
    `id_profesor_principal` INT NULL,
    `cupo_maximo` INT NOT NULL DEFAULT 30,
    PRIMARY KEY (`id_grupo`),
    KEY `grupos_periodo_idx` (`id_periodo`),
    KEY `grupos_nivel_idx` (`id_nivel`),
    KEY `grupos_grado_idx` (`id_grado`),
    KEY `grupos_seccion_idx` (`id_seccion`),
    KEY `grupos_turno_idx` (`id_turno`),
    KEY `grupos_profesor_idx` (`id_profesor_principal`),
    CONSTRAINT `fk_grupos_periodo` FOREIGN KEY (`id_periodo`)
        REFERENCES `periodos_academicos` (`id_periodo`) ON DELETE RESTRICT,
    CONSTRAINT `fk_grupos_nivel` FOREIGN KEY (`id_nivel`)
        REFERENCES `niveles_educativos` (`id_nivel`) ON DELETE RESTRICT,
    CONSTRAINT `fk_grupos_grado` FOREIGN KEY (`id_grado`)
        REFERENCES `grados_academicos` (`id_grado`) ON DELETE RESTRICT,
    CONSTRAINT `fk_grupos_seccion` FOREIGN KEY (`id_seccion`)
        REFERENCES `secciones` (`id_seccion`) ON DELETE RESTRICT,
    CONSTRAINT `fk_grupos_turno` FOREIGN KEY (`id_turno`)
        REFERENCES `turnos` (`id_turno`) ON DELETE RESTRICT,
    CONSTRAINT `fk_grupos_profesor` FOREIGN KEY (`id_profesor_principal`)
        REFERENCES `profesores` (`id_profesor`) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `inscripciones` (
    `id_inscripcion` INT NOT NULL AUTO_INCREMENT,
    `id_alumno` INT NOT NULL,
    `id_grupo` INT NOT NULL,
    `fecha_inscripcion` DATETIME(6) NULL,
    `estado_inscripcion` VARCHAR(50) NOT NULL DEFAULT 'Activa',
    `monto_pago` DECIMAL(10,2) NULL,
    `referencia_bancaria` VARCHAR(100) NULL,
    PRIMARY KEY (`id_inscripcion`),
    KEY `inscripciones_alumno_idx` (`id_alumno`),
    KEY `inscripciones_grupo_idx` (`id_grupo`),
    CONSTRAINT `fk_inscripciones_alumno` FOREIGN KEY (`id_alumno`)
        REFERENCES `alumnos` (`id_alumno`) ON DELETE CASCADE,
    CONSTRAINT `fk_inscripciones_grupo` FOREIGN KEY (`id_grupo`)
        REFERENCES `grupos_academicos` (`id_grupo`) ON DELETE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `calificaciones` (
    `id_calificacion` INT NOT NULL AUTO_INCREMENT,
    `id_inscripcion` INT NOT NULL,
    `id_profesor` INT NULL,
    `calificacion` VARCHAR(50) NULL,
    `fecha_registro` DATETIME(6) NULL,
    PRIMARY KEY (`id_calificacion`),
    KEY `calificaciones_inscripcion_idx` (`id_inscripcion`),
    KEY `calificaciones_profesor_idx` (`id_profesor`),
    CONSTRAINT `fk_calificaciones_inscripcion` FOREIGN KEY (`id_inscripcion`)
        REFERENCES `inscripciones` (`id_inscripcion`) ON DELETE CASCADE,
    CONSTRAINT `fk_calificaciones_profesor` FOREIGN KEY (`id_profesor`)
        REFERENCES `profesores` (`id_profesor`) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `asistencias` (
    `id_asistencia` INT NOT NULL AUTO_INCREMENT,
    `fecha` DATE NOT NULL,
    `id_alumno` INT NOT NULL,
    `id_grupo` INT NOT NULL,
    `estado` VARCHAR(1) NOT NULL,
    `observaciones` LONGTEXT NULL,
    `id_profesor_registro` INT NULL,
    `fecha_registro` DATETIME(6) NOT NULL,
    PRIMARY KEY (`id_asistencia`),
    UNIQUE KEY `asistencias_fecha_alumno_grupo_uniq` (`fecha`, `id_alumno`, `id_grupo`),
    KEY `asistencias_grupo_idx` (`id_grupo`),
    KEY `asistencias_profesor_idx` (`id_profesor_registro`),
    CONSTRAINT `fk_asistencias_alumno` FOREIGN KEY (`id_alumno`)
        REFERENCES `alumnos` (`id_alumno`) ON DELETE CASCADE,
    CONSTRAINT `fk_asistencias_grupo` FOREIGN KEY (`id_grupo`)
        REFERENCES `grupos_academicos` (`id_grupo`) ON DELETE CASCADE,
    CONSTRAINT `fk_asistencias_profesor` FOREIGN KEY (`id_profesor_registro`)
        REFERENCES `profesores` (`id_profesor`) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `representantes_legales` (
    `id_representante` INT NOT NULL AUTO_INCREMENT,
    `id_direccion_residencia` INT NULL,
    `primer_nombre` VARCHAR(100) NOT NULL,
    `segundo_nombre` VARCHAR(100) NULL,
    `primer_apellido` VARCHAR(100) NOT NULL,
    `segundo_apellido` VARCHAR(100) NULL,
    `cedula` VARCHAR(20) NOT NULL,
    `carnet_patria` VARCHAR(50) NULL,
    `telefono_principal` VARCHAR(20) NOT NULL,
    `telefono_secundario` VARCHAR(20) NULL,
    `email` VARCHAR(150) NULL,
    `ocupacion` VARCHAR(150) NULL,
    PRIMARY KEY (`id_representante`),
    UNIQUE KEY `representantes_cedula_uniq` (`cedula`),
    KEY `representantes_direccion_idx` (`id_direccion_residencia`),
    CONSTRAINT `fk_representantes_direccion` FOREIGN KEY (`id_direccion_residencia`)
        REFERENCES `direcciones` (`id_direccion`) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `alumno_representante` (
    `id_alumno` INT NOT NULL,
    `id_representante` INT NOT NULL,
    `parentesco` VARCHAR(50) NULL,
    `es_principal` TINYINT(1) NOT NULL DEFAULT 1,
    PRIMARY KEY (`id_alumno`, `id_representante`),
    KEY `alumno_representante_representante_idx` (`id_representante`),
    CONSTRAINT `fk_alumno_representante_alumno` FOREIGN KEY (`id_alumno`)
        REFERENCES `alumnos` (`id_alumno`) ON DELETE CASCADE,
    CONSTRAINT `fk_alumno_representante_representante` FOREIGN KEY (`id_representante`)
        REFERENCES `representantes_legales` (`id_representante`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
