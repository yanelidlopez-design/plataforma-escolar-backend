-- Script de inicialización para MariaDB - Plataforma Escolar
-- Crea las tablas legacy que tienen managed=False en Django
-- y son referenciadas por claves foráneas en migraciones posteriores.

CREATE DATABASE IF NOT EXISTS plataforma_escolar CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE plataforma_escolar;

-- Tabla legacy de cuentas de acceso (el modelo Django usa managed=False).
CREATE TABLE IF NOT EXISTS `usuarios` (
    `id_usuario` INT AUTO_INCREMENT PRIMARY KEY,
    `nombre_usuario` VARCHAR(150) NOT NULL UNIQUE,
    `clave_hash` VARCHAR(255) NOT NULL,
    `email` VARCHAR(254) NOT NULL UNIQUE,
    `rol` VARCHAR(20) NOT NULL DEFAULT 'profesor',
    `activo` TINYINT(1) NOT NULL DEFAULT 1,
    `fecha_creacion` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Tabla: alumnos (referenciada por constancia_prosecucion_final, evaluacion_lapso_criterio)
CREATE TABLE IF NOT EXISTS `alumnos` (
    `id_alumno` INT AUTO_INCREMENT PRIMARY KEY,
    `primer_nombre` VARCHAR(100) NOT NULL,
    `segundo_nombre` VARCHAR(100) NULL,
    `primer_apellido` VARCHAR(100) NOT NULL,
    `segundo_apellido` VARCHAR(100) NULL,
    `tipo_documento_identidad` VARCHAR(10) NULL,
    `numero_documento_identidad` VARCHAR(20) NOT NULL UNIQUE,
    `cedula_escolar` VARCHAR(20) NOT NULL UNIQUE,
    `fecha_nacimiento` DATE NOT NULL,
    `genero` VARCHAR(50) NULL,
    `lugar_nacimiento` VARCHAR(150) NULL,
    `nacionalidad` VARCHAR(50) NULL,
    `grupo_sanguineo` VARCHAR(5) NULL,
    `peso_kg` DECIMAL(5,2) NULL,
    `talla_cm` DECIMAL(5,2) NULL,
    `fecha_inscripcion_inicial` DATE NULL,
    `estatus_general` VARCHAR(50) NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Tabla: grupos_academicos (referenciada por criterio_evaluacion)
CREATE TABLE IF NOT EXISTS `grupos_academicos` (
    `id_grupo` INT AUTO_INCREMENT PRIMARY KEY,
    `cupo_maximo` INT NOT NULL DEFAULT 30
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;