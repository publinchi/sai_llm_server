# SAI LLM Server Documentation

## 📑 Tabla de Contenido

- [📋 Descripción General](#-descripción-general)
- [🏗️ Arquitectura](#️-arquitectura)
- [🚀 Inicio Rápido](#-inicio-rápido)
    - [Prerrequisitos](#prerrequisitos)
    - [Instalación](#instalación)
        - [Opción 1: Docker Compose (Desarrollo/Single Node)](#opción-1-docker-compose-desarrollosingle-node)
        - [Opción 2: Docker Stack (Producción/Swarm)](#opción-2-docker-stack-producciónswarm)
- [📁 Estructura de Archivos](#-estructura-de-archivos)
- [⚙️ Configuración](#️-configuración)
    - [Variables de Entorno](#variables-de-entorno)
    - [Diferencias entre Docker Compose y Docker Stack](#diferencias-entre-docker-compose-y-docker-stack)
    - [Autenticación Dual con API Key Personalizada](#autenticación-dual-con-api-key-personalizada)
- [🔌 Uso del API](#-uso-del-api)
    - [Endpoint](#endpoint)
    - [Ejemplo de Request](#ejemplo-de-request)
    - [Ejemplo con API Key Personalizada](#ejemplo-con-api-key-personalizada)
    - [Ejemplo con Streaming](#ejemplo-con-streaming)
    - [Respuesta](#respuesta)
- [🔍 Características Especiales](#-características-especiales)
- [📊 Monitoreo](#-monitoreo)
- [🐳 Docker](#-docker)
    - [Comandos Útiles - Docker Compose](#comandos-útiles---docker-compose)
    - [Comandos Útiles - Docker Stack](#comandos-útiles---docker-stack)
- [🔐 Gestión de Secrets (Docker Swarm)](#-gestión-de-secrets-docker-swarm)
- [🏗️ Configuración de Placement (Docker Swarm)](#️-configuración-de-placement-docker-swarm)
- [🔧 Desarrollo](#-desarrollo)
- [🛠️ Troubleshooting](#️-troubleshooting)
- [📝 Notas Importantes](#-notas-importantes)
- [🤝 Contribuir](#-contribuir)
- [📄 Licencia](#-licencia)
- [☕ Apoya este Proyecto](#-apoya-este-proyecto)
- [📞 Soporte](#-soporte)

---

## 📋 Descripción General

SAI LLM Server es un proxy personalizado que integra la API de SAI (SAI Applications) con LiteLLM, permitiendo usar modelos de SAI a través de una interfaz compatible con OpenAI. Soporta autenticación por usuario mediante API Keys personalizadas, con fallback automático a credenciales del sistema.

## 🏗️ Arquitectura

```
Cliente (OpenAI API) → LiteLLM Proxy → SAI Handler → SAI API
                              ↓
                    [user_api_key opcional]
                              ↓
                    [SAI_KEY/SAI_COOKIE fallback]
```

El servidor actúa como intermediario entre clientes que usan la API de OpenAI y el servicio SAI, manejando:
- **Autenticación por usuario** con API Keys personalizadas
- Autenticación dual del sistema (API Key + Cookie)
- Conversión de formatos de mensajes
- Streaming de respuestas
- Manejo de errores y reintentos
- Logging detallado con trazabilidad por request

## 🚀 Inicio Rápido

### Prerrequisitos

- Docker y Docker Compose instalados
- Credenciales de SAI (API Key y/o Cookie del sistema)
- Template ID de SAI
- **Para Docker Swarm**: Cluster de Docker Swarm configurado

### Instalación

#### Opción 1: Docker Compose (Desarrollo/Single Node)

1. **Clonar o crear el proyecto con los archivos necesarios**

2. **Crear archivo `.env` con las credenciales:**

```env
SAI_KEY=tu_api_key_sistema_aqui
SAI_COOKIE=tu_cookie_sistema_aqui
SAI_TEMPLATE_ID=tu_template_id_aqui
SAI_URL=tu_url_aqui
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

#### Opción 2: Docker Stack (Producción/Swarm)

1. **Crear los secrets en Docker Swarm:**

```bash
# Crear secret para SAI_KEY del sistema
echo "tu_api_key_sistema_aqui" | docker secret create SAI_KEY -

# Crear secret para SAI_COOKIE del sistema
echo "tu_cookie_sistema_aqui" | docker secret create SAI_COOKIE -
```

2. **Configurar variables de entorno (sin credenciales sensibles):**

```bash
export SAI_TEMPLATE_ID=tu_template_id_aqui
export SAI_URL=tu_url_aqui
export VERBOSE_LOGGING=false
```

3. **Desplegar el stack:**

```bash
docker stack deploy -c docker-stack.yml sai_llm
```

4. **Verificar el despliegue:**

```bash
# Ver servicios
docker stack services sai_llm

# Ver réplicas
docker service ls

# Ver logs
docker service logs -f sai_llm_sai_llm
```

## 📁 Estructura de Archivos

```
.
├── sai_handler.py       # Handler personalizado para SAI con soporte user_api_key
├── config.yaml          # Configuración de LiteLLM con forward headers
├── Dockerfile           # Imagen Docker
├── docker-compose.yml   # Orquestación para desarrollo
├── docker-stack.yml     # Orquestación para producción (Swarm)
├── .env                 # Variables de entorno (no incluir en git)
└── logs/               # Directorio de logs
    └── sai_handler.log
```

## ⚙️ Configuración

### Variables de Entorno

| Variable | Requerida | Default | Descripción |
|----------|-----------|---------|-------------|
| `SAI_KEY` | Sí* | - | API Key del sistema (fallback) |
| `SAI_COOKIE` | Sí* | - | Cookie de sesión del sistema (fallback) |
| `SAI_TEMPLATE_ID` | Sí | - | ID del template a usar |
| `SAI_URL` | Sí | - | URL base de SAI |
| `VERBOSE_LOGGING` | No | `false` | Activar logs detallados (DEBUG) |
| `REQUEST_TIMEOUT` | No | `600` | Timeout en segundos |
| `MAX_RETRIES` | No | `3` | Reintentos en caso de error |

\* Se requiere al menos `SAI_KEY` o `SAI_COOKIE` como credenciales del sistema

### Diferencias entre Docker Compose y Docker Stack

| Característica | Docker Compose | Docker Stack |
|----------------|----------------|--------------|
| **Uso** | Desarrollo/Testing | Producción |
| **Credenciales** | Variables de entorno en `.env` | Docker Secrets |
| **Réplicas** | 1 instancia | 8 réplicas (configurable) |
| **Logs** | `./logs` (local) | `/var/log` (host) |
| **Alta disponibilidad** | No | Sí |
| **Balanceo de carga** | No | Automático |
| **Placement** | No aplica | Worker nodes solamente |

### Autenticación Dual con API Key Personalizada

El sistema implementa un mecanismo de autenticación de **3 niveles** con fallback automático:

#### Prioridad de Autenticación

1. **API Key personalizada del usuario** (máxima prioridad)
    - Se extrae desde `litellm_params.metadata.user_api_key` (prioridad 1)
    - O desde `headers.user_api_key` (prioridad 2)
    - Se valida y rechaza si está vacía o es "raspberry" (placeholder)
    - **Uso:** Permite que cada usuario use su propia API Key de SAI

2. **API Key del sistema** (`SAI_KEY` configurada en variables de entorno)
    - Se usa cuando no hay `user_api_key` válida
    - Credencial compartida del servidor

3. **Cookie de sesión del sistema** (`SAI_COOKIE` como fallback final)
    - Se usa cuando falla la API Key con error 429 (rate limit)
    - O cuando no hay API Key configurada

#### Comportamiento de Fallback

**Flujo de autenticación:**

```
1. ¿Hay user_api_key válida?
   ├─ SÍ → Usar user_api_key
   │       ├─ ✅ Éxito → Responder
   │       ├─ ❌ Error 401 → Retornar error (NO reintentar)
   │       └─ ⚠️ Error 429 → Reintentar con SAI_COOKIE
   │
   └─ NO → ¿Hay SAI_KEY?
           ├─ SÍ → Usar SAI_KEY
           │       ├─ ✅ Éxito → Responder
           │       ├─ ❌ Error 401 → Retornar error (NO reintentar)
           │       └─ ⚠️ Error 429 → Reintentar con SAI_COOKIE
           │
           └─ NO → Usar SAI_COOKIE directamente
                   ├─ ✅ Éxito → Responder
                   └─ ❌ Error → Retornar error
```

**Reglas importantes:**
- **Error 401 (Unauthorized)**: NO reintenta con otro método (credencial inválida)
- **Error 429 (Rate Limit)**: Reintenta automáticamente con `SAI_COOKIE` si está disponible
- **Validación de user_api_key**: Rechaza valores vacíos o "raspberry"

#### Configuración en config.yaml

```yaml
litellm_settings:
  # Habilitar forwarding de headers del cliente al LLM
  add_user_information_to_llm_headers: true

  model_group_settings:
    forward_client_headers_to_llm_api:
      - sai-model  # Permite que user_api_key llegue al handler
```

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

### Ejemplo con API Key Personalizada

**Opción 1: Usando header `user_api_key`**

```bash
curl -X POST http://localhost:4000/chat/completions \
  -H "Content-Type: application/json" \
  -H "user_api_key: sk-user-abc123xyz" \
  -d '{
    "model": "sai-model",
    "messages": [
      {"role": "user", "content": "Hola"}
    ]
  }'
```

**Opción 2: Usando metadata en el body**

```bash
curl -X POST http://localhost:4000/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "sai-model",
    "messages": [
      {"role": "user", "content": "Hola"}
    ],
    "litellm_params": {
      "metadata": {
        "user_api_key": "sk-user-abc123xyz"
      }
    }
  }'
```

**Nota:** Si no se proporciona `user_api_key`, el sistema usará automáticamente `SAI_KEY` o `SAI_COOKIE` del servidor.

### Ejemplo con Streaming

```bash
curl -X POST http://localhost:4000/chat/completions \
  -H "Content-Type: application/json" \
  -H "user_api_key: sk-user-abc123xyz" \
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

### 1. Autenticación por Usuario con user_api_key

- **Extracción inteligente**: Busca `user_api_key` en headers o metadata
- **Validación estricta**: Rechaza valores vacíos o placeholder "raspberry"
- **Logging detallado**: Registra fuente, longitud y decisión de autenticación
- **Fallback transparente**: Si no hay user_api_key válida, usa credenciales del sistema

**Ejemplo de logs:**

```
🔑 [a1b2c3d4] [AUTH] user_api_key ACEPTADA | Fuente: headers | Longitud: 24 caracteres
🔑 [e5f6g7h8] [AUTH] user_api_key RECHAZADA | Fuente: metadata | Razón: valor vacío
```

### 2. Detección de Plugin de IDE

El handler detecta y procesa automáticamente mensajes envueltos por plugins de IDE (como Cursor), extrayendo el mensaje original del usuario.

**Ejemplo de log:**

```
🔍 [PLUGIN] Mensaje envuelto por IDE detectado | Longitud original: 450 chars | Longitud extraída: 80 chars
🔧 [PLUGIN] [a1b2c3d4] Mensaje #0 procesado | Tipo: user | Contenido extraído: 80 chars
```

### 3. Manejo de Contexto Largo

- **Validación temprana**: Estima tokens antes de enviar (~4 chars/token)
- **Error específico**: Retorna mensaje claro cuando el contexto es demasiado largo
- **Sugerencias**: Proporciona acciones para resolver el problema
- **Límite**: ~128,000 tokens (ajustable según modelo)

### 4. Logging Inteligente con Request ID

Cada request tiene un ID único de 8 caracteres para trazabilidad completa:

```
🔌 [CLIENT → SERVER] [a1b2c3d4] Mensajes recibidos | Total: 3 mensajes
🔑 [a1b2c3d4] [AUTH] user_api_key ACEPTADA | Fuente: headers
🐍 [SERVER → SAI] [a1b2c3d4] Preparando request | API Key: personalizada
🌐 [SERVER → SAI] [a1b2c3d4] Enviando HTTP POST | Auth: API Key (personalizada del usuario)
✅ [SERVER → CLIENT] [a1b2c3d4] Respuesta lista | Latencia: 2.34s | Tokens: 150 → 75
```

**Niveles de logging:**
- `INFO`: Flujo principal de requests (siempre activo)
- `WARNING`: Problemas no críticos
- `ERROR`: Errores que requieren atención
- `DEBUG`: Detalles completos (solo con `VERBOSE_LOGGING=true`)

**Con VERBOSE_LOGGING=true:**
```
[a1b2c3d4] [VERBOSE] Estructura completa de messages:
  [0] role=system | content_length=45 | preview='Eres un asistente útil'
  [1] role=user | content_length=120 | preview='Explica qué es...'
[a1b2c3d4] [VERBOSE] Payload completo: {...}
```

### 5. Manejo de Errores Mejorado

| Error | Código | Acción | user_api_key |
|-------|--------|--------|--------------|
| No autorizado | 401 | Mensaje específico (NO reintenta) | ✅ Soportado |
| Límite excedido | 429 | Fallback automático a Cookie | ✅ Soportado |
| Contexto largo | 500 | Mensaje con sugerencias | ✅ Soportado |
| Error interno SAI | 500 | Mensaje de error específico | ✅ Soportado |
| Timeout | - | Reintento automático | ✅ Soportado |
| Sin respuesta | - | Mensaje de error claro | ✅ Soportado |

**Detalles del manejo de errores:**

- **HTTP 401 (Unauthorized)**:
    - NO reintenta con otro método de autenticación
    - Retorna mensaje específico según el método usado (user_api_key, SAI_KEY o Cookie)
    - Proporciona pasos para resolver el problema
    - **Con user_api_key**: Indica que la API Key del usuario es inválida

- **HTTP 429 (Rate Limit)**:
    - Si falla con user_api_key o SAI_KEY, reintenta automáticamente con Cookie
    - Solo si `SAI_COOKIE` está configurada
    - Registra el cambio de método en los logs
    - **Ejemplo**: "Intento #1 FALLIDO: Rate limit con API Key personalizada → Reintentando con Cookie"

- **HTTP 500 (Prompt Too Long)**:
    - Detecta específicamente el error "prompt is too long"
    - Retorna `finish_reason=length` (compatible con OpenAI)
    - Proporciona sugerencias para reducir el contexto

- **HTTP 500 (Otros)**:
    - Errores internos del servidor SAI no relacionados con tamaño
    - Retorna `finish_reason=error`
    - Mensaje genérico con sugerencias de reintento

## 📊 Monitoreo

### Docker Compose

```bash
# Ver logs en tiempo real
docker-compose logs -f sai_llm

# Ver logs del archivo
tail -f logs/sai_handler.log

# Buscar requests de un usuario específico
grep "user_api_key ACEPTADA" logs/sai_handler.log

# Ver solo errores de autenticación
grep "HTTP 401" logs/sai_handler.log
```

### Docker Stack

```bash
# Ver logs del servicio
docker service logs -f sai_llm_sai_llm

# Ver logs de una réplica específica
docker service ps sai_llm_sai_llm
docker logs -f <container_id>

# Ver logs del host (todas las réplicas)
tail -f /var/log/sai_handler.log

# Filtrar por request ID
grep "\[a1b2c3d4\]" /var/log/sai_handler.log
```

### Métricas Incluidas en Logs

- 🆔 Request ID único (8 caracteres)
- 🔑 Método de autenticación usado (user_api_key, SAI_KEY, Cookie)
- ⏱️ Latencia de respuesta
- 🔢 Tokens (prompt/completion/total)
- 🚀 Velocidad (tokens/segundo)
- 📏 Tamaño de mensajes
- 🔌 Detección de plugin de IDE
- 📊 Distribución de roles en mensajes

## 🐳 Docker

### Construir Imagen Localmente

```bash
docker build -t sai_llm_server .
```

### Usar Imagen desde Docker Hub

```bash
docker pull cobistopaz/sai_llm_server
```

### Comandos Útiles - Docker Compose

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

# Ver logs con filtro
docker-compose logs -f | grep "user_api_key"
```

### Comandos Útiles - Docker Stack

```bash
# Desplegar stack
docker stack deploy -c docker-stack.yml sai_llm

# Listar stacks
docker stack ls

# Ver servicios del stack
docker stack services sai_llm

# Ver tareas/réplicas
docker service ps sai_llm_sai_llm

# Escalar servicio
docker service scale sai_llm_sai_llm=16

# Actualizar servicio
docker service update --image cobistopaz/sai_llm_server:latest sai_llm_sai_llm

# Ver logs
docker service logs -f sai_llm_sai_llm

# Eliminar stack
docker stack rm sai_llm
```

## 🔐 Gestión de Secrets (Docker Swarm)

### Crear Secrets

```bash
# Desde archivo
docker secret create SAI_KEY /path/to/sai_key.txt
docker secret create SAI_COOKIE /path/to/sai_cookie.txt

# Desde stdin
echo "mi_api_key_sistema" | docker secret create SAI_KEY -
echo "mi_cookie_sistema" | docker secret create SAI_COOKIE -
```

**Nota:** Los secrets `SAI_KEY` y `SAI_COOKIE` son las credenciales del sistema (fallback). Las `user_api_key` se envían por request y no se almacenan en secrets.

### Listar Secrets

```bash
docker secret ls
```

### Inspeccionar Secret (sin ver el valor)

```bash
docker secret inspect SAI_KEY
```

### Eliminar Secret

```bash
# Primero eliminar el stack que lo usa
docker stack rm sai_llm

# Luego eliminar el secret
docker secret rm SAI_KEY
docker secret rm SAI_COOKIE
```

### Actualizar Secret

```bash
# Los secrets son inmutables, hay que crear uno nuevo
docker secret create SAI_KEY_v2 /path/to/new_key.txt

# Actualizar el servicio para usar el nuevo secret
# (requiere modificar docker-stack.yml)
```

## 🏗️ Configuración de Placement (Docker Swarm)

El `docker-stack.yml` incluye restricciones de placement para controlar dónde se despliegan las réplicas:

```yaml
placement:
  constraints:
    - node.labels.db != true        # No en nodos de base de datos
    - node.labels.type != master    # No en nodos master
    - node.labels.type != test      # No en nodos de testing
    - node.role == worker           # Solo en workers
```

### Etiquetar Nodos

```bash
# Agregar etiqueta a un nodo
docker node update --label-add type=worker <node-id>
docker node update --label-add db=true <node-id>

# Ver etiquetas de un nodo
docker node inspect <node-id> --format '{{.Spec.Labels}}'

# Listar todos los nodos
docker node ls
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
    _extract_user_api_key()           # Extrae y valida user_api_key
    _prepare_messages()               # Procesa mensajes
    _call_sai()                       # Llama a SAI API
    _make_request()                   # HTTP request con auth
    _extract_plugin_wrapped_message() # Detecta plugin IDE
```

### Flujo de Autenticación en el Código

```python
# 1. Extraer user_api_key (si existe)
user_api_key = self._extract_user_api_key(kwargs, request_id)

# 2. Determinar qué API key usar
api_key_to_use = user_api_key if user_api_key else SAI_KEY

# 3. Intentar con API Key
if api_key_to_use:
    response = self._make_request(url, data, use_api_key=True, custom_api_key=api_key_to_use)
    
    # 4. Si falla con 429, reintentar con Cookie
    if response is None and SAI_COOKIE:
        response = self._make_request(url, data, use_api_key=False)
```

### Agregar Nuevas Características

1. Modificar `sai_handler.py`
2. Actualizar `config.yaml` si es necesario
3. Reconstruir imagen: `docker build -t cobistopaz/sai_llm_server .`
4. Publicar imagen: `docker push cobistopaz/sai_llm_server`
5. Actualizar servicio: `docker service update --image cobistopaz/sai_llm_server:latest sai_llm_sai_llm`

## 🛠️ Troubleshooting

### Problema: user_api_key no funciona o es rechazada

**Síntomas:**
- Logs muestran: `user_api_key RECHAZADA | Razón: valor vacío`
- O: `user_api_key RECHAZADA | Razón: valor 'raspberry' (placeholder)`

**Solución:**
1. Verificar que la API Key no esté vacía
2. Asegurarse de que no sea el placeholder "raspberry"
3. Verificar que se esté enviando en el header correcto: `user_api_key`
4. O en el body bajo `litellm_params.metadata.user_api_key`
5. Revisar logs con `VERBOSE_LOGGING=true` para ver el motivo del rechazo
6. Verificar que la API Key sea válida en el panel de SAI

**Ejemplo de log cuando se rechaza:**
```
[a1b2c3d4] [AUTH] user_api_key RECHAZADA | Fuente: headers | Razón: valor vacío
```

**Ejemplo de log cuando se acepta:**
```
🔑 [a1b2c3d4] [AUTH] user_api_key ACEPTADA | Fuente: headers | Longitud: 24 caracteres
```

### Problema: Error 401 con user_api_key

**Síntomas:**
- Logs muestran: `[HTTP 401] Unauthorized | Auth usado: API Key (personalizada del usuario)`
- Respuesta: "La **API Key** proporcionada no es válida o ha expirado"

**Solución:**
1. Verificar que la `user_api_key` del usuario sea válida en SAI
2. Generar una nueva API Key desde el panel de SAI
3. Actualizar la `user_api_key` en el cliente
4. **Nota:** El sistema NO reintentará con credenciales del sistema (comportamiento esperado)

### Problema: SAI_TEMPLATE_ID no configurado

**Solución:**
- **Docker Compose**: Verificar que el archivo `.env` existe y contiene `SAI_TEMPLATE_ID`
- **Docker Stack**: Verificar que la variable está exportada antes de desplegar

### Problema: Error 429 constante

**Solución:**
- Verificar que `SAI_COOKIE` está configurada (secret en Swarm)
- El sistema debería hacer fallback automáticamente
- Revisar logs para confirmar: `Intento #2 EXITOSO con Cookie`

### Problema: Respuestas lentas

**Solución:**
- Reducir `REQUEST_TIMEOUT` si es muy alto
- Verificar logs para identificar cuellos de botella
- Considerar reducir el historial de mensajes
- **En Swarm**: Verificar distribución de réplicas con `docker service ps`
- Revisar métricas de velocidad en logs: `Velocidad: X.X tok/s`

### Problema: "Contexto demasiado largo"

**Solución:**
- Reducir número de mensajes en el historial
- Resumir conversaciones anteriores
- Iniciar nueva conversación
- Revisar logs para ver tamaño estimado: `Tokens estimados: X`

### Problema: Secrets no se actualizan en Docker Swarm

**Solución:**
```bash
# Los secrets son inmutables, crear uno nuevo
docker secret create SAI_KEY_v2 -
# Actualizar docker-stack.yml para usar el nuevo secret
# Redesplegar el stack
docker stack deploy -c docker-stack.yml sai_llm
```

### Problema: Réplicas no se distribuyen correctamente

**Solución:**
```bash
# Verificar etiquetas de nodos
docker node ls
docker node inspect <node-id>

# Verificar constraints en el servicio
docker service inspect sai_llm_sai_llm

# Ver por qué una réplica no se despliega
docker service ps sai_llm_sai_llm --no-trunc
```

### Problema: No se puede acceder a los logs en /var/log

**Solución:**
```bash
# Verificar permisos del directorio
ls -la /var/log

# Verificar que el contenedor puede escribir
docker service logs sai_llm_sai_llm | grep -i "permission denied"

# Ajustar permisos si es necesario
sudo chmod 755 /var/log
```

### Problema: Headers no se están forwarding

**Síntomas:**
- `user_api_key` no llega al handler
- Logs muestran: `user_api_key NO encontrada`

**Solución:**
1. Verificar que `config.yaml` tiene:
```yaml
litellm_settings:
  add_user_information_to_llm_headers: true
  model_group_settings:
    forward_client_headers_to_llm_api:
      - sai-model
```
2. Reiniciar el servicio después de modificar `config.yaml`
3. Activar `VERBOSE_LOGGING=true` para ver los kwargs completos

## 📝 Notas Importantes

1. **Seguridad**:
    - Nunca commitear el archivo `.env` con credenciales
    - En producción, usar siempre Docker Secrets para `SAI_KEY` y `SAI_COOKIE`
    - Los secrets se montan en `/run/secrets/` dentro del contenedor
    - Las `user_api_key` se transmiten por request y no se almacenan

2. **Autenticación**:
    - `user_api_key`: API Key del usuario final (por request)
    - `SAI_KEY`: API Key del sistema (fallback, en secrets/env)
    - `SAI_COOKIE`: Cookie del sistema (fallback final, en secrets/env)
    - Prioridad: user_api_key > SAI_KEY > SAI_COOKIE

3. **Logs**:
    - Los logs rotan automáticamente (máx 5MB por archivo, 3 backups)
    - **Docker Compose**: Logs en `./logs` (directorio local)
    - **Docker Stack**: Logs en `/var/log` (host del nodo)
    - Cada request tiene un ID único de 8 caracteres para trazabilidad

4. **Zona Horaria**: Configurada para `America/Guayaquil` (modificar en Dockerfile si es necesario)

5. **Puerto**: Por defecto usa `4000` (modificar en archivos de compose si hay conflicto)

6. **Réplicas**:
    - Docker Compose: 1 instancia
    - Docker Stack: 8 réplicas (ajustar según necesidad)

7. **Alta Disponibilidad**:
    - Docker Stack distribuye automáticamente las réplicas
    - Si un nodo falla, las réplicas se redistribuyen
    - El balanceo de carga es automático

8. **Logging Verboso**:
    - `VERBOSE_LOGGING=false`: Solo logs INFO, WARNING, ERROR
    - `VERBOSE_LOGGING=true`: Incluye logs DEBUG con detalles completos

## 🤝 Contribuir

Para contribuir al proyecto:

1. Fork del repositorio
2. Crear rama feature (`git checkout -b feature/nueva-caracteristica`)
3. Commit cambios (`git commit -am 'Agregar nueva característica'`)
4. Push a la rama (`git push origin feature/nueva-caracteristica`)
5. Crear Pull Request

## 📄 Licencia

Este proyecto está licenciado bajo la **MIT License**, la misma licencia que utiliza [LiteLLM](https://github.com/BerriAI/litellm).

### MIT License

```
MIT License

Copyright (c) 2025 Publio Estupiñán

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

**Esto significa que puedes:**
- ✅ Usar el software comercialmente
- ✅ Modificar el software
- ✅ Distribuir el software
- ✅ Usar el software de forma privada
- ✅ Sublicenciar

**Con las siguientes condiciones:**
- 📋 Incluir el aviso de copyright y licencia en todas las copias
- ⚠️ El software se proporciona "tal cual", sin garantías

## ☕ Apoya este Proyecto

Si este proyecto te ha sido útil y te ha ahorrado tiempo, considera invitarme un café para apoyar su desarrollo y mantenimiento continuo.

<a href="https://buymeacoffee.com/publinchi4" target="_blank">
  <img src="https://cdn.buymeacoffee.com/buttons/v2/default-yellow.png" alt="Buy Me A Coffee" style="height: 60px !important;width: 217px !important;" >
</a>

**¿Por qué apoyar?**
- 🚀 Mantiene el proyecto activo y actualizado
- 🐛 Permite dedicar tiempo a corregir bugs
- ✨ Ayuda a implementar nuevas características
- 📚 Mejora la documentación
- 💬 Proporciona mejor soporte a la comunidad

**Otras formas de apoyar:**
- ⭐ Dale una estrella al repositorio en GitHub
- 🐛 Reporta bugs o sugiere mejoras
- 📖 Mejora la documentación
- 🔀 Contribuye con código
- 📢 Comparte el proyecto con otros

¡Cada contribución, por pequeña que sea, es muy apreciada! 🙏

## 📞 Soporte

Para reportar problemas o solicitar características:
- Revisar logs en `logs/sai_handler.log` (Compose) o `/var/log/sai_handler.log` (Stack)
- Activar `VERBOSE_LOGGING=true` para más detalles
- Buscar por request ID en logs para trazabilidad completa
- 🐙 GitHub: https://github.com/publinchi/sai_llm_server
- ☕ Buy Me a Coffee: https://buymeacoffee.com/publinchi4

---

**Versión:** 1.0.0  
**Última actualización:** 2025  
**Autor:** Publio Estupiñán  
**Licencia:** MIT (Compatible con LiteLLM)  
**Nuevas características v1.0.0:**
- ✨ Soporte para `user_api_key` personalizada por usuario
- 🔍 Request ID único para trazabilidad completa
- 📊 Logging mejorado con métricas detalladas
- 🔐 Autenticación de 3 niveles con fallback inteligente
- 🔌 Detección automática de plugins de IDE
- ⚡ Optimización de rendimiento y manejo de errores