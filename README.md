# SAI LLM Server Documentation

## 📑 Índice de Contenidos

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
    - [Autenticación Dual](#autenticación-dual)
- [🔌 Uso del API](#-uso-del-api)
    - [Endpoint](#endpoint)
    - [Ejemplo de Request](#ejemplo-de-request)
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
- **Para Docker Swarm**: Cluster de Docker Swarm configurado

### Instalación

#### Opción 1: Docker Compose (Desarrollo/Single Node)

1. **Clonar o crear el proyecto con los archivos necesarios**

2. **Crear archivo `.env` con las credenciales:**

```env
SAI_KEY=tu_api_key_aqui
SAI_COOKIE=tu_cookie_aqui
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
# Crear secret para SAI_KEY
echo "tu_api_key_aqui" | docker secret create SAI_KEY -

# Crear secret para SAI_COOKIE
echo "tu_cookie_aqui" | docker secret create SAI_COOKIE -
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
├── sai_handler.py       # Handler personalizado para SAI
├── config.yaml          # Configuración de LiteLLM
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
| `SAI_KEY` | Sí* | - | API Key de SAI |
| `SAI_COOKIE` | Sí* | - | Cookie de sesión de SAI |
| `SAI_TEMPLATE_ID` | Sí | - | ID del template a usar |
| `SAI_URL` | Sí | - | URL base de SAI |
| `VERBOSE_LOGGING` | No | `false` | Activar logs detallados |
| `REQUEST_TIMEOUT` | No | `600` | Timeout en segundos |
| `MAX_RETRIES` | No | `3` | Reintentos en caso de error |

\* Se requiere al menos `SAI_KEY` o `SAI_COOKIE`

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

### Docker Compose

```bash
# Ver logs en tiempo real
docker-compose logs -f sai_llm

# Ver logs del archivo
tail -f logs/sai_handler.log
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
echo "mi_api_key" | docker secret create SAI_KEY -
echo "mi_cookie" | docker secret create SAI_COOKIE -
```

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
    _prepare_messages()   # Procesa mensajes
    _call_sai()          # Llama a SAI API
    _make_request()      # HTTP request
    _extract_plugin_wrapped_message()  # Detecta plugin IDE
```

### Agregar Nuevas Características

1. Modificar `sai_handler.py`
2. Actualizar `config.yaml` si es necesario
3. Reconstruir imagen: `docker build -t cobistopaz/sai_llm_server .`
4. Publicar imagen: `docker push cobistopaz/sai_llm_server`
5. Actualizar servicio: `docker service update --image cobistopaz/sai_llm_server:latest sai_llm_sai_llm`

## 🛠️ Troubleshooting

### Problema: "SAI_TEMPLATE_ID no está configurado"

**Solución:**
- **Docker Compose**: Verificar que el archivo `.env` existe y contiene `SAI_TEMPLATE_ID`
- **Docker Stack**: Verificar que la variable está exportada antes de desplegar

### Problema: Error 429 constante

**Solución:**
- Verificar que `SAI_COOKIE` está configurada (secret en Swarm)
- El sistema debería hacer fallback automáticamente

### Problema: Respuestas lentas

**Solución:**
- Reducir `REQUEST_TIMEOUT` si es muy alto
- Verificar logs para identificar cuellos de botella
- Considerar reducir el historial de mensajes
- **En Swarm**: Verificar distribución de réplicas con `docker service ps`

### Problema: "Contexto demasiado largo"

**Solución:**
- Reducir número de mensajes en el historial
- Resumir conversaciones anteriores
- Iniciar nueva conversación

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

## 📝 Notas Importantes

1. **Seguridad**:
    - Nunca commitear el archivo `.env` con credenciales
    - En producción, usar siempre Docker Secrets
    - Los secrets se montan en `/run/secrets/` dentro del contenedor

2. **Logs**:
    - Los logs rotan automáticamente (máx 5MB por archivo, 3 backups)
    - **Docker Compose**: Logs en `./logs` (directorio local)
    - **Docker Stack**: Logs en `/var/log` (host del nodo)

3. **Zona Horaria**: Configurada para `America/Guayaquil` (modificar en Dockerfile si es necesario)

4. **Puerto**: Por defecto usa `4000` (modificar en archivos de compose si hay conflicto)

5. **Réplicas**:
    - Docker Compose: 1 instancia
    - Docker Stack: 8 réplicas (ajustar según necesidad)

6. **Alta Disponibilidad**:
    - Docker Stack distribuye automáticamente las réplicas
    - Si un nodo falla, las réplicas se redistribuyen
    - El balanceo de carga es automático

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
- 🐙 GitHub: https://github.com/publinchi/sai_llm_server
- ☕ Buy Me a Coffee: https://buymeacoffee.com/publinchi4

---

**Versión:** 1.0.0  
**Última actualización:** 2025  
**Autor:** Publio Estupiñán  
**Licencia:** MIT (Compatible con LiteLLM)