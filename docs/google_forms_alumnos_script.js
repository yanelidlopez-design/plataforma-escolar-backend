/**
 * ============================================================================
 *  GOOGLE FORMS → PLATAFORMA ESCOLAR (webhook de inscripción de alumnos)
 * ============================================================================
 *
 *  QUÉ HACE:
 *    Al enviarse el formulario, empaqueta las respuestas en un payload PLANO
 *    (tal como lo espera el backend) y hace:
 *      POST {URL_WEBHOOK}  con header  X-Webhook-Token: {TOKEN}
 *    El backend crea el alumno, su dirección, carnet/finanzas/datos familiares
 *    y, si reconoce el grupo, la inscripción con pago.
 *
 *  INSTALACIÓN (1 sola vez):
 *    1. Editor del Google Form: ⋮ (menú superior) → Script editor.
 *    2. Pega TODO este archivo y guarda (Ctrl+S).
 *    3. Edita CONFIG abajo:
 *       - URL_WEBHOOK: tu túnel ngrok + /api/academico/webhook-google-forms/
 *       - TOKEN: valor de WEBHOOK_SECRET_TOKEN del .env del backend.
 *       - GRUPOS: texto EXACTO de cada opción de tu pregunta de grupo → id.
 *    4. IMPORTANTE: los disparadores simples de Forms NO ejecutan UrlFetchApp.
 *       Crea el disparador instalable:
 *       ⏰ Disparadores (panel izquierdo) → + Añadir disparador →
 *       Función: alEnviarFormulario → Evento: Al enviar formulario → Guardar.
 *    5. Envía una respuesta de prueba → ⏰ Disparadores → Registro de
 *       ejecuciones debe decir "finalizada" con "Backend respondió 201".
 *
 *  DIAGNÓSTICO DE PREGUNTAS:
 *    Ejecuta la función `listarPreguntas()` desde el editor: lista cada
 *    pregunta del form y a qué campo del backend se mapea ("SIN MAPEAR" o
 *    campo raro → ajusta la entrada correspondiente de MAPEO).
 * ============================================================================
 */

var CONFIG = {
  // URL pública del backend (reemplaza el túnel ngrok por el definitivo cuando lo tengas)
  URL_WEBHOOK: 'https://TU_URL_DE_NGROK.ngrok-free.app/api/academico/webhook-google-forms/',
  // Token: misma variable WEBHOOK_SECRET_TOKEN del .env del backend
  TOKEN: 'PEGA_AQUI_TU_TOKEN',

  // Mapa grupo académico: texto EXACTO de la opción en el formulario → id_grupo.
  // (GET /grupos/ exige login de admin, por eso no se puede autodetectar.)
  // Ids actuales de la BD: Primer Grado A=1/B=2, Segundo A=3/B=4/C=5,
  // Tercer A=6/B=7, Cuarto A=8/B=9, Quinto A=10/B=11, Sexto Única=12,
  // Inicial 1 A=13, Inicial 2 A=14, Inicial 3 A=15.
  GRUPOS: {
    "Primer Grado 'A'": 1,
    "Primer Grado 'B'": 2,
    "Segundo Grado 'A'": 3,
    "Segundo Grado 'B'": 4,
    "Segundo Grado 'C'": 5,
    "Tercer Grado 'A'": 6,
    "Tercer Grado 'B'": 7,
    "Cuarto Grado 'A'": 8,
    "Cuarto Grado 'B'": 9,
    "Quinto Grado 'A'": 10,
    "Quinto Grado 'B'": 11,
    "Sexto Grado 'Única'": 12,
    "Inicial 1 'A'": 13,
    "Inicial 2 'A'": 14,
    "Inicial 3 'A'": 15
  }
};

/**
 * Mapeo pregunta → campo del backend.
 *  - `contiene`: fragmentos del título de la pregunta (comparados en minúsculas,
 *    sin acentos, sin signos y sin palabras vacías: "N° de cuenta" ≡ "n cuenta"),
 *    gana la PRIMERA coincidencia.
 *  - `campo`: clave del payload del backend (anidados como 'direccion.calle').
 *  - `tipo` (opcional): 'fecha' | 'booleano' → conversión especial.
 * Si agregas una pregunta al form, añade aquí su entrada (o corre listarPreguntas()).
 */
var MAPEO = [
  // --- Datos personales del alumno ---
  { contiene: ['tipo documento'], campo: 'tipo_documento_identidad' },
  { contiene: ['numero documento'], campo: 'numero_documento_identidad' },
  { contiene: ['cedula escolar'], campo: 'cedula_escolar' },
  { contiene: ['primer nombre'], campo: 'primer_nombre' },
  { contiene: ['segundo nombre'], campo: 'segundo_nombre' },
  { contiene: ['primer apellido'], campo: 'primer_apellido' },
  { contiene: ['segundo apellido'], campo: 'segundo_apellido' },
  { contiene: ['fecha nacimiento'], campo: 'fecha_nacimiento', tipo: 'fecha' },
  { contiene: ['genero'], campo: 'genero' },
  { contiene: ['lugar nacimiento'], campo: 'lugar_nacimiento' },
  { contiene: ['nacionalidad'], campo: 'nacionalidad' },

  // --- Lugar de nacimiento administrativo (estado/municipio/parroquia) ---
  { contiene: ['entidad federal', 'estado de nacimiento'], campo: 'entidad_federal_nacimiento' },
  { contiene: ['municipio de nacimiento', 'municipio nacimiento'], campo: 'municipio_nacimiento' },
  { contiene: ['parroquia'], campo: 'parroquia_nacimiento' },

  // --- Datos médicos y medidas ---
  { contiene: ['grupo sanguineo'], campo: 'grupo_sanguineo' },
  { contiene: ['talla (cm)', 'talla cm', 'talla en cm'], campo: 'talla_cm' },
  { contiene: ['talla camisa'], campo: 'talla_camisa' },
  { contiene: ['talla pantalon'], campo: 'talla_pantalon' },
  { contiene: ['talla zapato'], campo: 'talla_zapato' },
  { contiene: ['peso'], campo: 'peso_kg' },
  { contiene: ['alergias', 'alergico'], campo: 'alergico_a' },
  { contiene: ['tratamiento medico'], campo: 'tratamiento_medico' },
  { contiene: ['condicion fisica'], campo: 'condicion_fisica' },
  { contiene: ['apoyo escolar'], campo: 'apoyo_escolar', tipo: 'booleano' },
  { contiene: ['vacunas'], campo: 'vacunas_completas', tipo: 'booleano' },
  { contiene: ['tipo de discapacidad'], campo: 'tipo_discapacidad' },
  { contiene: ['discapacidad'], campo: 'discapacidad', tipo: 'booleano' },

  // --- Carnet de la Patria ---
  { contiene: ['codigo carnet', 'codigo de carnet'], campo: 'carnet_patria_codigo' },
  { contiene: ['serial carnet', 'serial de carnet'], campo: 'carnet_patria_serial' },

  // --- Pagos y cuenta (¡referencia bancaria ANTES que "referencia" a secas!) ---
  { contiene: ['referencia bancaria'], campo: 'referencia_bancaria' },
  { contiene: ['n de cuenta', 'numero de cuenta'], campo: 'numero_cuenta' },
  { contiene: ['tipo de cuenta'], campo: 'tipo_cuenta' },
  { contiene: ['banco'], campo: 'banco' },
  { contiene: ['monto'], campo: 'monto_pago' },

  // --- Dirección de residencia ---
  { contiene: ['calle'], campo: 'direccion.calle' },
  { contiene: ['ciudad', 'municipio de residencia', 'municipio residencia'], campo: 'direccion.ciudad' },
  { contiene: ['estado civil'], campo: 'estado_civil_padres' },
  { contiene: ['estado'], campo: 'direccion.estado' },
  { contiene: ['referencia'], campo: 'direccion.referencia' },

  // --- Datos familiares ---
  { contiene: ['tipo de vivienda'], campo: 'tipo_vivienda' },
  { contiene: ['profesion madre'], campo: 'profesion_madre' },
  { contiene: ['profesion padre'], campo: 'profesion_padre' },
  { contiene: ['hermanos'], campo: 'numero_hermanos' },
  { contiene: ['planter'], campo: 'numero_en_el_planter' },
  { contiene: ['ingreso familiar'], campo: 'ingreso_familiar' },
  { contiene: ['observaciones', 'observacion'], campo: 'observaciones' },

  // --- Grupo académico (¡el último! "grupo" solo no pisa "grupo sanguineo") ---
  { contiene: ['grupo academico', 'grupo'], campo: 'id_grupo' }
];

/**
 * Disparador principal: ejecútalo con un disparador INSTALABLE
 * (⏰ Disparadores → Añadir disparador → Evento: Al enviar formulario).
 */
function alEnviarFormulario(e) {
  if (!e || !e.response) {
    Logger.log('⚠ Esta función necesita una respuesta de formulario (usa un disparador "Al enviar formulario").');
    return;
  }

  var datos = construirPayload_(e.response.getItemResponses());

  // Validación mínima ANTES de llamar al backend (mismos requeridos del webhook)
  var requeridos = ['primer_nombre', 'primer_apellido', 'numero_documento_identidad', 'cedula_escolar', 'fecha_nacimiento'];
  var faltantes = requeridos.filter(function (campo) { return !datos[campo]; });
  if (faltantes.length > 0) {
    Logger.log('✖ FORMULARIO INCOMPLETO, no se envía. Faltan: ' + faltantes.join(', '));
    return;
  }

  var opciones = {
    method: 'post',
    contentType: 'application/json',
    headers: { 'X-Webhook-Token': CONFIG.TOKEN },
    payload: JSON.stringify(datos),
    muteHttpExceptions: true
  };

  try {
    var r = UrlFetchApp.fetch(CONFIG.URL_WEBHOOK, opciones);
    var codigo = r.getResponseCode();
    var cuerpo = r.getContentText();
    Logger.log('Backend respondió ' + codigo + ': ' + cuerpo);

    if (codigo === 201) {
      var json = JSON.parse(cuerpo);
      Logger.log('✔ Alumno #' + json.alumno_id +
        (json.inscripcion_id ? ' | Inscripción #' + json.inscripcion_id : ' | Sin inscripción (grupo no reconocido)'));
    } else if (codigo === 403) {
      Logger.log('✖ Token inválido: revisa CONFIG.TOKEN (WEBHOOK_SECRET_TOKEN del .env).');
    } else if (codigo === 400) {
      Logger.log('✖ El backend rechazó los datos (revisa campos requeridos o duplicados).');
    }
  } catch (error) {
    Logger.log('✖ Fallo de conexión con el backend: ' + error.toString());
  }
}

/** Convierte las respuestas del form en el payload PLANO del backend. */
function construirPayload_(respuestas) {
  var datos = {};
  for (var i = 0; i < respuestas.length; i++) {
    var titulo = respuestas[i].getItem().getTitle();
    var respuesta = respuestas[i].getResponse();
    var entrada = resolverCampo_(titulo);
    if (!entrada) continue; // preguntas fuera de MAPEO: se ignoran

    if (entrada.campo === 'id_grupo') {
      var idGrupo = CONFIG.GRUPOS[String(respuesta).trim()];
      if (idGrupo) {
        datos.id_grupo = idGrupo;
      } else {
        Logger.log('⚠ Grupo "' + respuesta + '" no está en CONFIG.GRUPOS → alumno SIN inscripción.');
      }
      continue;
    }

    var valor = normalizarRespuesta_(entrada, respuesta);
    if (entrada.campo.indexOf('direccion.') === 0) {
      var clave = entrada.campo.split('.')[1];
      datos.direccion = datos.direccion || {};
      if (valor !== '') datos.direccion[clave] = valor;
    } else {
      datos[entrada.campo] = valor;
    }
  }
  return datos;
}

/** Busca en MAPEO la PRIMERA entrada cuyo fragmento coincida con el título. */
function resolverCampo_(titulo) {
  var t = normalizar_(titulo);
  for (var i = 0; i < MAPEO.length; i++) {
    for (var j = 0; j < MAPEO[i].contiene.length; j++) {
      if (t.indexOf(normalizar_(MAPEO[i].contiene[j])) !== -1) {
        return MAPEO[i];
      }
    }
  }
  return null;
}

/** Palabras vacías que se ignoran al comparar ("Tipo DE documento" ≡ "Tipo documento"). */
var PALABRAS_VACIAS_ = ['de', 'del', 'la', 'el', 'los', 'las', 'y', 'en', 'con', 'por', 'para', 'al'];

/**
 * Normaliza texto para comparar títulos y fragmentos:
 * minúsculas, sin acentos, sin signos/puntuación, sin palabras vacías
 * y con espacios simples. Ej: '¿N° de cuenta?' → 'n cuenta'.
 */
function normalizar_(texto) {
  var limpio = String(texto)
    .toLowerCase()
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .replace(/[^a-z0-9]+/g, ' ')
    .replace(/\s+/g, ' ')
    .trim();
  var palabras = limpio.split(' ').filter(function (p) {
    return p !== '' && PALABRAS_VACIAS_.indexOf(p) === -1;
  });
  return palabras.join(' ');
}

/**
 * Convierte la respuesta cruda al formato que espera el backend:
 *  - fechas  → 'yyyy-MM-dd'
 *  - booleanos → true/false reales
 *  - varias opciones (checkbox) → 'a, b'
 */
function normalizarRespuesta_(entrada, respuesta) {
  if (respuesta === null || respuesta === undefined) return '';
  if (Array.isArray(respuesta)) respuesta = respuesta.join(', ');
  var texto = String(respuesta).trim();

  if (entrada.tipo === 'fecha') return convertirFechaISO_(texto);
  if (entrada.tipo === 'booleano') {
    var t = normalizar_(texto);
    return (t === 'si' || t === 'true' || t === '1' || t === 's');
  }
  return texto;
}

/**
 * '14/10/2015' | '10/14/2015' | '2015-10-14' → '2015-10-14'.
 * Google Forms devuelve fechas con '/' (mes primero salvo que el primer
 * número sea >12); el backend solo acepta ISO de forma inequívoca.
 */
function convertirFechaISO_(valor) {
  if (/^\d{4}-\d{2}-\d{2}$/.test(valor)) return valor;
  var p = valor.split('/');
  if (p.length !== 3) return valor; // formato desconocido: lo manda tal cual (el backend valida)
  var a = parseInt(p[0], 10), b = parseInt(p[1], 10), anio = parseInt(p[2], 10);
  var mes = a, dia = b;
  if (a > 12) { dia = a; mes = b; } // venía dd/MM/yyyy
  return anio + '-' + ('0' + mes).slice(-2) + '-' + ('0' + dia).slice(-2);
}

/**
 * DIAGNÓSTICO: ejecuta esta función desde el editor (con el proyecto
 * vinculado al formulario) para ver cada pregunta y su campo mapeado.
 */
function listarPreguntas() {
  var form = FormApp.getActiveForm();
  if (!form) {
    Logger.log('⚠ No hay formulario activo: este proyecto debe estar vinculado al Google Form (⋮ → Script editor desde el form).');
    return;
  }
  var items = form.getItems();
  for (var i = 0; i < items.length; i++) {
    var titulo = items[i].getTitle();
    var entrada = resolverCampo_(titulo);
    Logger.log('[' + items[i].getType() + '] "' + titulo + '" → ' +
      (entrada ? entrada.campo : '*** SIN MAPEAR ***'));
  }
  Logger.log('Total preguntas: ' + items.length + '. Ajusta MAPEO si algo sale raro.');
}



