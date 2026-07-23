from __future__ import annotations

import http.server
import logging
import os
import secrets
import threading
import time
from pathlib import Path
from typing import Any

import requests
from pyngrok import conf, ngrok

logger = logging.getLogger("instagram_publisher")

GRAPH_API_VERSION = os.getenv("GRAPH_API_VERSION", "v21.0")
# Instagram API with Instagram Login: los tokens IGAA... solo son válidos en graph.instagram.com,
# no en graph.facebook.com (ese host es para el flujo clásico vía Página de Facebook).
GRAPH_API_BASE = f"https://graph.instagram.com/{GRAPH_API_VERSION}"

CONTAINER_POLL_TIMEOUT_S = 90
CONTAINER_POLL_INTERVAL_S = 3


class InstagramPublishError(RuntimeError):
    """Error al crear, procesar o publicar una historia en Instagram."""


def _crear_handler_de_archivo_unico(ruta_publica: str, archivo: Path) -> type[http.server.BaseHTTPRequestHandler]:
    """Handler HTTP que solo sirve `archivo` en `ruta_publica`; cualquier otra ruta devuelve 404."""

    class HandlerArchivoUnico(http.server.BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802 (nombre impuesto por BaseHTTPRequestHandler)
            if self.path != ruta_publica:
                self.send_error(404)
                return
            contenido = archivo.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "image/png")
            self.send_header("Content-Length", str(len(contenido)))
            self.end_headers()
            self.wfile.write(contenido)

        def log_message(self, format: str, *args: Any) -> None:  # noqa: A002
            logger.debug("hosting temporal: " + format, *args)

    return HandlerArchivoUnico


def iniciar_hosting_temporal(
    archivo: Path,
) -> tuple[http.server.ThreadingHTTPServer, threading.Thread, Any, str]:
    """Expone `archivo` en una URL pública efímera vía un túnel ngrok.

    La ruta incluye un token aleatorio para que la URL no sea adivinable
    mientras el túnel está activo.
    """
    if not archivo.exists():
        raise FileNotFoundError(f"No se encontró la imagen a publicar: {archivo}")

    ruta_publica = f"/{secrets.token_urlsafe(24)}.png"
    handler_cls = _crear_handler_de_archivo_unico(ruta_publica, archivo)
    servidor = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler_cls)
    hilo = threading.Thread(target=servidor.serve_forever, daemon=True)
    hilo.start()

    authtoken = os.getenv("NGROK_AUTHTOKEN")
    if authtoken:
        conf.get_default().auth_token = authtoken

    puerto = servidor.server_address[1]
    tunel = ngrok.connect(puerto, "http")
    url_publica = f"{tunel.public_url}{ruta_publica}"
    logger.info("Imagen expuesta temporalmente en: %s", url_publica)
    return servidor, hilo, tunel, url_publica


def detener_hosting_temporal(
    servidor: http.server.ThreadingHTTPServer,
    hilo: threading.Thread,
    tunel: Any,
) -> None:
    try:
        ngrok.disconnect(tunel.public_url)
    finally:
        servidor.shutdown()
        hilo.join(timeout=5)
        logger.info("Túnel y servidor temporal cerrados")


def crear_contenedor_story(image_url: str, ig_user_id: str, access_token: str) -> str:
    respuesta = requests.post(
        f"{GRAPH_API_BASE}/{ig_user_id}/media",
        data={
            "image_url": image_url,
            "media_type": "STORIES",
            "access_token": access_token,
        },
        timeout=30,
    )
    if not respuesta.ok:
        raise InstagramPublishError(f"No se pudo crear el contenedor de la historia: {respuesta.text}")
    return respuesta.json()["id"]


def esperar_contenedor_listo(
    creation_id: str,
    access_token: str,
    timeout_s: int = CONTAINER_POLL_TIMEOUT_S,
    intervalo_s: int = CONTAINER_POLL_INTERVAL_S,
) -> None:
    limite = time.monotonic() + timeout_s
    while time.monotonic() < limite:
        respuesta = requests.get(
            f"{GRAPH_API_BASE}/{creation_id}",
            params={"fields": "status_code", "access_token": access_token},
            timeout=15,
        )
        if not respuesta.ok:
            raise InstagramPublishError(f"No se pudo consultar el estado del contenedor: {respuesta.text}")

        estado = respuesta.json().get("status_code")
        if estado == "FINISHED":
            return
        if estado in {"ERROR", "EXPIRED"}:
            raise InstagramPublishError(f"El contenedor de la historia terminó en estado {estado}")
        time.sleep(intervalo_s)

    raise TimeoutError("El contenedor de la historia no terminó de procesarse a tiempo")


def publicar_story(creation_id: str, ig_user_id: str, access_token: str) -> str:
    respuesta = requests.post(
        f"{GRAPH_API_BASE}/{ig_user_id}/media_publish",
        data={"creation_id": creation_id, "access_token": access_token},
        timeout=30,
    )
    if not respuesta.ok:
        raise InstagramPublishError(f"No se pudo publicar la historia: {respuesta.text}")
    return respuesta.json()["id"]


def publicar_historia(image_path: Path) -> str:
    """Publica `image_path` como Historia de Instagram vía la Graph API.

    Requiere IG_ACCESS_TOKEN (con permiso instagram_content_publish) e
    IG_BUSINESS_ACCOUNT_ID en el entorno.
    """
    access_token = os.environ["IG_ACCESS_TOKEN"]
    ig_user_id = os.environ["IG_BUSINESS_ACCOUNT_ID"]

    servidor, hilo, tunel, url_publica = iniciar_hosting_temporal(image_path)
    try:
        logger.info("Creando contenedor de historia en Instagram...")
        creation_id = crear_contenedor_story(url_publica, ig_user_id, access_token)
        logger.info("Contenedor creado (%s); esperando procesamiento...", creation_id)
        esperar_contenedor_listo(creation_id, access_token)
        logger.info("Publicando historia...")
        media_id = publicar_story(creation_id, ig_user_id, access_token)
        logger.info("Historia publicada con éxito (media_id=%s)", media_id)
        return media_id
    finally:
        detener_hosting_temporal(servidor, hilo, tunel)
