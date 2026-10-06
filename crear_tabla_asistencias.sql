-- ============================================================================
-- Script: Crear tabla de asistencias
-- Descripción: Tabla para registro de asistencias diarias de alumnos
-- ============================================================================

USE plataforma_escolar;

-- Crear tabla de asistencias
CREATE TABLE IF NOT EXISTS `asistencias` (
  `id_asistencia` INT UNSIGNED NOT NULL AUTO_INCREMENT,
  `fecha` DATE NOT NULL,
  `id_alumno` INT UNSIGNED NOT NULL,
  `id_grupo` INT UNSIGNED NOT NULL,
  `estado` ENUM('P', 'A', 'T', 'J') NOT NULL COMMENT 'P=Presente, A=Ausente, T=Tarde, J=Justificado',
  `observaciones` TEXT NULL,
  `id_profesor_registro` INT UNSIGNED NULL,
  `fecha_registro` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id_asistencia`),
  UNIQUE KEY `uk_fecha_alumno_grupo` (`fecha`, `id_alumno`, `id_grupo`),
  INDEX `idx_fecha` (`fecha`),
  INDEX `idx_alumno` (`id_alumno`),
  INDEX `idx_grupo` (`id_grupo`),
  INDEX `idx_estado` (`estado`),
  CONSTRAINT `fk_asistencia_alumno` FOREIGN KEY (`id_alumno`) REFERENCES `alumnos` (`id_alumno`) ON DELETE CASCADE ON UPDATE CASCADE,
  CONSTRAINT `fk_asistencia_grupo` FOREIGN KEY (`id_grupo`) REFERENCES `grupos_academicos` (`id_grupo`) ON DELETE CASCADE ON UPDATE CASCADE,
  CONSTRAINT `fk_asistencia_profesor` FOREIGN KEY (`id_profesor_registro`) REFERENCES `profesores` (`id_profesor`) ON DELETE SET NULL ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ============================================================================
-- Fin del script
-- ============================================================================
