-- Script para agregar nuevos campos a la tabla alumnos
-- Ejecutar en MariaDB/MySQL

ALTER TABLE alumnos
ADD COLUMN talla_camisa VARCHAR(10) NULL COMMENT 'Talla de camisa del uniforme' AFTER talla_cm,
ADD COLUMN talla_pantalon VARCHAR(10) NULL COMMENT 'Talla de pantalón del uniforme' AFTER talla_camisa,
ADD COLUMN talla_zapato INT NULL COMMENT 'Talla de zapatos' AFTER talla_pantalon,
ADD COLUMN alergico_a TEXT NULL COMMENT 'Alergias del alumno' AFTER talla_zapato,
ADD COLUMN tratamiento_medico TEXT NULL COMMENT 'Tratamientos médicos del alumno' AFTER alergico_a,
ADD COLUMN condicion_fisica TEXT NULL COMMENT 'Condición física del alumno' AFTER tratamiento_medico,
ADD COLUMN discapacidad TEXT NULL COMMENT 'Discapacidad del alumno' AFTER condicion_fisica;
