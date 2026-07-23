from __future__ import annotations

import argparse
import logging
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

from hielito_story_generator_V2 import (
    CREATIVE_CONCEPTS,
    IMAGE_QUALITY_PROFILES,
    OUTPUT_DIR,
    TIMEZONE,
    DEFAULT_OPENAI_IMAGE_MODEL,
    DEFAULT_OPENAI_MODEL,
    build_context,
    build_story_content,
    generate_complete_openai_story,
    generate_story_content_with_openai,
    load_business_facts,
    select_reference_image,
)
from instagram_publisher import publicar_historia

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("hielito_daily_story")

# Estrategia de contenido por día de la semana: (objetivo comercial, concepto creativo).
ESTRATEGIA_POR_DIA: dict[str, tuple[str, str]] = {
    "monday": ("Recordar que ya estamos tomando pedidos para la semana", "producto"),
    "tuesday": ("Reforzar la disponibilidad de stock y pedidos por WhatsApp", "comercio"),
    "wednesday": ("Destacar la bolsa de 15 kg para juntadas de mitad de semana", "producto"),
    "thursday": ("Invitar a reservar hielo para el finde que se viene", "evento"),
    "friday": ("Impulsar pedidos para el finde, previas y asados", "asado"),
    "saturday": ("Venta urgente para eventos y compras de último momento", "evento"),
    "sunday": ("Recordar entregas coordinadas y stock disponible para la semana", "comercio"),
}


def obtener_prompt_del_dia(weekday: str) -> tuple[str, str]:
    """Devuelve (objetivo, concepto_creativo) según el día de la semana."""
    return ESTRATEGIA_POR_DIA.get(weekday, ESTRATEGIA_POR_DIA["monday"])


def generar_imagen(cost_profile: str = "balanced", usar_copy_local: bool = False) -> Path:
    """Genera la historia del día (imagen 1080x1920) usando la API de OpenAI y la guarda en output/."""
    logger.info("Generando contenido e imagen de la historia del día...")

    args = SimpleNamespace(
        hour=None,
        day=None,
        weather="normal",
        temp=None,
        stock="medium",
        brand_name=None,
        whatsapp_label=None,
        delivery_zones=None,
        major_message=None,
    )
    ctx = build_context(args)
    facts = load_business_facts()
    objective, creative_concept = obtener_prompt_del_dia(ctx.weekday)
    logger.info("Día: %s | Objetivo: %s | Concepto: %s", ctx.weekday, objective, creative_concept)

    if usar_copy_local:
        content = build_story_content(ctx)
    else:
        try:
            content = generate_story_content_with_openai(ctx, facts, DEFAULT_OPENAI_MODEL, objective)
        except Exception as exc:
            logger.warning("OpenAI no disponible para el copy; usando contenido local: %s", exc)
            content = build_story_content(ctx)

    reference = select_reference_image(creative_concept)
    image, _prompt = generate_complete_openai_story(
        ctx,
        content,
        facts,
        DEFAULT_OPENAI_IMAGE_MODEL,
        objective,
        creative_concept,
        reference,
        IMAGE_QUALITY_PROFILES[cost_profile],
    )

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(TIMEZONE).strftime("%Y%m%d_%H%M%S")
    image_path = OUTPUT_DIR / f"story_{timestamp}.png"
    image.save(image_path, quality=95)
    logger.info("Imagen generada: %s", image_path)
    return image_path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Genera y publica la historia diaria de Hielito en Instagram"
    )
    parser.add_argument(
        "--cost-profile",
        choices=sorted(IMAGE_QUALITY_PROFILES),
        default="balanced",
        help="Calidad de la imagen generada (impacta el costo de la llamada a OpenAI)",
    )
    parser.add_argument(
        "--local-copy",
        action="store_true",
        help="Usa el copy local en vez de generarlo con OpenAI",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Genera la imagen pero no la publica en Instagram",
    )
    parser.add_argument(
        "--image",
        type=Path,
        default=None,
        help="Publica este archivo ya generado en vez de crear uno nuevo (evita otra llamada a OpenAI)",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    try:
        logger.info("=== Inicio: historia diaria de Hielito ===")
        if args.image:
            image_path = args.image
            logger.info("Usando imagen ya generada: %s", image_path)
        else:
            image_path = generar_imagen(cost_profile=args.cost_profile, usar_copy_local=args.local_copy)

        if args.dry_run:
            logger.info("Modo --dry-run: no se publica en Instagram. Archivo: %s", image_path)
            return

        logger.info("=== Publicación en Instagram ===")
        media_id = publicar_historia(image_path)
        logger.info("=== Éxito: historia publicada (media_id=%s) ===", media_id)
    except Exception:
        logger.exception("Falló la generación o publicación de la historia diaria")
        raise


if __name__ == "__main__":
    main()
