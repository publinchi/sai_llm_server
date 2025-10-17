import asyncio
from typing import AsyncIterator, Optional
import os
import time
import uuid
from dotenv import load_dotenv
import requests
from litellm import CustomLLM, ModelResponse
from litellm.types.utils import GenericStreamingChunk
import logging
from logging.handlers import RotatingFileHandler

# Cargar variables de entorno
load_dotenv()

# ---------------- Logging ----------------
log_dir = "logs"
os.makedirs(log_dir, exist_ok=True)

logger = logging.getLogger("sai_handler_llm")

file_handler = RotatingFileHandler(
    filename=os.path.join(log_dir, "sai_handler.log"),
    maxBytes=5 * 1024 * 1024,
    backupCount=3,
    encoding='utf-8'
)
file_handler.setFormatter(logging.Formatter('[%(asctime)s] %(levelname)s - %(message)s'))
logger.addHandler(file_handler)

console_handler = logging.StreamHandler()
console_handler.setLevel(logging.WARNING)
console_handler.setFormatter(logging.Formatter('[%(asctime)s] %(levelname)s - %(message)s'))
logger.addHandler(console_handler)

SAI_TEMPLATE_ID = os.getenv("SAI_TEMPLATE_ID")
SAI_KEY = os.getenv("SAI_KEY")
SAI_URL = os.getenv("SAI_URL")
SAI_COOKIE = os.getenv("SAI_COOKIE")

# Validar variables de entorno críticas
if not SAI_TEMPLATE_ID:
    raise ValueError("SAI_TEMPLATE_ID no está configurado en las variables de entorno")
if not SAI_KEY and not SAI_COOKIE:
    raise ValueError("Debe configurar al menos SAI_KEY o SAI_COOKIE en las variables de entorno")

CHUNK_SIZE = 50  # caracteres por chunk
REQUEST_TIMEOUT = int(os.getenv("REQUEST_TIMEOUT", "600"))  # segundos
MAX_RETRIES = int(os.getenv("MAX_RETRIES", "3"))
VERBOSE_LOGGING = os.getenv("VERBOSE_LOGGING", "false").lower() == "true"

# Cambia según la variable de entorno VERBOSE_LOGGING
if VERBOSE_LOGGING:
    logger.setLevel(logging.DEBUG)
else:
    logger.setLevel(logging.INFO)

# Configurar sesión HTTP reutilizable con pool optimizado
http_session = requests.Session()
http_session.timeout = REQUEST_TIMEOUT
adapter = requests.adapters.HTTPAdapter(
    max_retries=MAX_RETRIES,
    pool_connections=10,  # Mantener más conexiones en pool
    pool_maxsize=20       # Tamaño máximo del pool
)
http_session.mount("https://", adapter)
http_session.mount("http://", adapter)


# ---------------- Excepciones personalizadas ----------------
class SAIAPIError(Exception):
    """Error base para excepciones de la API SAI"""
    pass


class SAIRateLimitError(SAIAPIError):
    """Error cuando se excede el límite de uso"""
    pass


class SAIAuthenticationError(SAIAPIError):
    """Error de autenticación con la API"""
    pass


class SAILLM(CustomLLM):
    def __init__(self):
        super().__init__()

    def _extract_plugin_wrapped_message(self, content: str) -> tuple[bool, str]:
        """
        Detecta si el mensaje fue envuelto por el plugin del IDE y extrae el mensaje original.

        Returns:
            tuple[bool, str]: (es_mensaje_plugin, mensaje_original_o_contenido)
        """
        if not isinstance(content, str):
            return False, content

        # Detectar el patrón del plugin
        plugin_prefix = "Determine if the following context is required to solve the task in the user's input in the chat session: \""
        plugin_suffix_start = "\"\nContext:"

        if content.startswith(plugin_prefix) and plugin_suffix_start in content:
            # Extraer el mensaje original entre las comillas
            start_idx = len(plugin_prefix)
            end_idx = content.find(plugin_suffix_start, start_idx)

            if end_idx > start_idx:
                original_message = content[start_idx:end_idx]
                logger.info(f"🔍 Plugin del IDE detectado | Mensaje original extraído: {original_message[:100]}")
                return True, original_message

        return False, content

    def _prepare_messages(self, messages, request_id: str):
        if not messages or not isinstance(messages, list):
            raise ValueError("messages debe ser una lista no vacía")

        # Detectar y procesar mensajes envueltos por el plugin del IDE
        plugin_detected = False
        for msg in messages:
            if isinstance(msg, dict) and "content" in msg:
                is_plugin_msg, original_content = self._extract_plugin_wrapped_message(msg["content"])
                if is_plugin_msg:
                    msg["content"] = original_content
                    plugin_detected = True
                    logger.info(
                        f"🔧 [PLUGIN INTERCEPTED] [{request_id}] Mensaje del plugin reemplazado | "
                        f"Original extraído: {original_content[:80]}{'...' if len(original_content) > 80 else ''}"
                    )

        # Log de mensajes recibidos desde el cliente
        total_chars = sum(len(str(msg.get("content", ""))) for msg in messages)
        logger.info(
            f"🔌 [CLIENT → SERVER] [{request_id}] Mensajes recibidos desde cliente | "
            f"Cantidad: {len(messages)} | "
            f"Tamaño total: {total_chars} caracteres | "
            f"Plugin detectado: {'Sí' if plugin_detected else 'No'}"
        )

        # Log detallado solo si VERBOSE_LOGGING está activado
        if VERBOSE_LOGGING:
            logger.debug(f"[{request_id}] Messages completos: {messages}")

        # Validar estructura de mensajes
        for msg in messages:
            if not isinstance(msg, dict):
                raise ValueError("Cada mensaje debe ser un diccionario")
            if "role" not in msg or "content" not in msg:
                raise ValueError("Cada mensaje debe tener 'role' y 'content'")

        # Extraer system prompt si existe
        system_prompt = ""
        processed_messages = messages

        if messages and messages[0].get("role") == "system":
            system_prompt = messages[0].get("content", "")
            processed_messages = messages[1:]

        # Convertir mensajes al formato esperado por SAI
        chat_messages = [{
            "content": msg.get("content", ""),
            "role": msg.get("role"),
            "id": int(time.time() * 1000) + idx
        } for idx, msg in enumerate(processed_messages)]

        # Validación temprana de tamaño (estimación conservadora)
        # Aproximadamente 4 caracteres por token
        estimated_tokens = total_chars // 4
        max_context_tokens = 128000  # Ajustar según el modelo de SAI

        if estimated_tokens > max_context_tokens:
            logger.warning(
                f"⚠️ [SERVER] [{request_id}] Contexto potencialmente demasiado grande | "
                f"Tokens estimados: {estimated_tokens} | "
                f"Máximo recomendado: {max_context_tokens} | "
                f"El cliente debería reducir el historial"
            )

        return system_prompt, chat_messages

    # ---------------- Síncrono ----------------
    def completion(self, messages=None, **kwargs) -> ModelResponse:
        request_id = str(uuid.uuid4())[:8]  # Usar solo los primeros 8 caracteres para legibilidad

        if not messages:
            raise ValueError("Se requiere al menos un mensaje")

        system, chat_messages = self._prepare_messages(messages, request_id)

        if not messages:
            raise ValueError("No hay mensajes para procesar después de extraer system prompt")

        prompt = messages[-1]["content"]
        response_text, finish_reason, usage_data = self._call_sai(system, prompt, chat_messages, request_id)

        response = ModelResponse(
            text=response_text,
            usage={
                "prompt_tokens": usage_data["prompt_tokens"],
                "completion_tokens": usage_data["completion_tokens"],
                "total_tokens": usage_data["total_tokens"]
            }
        )
        response.choices[0].finish_reason = finish_reason
        response.model = usage_data["model"]

        return response

    # ---------------- Asíncrono ----------------
    async def acompletion(self, messages=None, **kwargs) -> ModelResponse:
        request_id = str(uuid.uuid4())[:8]  # Usar solo los primeros 8 caracteres para legibilidad

        if not messages:
            raise ValueError("Se requiere al menos un mensaje")

        system, chat_messages = self._prepare_messages(messages, request_id)

        if not messages:
            raise ValueError("No hay mensajes para procesar después de extraer system prompt")

        prompt = messages[-1]["content"]
        loop = asyncio.get_running_loop()
        response_text, finish_reason, usage_data = await loop.run_in_executor(
            None,
            self._call_sai,
            system,
            prompt,
            chat_messages,
            request_id
        )

        response = ModelResponse(
            text=response_text,
            usage={
                "prompt_tokens": usage_data["prompt_tokens"],
                "completion_tokens": usage_data["completion_tokens"],
                "total_tokens": usage_data["total_tokens"]
            }
        )
        response.choices[0].finish_reason = finish_reason
        response.model = usage_data["model"]

        return response

    # ---------------- Streaming ----------------
    async def astreaming(self, messages=None, **kwargs) -> AsyncIterator[GenericStreamingChunk]:
        response = await self.acompletion(messages)
        text = response.text
        usage_dict = response.usage.__dict__ if not isinstance(response.usage, dict) else response.usage
        finish_reason = response.choices[0].finish_reason

        for idx, start in enumerate(range(0, len(text), CHUNK_SIZE)):
            chunk_text = text[start:start + CHUNK_SIZE]
            await asyncio.sleep(0.001)  # Reducido de 0.01s a 0.001s para mayor velocidad
            is_final = start + CHUNK_SIZE >= len(text)
            yield GenericStreamingChunk(
                text=chunk_text,
                index=idx,
                is_finished=is_final,
                finish_reason=finish_reason if is_final else None,
                tool_use=None,
                usage=usage_dict
            )

    # ---------------- Llamada privada a SAI ----------------
    def _call_sai(self, system: str, user: str, chat_messages: list, request_id: str) -> tuple[str, str, dict]:
        url = f"{SAI_URL}/api/templates/{SAI_TEMPLATE_ID}/execute"
        data = {"inputs":{"system":system,"user":user}}
        if chat_messages:
            data["chatMessages"] = chat_messages

        # Logging optimizado del mensaje enviado al API
        logger.info(
            f"🐍 [SERVER → SAI] [{request_id}] Preparando request | "
            f"System: {len(system)} chars | "
            f"User: {len(user)} chars | "
            f"Historial: {len(chat_messages)} mensajes | "
            f"Template: {SAI_TEMPLATE_ID}"
        )

        # Log detallado solo si VERBOSE_LOGGING está activado
        if VERBOSE_LOGGING:
            logger.debug(f"[{request_id}] Payload completo:\n{data}")

        response = None
        response_headers = None

        # Si hay API Key, intentar primero con ella
        if SAI_KEY:
            logger.info(f"🔑 [{request_id}] Intentando con API Key")
            response, response_headers = self._make_request(url, data, use_api_key=True, request_id=request_id)

            # Si falla con 429 "Test template usage limit exceeded", reintentar solo con cookie
            if response is None and SAI_COOKIE:
                logger.info(
                    f"🔄 [{request_id}] Reintentando con Cookie debido a error 429 'Test template usage limit exceeded' con API Key | "
                    f"Cambiando método de autenticación: API Key → Cookie"
                )
                response, response_headers = self._make_request(url, data, use_api_key=False, request_id=request_id)
            elif response is None and not SAI_COOKIE:
                logger.error(
                    f"❌ [{request_id}] Error 429 con API Key pero no hay SAI_COOKIE configurada para reintentar | "
                    f"Configure SAI_COOKIE para usar autenticación alternativa"
                )
        else:
            # Si no hay API Key, usar solo cookie desde el inicio
            logger.info(f"🍪 [{request_id}] Usando solo Cookie (sin API Key configurada)")
            response, response_headers = self._make_request(url, data, use_api_key=False, request_id=request_id)

        # Valores por defecto para usage
        usage_data = {
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0,
            "model": "unknown",
            "response_time": 0.0
        }

        # Detectar error de prompt demasiado largo (HTTP 500: prompt is too long)
        if response == "PROMPT_TOO_LONG":
            logger.error(
                f"❌ [SAI → SERVER] [{request_id}] Error: Contexto demasiado largo | "
                f"Mensajes en historial: {len(chat_messages)} | "
                f"Acción requerida: El cliente debe reducir el historial"
            )
            return (
                "⚠️ **Contexto demasiado largo**\n\n"
                f"El historial de conversación excede el límite del modelo ({len(chat_messages)} mensajes).\n"
                "**Acciones sugeridas:**\n"
                "1. Reduzca el número de mensajes en el historial\n"
                "2. Inicie una nueva conversación\n"
                "3. Resuma el contexto anterior en un mensaje más corto"
            ), "length", usage_data

        # Detectar error HTTP 500 no controlado
        if response == "HTTP_500_ERROR":
            logger.error(
                f"❌ [SAI → SERVER] [{request_id}] Error HTTP 500 no controlado | "
                f"Template: {SAI_TEMPLATE_ID}"
            )
            return (
                "❌ **Error interno del servidor SAI (HTTP 500)**\n\n"
                "El servidor SAI encontró un error inesperado al procesar la solicitud.\n"
                "**Posibles causas:**\n"
                "1. Error interno del modelo o servicio\n"
                "2. Configuración incorrecta del template\n"
                "3. Problema temporal del servidor\n\n"
                "Por favor, intente nuevamente. Si el problema persiste, contacte al administrador."
            ), "error", usage_data

        if response is None:
            logger.error(
                f"❌ [SERVER → CLIENT] [{request_id}] Error: Sin respuesta de SAI | "
                f"Template: {SAI_TEMPLATE_ID} | "
                f"URL: {url} | "
                f"Auth disponible: API Key={bool(SAI_KEY)}, Cookie={bool(SAI_COOKIE)}"
            )
            return (
                "❌ **Error de conexión con SAI**\n\n"
                "No se pudo obtener respuesta del servidor SAI.\n"
                "**Posibles causas:**\n"
                "1. Problemas de red o conectividad\n"
                "2. Credenciales de autenticación inválidas\n"
                "3. Servicio SAI temporalmente no disponible\n\n"
                "Por favor, intente nuevamente en unos momentos."
            ), "error", usage_data

        # Actualizar usage_data con valores reales de los headers
        if response_headers:
            usage_data["prompt_tokens"] = response_headers.get("prompt_tokens", 0)
            usage_data["completion_tokens"] = response_headers.get("completion_tokens", 0)
            usage_data["total_tokens"] = usage_data["prompt_tokens"] + usage_data["completion_tokens"]
            usage_data["model"] = response_headers.get("model", "unknown")
            usage_data["response_time"] = response_headers.get("response_time", 0.0)

        # Logging consolidado de respuesta con toda la información
        status_code = response_headers.get("status_code", "N/A") if response_headers else "N/A"
        response_time = usage_data['response_time']
        tokens_per_second = response_headers.get("tokens_per_second", 0.0) if response_headers else 0.0

        logger.info(
            f"✅ [SERVER → CLIENT] [{request_id}] Respuesta lista para enviar | "
            f"Status: {status_code} | "
            f"⏱️ " + f" Latencia: {response_time:.2f}s | "
            f"Longitud: {len(response)} chars | "
            f"Tokens: {usage_data['prompt_tokens']} → {usage_data['completion_tokens']} (total: {usage_data['total_tokens']}) | "
            f"Velocidad: {tokens_per_second:.1f} tok/s | "
            f"Modelo: {usage_data['model']} | "
            f"Preview: {response[:120]!r}{'...' if len(response) > 120 else ''}"
        )

        return response, "stop", usage_data

    def _make_request(self, url: str, data: dict, use_api_key: bool = False, timeout: int = None, request_id: str = "unknown") -> tuple[Optional[str], Optional[dict]]:
        resp = None
        request_timeout = timeout or REQUEST_TIMEOUT
        auth_method = "API Key" if use_api_key else "Cookie"

        try:
            headers = {
                "Content-Type":"application/json",
                "Accept":"application/json, text/plain, */*",
                "Accept-Encoding": "gzip, deflate"  # Habilitar compresión
            }

            # Usar SOLO un método de autenticación (excluyente)
            if use_api_key and SAI_KEY:
                headers["X-Api-Key"] = SAI_KEY
            elif SAI_COOKIE:
                headers["Cookie"] = SAI_COOKIE
            else:
                logger.error(f"❌ [{request_id}] No hay método de autenticación disponible (ni API Key ni Cookie)")
                return None, None

            # Logging optimizado del payload enviado
            chat_msg_count = len(data.get("chatMessages", []))

            logger.info(
                f"🌐 [SERVER → SAI] [{request_id}] Enviando request | "
                f"Auth: {auth_method} | "
                f"Timeout: {request_timeout}s | "
                f"Mensajes: {chat_msg_count}"
            )

            # Log detallado solo si VERBOSE_LOGGING está activado
            if VERBOSE_LOGGING:
                system_preview = data.get("inputs", {}).get("system", "")[:80]
                user_preview = data.get("inputs", {}).get("user", "")[:80]
                logger.debug(
                    f"[{request_id}] System: {system_preview!r}{'...' if len(system_preview) >= 80 else ''} | "
                    f"User: {user_preview!r}{'...' if len(user_preview) >= 80 else ''}"
                )
                logger.debug(f"[{request_id}] 💬 Chat messages: {data.get('chatMessages', [])}")

            # Iniciar medición de tiempo
            start_time = time.time()

            resp = http_session.post(url, json=data, headers=headers, timeout=request_timeout, verify=False)
            resp.raise_for_status()

            # Calcular tiempo de respuesta
            response_time = time.time() - start_time

            # Extraer headers relevantes para OpenAI compatibility
            try:
                prompt_tokens = int(resp.headers.get("prompttokens", 0))
            except (ValueError, TypeError):
                prompt_tokens = 0

            try:
                completion_tokens = int(resp.headers.get("completiontokens", 0))
            except (ValueError, TypeError):
                completion_tokens = 0

            response_headers = {
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "model": resp.headers.get("model", "unknown"),
                "response_time": response_time
            }

            # Calcular tokens por segundo para métricas de rendimiento
            tokens_per_second = response_headers['completion_tokens'] / response_time if response_time > 0 else 0

            # Agregar métricas adicionales a response_headers para el log consolidado
            response_headers['status_code'] = resp.status_code
            response_headers['tokens_per_second'] = tokens_per_second
            response_headers['response_length'] = len(resp.text)

            return resp.text, response_headers

        except requests.HTTPError as e:
            if resp and resp.status_code == 429 and "Test template usage limit exceeded" in resp.text:
                logger.warning(
                    f"⚠️ [{request_id}] Error HTTP 429: 'Test template usage limit exceeded' detectado | "
                    f"Método auth usado: {auth_method} | "
                    f"Se reintentará con Cookie si está disponible"
                )
                return None, None  # señal para reintentar con cookie

            # Detectar error de prompt demasiado largo (HTTP 500)
            if resp and resp.status_code == 500:
                response_text = resp.text if resp else ""
                if "prompt is too long" in response_text.lower() or "openaicompatible" in response_text.lower():
                    logger.warning(
                        f"⚠️ [{request_id}] Error HTTP 500: Prompt demasiado largo detectado | "
                        f"Auth: {auth_method} | "
                        f"Respuesta SAI: {response_text[:300]}"
                    )
                    return "PROMPT_TOO_LONG", None  # Señal especial para marcar finish_reason=length
                else:
                    # Error HTTP 500 no controlado (no es "prompt too long")
                    logger.error(
                        f"❌ [{request_id}] Error HTTP 500 no controlado | "
                        f"Auth: {auth_method} | "
                        f"Respuesta SAI: {response_text[:300]}"
                    )
                    return "HTTP_500_ERROR", None  # Señal especial para marcar finish_reason=error

            # Logging detallado de errores HTTP
            status_code = resp.status_code
            response_text = resp.text[:200]
            logger.error(
                f"❌ [{request_id}] Error HTTP en solicitud SAI | "
                f"Status: {status_code} | "
                f"Método auth: {auth_method} | "
                f"URL: {url} | "
                f"Error: {str(e)} | "
                f"Respuesta: {response_text}"
            )
            return None, None

        except requests.Timeout:
            logger.error(
                f"⏱️ [{request_id}] Timeout en solicitud SAI | "
                f"Timeout: {request_timeout}s | "
                f"Método auth: {auth_method} | "
                f"URL: {url}"
            )
            return None, None

        except requests.RequestException as e:
            logger.error(
                f"❌ [{request_id}] Error de conexión con SAI | "
                f"Método auth: {auth_method} | "
                f"URL: {url} | "
                f"Error técnico: {type(e).__name__}: {str(e)}"
            )
            return None, None


# ---------------- Instancia ----------------
sai_llm = SAILLM()
logger.info(f"✅ SAILLM inicializado correctamente")