# Webhook de Google Forms para Plataforma Escolar

## Endpoint del Webhook

```
POST http://127.0.0.1:8000/api/academico/webhook-google-forms/
```

## Seguridad del Webhook

El webhook está protegido con un token de seguridad que debe enviarse en la cabecera HTTP `X-Webhook-Token`.

**Token actual:** `whk-7f3b9c2e5a8d4f6b0c1e9a7d3b5f2846`

**Para cambiar el token:** Configura la variable de entorno `WEBHOOK_SECRET_TOKEN` en el archivo `.env` de Django:

```bash
WEBHOOK_SECRET_TOKEN=tu-token-seguro-personalizado
```

Y actualiza la constante `webhookToken` en el script de Apps Script con el mismo valor.

Sin el token correcto, o si `WEBHOOK_SECRET_TOKEN` no está definido en el servidor, el webhook retornará un error `403 Forbidden`.

> **Nota de seguridad:** El token del `.env` nunca debe subirse a Git (`.env` está en `.gitignore`). En producción, genera un token aleatorio distinto y compártelo solo con quien administra el script de Apps Script.

## Ejemplo de Código para Google Apps Script

```javascript
function enviarDatosAlumno() {
  // Configuración del endpoint
  const webhookUrl = 'http://127.0.0.1:8000/api/academico/webhook-google-forms/';
  
  // Token de seguridad (debe coincidir con WEBHOOK_SECRET_TOKEN en el .env de Django)
  const webhookToken = 'whk-7f3b9c2e5a8d4f6b0c1e9a7d3b5f2846';
  
  // Obtener datos del formulario de Google
  const form = FormApp.getActiveForm();
  const responses = form.getResponses();
  const latestResponse = responses[responses.length - 1];
  const itemResponses = latestResponse.getItemResponses();
  
  // Mapear respuestas del formulario a los campos del sistema
  const data = {
    // Datos personales
    primer_nombre: obtenerRespuesta(itemResponses, 'Primer Nombre'),
    segundo_nombre: obtenerRespuesta(itemResponses, 'Segundo Nombre'),
    primer_apellido: obtenerRespuesta(itemResponses, 'Primer Apellido'),
    segundo_apellido: obtenerRespuesta(itemResponses, 'Segundo Apellido'),
    
    // Documentos
    tipo_documento_identidad: obtenerRespuesta(itemResponses, 'Tipo de Documento') || 'V',
    numero_documento_identidad: obtenerRespuesta(itemResponses, 'Número de Documento'),
    cedula_escolar: obtenerRespuesta(itemResponses, 'Cédula Escolar'),
    
    // Datos demográficos
    fecha_nacimiento: obtenerRespuesta(itemResponses, 'Fecha de Nacimiento'),
    genero: obtenerRespuesta(itemResponses, 'Género') || 'Masculino',
    nacionalidad: obtenerRespuesta(itemResponses, 'Nacionalidad') || 'Venezolana',
    lugar_nacimiento: obtenerRespuesta(itemResponses, 'Lugar de Nacimiento'),
    
    // Medidas antropométricas
    grupo_sanguineo: obtenerRespuesta(itemResponses, 'Grupo Sanguíneo') || 'O+',
    peso_kg: parseFloat(obtenerRespuesta(itemResponses, 'Peso (kg)')),
    talla_cm: parseFloat(obtenerRespuesta(itemResponses, 'Talla (cm)')),
    talla_camisa: obtenerRespuesta(itemResponses, 'Talla de Camisa'),
    talla_pantalon: obtenerRespuesta(itemResponses, 'Talla de Pantalón'),
    talla_zapato: obtenerRespuesta(itemResponses, 'Talla de Zapato'),
    
    // Datos médicos
    alergico_a: obtenerRespuesta(itemResponses, 'Alergias'),
    tratamiento_medico: obtenerRespuesta(itemResponses, 'Tratamiento Médico'),
    condicion_fisica: obtenerRespuesta(itemResponses, 'Condición Física'),
    discapacidad: obtenerRespuesta(itemResponses, '¿Tiene Discapacidad?') === 'Sí',
    tipo_discapacidad: obtenerRespuesta(itemResponses, 'Tipo de Discapacidad'),
    
    // Datos de inscripción (opcional)
    id_grupo: parseInt(obtenerRespuesta(itemResponses, 'Grupo Académico')),
    monto_pago: parseFloat(obtenerRespuesta(itemResponses, 'Monto de Pago')),
    referencia_bancaria: obtenerRespuesta(itemResponses, 'Referencia Bancaria')
  };
  
  // Enviar datos al webhook
  try {
    const response = UrlFetchApp.fetch(webhookUrl, {
      method: 'post',
      contentType: 'application/json',
      headers: {
        'X-Webhook-Token': webhookToken
      },
      payload: JSON.stringify(data),
      muteHttpExceptions: true
    });
    
    const responseCode = response.getResponseCode();
    const responseBody = response.getContentText();
    
    if (responseCode === 201) {
      const result = JSON.parse(responseBody);
      Logger.log('Alumno creado exitosamente. ID: ' + result.alumno_id);
      return 'Alumno registrado exitosamente. ID: ' + result.alumno_id;
    } else {
      Logger.log('Error: ' + responseBody);
      return 'Error al registrar alumno: ' + responseBody;
    }
  } catch (error) {
    Logger.log('Excepción: ' + error.toString());
    return 'Error de conexión: ' + error.toString();
  }
}

function obtenerRespuesta(itemResponses, tituloPregunta) {
  for (let i = 0; i < itemResponses.length; i++) {
    if (itemResponses[i].getItem().getTitle() === tituloPregunta) {
      return itemResponses[i].getResponse();
    }
  }
  return '';
}

// Configurar el trigger para ejecutar automáticamente cuando se envía el formulario
function configurarTrigger() {
  const form = FormApp.getActiveForm();
  ScriptApp.newTrigger('enviarDatosAlumno')
    .forForm(form)
    .onFormSubmit()
    .create();
}
```

## Estructura del JSON Payload

```json
{
  "primer_nombre": "string (requerido)",
  "segundo_nombre": "string (opcional)",
  "primer_apellido": "string (requerido)",
  "segundo_apellido": "string (opcional)",
  "tipo_documento_identidad": "string (opcional, default: 'V')",
  "numero_documento_identidad": "string (requerido, único)",
  "cedula_escolar": "string (requerido, único)",
  "fecha_nacimiento": "date (YYYY-MM-DD, requerido)",
  "genero": "string (opcional, default: 'Masculino')",
  "nacionalidad": "string (opcional, default: 'Venezolana')",
  "lugar_nacimiento": "string (opcional)",
  "grupo_sanguineo": "string (opcional, default: 'O+')",
  "peso_kg": "number (opcional)",
  "talla_cm": "number (opcional)",
  "talla_camisa": "string (opcional)",
  "talla_pantalon": "string (opcional)",
  "talla_zapato": "string (opcional)",
  "alergico_a": "string (opcional)",
  "tratamiento_medico": "string (opcional)",
  "condicion_fisica": "string (opcional)",
  "discapacidad": "boolean (opcional, default: false)",
  "tipo_discapacidad": "string (opcional)",
  "id_grupo": "integer (opcional)",
  "monto_pago": "number (opcional)",
  "referencia_bancaria": "string (opcional)"
}
```

## Respuestas del Webhook

### Exitoso (201 Created)
```json
{
  "success": true,
  "message": "Alumno creado exitosamente",
  "alumno_id": 8,
  "inscripcion_id": 2
}
```

### Error de Validación (400 Bad Request)
```json
{
  "error": "El campo primer_nombre es requerido"
}
```

### Alumno Duplicado (400 Bad Request)
```json
{
  "error": "Ya existe un alumno con este número de documento"
}
```

### Error del Servidor (500 Internal Server Error)
```json
{
  "error": "Error al procesar la solicitud"
}
```

> El detalle técnico se registra en los logs del servidor (no se expone al cliente).

### Token Inválido o Ausente (403 Forbidden)
```json
{
  "error": "Token de seguridad inválido o no proporcionado"
}
```

## Instrucciones de Configuración

1. **Crear el Google Form** con las preguntas correspondientes a los campos del sistema
2. **Abrir el Editor de Apps Script** en el formulario (Extensiones > Apps Script)
3. **Copiar el código** proporcionado arriba
4. **Verificar el token** `webhookToken` en el script: debe coincidir con `WEBHOOK_SECRET_TOKEN` del `.env` de Django
5. **Personalizar los títulos de las preguntas** en la función `obtenerRespuesta` para que coincidan con tu formulario
6. **Configurar el trigger** ejecutando la función `configurarTrigger()`
7. **Guardar y probar** enviando una respuesta al formulario

## Endpoint del Comprobante de Inscripción (PDF)

```
GET /api/academico/inscripciones/{id}/pdf/
```

Genera en PDF los datos del plantel, datos personales del alumno, tallas de uniforme, datos médicos y el grupo académico asignado.

## Notas Importantes

- El webhook permite acceso público (`AllowAny`) para facilitar la integración con Google Apps Script
- Si se incluye `id_grupo`, se crea automáticamente la inscripción del alumno en ese grupo
- Los campos marcados como "requerido" deben estar presentes en el payload
- Los campos de documento (`numero_documento_identidad` y `cedula_escolar`) deben ser únicos
- La fecha de inscripción se genera automáticamente si no se proporciona
