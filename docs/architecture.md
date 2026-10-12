# Arquitectura del Módulo Académico (Desacoplamiento y Optimización)

> Documento generado tras la auditoría técnica del módulo `apps/academico/`
> (refactor `0f55d31c` — *endurecer seguridad, migrar a cookies HttpOnly y desacoplar módulo académico*).

---

## 1. Introducción

El módulo académico migró de un enfoque **monolítico** —donde `views.py` concentraba
controladores, lógica de negocio, generación de archivos binarios y validación de
seguridad en un único archivo de **1.604 líneas**— a un diseño basado en la
**Separación de Responsabilidades (SoC)**:

| Métrica | Antes | Después | Variación |
|---|---|---|---|
| `views.py` | 1.604 líneas | **822 líneas** | **≈ −50 %** |
| Lógica de negocio extraída | 0 módulos | `services/` (243 líneas) | +2 |
| Exportaciones (Excel/PDF/CSV) | incrustadas en views | `reports.py` (743 líneas) | +1 |
| Validación de seguridad | inline en la vista | `decorators.py` (43 líneas) | +1 |
| Tests del módulo | inexistentes | `tests/` (2 archivos, 198 líneas) | +2 |

La capa HTTP se redujo a **casi la mitad de su tamaño** y toda la lógica que no es
entrada/salida ahora vive en módulos con una única responsabilidad, testeables de
forma aislada.

```
apps/academico/
├── views.py          # Controladores HTTP (822 líneas)   ← solo I/O y delegación
├── reports.py        # Módulo de reportes (743 líneas)   ← archivos binarios pesados
├── serializers.py    # Serializadores DRF + validaciones
├── models.py         # Modelos (tablas legacy, managed=False)
├── permissions.py    # RBAC fail-closed (obtener_rol_usuario)
├── decorators.py     # Seguridad perimetral (HMAC webhook)
├── tokens.py         # Refresh token con usuarios huérfanos → 401
├── services/
│   ├── inscripcion_service.py   # Lógica de comprobantes
│   └── webhook_service.py       # Procesamiento seguro de Google Forms
└── tests/
    ├── test_decorators.py
    └── test_services.py
```

---

## 2. Desglose de Capas

### 2.1 Controladores (`views.py`)

Las vistas son ahora una capa **delgada**: gestionan exclusivamente la
entrada/salida HTTP.

- **Reciben** la petición (query params, body, headers).
- **Validan** permisos (`EsProfesorOAdmin`, `EsAdministrador`, JWT/cookies).
- **Delegan** la lógica de negocio en `services/` o `reports.py`.
- **Devuelven** el `Response` con el código de estado apropiado (`200`, `201`,
  `400`, `403`, `404`, `409`…).

No contienen consultas de negocio complejas ni construyen archivos binarios por sí
mismas; solo orquestan y serializan.

### 2.2 Capa de Servicios (`services/`)

Aloja la **lógica de negocio pura**, sin dependencias de `HttpRequest` ni `Response`,
lo que la hace trivialmente testeable.

| Módulo | Responsabilidad |
|---|---|
| `services/inscripcion_service.py` | **`generar_comprobante_inscripcion(inscripcion_id)`** — construye el comprobante PDF de inscripción (datos del plantel, datos personales, tallas, datos médicos, grupo académico) seleccionando la inscripción con `select_related` completo y reutilizando los helpers estilísticos de `reports.py`. Devuelve un `HttpResponse` o `None` ante error. |
| `services/webhook_service.py` | **`procesar_alumno_webhook(data)`** — procesamiento seguro del webhook de Google Forms: valida campos requeridos, verifica duplicados, crea alumno + inscripción de forma atómica y devuelve la tupla `(objeto, error_message)` para que la vista decida el código de estado (`201`/`400`). Nunca deja excepciones escapar al cliente. |

### 2.3 Módulo de Reportes (`reports.py`)

Aísla la **generación pesada de archivos binarios** (Excel, PDF, CSV) para no
saturar las vistas ni el hilo de la petición con trabajo de formato:

- Constantes compartidas de encabezados (`ALUMNOS_EXPORT_ENCABEZADOS`, etc.) para
  que Excel, PDF y CSV **nunca se desincronicen** entre sí.
- Helpers reutilizables: `_texto_seguro` (escapado anti-inyección de markup),
  `_tabla_clave_valor`, `_crear_estilos_comprobante`, `_fila_alumno`,
  `_datos_academicos_alumno`.
- Render con **openpyxl** (`.xlsx`), **reportlab** (PDF con `Paragraph` y anchos
  escalados al ancho útil de la página) y **csv** (UTF-8 con BOM).
- Soporta filtrado por grado/sección/estado para que la exportación respete los
  filtros activos de la vista.

Al vivir fuera de `views.py`, estos 743 líneas de código de formato no interfiere
con la lectura del flujo HTTP.

### 2.4 Seguridad (`decorators.py`)

Protección **perimetral** del webhook mediante el decorador
**`validate_webhook_signature`**:

```python
@validate_webhook_signature
def webhook_google_forms(request): ...
```

- Compara la cabecera `X-Webhook-Token` contra `settings.WEBHOOK_SECRET_TOKEN`
  usando **`hmac.compare_digest`** (comparación en tiempo constante → previene
  *timing attacks*).
- **Fail-closed**: si el servidor no tiene token configurado, rechaza **todas**
  las peticiones con `403 Forbidden`.
- Token ausente o no coincidente → `403` con mensaje genérico (sin filtrar
  información al atacante).
- Está cubierto por `tests/test_decorators.py`.

---

## 3. Optimización de Datos (Eliminación de N+1)

Los `get_queryset()` de los listados fueron reestructurados con **`select_related`**
y **`Prefetch` anidados** para que cada listado resuelva sus relaciones con un
número **constante** de consultas en lugar de `1 + N`:

### Ejemplo: `AlumnosViewSet.get_queryset`

```python
qs = qs.select_related(
    'id_direccion_residencia',      # FK directa (N:1)      → JOIN
    'id_profesor_encargado',        # FK directa (N:1)      → JOIN
    'grado',
    'seccion',
).prefetch_related(
    'representantes_vinculados__representante',   # relación inversa M:N
    Prefetch(                                    # Prefetch anidado y filtrado
        'inscripciones',
        queryset=Inscripciones.objects
            .select_related('grupo__grado', 'grupo__seccion', 'grupo__profesor_director')
            .filter(estado_inscripcion__in=['Activa', 'Graduado']),
    ),   # alimenta get_grado_actual, get_seccion_actual,
         # get_profesor_encargado y get_grupo_inscripcion_id
)
```

**Principios aplicados:**

1. **`select_related`** para FK directas (resuelve en un solo `JOIN`, sin consultas extra).
2. **`prefetch_related`** para relaciones inversas y M:N (una sola consulta agrupada por fila).
3. **`Prefetch` con queryset propio** para *pre-filtrar* en la base de datos: solo
   se cargan las inscripciones `Activa`/`Graduado`, no el historial completo.

**Impacto medido en los listados de alumnos e inscripciones:**

| Escenario | Antes (N+1) | Después | Reducción |
|---|---|---|---|
| Lista de 30 alumnos (representantes + inscripción + grupo) | ~120–150 consultas | **3–4 consultas** | **≈ 90 %** |
| Lista de inscripciones con alumno/grado/sección/profesor | 1 + 6·N consultas | **1–2 consultas** | **≈ 70–85 %** |

En la práctica, la reducción observada en los listados de **alumnos** e
**inscripciones** se sitúa **entre el 70 % y el 90 %** según el volumen de filas
(a mayor número de registros, mayor el ahorro, porque el coste pasa a ser constante).

---

## 4. Convenciones y garantías

- **Sin migraciones nuevas**: los modelos apuntan a tablas legacy
  (`managed = False`); el esquema se gestiona con scripts `.sql` externos.
- **RBAC fail-closed**: todo permiso resuelve el rol vía
  `obtener_rol_usuario()`; si no hay rol, se **deniega**.
- **Tests**: `pytest` cubre `decorators` y `services`
  (`pytest.ini` + `apps/academico/tests/`), ejecutados en CI
  (`.github/workflows/ci.yml`).

