from __future__ import annotations

import logging
import os
import secrets
import time
from pathlib import Path

import boto3
import requests

logger = logging.getLogger("instagram_publisher")

GRAPH_API_VERSION = os.getenv("GRAPH_API_VERSION", "v21.0")
# Instagram API with Instagram Login: los tokens IGAA... solo son válidos en graph.instagram.com,
# no en graph.facebook.com (ese host es para el flujo clásico vía Página de Facebook).
GRAPH_API_BASE = f"https://graph.instagram.com/{GRAPH_API_VERSION}"

CONTAINER_POLL_TIMEOUT_S = 90
CONTAINER_POLL_INTERVAL_S = 3


class InstagramPublishError(RuntimeError):
    """Error al crear, procesar o publicar una historia en Instagram."""


def _r2_client():
    return boto3.client(
        "s3",
        endpoint_url=f"https://{os.environ['R2_ACCOUNT_ID']}.r2.cloudflarestorage.com",
        aws_access_key_id=os.environ["R2_ACCESS_KEY_ID"],
        aws_secret_access_key=os.environ["R2_SECRET_ACCESS_KEY"],
        region_name="auto",
    )


def subir_imagen_temporal(archivo: Path) -> tuple[str, str]:
    """Sube `archivo` a un bucket de Cloudflare R2 y devuelve (url_publica, object_key).

    La Graph API de Meta requiere una URL pública (no acepta upload de archivo)
    para crear el contenedor de una Historia. El object_key incluye un token
    aleatorio para que la URL no sea adivinable mientras el objeto exista.
    """
    if not archivo.exists():
        raise FileNotFoundError(f"No se encontró la imagen a publicar: {archivo}")

    object_key = f"{secrets.token_urlsafe(24)}.png"
    bucket = os.environ["R2_BUCKET_NAME"]
    public_base_url = os.environ["R2_PUBLIC_BASE_URL"].rstrip("/")

    _r2_client().upload_file(str(archivo), bucket, object_key, ExtraArgs={"ContentType": "image/png"})

    url_publica = f"{public_base_url}/{object_key}"
    logger.info("Imagen expuesta temporalmente en: %s", url_publica)
    return url_publica, object_key


def borrar_imagen_temporal(object_key: str) -> None:
    bucket = os.environ["R2_BUCKET_NAME"]
    _r2_client().delete_object(Bucket=bucket, Key=object_key)
    logger.info("Imagen temporal eliminada de R2: %s", object_key)


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
    IG_BUSINESS_ACCOUNT_ID en el entorno, además de las credenciales de
    Cloudflare R2 (R2_ACCOUNT_ID, R2_ACCESS_KEY_ID, R2_SECRET_ACCESS_KEY,
    R2_BUCKET_NAME, R2_PUBLIC_BASE_URL) usadas para exponer la imagen con una
    URL pública temporal, tal como lo requiere la Graph API.
    """
    access_token = os.environ["IG_ACCESS_TOKEN"]
    ig_user_id = os.environ["IG_BUSINESS_ACCOUNT_ID"]

    url_publica, object_key = subir_imagen_temporal(image_path)
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
        borrar_imagen_temporal(object_key)
