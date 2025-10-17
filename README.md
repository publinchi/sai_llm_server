# SAI LLM Server Documentation

## 📋 Descripción General

SAI LLM Server es un proxy personalizado que integra la API de SAI (SAI Applications) con LiteLLM, permitiendo usar modelos de SAI a través de una interfaz compatible con OpenAI.

## 🏗️ Arquitectura

```
Cliente (OpenAI API) → LiteLLM Proxy → SAI Handler → SAI API
```

El servidor actúa como intermediario entre clientes que usan la API de OpenAI y el servicio SAI, manejando:
- Autenticación dual (API Key + Cookie)
- Conversión de formatos de mensajes
- Streaming de respuestas
- Manejo de errores y reintentos
- Logging detallado

## 🚀 Inicio Rápido

### Prerrequisitos

- Docker y Docker Compose instalados
- Credenciales de SAI (API Key y/o Cookie)
- Template ID de SAI

### Instalación

1. **Clonar o crear el proyecto con los archivos necesarios**

2. **Crear archivo `.env` con las credenciales:**

```env
SAI_KEY=tu_api_key_aqui
SAI_COOKIE=tu_cookie_aqui
SAI_TEMPLATE_ID=68ed29013854891e3227d338
SAI_URL=https://sai-library.saiapplications.com
VERBOSE_LOGGING=false
REQUEST_TIMEOUT=600
MAX_RETRIES=3
```

3. **Iniciar el servidor:**

```bash
docker-compose up -d
```

4. **Verificar que está funcionando:**

```bash
curl http://localhost:4000/health
```

## 📁 Estructura de Archivos

```
.
├── sai_handler.py       # Handler personalizado para SAI
├── config.yaml          # Configuración de LiteLLM
├── Dockerfile           # Imagen Docker
├── docker-compose.yml   # Orquestación de contenedores
├── .env                 # Variables de entorno (no incluir en git)
└── logs/               # Directorio de logs (creado automáticamente)
    └── sai_handler.log
```

## ⚙️ Configuración

### Variables de Entorno

| Variable | Requerida | Default | Descripción |
|----------|-----------|---------|-------------|
| `SAI_KEY` | Sí* | - | API Key de SAI |
| `SAI_COOKIE` | Sí* | - | Cookie de sesión de SAI |
| `SAI_TEMPLATE_ID` | Sí | - | ID del template a usar |
| `SAI_URL` | No | `https://sai-library.saiapplications.com` | URL base de SAI |
| `VERBOSE_LOGGING` | No | `false` | Activar logs detallados |
| `REQUEST_TIMEOUT` | No | `600` | Timeout en segundos |
| `MAX_RETRIES` | No | `3` | Reintentos en caso de error |

\* Se requiere al menos `SAI_KEY` o `SAI_COOKIE`

### Autenticación Dual

El sistema implementa un mecanismo de fallback:

1. **Intenta primero con API Key** (si está configurada)
2. **Si falla con error 429** (límite excedido), reintenta con Cookie
3. **Si solo hay Cookie**, la usa directamente

## 🔌 Uso del API

### Endpoint

```
POST http://localhost:4000/chat/completions
```

### Ejemplo de Request

```bash
curl -X POST http://localhost:4000/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "sai-model",
    "messages": [
      {"role": "system", "content": "Eres un asistente útil"},
      {"role": "user", "content": "Hola, ¿cómo estás?"}
    ],
    "stream": false
  }'
```

### Ejemplo con Streaming

```bash
curl -X POST http://localhost:4000/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "sai-model",
    "messages": [
      {"role": "user", "content": "Escribe un poema corto"}
    ],
    "stream": true
  }'
```

### Respuesta

```json
{
  "id": "chatcmpl-abc123",
  "object": "chat.completion",
  "created": 1234567890,
  "model": "sai-model",
  "choices": [
    {
      "index": 0,
      "message": {
        "role": "assistant",
        "content": "¡Hola! Estoy bien, gracias por preguntar..."
      },
      "finish_reason": "stop"
    }
  ],
  "usage": {
    "prompt_tokens": 25,
    "completion_tokens": 50,
    "total_tokens": 75
  }
}
```

## 🔍 Características Especiales

### 1. Detección de Plugin de IDE

El handler detecta y procesa automáticamente mensajes envueltos por plugins de IDE (como Cursor), extrayendo el mensaje original del usuario.

### 2. Manejo de Contexto Largo

- **Validación temprana**: Estima tokens antes de enviar
- **Error específico**: Retorna mensaje claro cuando el contexto es demasiado largo
- **Sugerencias**: Proporciona acciones para resolver el problema

### 3. Logging Inteligente

```
🔌 [CLIENT → SERVER] - Mensajes recibidos
🐍 [SERVER → SAI] - Request preparado
🌐 [SERVER → SAI] - Enviando request
✅ [SERVER → CLIENT] - Respuesta lista
```

**Niveles de logging:**
- `INFO`: Flujo principal de requests
- `WARNING`: Problemas no críticos
- `ERROR`: Errores que requieren atención
- `DEBUG`: Detalles completos (solo con `VERBOSE_LOGGING=true`)

### 4. Manejo de Errores

| Error | Código | Acción |
|-------|--------|--------|
| Límite excedido | 429 | Fallback a Cookie |
| Contexto largo | 500 | Mensaje con sugerencias |
| Timeout | - | Reintento automático |
| Sin respuesta | - | Mensaje de error claro |

## 📊 Monitoreo

### Ver Logs en Tiempo Real

```bash
docker-compose logs -f sai_llm
```

### Ver Logs del Archivo

```bash
tail -f logs/sai_handler.log
```

### Métricas Incluidas en Logs

- ⏱️ Latencia de respuesta
- 🔢 Tokens (prompt/completion/total)
- 🚀 Velocidad (tokens/segundo)
- 📏 Tamaño de mensajes
- 🔑 Método de autenticación usado

## 🐳 Docker

### Construir Imagen Localmente

```bash
docker build -t sai_llm_server .
```

### Usar Imagen desde Docker Hub

```bash
docker pull cobistopaz/sai_llm_server
```

### Comandos Útiles

```bash
# Iniciar
docker-compose up -d

# Detener
docker-compose down

# Reiniciar
docker-compose restart

# Ver estado
docker-compose ps

# Ver logs
docker-compose logs -f
```

## 🔧 Desarrollo

### Estructura del Handler (`sai_handler.py`)

```python
class SAILLM(CustomLLM):
    # Métodos principales
    completion()           # Síncrono
    acompletion()         # Asíncrono
    astreaming()          # Streaming asíncrono
    
    # Métodos privados
    _prepare_messages()   # Procesa mensajes
    _call_sai()          # Llama a SAI API
    _make_request()      # HTTP request
    _extract_plugin_wrapped_message()  # Detecta plugin IDE
```

### Agregar Nuevas Características

1. Modificar `sai_handler.py`
2. Actualizar `config.yaml` si es necesario
3. Reconstruir imagen: `docker-compose build`
4. Reiniciar: `docker-compose up -d`

## 🛠️ Troubleshooting

### Problema: "SAI_TEMPLATE_ID no está configurado"

**Solución:** Verificar que el archivo `.env` existe y contiene `SAI_TEMPLATE_ID`

### Problema: Error 429 constante

**Solución:**
- Verificar que `SAI_COOKIE` está configurada
- El sistema debería hacer fallback automáticamente

### Problema: Respuestas lentas

**Solución:**
- Reducir `REQUEST_TIMEOUT` si es muy alto
- Verificar logs para identificar cuellos de botella
- Considerar reducir el historial de mensajes

### Problema: "Contexto demasiado largo"

**Solución:**
- Reducir número de mensajes en el historial
- Resumir conversaciones anteriores
- Iniciar nueva conversación

## 📝 Notas Importantes

1. **Seguridad**: Nunca commitear el archivo `.env` con credenciales
2. **Logs**: Los logs rotan automáticamente (máx 5MB por archivo, 3 backups)
3. **Zona Horaria**: Configurada para `America/Guayaquil` (modificar en Dockerfile si es necesario)
4. **Puerto**: Por defecto usa `4000` (modificar en `docker-compose.yml` si hay conflicto)

## 🤝 Contribuir

Para contribuir al proyecto:

1. Fork del repositorio
2. Crear rama feature (`git checkout -b feature/nueva-caracteristica`)
3. Commit cambios (`git commit -am 'Agregar nueva característica'`)
4. Push a la rama (`git push origin feature/nueva-caracteristica`)
5. Crear Pull Request

## 📄 Licencia

☕ **Invítame un café**

Si este proyecto te ha sido útil, considera invitarme un café para apoyar su desarrollo y mantenimiento.

## 📞 Soporte

Para reportar problemas o solicitar características:
- Revisar logs en `logs/sai_handler.log`
- Activar `VERBOSE_LOGGING=true` para más detalles
- https://github.com/publinchi/sai_llm_server

---

**Versión:** 1.0.0  
**Última actualización:** 2025 Publio Estupiñán