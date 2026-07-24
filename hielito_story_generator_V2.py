from __future__ import annotations

import argparse
import base64
import contextlib
import io
import json
import math
import os
import random
import re
import textwrap
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Optional
from zoneinfo import ZoneInfo

from google import genai
from google.genai import types as genai_types
from openai import OpenAI
from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageOps
from dotenv import load_dotenv
from pydantic import BaseModel, Field

load_dotenv()


# ============================================================
# HIELITO - Generador automático de historias para Instagram
# ============================================================
# Qué hace:
# - Genera una historia 1080x1920 lista para publicar.
# - Decide el mensaje según día, hora, clima y stock.
# - Usa plantillas visuales simples dibujadas por código.
# - Exporta un PNG en la carpeta output/.
#
# Ejemplo de uso:
# python hielito_story_generator.py --weather hot --temp 34 --stock high
# python hielito_story_generator.py --weather rainy --temp 19 --stock medium --hour 21
# python hielito_story_generator.py --weather normal --temp 28 --stock low --day saturday
#
# Requisitos:
# pip install pillow
# ============================================================


TIMEZONE = ZoneInfo("America/Argentina/Buenos_Aires")
CANVAS_SIZE = (1080, 1920)
OUTPUT_DIR = Path("output")
ASSETS_DIR = Path("assets")
LOGO_PATH = ASSETS_DIR / "logo.png"
TEMPLATES_DIR = ASSETS_DIR / "templates"
BACKGROUNDS_DIR = ASSETS_DIR / "backgrounds"
BRAND_CONFIG_PATH = ASSETS_DIR / "brand_config.json"
BUSINESS_FACTS_PATH = Path("business_facts.json")
BUSINESS_IDENTITY_PATH = Path("business.json")
REFERENCE_LIBRARY_PATH = Path("referencias/reference_library.json")
DEFAULT_OPENAI_MODEL = "gpt-5-mini"
DEFAULT_OPENAI_IMAGE_MODEL = "gpt-image-2"
# Nombre de modelo verificable/ajustable sin tocar código: confirmá el disponible para tu cuenta en
# https://aistudio.google.com/ antes de depender de este default en producción.
DEFAULT_GEMINI_IMAGE_MODEL = os.getenv("GEMINI_IMAGE_MODEL", "gemini-3-pro-image")

CREATIVE_CONCEPTS: dict[str, list[str]] = {
    "asado": [
        "Editorial lifestyle advertising at an Argentine weekend asado: a zinc beverage tub full of crystal-clear ice "
        "and cold bottles, warm late-afternoon sunlight, subtle grill smoke in the background, candid but no visible people, "
        "inviting social energy, premium beverage-campaign art direction.",
        "Argentine backyard asado at golden hour: a wooden table corner holding a galvanized ice bucket overflowing "
        "with clear cubes next to sweating soda bottles, dry autumn-green grass blurred behind, warm low sun "
        "rim-lighting the ice edges, relaxed pre-gathering mood, no people visible.",
        "Close-up hero shot on an asado prep table: a mound of crystal-clear ice cubes spilling from an open "
        "transparent bag onto a rustic wooden board next to a chimichurri jar and cold drink cans, morning-to-noon "
        "natural light, shallow depth of field, appetite-appeal advertising photography.",
        "Wide establishing shot of a patio asado setup at dusk: string lights softly out of focus in the background, "
        "a large cooler brimming with ice and drinks in the foreground, cool blue twilight sky contrasting the warm "
        "string-light glow, premium lifestyle-brand color grading, no people visible.",
        "Overhead (top-down) flat-lay of an asado ice station: a galvanized tub packed with ice cubes and drink cans "
        "arranged in a loose circular pattern on a wooden deck, hard midday sun creating crisp shadows, high-contrast "
        "graphic composition, modern food-and-beverage editorial style.",
    ],
    "evento": [
        "Premium event-bar advertising: elegant transparent glasses, polished metal ice bucket, dramatic crystal-clear ice, "
        "cinematic blue and amber lighting, refined celebration atmosphere, upscale but approachable.",
        "Intimate evening event bar corner: a stack of transparent ice bags beside a bartender's station with citrus "
        "garnishes and glassware softly blurred in the foreground, warm amber string lighting against a deep navy "
        "background, cinematic depth, no people visible.",
        "Outdoor event setup at blue hour: a large clear ice tub reflecting string lights and a distant marquee tent, "
        "cool dusk sky transitioning to warm tungsten highlights, shallow depth of field isolating the ice, premium "
        "hospitality-brand photography.",
        "Corporate event catering angle: neatly stacked transparent ice bags beside chrome catering trays under clean "
        "architectural lighting, minimal color palette of steel gray and ice blue, precise and professional "
        "composition, no people visible.",
        "Rooftop sunset event scene: a sculptural ice-filled glass bowl on a high-top table, city lights beginning to "
        "glow out of focus in the background, warm-to-cool gradient sky, aspirational lifestyle-advertising mood.",
    ],
    "producto": [
        "Bold product hero shot: one transparent 15 kg-style ice bag and sculptural crystal-clear cubes on a wet reflective surface, "
        "dramatic studio lighting, strong depth, premium supermarket campaign photography, visually striking and minimal.",
        "Studio still-life of an open transparent ice bag with cubes cascading onto a dark reflective surface, single "
        "hard key light from the upper left creating long dramatic shadows, high-contrast blue-black background, "
        "luxury cold-beverage-brand aesthetic.",
        "Macro-detail product shot: extreme close-up on stacked crystal-clear ice cubes with visible internal "
        "fracture patterns and condensation beads, cool rim lighting, extremely shallow depth of field, textural and "
        "tactile advertising photography.",
        "Symmetrical centered product composition: a sealed transparent ice bag standing upright on a frosted white "
        "surface, soft diffused overhead lighting, subtle blue gradient backdrop, clean minimalist e-commerce-hero "
        "style with generous negative space.",
        "Dynamic action-style product shot: ice cubes appearing to tumble mid-air from a tilted transparent bag onto "
        "a wet dark surface, frozen-motion studio strobe lighting, high-speed-photography feel, dramatic splash "
        "droplets, premium beverage-campaign energy.",
    ],
    "comercio": [
        "Professional gastronomy supply campaign: organized bar or restaurant prep station, abundant clean ice, stainless steel details, "
        "efficient and reliable mood, modern editorial photography, visually polished rather than industrial.",
        "Behind-the-counter bar prep angle: a stainless steel ice well filled to the brim next to neatly stacked "
        "transparent ice bags, cool fluorescent-to-daylight mixed lighting, orderly and dependable commercial mood.",
        "Loading-dock / delivery-ready angle: a tidy row of sealed transparent ice bags stacked on a hand truck near "
        "a stainless steel service door, crisp morning light, logistics-and-reliability visual storytelling, no "
        "people visible.",
        "Restaurant kitchen pass angle: a commercial ice bin built into a stainless steel counter, ice mounded neatly, "
        "warm kitchen ambient light contrasting with cool blue ice tones, professional food-service editorial style.",
        "Small foodtruck/bar counter scene: a compact stainless ice chest with the lid propped open revealing packed "
        "clear cubes, warm string-light ambiance blurred behind, approachable small-business energy, no people visible.",
    ],
}

PHOTOGRAPHIC_STYLES: list[str] = [
    "Shot as if captured with an 85mm portrait lens at a wide aperture (f/2), producing creamy background blur "
    "(bokeh) that isolates the product; warm directional side light raking across the ice to reveal condensation "
    "texture; rule-of-thirds composition.",
    "Shot as if captured with a 35mm environmental lens, deep-enough depth of field to keep supporting props "
    "readable; soft overcast-style diffused lighting with gentle fill; leading-line composition guiding the eye "
    "toward the product.",
    "Shot as if captured with a macro lens at close working distance, emphasizing micro-texture: frost crystals, "
    "condensation beads, sharp internal ice fractures; single hard rim light for graphic contrast; centered, "
    "texture-forward composition.",
    "Shot as if captured with a medium-format studio setup, soft large-source key light plus subtle negative fill "
    "for controlled shadow falloff; symmetrical, editorial-catalog composition with generous negative space.",
    "Shot as if captured with a fast 50mm lens in available/practical light (string lights, golden hour), slight "
    "motion-frozen realism, natural imperfect highlights and lens flare, documentary-editorial composition.",
]

IMAGE_QUALITY_PROFILES = {
    "draft": "low",
    "balanced": "medium",
    "final": "high",
}

GEMINI_IMAGE_SIZE_PROFILES = {
    "draft": "1K",
    "balanced": "2K",
    "final": "4K",
}


# ----------------------------
# Modelos de datos
# ----------------------------

@dataclass
class WeatherContext:
    label: str  # hot, warm, normal, cold, rainy
    temperature_c: Optional[int] = None


@dataclass
class BusinessContext:
    brand_name: str
    whatsapp_label: str
    delivery_zones: str
    stock_level: str  # high, medium, low
    major_message: str
    primary_color: str = "#0D47A1"
    secondary_color: str = "#42A5F5"
    accent_color: str = "#E0F2FE"
    text_color: str = "#FFFFFF"
    dark_overlay: str = "#0A1942"


@dataclass
class StoryContext:
    now: datetime
    weekday: str
    hour: int
    weather: WeatherContext
    business: BusinessContext


@dataclass
class StoryContent:
    template_name: str
    kicker: str
    headline: str
    subheadline: str
    cta: str
    footer: str
    badge: Optional[str] = None


class GeneratedStoryContent(BaseModel):
    kicker: str = Field(min_length=1, max_length=18)
    headline: str = Field(min_length=1, max_length=52)
    subheadline: str = Field(min_length=1, max_length=90)
    cta: str = Field(min_length=1, max_length=32)
    footer: str = Field(min_length=1, max_length=65)
    badge: Optional[str] = Field(default=None, max_length=22)


# ----------------------------
# Utilidades de fecha y texto
# ----------------------------

def get_now(hour: Optional[int] = None, day: Optional[str] = None) -> datetime:
    now = datetime.now(TIMEZONE)

    if day:
        day = day.strip().lower()
        weekday_map = {
            "monday": 0,
            "tuesday": 1,
            "wednesday": 2,
            "thursday": 3,
            "friday": 4,
            "saturday": 5,
            "sunday": 6,
            "lunes": 0,
            "martes": 1,
            "miércoles": 2,
            "miercoles": 2,
            "jueves": 3,
            "viernes": 4,
            "sábado": 5,
            "sabado": 5,
            "domingo": 6,
        }
        if day not in weekday_map:
            raise ValueError(f"Día inválido: {day}")

        target_weekday = weekday_map[day]
        current_weekday = now.weekday()
        delta_days = target_weekday - current_weekday
        now = now.replace(hour=now.hour, minute=0, second=0, microsecond=0)
        now = now.fromtimestamp((now.timestamp() + delta_days * 86400), TIMEZONE)

    if hour is not None:
        if not 0 <= hour <= 23:
            raise ValueError("La hora debe estar entre 0 y 23")
        now = now.replace(hour=hour, minute=0, second=0, microsecond=0)

    return now


def weekday_slug(dt: datetime) -> str:
    names = [
        "monday",
        "tuesday",
        "wednesday",
        "thursday",
        "friday",
        "saturday",
        "sunday",
    ]
    return names[dt.weekday()]


def hour_bucket(hour: int) -> str:
    if 6 <= hour <= 10:
        return "morning"
    if 11 <= hour <= 16:
        return "afternoon"
    if 17 <= hour <= 21:
        return "evening"
    return "night"


def wrap_text(text: str, width: int) -> str:
    return "\n".join(textwrap.wrap(text, width=width, break_long_words=False))


def wrap_text_pixels(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.ImageFont, max_width: int) -> str:
    lines: list[str] = []
    current: list[str] = []

    for word in text.split():
        candidate = " ".join([*current, word])
        if current and draw.textbbox((0, 0), candidate, font=font)[2] > max_width:
            lines.append(" ".join(current))
            current = [word]
        else:
            current.append(word)

    if current:
        lines.append(" ".join(current))
    return "\n".join(lines)


def fit_multiline_text(
    draw: ImageDraw.ImageDraw,
    text: str,
    max_width: int,
    max_height: int,
    max_size: int,
    min_size: int,
    bold: bool = False,
    spacing: int = 8,
) -> tuple[str, ImageFont.ImageFont]:
    for size in range(max_size, min_size - 1, -2):
        font = load_font(size, bold=bold)
        wrapped = wrap_text_pixels(draw, text, font, max_width)
        bbox = draw.multiline_textbbox((0, 0), wrapped, font=font, spacing=spacing)
        if bbox[2] <= max_width and bbox[3] - bbox[1] <= max_height:
            return wrapped, font

    font = load_font(min_size, bold=bold)
    return wrap_text_pixels(draw, text, font, max_width), font


def normalize_for_validation(text: str) -> str:
    replacements = str.maketrans("áéíóúüñ", "aeiouun")
    return text.lower().translate(replacements)


def clean_generated_text(text: str) -> str:
    dangling_words = {"a", "al", "con", "de", "desde", "el", "en", "la", "las", "los", "o", "para", "por", "y"}
    words = text.strip().split()
    while words and normalize_for_validation(words[-1].strip(".,;:!?")) in dangling_words:
        words.pop()
    cleaned = " ".join(words).rstrip(" ,;:-")
    if cleaned and cleaned[-1] not in ".!?":
        cleaned += "."
    return cleaned


def safe_text(value: Any) -> str:
    """Normaliza valores usados dentro de prompts."""
    return " ".join(str(value or "").strip().split())


def format_zones(zones: list[Any], max_zones: int = 6) -> str:
    """Limita las zonas visibles para no sobrecargar la pieza."""
    clean_zones = [safe_text(zone) for zone in zones if safe_text(zone)]
    if not clean_zones:
        return ""
    if len(clean_zones) <= max_zones:
        return ", ".join(clean_zones)
    return f"{', '.join(clean_zones[:max_zones])} y alrededores"


def clean_supporting_text_for_layout(text: str) -> str:
    """Quita del subtítulo datos que ya tienen bloques visuales propios."""
    sentences = re.split(r"(?<=[.!?])\s+", safe_text(text))
    filtered = [
        sentence
        for sentence in sentences
        if not any(
            marker in normalize_for_validation(sentence)
            for marker in ("whatsapp", "entrega", "envio", "berazategui", "quilmes", "florencio varela")
        )
    ]
    return safe_text(" ".join(filtered))


def load_business_facts() -> dict[str, Any]:
    try:
        payload = json.loads(BUSINESS_FACTS_PATH.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise RuntimeError(f"No se encontró {BUSINESS_FACTS_PATH}") from exc
    except (json.JSONDecodeError, OSError) as exc:
        raise RuntimeError(f"No se pudo leer {BUSINESS_FACTS_PATH}: {exc}") from exc

    required_sections = {"products", "orders", "delivery", "business_hours", "content_rules"}
    missing = required_sections.difference(payload)
    if missing:
        raise RuntimeError(f"Faltan secciones en {BUSINESS_FACTS_PATH}: {', '.join(sorted(missing))}")
    return payload


def load_brand_identity() -> dict[str, list[str]]:
    """Identidad de marca reutilizable desde business.json (nunca precios/campañas históricas:
    ver content_rules.historical_content_policy en business_facts.json)."""
    try:
        payload = json.loads(BUSINESS_IDENTITY_PATH.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return {}

    return {
        "visual_aesthetics": [safe_text(v) for v in payload.get("visualAesthetics", []) if safe_text(v)],
        "tone_of_voice": [safe_text(v) for v in payload.get("toneOfVoice", []) if safe_text(v)],
        "brand_values": [safe_text(v) for v in payload.get("brandValues", []) if safe_text(v)],
        "fonts": [safe_text(v) for v in payload.get("fonts", []) if safe_text(v)],
    }


def select_creative_variation(creative_concept: str, variation_seed: str) -> str:
    """Elige una escena + un estilo fotográfico de forma determinística para un seed dado.

    El mismo (concepto, seed) siempre produce la misma combinación (reproducible),
    pero seeds distintos (ej. fechas distintas) producen combinaciones distintas.
    """
    scenes = CREATIVE_CONCEPTS.get(creative_concept)
    if not scenes:
        return "Clean, cold, realistic, high-conversion local Instagram Story ad."

    scene = random.Random(f"scene::{creative_concept}::{variation_seed}").choice(scenes)
    style = random.Random(f"style::{creative_concept}::{variation_seed}").choice(PHOTOGRAPHIC_STYLES)
    return f"{scene} {style}"


def select_reference_image(creative_concept: str) -> Optional[Path]:
    if not REFERENCE_LIBRARY_PATH.exists():
        return None

    try:
        library = json.loads(REFERENCE_LIBRARY_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        raise RuntimeError(f"No se pudo leer {REFERENCE_LIBRARY_PATH}: {exc}") from exc

    candidates = [
        Path("referencias") / item["file"]
        for item in library.get("references", [])
        if item.get("enabled", True) and creative_concept in item.get("concepts", [])
    ]
    existing = [path for path in candidates if path.exists()]
    return random.choice(existing) if existing else None


def select_background_image() -> Optional[Path]:
    """Elige al azar una foto real propia de assets/backgrounds, si hay alguna disponible."""
    if not BACKGROUNDS_DIR.exists():
        return None

    candidates = [
        path
        for path in BACKGROUNDS_DIR.iterdir()
        if path.is_file() and path.suffix.lower() in {".png", ".jpg", ".jpeg"}
    ]
    return random.choice(candidates) if candidates else None


def story_text(content: StoryContent) -> str:
    return " ".join(
        part for part in [
            content.kicker,
            content.headline,
            content.subheadline,
            content.cta,
            content.footer,
            content.badge or "",
        ] if part
    )


def validate_story_content(content: StoryContent, facts: dict[str, Any]) -> list[str]:
    text = story_text(content)
    normalized = normalize_for_validation(text)
    errors: list[str] = []

    prohibited_phrases = [
        "envio gratis",
        "envio gratuito",
        "envio sin cargo",
        "entrega inmediata",
        "entregas inmediatas",
        "entrega hoy mismo",
        "entrega en el dia",
        "entrega garantizada",
        "calidad certificada",
        "certificacion",
        "certificado",
        "certificada",
    ]
    for phrase in prohibited_phrases:
        if phrase in normalized:
            errors.append(f"Afirmación no permitida: {phrase}")

    allowed_prices = {int(product["price_ars"]) for product in facts["products"]}
    mentioned_prices = {
        int(raw.replace(".", ""))
        for raw in re.findall(r"\$\s*([0-9][0-9.]*)", text)
    }
    unknown_prices = mentioned_prices.difference(allowed_prices)
    if unknown_prices:
        errors.append(f"Precio no autorizado: {sorted(unknown_prices)}")

    allowed_weights = {int(product["weight_kg"]) for product in facts["products"]}
    allowed_weights.add(int(facts["delivery"]["minimum_order_kg"]))
    mentioned_weights = {
        int(raw)
        for raw in re.findall(r"\b([0-9]+)\s*kg\b", normalized)
    }
    unknown_weights = mentioned_weights.difference(allowed_weights)
    if unknown_weights:
        errors.append(f"Cantidad en kg no autorizada: {sorted(unknown_weights)}")

    digits = re.sub(r"\D", "", text)
    expected_phone = str(facts["orders"]["whatsapp_number"])
    if "whatsapp" in normalized and "11" in digits and expected_phone not in digits:
        errors.append("Número de WhatsApp incompleto o incorrecto")

    if normalized.endswith(("florenc", "quil", "beraz")):
        errors.append("Localidad incompleta")

    if ("envio" in normalized or "entrega" in normalized) and "desde 45 kg" not in normalized:
        if any(word in normalized for word in ["gratis", "sin cargo", "inmediata", "garantizada"]):
            errors.append("La entrega contradice las condiciones comerciales confirmadas")

    return errors


def build_openai_prompt(ctx: StoryContext, facts: dict[str, Any], objective: str) -> str:
    prompt_context = {
        "objective": objective,
        "date": ctx.now.strftime("%Y-%m-%d"),
        "weekday": ctx.weekday,
        "hour": ctx.hour,
        "weather": ctx.weather.label,
        "temperature_c": ctx.weather.temperature_c,
        "stock_level": ctx.business.stock_level,
        "business_facts": facts,
    }
    return json.dumps(prompt_context, ensure_ascii=False, indent=2)


def generate_story_content_with_openai(
    ctx: StoryContext,
    facts: dict[str, Any],
    model: str,
    objective: str,
) -> StoryContent:
    if not os.getenv("OPENAI_API_KEY"):
        raise RuntimeError("Falta la variable de entorno OPENAI_API_KEY")

    client = OpenAI()
    response = client.responses.parse(
        model=model,
        instructions=(
            "Sos el redactor de historias de Instagram de Hielito, un negocio argentino de hielo. "
            "Escribí en español rioplatense, con tono directo, útil y confiable. "
            "Generá una única historia breve y fácil de leer en celular. "
            "Usá exclusivamente los datos incluidos en business_facts. "
            "Nunca inventes precios, promociones, disponibilidad, zonas, certificaciones ni condiciones de entrega. "
            "No prometas envío gratis, entrega inmediata ni entrega en el día. "
            "Si mencionás entregas, aclaralas como coordinadas desde 45 kg. "
            "Comunicá una sola idea comercial por historia; no listes todos los productos y precios juntos. "
            "El CTA debe ser muy corto y nunca debe incluir el número de teléfono. "
            "No cortes palabras, localidades ni datos para respetar límites de longitud. "
            "Evitá hashtags y emojis porque el diseño ya aporta el aspecto visual. "
            "El footer debe contener una zona, una condición de entrega o un dato comercial confirmado."
        ),
        input=build_openai_prompt(ctx, facts, objective),
        text_format=GeneratedStoryContent,
    )
    generated = response.output_parsed
    if generated is None:
        raise RuntimeError("OpenAI no devolvió contenido estructurado")

    content = StoryContent(
        template_name=choose_template(ctx.weather, ctx.weekday, ctx.hour, ctx.business.stock_level),
        kicker=clean_generated_text(generated.kicker).rstrip("."),
        headline=clean_generated_text(generated.headline).rstrip("."),
        subheadline=clean_generated_text(generated.subheadline),
        cta=clean_generated_text(generated.cta).rstrip("."),
        footer=ctx.business.major_message,
        badge=generated.badge,
    )
    validation_errors = validate_story_content(content, facts)
    if validation_errors:
        raise RuntimeError("; ".join(validation_errors))
    return content


def build_openai_image_prompt(
    ctx: StoryContext,
    facts: dict[str, Any],
    objective: str,
    creative_concept: str,
    variation_seed: Optional[str] = None,
) -> str:
    products = ", ".join(f"{product['weight_kg']} kg" for product in facts["products"])
    zones = ", ".join(facts["delivery"]["zones"])
    weather_notes = {
        "hot": "hot summer day, refreshing condensation and strong cold contrast",
        "warm": "warm pleasant day, refreshing atmosphere",
        "normal": "neutral commercial atmosphere",
        "cold": "cool day, professional supply atmosphere",
        "rainy": "cozy event atmosphere on a rainy day",
    }
    concept_direction = select_creative_variation(creative_concept, variation_seed or ctx.now.date().isoformat())
    return (
        "Create a visually memorable vertical Instagram Story advertising image for Hielito, "
        "an ice cube production and distribution business in Zona Sur, Buenos Aires. "
        f"Campaign objective: {objective}. "
        f"Available ice bag sizes: {products}. General service area: {zones}. "
        f"Scene mood: {weather_notes[ctx.weather.label]}. "
        f"Creative direction: {concept_direction} "
        "The result must feel like a finished campaign concept created by an experienced Latin American advertising art director, "
        "not a generic stock photo and not a plain product catalog image. Use realistic materials, nuanced lighting, depth, "
        "intentional color contrast, and an asymmetrical editorial composition. "
        "Leave usable negative space for later typography overlay without making the composition feel empty. "
        "Do not include any text, letters, numbers, prices, logos, watermarks, labels, people, hands, or brand names."
    )


def generate_openai_background(
    ctx: StoryContext,
    facts: dict[str, Any],
    model: str,
    objective: str,
    creative_concept: str,
    reference_image: Optional[Path] = None,
    image_quality: str = "high",
    variation_seed: Optional[str] = None,
) -> Image.Image:
    if not os.getenv("OPENAI_API_KEY"):
        raise RuntimeError("Falta la variable de entorno OPENAI_API_KEY")

    prompt = build_openai_image_prompt(ctx, facts, objective, creative_concept, variation_seed)
    client = OpenAI()
    if reference_image:
        if not reference_image.exists():
            raise RuntimeError(f"No se encontró la referencia visual: {reference_image}")
        with reference_image.open("rb") as reference_file:
            response = client.images.edit(
                model=model,
                image=reference_file,
                prompt=(
                    f"Use the attached image only as a visual art-direction reference for composition, color relationships, "
                    f"lighting, graphic energy, typography density, and level of polish. Do not copy or reproduce any text, logos, "
                    f"prices, claims, exact objects, or layout from the reference. {prompt}"
                ),
                size="1024x1536",
                quality=image_quality,
                output_format="png",
            )
    else:
        response = client.images.generate(
            model=model,
            prompt=prompt,
            size="1024x1536",
            quality=image_quality,
            output_format="png",
        )
    if not response.data or not response.data[0].b64_json:
        raise RuntimeError("OpenAI no devolvió una imagen")

    raw = base64.b64decode(response.data[0].b64_json)
    image = Image.open(io.BytesIO(raw)).convert("RGBA")
    return ImageOps.fit(image, CANVAS_SIZE, method=Image.Resampling.LANCZOS)


def build_full_openai_story_prompt(
    ctx: StoryContext,
    content: StoryContent,
    facts: dict[str, Any],
    objective: str,
    creative_concept: str,
    has_reference: bool,
    variation_seed: Optional[str] = None,
    brand_identity: Optional[dict[str, list[str]]] = None,
    has_background: bool = False,
) -> str:
    delivery = facts.get("delivery", {})
    orders = facts.get("orders", {})
    zones = format_zones(delivery.get("zones", []))
    whatsapp = safe_text(orders.get("whatsapp_display"))
    major_message = safe_text(ctx.business.major_message)
    concept_text = select_creative_variation(creative_concept, variation_seed or ctx.now.date().isoformat())

    identity = brand_identity if brand_identity is not None else load_brand_identity()
    visual_style = ", ".join(identity.get("visual_aesthetics") or []) or "clean, cold, commercial, trustworthy"
    tone = ", ".join(identity.get("tone_of_voice") or []) or "direct, helpful, practical, reliable"
    values = ", ".join(identity.get("brand_values") or []) or "reliability, practicality, efficiency"
    fonts_hint = ", ".join(identity.get("fonts") or []) or "a modern geometric sans-serif"
    # Las imágenes de entrada se pasan a la API en este mismo orden: fondo real (si hay),
    # referencia de estilo (si hay), logo actual (siempre). Los textos de abajo deben describir
    # cada "Image N" en ese mismo orden.
    image_descriptions: list[str] = []
    if has_background:
        image_descriptions.append(
            "an authentic real photograph taken by the Hielito team on location.\n"
            "  Use this as the actual visual base and main scene of the ad. Preserve its real, "
            "authentic photographic character — the objects, environment, and composition must "
            "remain recognizable as this same photo.\n"
            "  You may refine lighting and color grading and add the cold/frost texture described "
            "below, and you must add the design elements (logo, text, CTA) on top of it, but do not "
            "replace it with a different generated scene or invent a different location."
        )
    if has_reference:
        reference_note = (
            "previously approved Hielito Instagram Story.\n"
            "  Use it ONLY as art direction for visual hierarchy, typography energy, price prominence, "
            "centered composition, blue/cold palette, contrast, polish, and commercial structure.\n"
            "  Do NOT copy old words, old numbers, old claims, or old logo."
        )
        if has_background:
            reference_note += (
                "\n  Do NOT use this image as the scene/background — the real photo above is the "
                "actual visual base."
            )
        image_descriptions.append(reference_note)
    image_descriptions.append(
        "current Hielito logo.\n"
        "  Use this current logo as the brand mark. Reproduce it as cleanly and accurately as possible.\n"
        "  Do not redesign, distort, simplify, replace, or invent a different logo."
    )

    heading = "REFERENCE IMAGES:" if len(image_descriptions) > 1 else "REFERENCE IMAGE:"
    reference_instructions = "\n" + heading + "\n" + "\n\n".join(
        f"- Image {index}: {description}"
        for index, description in enumerate(image_descriptions, start=1)
    ) + "\n"

    visible_copy_items = [("LOGO", "Hielito")]
    kicker = safe_text(content.kicker)
    if normalize_for_validation(kicker) != "hielito":
        visible_copy_items.append(("KICKER", kicker))
    visible_copy_items.extend(
        [
            ("MAIN_HEADLINE", safe_text(content.headline)),
            ("SUPPORTING_TEXT", clean_supporting_text_for_layout(content.subheadline)),
            ("CTA", safe_text(content.cta)),
        ]
    )
    if major_message:
        visible_copy_items.append(("DELIVERY_CONDITION", major_message))
    if whatsapp:
        visible_copy_items.append(("WHATSAPP", whatsapp))
    if zones:
        visible_copy_items.append(("SERVICE_ZONES", zones))

    visible_copy_block = "\n".join(
        f'- {label}: "{text}"'
        for label, text in visible_copy_items
        if text
    )

    return f"""
Create the COMPLETE final vertical Instagram Story advertisement for Hielito.

This must be a finished ad, not a mockup:
include realistic photography, graphic design, typography, current logo, price/commercial copy, CTA, and service information.
Do not leave empty placeholders for later editing.

{reference_instructions}

CANVAS / FORMAT:
- Vertical Instagram Story.
- 1080 x 1920 px.
- 9:16 aspect ratio.
- High resolution.
- Optimized for mobile viewing.
- Professional Meta Ads / Instagram Stories look.

CAMPAIGN OBJECTIVE:
{safe_text(objective)}

CREATIVE DIRECTION:
{concept_text}

BRAND FEEL:
- Argentine local delivery business in Zona Sur, Buenos Aires.
- Visual style to convey: {visual_style}.
- Tone of voice to convey visually (mood, not literal words): {tone}.
- Brand values to communicate through the scene: {values}.
- Cold, fresh, practical, high-conversion — never sacrifice legibility or realism for style.
- It should look like a polished WhatsApp-driven local ad, not a generic poster.

VISUAL SCENE:
- Use realistic transparent bags of ice as the main product.
- Ice must be visible inside the bags.
- Render this as professional advertising product photography, not a 3D render or illustration:
  believable optical imperfections (subtle lens vignetting, natural highlight bloom on wet surfaces,
  realistic depth of field), physically plausible light falloff and shadow softness.
- Add cold texture with tactile detail: individual condensation droplets, fine frost crystals, sharp
  internal fracture lines inside the ice, cool blue specular reflections on wet surfaces.
- Use deliberate directional lighting (single key light or golden-hour/blue-hour ambient light as
  specified in the creative direction above) rather than flat, shadowless lighting.
- The product must feel abundant, clean, cold, and ready for delivery.
- Background should support readability, not compete with the text.
- Avoid fake-looking 3D renders, plastic/waxy surfaces, or overly uniform CGI ice cubes.
- Avoid cartoon style.
- Avoid overdecorated party imagery.

COLOR PALETTE:
- Dominant: ice blue, white, cyan, cold gray, deep navy.
- Use high contrast.
- Prefer a dark blue translucent overlay, gradient, or text plate behind the copy.
- Keep the overall look cold and clean.

LAYOUT / SAFE AREA (Instagram Stories, 1080 x 1920 px canvas):
- Picture this canvas as a phone screen with real, opaque Instagram UI permanently covering two
  horizontal bands: the top ~13% of the image (roughly the top 250 px) is covered by the profile
  picture, username, timestamp, and close button; the bottom ~20% of the image (roughly the
  bottom 380 px) is covered by the reply message bar, text input field, and interactive stickers.
  Anything placed in those two bands will be physically hidden from viewers — treat them as if
  they do not exist for text purposes.
- Those top and bottom bands must contain ONLY background photo / decorative gradient, with zero
  text, logo, price, or CTA in them.
- Horizontal safe area: leave ~65 px (~6%) of clear padding on both the left and right edges;
  keep important content within the central ~950 px (~88% of the canvas width).
- Design all text so it fits and finishes within the middle ~67% of the canvas height (roughly
  from the 13% mark down to the 80% mark, i.e. approximately y = 250 px to y = 1540 px) — aim to
  finish the very last line of text by about the 75% mark (~1440 px) so there is visible breathing
  room before the bottom UI band, not text touching its edge.
- Center the entire main text block horizontally.
- Use strong spacing between title, price/commercial info, delivery info, and CTA.
- Do not place text near edges.
- Do not tilt, curve, warp, or scatter the text.

GRAPHIC HIERARCHY:
1. Current Hielito logo: visible, clean, brand-like, not oversized.
2. Kicker/headline: bold and immediately readable.
3. Main commercial message: strongest central focus.
4. Supporting text: clear and secondary.
5. Delivery condition and zones: smaller, readable, not dominant.
6. CTA and WhatsApp: clear, centered, visible, not too low.

TYPOGRAPHY:
- Bold sans-serif.
- Modern, clean, thick, highly legible.
- Preferred brand typeface spirit: {fonts_hint} — if unavailable, use the closest clean, modern,
  highly legible geometric sans-serif with a similar spirit.
- White text or very light text over dark blue overlay.
- Price or key commercial line must have the strongest emphasis when present in the provided copy.
- Do not use tiny text.
- Do not use decorative fonts.
- Do not generate distorted letters.

VISIBLE TEXT RULES:
Use ONLY the exact Spanish text listed below.
The role labels LOGO, KICKER, MAIN_HEADLINE, SUPPORTING_TEXT, CTA, DELIVERY_CONDITION, WHATSAPP, and SERVICE_ZONES are internal layout labels.
Do NOT render those role labels in the image.
Do NOT add, remove, translate, abbreviate, paraphrase, or invent any visible words, numbers, emojis, symbols, claims, prices, or zones.
Render every provided copy item exactly once. Do not repeat the CTA, WhatsApp, delivery condition, zones, headline, or supporting text.

VISIBLE COPY TO RENDER:
{visible_copy_block}

SAFE AREA REMINDER FOR THE ITEMS ABOVE:
- None of the copy items above may be placed inside the top 250 px or bottom 380 px exclusion zones
  (the ones physically covered by Instagram's own UI), or within ~65 px of the left/right edges.
- DELIVERY_CONDITION, WHATSAPP, and SERVICE_ZONES sit lowest in the hierarchy and are the ones most
  likely to get pushed too close to the bottom edge — double-check these three specifically before
  finalizing the layout.
- If space is tight, shrink font size or spacing for these items first. Never solve tight spacing by
  extending text into the bottom 380 px band — that text would be invisible to real viewers.

CONTENT RESTRICTIONS:
- Do not mention free shipping.
- Do not mention immediate delivery.
- Do not mention same-day guaranteed delivery.
- Do not mention certifications.
- Do not include any unlisted price.
- Do not add extra discounts or promotions.
- Do not include watermarks.
- Do not include unrelated logos.
- Do not include fake brands on ice bags.
- Do not include people, faces, hands, alcohol bottles, nightclub scenes, or unrelated products.

QUALITY CHECK BEFORE FINAL IMAGE:
- Does it look like a real Hielito Instagram Story ad?
- Is the product clearly ice in bags?
- Is the text centered and readable on a phone?
- Look specifically at the bottom 380 px of the canvas: is it completely free of text, price, CTA,
  WhatsApp, and delivery/zone information? If any of that content overlaps this band, move it up
  before finalizing — it would be invisible behind Instagram's reply bar and stickers.
- Is the visual hierarchy similar in quality and polish to the approved reference?
- Is the current logo used, not an invented logo?
- Are there zero extra words beyond the approved visible copy?
""".strip()


def generate_complete_openai_story(
    ctx: StoryContext,
    content: StoryContent,
    facts: dict[str, Any],
    model: str,
    objective: str,
    creative_concept: str,
    reference_image: Optional[Path] = None,
    image_quality: str = "high",
    variation_seed: Optional[str] = None,
    brand_identity: Optional[dict[str, list[str]]] = None,
    background_image: Optional[Path] = None,
) -> tuple[Image.Image, str]:
    if not os.getenv("OPENAI_API_KEY"):
        raise RuntimeError("Falta la variable de entorno OPENAI_API_KEY")
    if not LOGO_PATH.exists():
        raise RuntimeError(f"No se encontró el logo actual: {LOGO_PATH}")
    if reference_image and not reference_image.exists():
        raise RuntimeError(f"No se encontró la referencia visual: {reference_image}")
    if background_image and not background_image.exists():
        raise RuntimeError(f"No se encontró la imagen de fondo: {background_image}")

    prompt = build_full_openai_story_prompt(
        ctx,
        content,
        facts,
        objective,
        creative_concept,
        has_reference=reference_image is not None,
        variation_seed=variation_seed,
        brand_identity=brand_identity,
        has_background=background_image is not None,
    )
    client = OpenAI()

    # El orden acá debe coincidir con el orden que describe reference_instructions:
    # fondo real (si hay), referencia de estilo (si hay), logo actual (siempre).
    with contextlib.ExitStack() as stack:
        image_files = []
        if background_image:
            image_files.append(stack.enter_context(background_image.open("rb")))
        if reference_image:
            image_files.append(stack.enter_context(reference_image.open("rb")))
        image_files.append(stack.enter_context(LOGO_PATH.open("rb")))

        response = client.images.edit(
            model=model,
            image=image_files if len(image_files) > 1 else image_files[0],
            prompt=prompt,
            size="1024x1536",
            quality=image_quality,
            output_format="png",
        )

    if not response.data or not response.data[0].b64_json:
        raise RuntimeError("OpenAI no devolvió una historia completa")

    raw = base64.b64decode(response.data[0].b64_json)
    image = Image.open(io.BytesIO(raw)).convert("RGB")
    return ImageOps.fit(image, CANVAS_SIZE, method=Image.Resampling.LANCZOS), prompt


def generate_complete_gemini_story(
    ctx: StoryContext,
    content: StoryContent,
    facts: dict[str, Any],
    model: str,
    objective: str,
    creative_concept: str,
    reference_image: Optional[Path] = None,
    image_size: str = "2K",
    variation_seed: Optional[str] = None,
    brand_identity: Optional[dict[str, list[str]]] = None,
    background_image: Optional[Path] = None,
) -> tuple[Image.Image, str]:
    """Misma pieza que generate_complete_openai_story, pero generada con Gemini (Nano Banana)
    en vez de OpenAI. Reutiliza el mismo prompt (no es específico de ningún proveedor)."""
    if not os.getenv("GEMINI_API_KEY"):
        raise RuntimeError("Falta la variable de entorno GEMINI_API_KEY")
    if not LOGO_PATH.exists():
        raise RuntimeError(f"No se encontró el logo actual: {LOGO_PATH}")
    if reference_image and not reference_image.exists():
        raise RuntimeError(f"No se encontró la referencia visual: {reference_image}")
    if background_image and not background_image.exists():
        raise RuntimeError(f"No se encontró la imagen de fondo: {background_image}")

    prompt = build_full_openai_story_prompt(
        ctx,
        content,
        facts,
        objective,
        creative_concept,
        has_reference=reference_image is not None,
        variation_seed=variation_seed,
        brand_identity=brand_identity,
        has_background=background_image is not None,
    )
    client = genai.Client()

    # Mismo orden que describe reference_instructions: fondo real (si hay),
    # referencia de estilo (si hay), logo actual (siempre).
    contents: list[Any] = [prompt]
    if background_image:
        contents.append(Image.open(background_image))
    if reference_image:
        contents.append(Image.open(reference_image))
    contents.append(Image.open(LOGO_PATH))

    response = client.models.generate_content(
        model=model,
        contents=contents,
        config=genai_types.GenerateContentConfig(
            response_modalities=[genai_types.Modality.TEXT, genai_types.Modality.IMAGE],
            image_config=genai_types.ImageConfig(aspect_ratio="9:16", image_size=image_size),
        ),
    )

    candidates = response.candidates or []
    parts = candidates[0].content.parts if candidates and candidates[0].content else []
    for part in parts:
        if part.inline_data is not None and part.inline_data.data:
            image = Image.open(io.BytesIO(part.inline_data.data)).convert("RGB")
            return ImageOps.fit(image, CANVAS_SIZE, method=Image.Resampling.LANCZOS), prompt

    raise RuntimeError("Gemini no devolvió una imagen")


# ----------------------------
# Reglas de negocio
# ----------------------------

def choose_template(weather: WeatherContext, weekday: str, hour: int, stock_level: str) -> str:
    bucket = hour_bucket(hour)

    if stock_level == "low":
        return "minimal"
    if weather.label == "rainy":
        return "soft-blue"
    if weather.label in {"hot", "warm"}:
        return "intense-blue"
    if weekday in {"friday", "saturday"}:
        return "party-blue"
    if bucket in {"evening", "night"}:
        return "dark-blue"
    return "clean-blue"


def choose_strategy(ctx: StoryContext) -> str:
    weekday = ctx.weekday
    bucket = hour_bucket(ctx.hour)
    weather = ctx.weather.label
    stock = ctx.business.stock_level

    if stock == "low":
        return "limited_stock"
    if weekday == "friday":
        return "friday_push"
    if weekday == "saturday":
        return "urgent_sale"
    if weather == "hot" and bucket in {"afternoon", "evening"}:
        return "heat_push"
    if weather == "rainy":
        return "event_sale"
    if bucket == "morning":
        return "morning_reminder"
    if bucket == "night":
        return "late_order"
    return "general_sale"


def build_story_content(ctx: StoryContext) -> StoryContent:
    strategy = choose_strategy(ctx)
    template = choose_template(ctx.weather, ctx.weekday, ctx.hour, ctx.business.stock_level)

    brand = ctx.business.brand_name
    zones = ctx.business.delivery_zones
    temp = ctx.weather.temperature_c
    temp_text = f"{temp}°" if temp is not None else ""

    options: dict[str, list[StoryContent]] = {
        "friday_push": [
            StoryContent(
                template_name=template,
                kicker="VIERNES",
                headline="Se viene el finde",
                subheadline="Que no te falte hielo para la previa, el cumple o el asado.",
                cta="Escribinos y coordiná tu pedido hoy",
                footer=zones,
                badge="Pedidos abiertos",
            ),
            StoryContent(
                template_name=template,
                kicker="FINDE",
                headline="Hoy se vende hielo",
                subheadline="Y mucho. Pedilo antes de que arranque el movimiento.",
                cta="Consultanos por WhatsApp",
                footer=zones,
                badge="Entregas coordinadas",
            ),
        ],
        "urgent_sale": [
            StoryContent(
                template_name=template,
                kicker="SÁBADO",
                headline="¿Necesitás hielo hoy?",
                subheadline="Tomamos pedidos para eventos, juntadas y compras de último momento.",
                cta="Mandanos mensaje ahora",
                footer=zones,
                badge="Consultá disponibilidad",
            ),
            StoryContent(
                template_name=template,
                kicker="HOY",
                headline="No te quedes sin hielo",
                subheadline="Si tenés gente en casa, resolvelo rápido.",
                cta="Pedinos ahora",
                footer=zones,
                badge="Últimos horarios",
            ),
        ],
        "heat_push": [
            StoryContent(
                template_name=template,
                kicker=temp_text or "CALOR",
                headline="Con este calor el hielo vuela",
                subheadline="Aprovechá y hacé tu pedido antes del pico de la tarde.",
                cta="Pedinos por WhatsApp",
                footer=zones,
                badge="Día fuerte",
            ),
            StoryContent(
                template_name=template,
                kicker="CALOR",
                headline="Más calor = más hielo",
                subheadline="Ideal para bebidas, eventos y negocios.",
                cta="Consultanos por cantidad",
                footer=ctx.business.major_message,
                badge="Venta minorista y mayorista",
            ),
        ],
        "event_sale": [
            StoryContent(
                template_name=template,
                kicker="PLANES EN CASA",
                headline="Aunque llueva, el hielo sigue saliendo",
                subheadline="Si tenés reunión, cumple o juntada, te lo resolvemos.",
                cta="Escribinos y reservá",
                footer=zones,
                badge="Pedidos programados",
            ),
            StoryContent(
                template_name=template,
                kicker="EVENTOS",
                headline="Hielo para hoy o para el finde",
                subheadline="Pedidos para casas, comercios y reuniones.",
                cta="Consultanos disponibilidad",
                footer=zones,
                badge="Tomamos pedidos",
            ),
        ],
        "morning_reminder": [
            StoryContent(
                template_name=template,
                kicker="BUEN DÍA",
                headline="Dejá tu pedido temprano",
                subheadline="Y coordinamos mejor la entrega para hoy.",
                cta="Escribinos ahora",
                footer=zones,
                badge="Organizá tu día",
            ),
            StoryContent(
                template_name=template,
                kicker="TEMPRANO",
                headline=f"{brand} ya está tomando pedidos",
                subheadline="Si necesitás hielo más tarde, mejor reservar ahora.",
                cta="Pedí por WhatsApp",
                footer=zones,
                badge="Pedidos abiertos",
            ),
        ],
        "late_order": [
            StoryContent(
                template_name=template,
                kicker="NOCHE",
                headline="Todavía estás a tiempo",
                subheadline="Si te falta hielo para hoy, escribinos ya.",
                cta="Consultá disponibilidad",
                footer=zones,
                badge="Últimos pedidos",
            ),
            StoryContent(
                template_name=template,
                kicker="AHORA",
                headline="El plan sigue. El hielo también.",
                subheadline="Tomamos pedidos según disponibilidad.",
                cta="Mandanos mensaje",
                footer=zones,
                badge="Noche activa",
            ),
        ],
        "limited_stock": [
            StoryContent(
                template_name=template,
                kicker="STOCK LIMITADO",
                headline="Reservá tu pedido cuanto antes",
                subheadline="Hoy estamos con disponibilidad reducida.",
                cta="Consultanos antes de pedir",
                footer=zones,
                badge="Cupos limitados",
            ),
            StoryContent(
                template_name=template,
                kicker="IMPORTANTE",
                headline="Queda poco stock",
                subheadline="Tomamos pedidos según disponibilidad del momento.",
                cta="Escribinos y te confirmamos",
                footer=zones,
                badge="Disponibilidad variable",
            ),
        ],
        "general_sale": [
            StoryContent(
                template_name=template,
                kicker="HIELITO",
                headline="Hielo para tu día",
                subheadline="Pedidos para casas, comercios, eventos y juntadas.",
                cta="Escribinos por WhatsApp",
                footer=zones,
                badge="Venta directa",
            ),
            StoryContent(
                template_name=template,
                kicker="PEDIDOS",
                headline="Tomamos pedidos todos los días",
                subheadline="Consultanos por cantidad y zonas de entrega.",
                cta="Mandanos mensaje",
                footer=ctx.business.major_message,
                badge="Minorista y mayorista",
            ),
        ],
    }

    return random.choice(options[strategy])


# ----------------------------
# Render visual
# ----------------------------

def load_font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    candidates = []
    if bold:
        candidates.extend(
            [
                "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
                "/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf",
            ]
        )
    else:
        candidates.extend(
            [
                "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
                "/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf",
            ]
        )

    for path in candidates:
        if Path(path).exists():
            return ImageFont.truetype(path, size=size)

    return ImageFont.load_default()


def load_brand_config() -> dict:
    if BRAND_CONFIG_PATH.exists():
        try:
            return json.loads(BRAND_CONFIG_PATH.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            pass

    return {
        "brand_name": "Hielito",
        "whatsapp_label": "WhatsApp: 11 7062-8132",
        "delivery_zones": "Berazategui • Quilmes • Florencio Varela",
        "major_message": "Entregas coordinadas desde 45 kg",
        "primary_color": "#0D47A1",
        "secondary_color": "#42A5F5",
        "accent_color": "#E0F2FE",
        "text_color": "#FFFFFF",
        "dark_overlay": "#0A1942",
    }


def load_template_image(template_name: str, fallback_top: str, fallback_bottom: str) -> Image.Image:
    candidates = [
        TEMPLATES_DIR / f"{template_name}.png",
        TEMPLATES_DIR / f"{template_name}.jpg",
        TEMPLATES_DIR / f"{template_name}.jpeg",
        TEMPLATES_DIR / "default.png",
        TEMPLATES_DIR / "default.jpg",
        TEMPLATES_DIR / "default.jpeg",
    ]

    for candidate in candidates:
        if candidate.exists():
            try:
                image = Image.open(candidate).convert("RGBA")
                return ImageOps.fit(image, CANVAS_SIZE, method=Image.Resampling.LANCZOS)
            except OSError:
                continue

    return vertical_gradient(CANVAS_SIZE, fallback_top, fallback_bottom).convert("RGBA")


def hex_to_rgb(value: str) -> tuple[int, int, int]:
    value = value.lstrip("#")
    return tuple(int(value[i:i + 2], 16) for i in (0, 2, 4))


def vertical_gradient(size: tuple[int, int], top: str, bottom: str) -> Image.Image:
    width, height = size
    top_rgb = hex_to_rgb(top)
    bottom_rgb = hex_to_rgb(bottom)
    base = Image.new("RGB", size)
    draw = ImageDraw.Draw(base)

    for y in range(height):
        ratio = y / max(height - 1, 1)
        r = int(top_rgb[0] * (1 - ratio) + bottom_rgb[0] * ratio)
        g = int(top_rgb[1] * (1 - ratio) + bottom_rgb[1] * ratio)
        b = int(top_rgb[2] * (1 - ratio) + bottom_rgb[2] * ratio)
        draw.line([(0, y), (width, y)], fill=(r, g, b))

    return base


def add_ice_circles(image: Image.Image, count: int = 18) -> None:
    draw = ImageDraw.Draw(image, "RGBA")
    width, height = image.size

    for _ in range(count):
        radius = random.randint(35, 120)
        x = random.randint(-50, width + 50)
        y = random.randint(100, height - 100)
        alpha = random.randint(18, 55)
        draw.ellipse((x, y, x + radius, y + radius), fill=(255, 255, 255, alpha))


def add_glow_box(image: Image.Image, box: tuple[int, int, int, int], radius: int = 45) -> None:
    overlay = Image.new("RGBA", image.size, (0, 0, 0, 0))
    od = ImageDraw.Draw(overlay)
    od.rounded_rectangle(box, radius=radius, fill=(255, 255, 255, 28))
    overlay = overlay.filter(ImageFilter.GaussianBlur(5))
    image.alpha_composite(overlay)


def add_vignette(image: Image.Image, strength: int = 90) -> None:
    width, height = image.size
    vignette = Image.new("RGBA", image.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(vignette)

    # sombra superior
    for i in range(220):
        alpha = max(0, strength - i // 2)
        draw.rectangle((0, 0, width, i + 1), fill=(0, 0, 0, alpha))

    # sombra inferior
    for i in range(380):
        alpha = max(0, strength + 25 - i // 3)
        y0 = height - i - 1
        draw.rectangle((0, y0, width, height), fill=(0, 0, 0, alpha))

    image.alpha_composite(vignette)


def draw_soft_shadow(draw: ImageDraw.ImageDraw, box: tuple[int, int, int, int], radius: int = 36) -> None:
    x1, y1, x2, y2 = box
    draw.rounded_rectangle((x1 + 6, y1 + 10, x2 + 6, y2 + 10), radius=radius, fill=(0, 0, 0, 42))


def add_frost_edges(image: Image.Image, count: int = 12) -> None:
    draw = ImageDraw.Draw(image, "RGBA")
    width, height = image.size

    for _ in range(count):
        side = random.choice(["left", "right"])
        y = random.randint(180, height - 260)
        length = random.randint(90, 220)
        thickness = random.randint(10, 22)
        if side == "left":
            points = [(0, y), (length, y + thickness), (0, y + thickness * 2)]
        else:
            points = [(width, y), (width - length, y + thickness), (width, y + thickness * 2)]
        draw.polygon(points, fill=(255, 255, 255, random.randint(28, 55)))


def draw_badge(draw: ImageDraw.ImageDraw, text: str, x: int, y: int, fill_rgb: tuple[int, int, int]) -> None:
    badge_font = load_font(34, bold=True)
    bbox = draw.textbbox((x, y), text, font=badge_font)
    pad_x = 24
    pad_y = 14
    box = (bbox[0] - pad_x, bbox[1] - pad_y, bbox[2] + pad_x, bbox[3] + pad_y)
    draw.rounded_rectangle((box[0] + 4, box[1] + 8, box[2] + 4, box[3] + 8), radius=26, fill=(0, 0, 0, 40))
    draw.rounded_rectangle(box, radius=26, fill=(255, 255, 255, 235), outline=(255, 255, 255, 140), width=2)
    draw.text((x, y), text, font=badge_font, fill=(*fill_rgb, 255))


def draw_chip(draw: ImageDraw.ImageDraw, text: str, x: int, y: int, fill: tuple[int, int, int], text_fill: tuple[int, int, int]) -> tuple[int, int, int, int]:
    chip_font = load_font(26, bold=True)
    bbox = draw.textbbox((x, y), text, font=chip_font)
    box = (bbox[0] - 18, bbox[1] - 12, bbox[2] + 18, bbox[3] + 12)
    draw.rounded_rectangle(box, radius=24, fill=(*fill, 210))
    draw.text((x, y), text, font=chip_font, fill=(*text_fill, 255))
    return box


def render_story(content: StoryContent, ctx: StoryContext) -> Image.Image:
    template_palette = {
        "intense-blue": ("#0A2E8A", "#73B7FF"),
        "soft-blue": ("#123B93", "#B9DCFF"),
        "party-blue": ("#081F68", "#4F94FF"),
        "dark-blue": ("#061742", "#2A68E8"),
        "clean-blue": ("#0D47A1", "#A9D1FF"),
        "minimal": ("#0B3E9B", "#C2E1FF"),
    }

    top, bottom = template_palette.get(content.template_name, ("#0D47A1", "#A9D1FF"))
    base = load_template_image(content.template_name, top, bottom)
    add_vignette(base, strength=48)

    draw = ImageDraw.Draw(base, "RGBA")
    text_fill = hex_to_rgb(ctx.business.text_color)
    accent_fill = hex_to_rgb(ctx.business.accent_color)
    primary_fill = hex_to_rgb(ctx.business.primary_color)
    overlay_rgb = hex_to_rgb(ctx.business.dark_overlay)
    left = 84
    right = 996
    content_width = right - left

    # Encabezado compacto
    brand_font = load_font(30, bold=True)
    kicker_font = load_font(28, bold=True)
    draw.rounded_rectangle((left, 74, left + 245, 130), radius=28, fill=(255, 255, 255, 238))
    draw.text((left + 24, 87), ctx.business.brand_name.upper(), font=brand_font, fill=(*primary_fill, 255))
    kicker_text = content.kicker.upper()
    if normalize_for_validation(kicker_text) == normalize_for_validation(ctx.business.brand_name):
        kicker_text = "HIELO EN CUBOS"
    draw.text((left, 176), kicker_text, font=kicker_font, fill=(*accent_fill, 255))

    if content.badge:
        badge_font = load_font(24, bold=True)
        badge_text = content.badge.upper()
        badge_width = min(390, draw.textbbox((0, 0), badge_text, font=badge_font)[2] + 44)
        draw.rounded_rectangle((right - badge_width, 164, right, 218), radius=27, fill=(*overlay_rgb, 190))
        draw.text((right - badge_width + 22, 178), badge_text, font=badge_font, fill=(*text_fill, 255))

    # Tarjeta principal con texto medido en píxeles
    hero_box = (left, 270, right, 940)
    draw.rounded_rectangle((left + 8, 282, right + 8, 952), radius=54, fill=(0, 0, 0, 35))
    draw.rounded_rectangle(hero_box, radius=54, fill=(*overlay_rgb, 158), outline=(255, 255, 255, 55), width=2)
    inner_left = left + 48
    inner_width = content_width - 96

    headline, title_font = fit_multiline_text(
        draw, content.headline.upper(), inner_width, 330, 86, 54, bold=True, spacing=4
    )
    draw.multiline_text((inner_left, 330), headline, font=title_font, fill=(*text_fill, 255), spacing=4)

    sub, sub_font = fit_multiline_text(
        draw, content.subheadline, inner_width, 190, 40, 30, spacing=8
    )
    draw.multiline_text((inner_left, 690), sub, font=sub_font, fill=(235, 245, 255, 242), spacing=8)

    # CTA siempre cabe y deja espacio reservado para el icono
    cta_box = (left, 1000, right, 1155)
    draw.rounded_rectangle((left + 7, 1011, right + 7, 1166), radius=42, fill=(0, 0, 0, 42))
    draw.rounded_rectangle(cta_box, radius=42, fill=(255, 255, 255, 245))
    cta, cta_font = fit_multiline_text(draw, content.cta, content_width - 150, 82, 43, 30, bold=True, spacing=2)
    cta_bbox = draw.multiline_textbbox((0, 0), cta, font=cta_font, spacing=2)
    cta_y = cta_box[1] + ((cta_box[3] - cta_box[1]) - (cta_bbox[3] - cta_bbox[1])) // 2 - cta_bbox[1]
    draw.multiline_text((left + 34, cta_y), cta, font=cta_font, fill=(*primary_fill, 255), spacing=2)
    icon_cx, icon_cy = right - 65, (cta_box[1] + cta_box[3]) // 2
    draw.ellipse((icon_cx - 28, icon_cy - 28, icon_cx + 28, icon_cy + 28), fill=(*primary_fill, 255))
    draw.polygon([(icon_cx - 7, icon_cy - 11), (icon_cx - 7, icon_cy + 11), (icon_cx + 11, icon_cy)], fill=(255, 255, 255, 255))

    # Información comercial breve
    footer_box = (left, 1235, right, 1545)
    draw.rounded_rectangle((left + 7, 1246, right + 7, 1556), radius=48, fill=(0, 0, 0, 38))
    draw.rounded_rectangle(footer_box, radius=48, fill=(255, 255, 255, 232))
    label_font = load_font(24, bold=True)
    draw.text((left + 38, 1275), "INFO ÚTIL", font=label_font, fill=(*primary_fill, 205))
    footer, footer_font = fit_multiline_text(
        draw, content.footer, content_width - 76, 190, 38, 28, bold=True, spacing=7
    )
    draw.multiline_text((left + 38, 1332), footer, font=footer_font, fill=(*overlay_rgb, 255), spacing=7)
    whatsapp_font = load_font(27, bold=True)
    draw.text((left + 38, 1470), ctx.business.whatsapp_label, font=whatsapp_font, fill=(*primary_fill, 255))

    # Logo discreto, sin competir con el contenido
    if LOGO_PATH.exists():
        try:
            logo = Image.open(LOGO_PATH).convert("RGBA")
            logo.thumbnail((108, 108))
            logo_bg = Image.new("RGBA", (124, 124), (0, 0, 0, 0))
            lg = ImageDraw.Draw(logo_bg)
            lg.ellipse((4, 8, 120, 124), fill=(0, 0, 0, 30))
            lg.ellipse((0, 0, 116, 116), fill=(255, 255, 255, 235))
            logo_bg.alpha_composite(logo, dest=((116 - logo.width) // 2, (116 - logo.height) // 2))
            base.alpha_composite(logo_bg, dest=(right - 124, 1685))
        except OSError:
            pass

    micro_font = load_font(22, bold=False)
    draw.text((left, 1736), "HIELO EN CUBOS · ZONA SUR", font=micro_font, fill=(255, 255, 255, 205))

    return base.convert("RGB")


def render_story_on_ai_background(content: StoryContent, ctx: StoryContext, background: Image.Image) -> Image.Image:
    base = background.convert("RGBA")
    overlay = Image.new("RGBA", CANVAS_SIZE, (0, 0, 0, 0))
    od = ImageDraw.Draw(overlay, "RGBA")

    # Oscurece bordes donde irá la información sin tapar la fotografía.
    for y in range(780):
        alpha = int(190 * (1 - y / 780))
        od.rectangle((0, y, 1080, y + 1), fill=(3, 18, 55, alpha))
    for y in range(720):
        alpha = int(220 * (y / 720))
        od.rectangle((0, 1200 + y, 1080, 1200 + y + 1), fill=(3, 18, 55, alpha))
    base.alpha_composite(overlay)

    draw = ImageDraw.Draw(base, "RGBA")
    left, right = 72, 1008
    width = right - left
    white = (255, 255, 255, 255)
    cyan = (188, 232, 255, 255)
    primary = hex_to_rgb(ctx.business.primary_color)

    # Marca
    brand_font = load_font(30, bold=True)
    draw.rounded_rectangle((left, 66, left + 245, 124), radius=29, fill=(255, 255, 255, 238))
    draw.text((left + 24, 80), ctx.business.brand_name.upper(), font=brand_font, fill=(*primary, 255))

    kicker_font = load_font(27, bold=True)
    kicker = content.kicker.upper()
    if normalize_for_validation(kicker) == normalize_for_validation(ctx.business.brand_name):
        kicker = "HIELO EN CUBOS"
    draw.text((left, 174), kicker, font=kicker_font, fill=cyan)

    # Titular sobre la fotografía
    headline, headline_font = fit_multiline_text(
        draw, content.headline.upper(), width, 350, 92, 58, bold=True, spacing=3
    )
    draw.multiline_text((left, 235), headline, font=headline_font, fill=white, spacing=3, stroke_width=2, stroke_fill=(0, 20, 60, 130))

    # Tarjeta inferior translúcida
    card = (left, 1320, right, 1780)
    draw.rounded_rectangle((card[0] + 7, card[1] + 10, card[2] + 7, card[3] + 10), radius=48, fill=(0, 0, 0, 50))
    draw.rounded_rectangle(card, radius=48, fill=(5, 25, 68, 218), outline=(255, 255, 255, 70), width=2)

    sub, sub_font = fit_multiline_text(draw, content.subheadline, width - 80, 145, 39, 29, spacing=7)
    draw.multiline_text((left + 40, 1370), sub, font=sub_font, fill=white, spacing=7)

    cta_font = load_font(34, bold=True)
    cta_text = content.cta
    cta_bbox = draw.textbbox((0, 0), cta_text, font=cta_font)
    cta_width = min(width - 80, cta_bbox[2] + 64)
    draw.rounded_rectangle((left + 40, 1535, left + 40 + cta_width, 1618), radius=41, fill=(255, 255, 255, 242))
    draw.text((left + 70, 1555), cta_text, font=cta_font, fill=(*primary, 255))

    footer, footer_font = fit_multiline_text(draw, content.footer, width - 80, 70, 27, 22, bold=True, spacing=4)
    draw.multiline_text((left + 40, 1662), footer, font=footer_font, fill=cyan, spacing=4)
    phone_font = load_font(24, bold=True)
    draw.text((left + 40, 1730), ctx.business.whatsapp_label, font=phone_font, fill=white)

    if LOGO_PATH.exists():
        try:
            logo = Image.open(LOGO_PATH).convert("RGBA")
            logo.thumbnail((105, 105))
            base.alpha_composite(logo, dest=(right - logo.width, 1800 - logo.height))
        except OSError:
            pass

    return base.convert("RGB")


# ----------------------------
# Entrada / salida
# ----------------------------

def build_context(args: argparse.Namespace) -> StoryContext:
    now = get_now(hour=args.hour, day=args.day)
    weather = WeatherContext(label=args.weather, temperature_c=args.temp)
    brand_config = load_brand_config()
    business = BusinessContext(
        brand_name=args.brand_name or brand_config.get("brand_name", "Hielito"),
        whatsapp_label=args.whatsapp_label or brand_config.get("whatsapp_label", "WhatsApp: 11 7062-8132"),
        delivery_zones=args.delivery_zones or brand_config.get("delivery_zones", "Berazategui • Quilmes • Florencio Varela"),
        stock_level=args.stock,
        major_message=args.major_message or brand_config.get("major_message", "Entregas coordinadas desde 45 kg"),
        primary_color=brand_config.get("primary_color", "#0D47A1"),
        secondary_color=brand_config.get("secondary_color", "#42A5F5"),
        accent_color=brand_config.get("accent_color", "#E0F2FE"),
        text_color=brand_config.get("text_color", "#FFFFFF"),
        dark_overlay=brand_config.get("dark_overlay", "#0A1942"),
    )
    return StoryContext(
        now=now,
        weekday=weekday_slug(now),
        hour=now.hour,
        weather=weather,
        business=business,
    )


def save_debug_metadata(
    path: Path,
    ctx: StoryContext,
    content: StoryContent,
    content_source: str,
    openai_model: Optional[str] = None,
    fallback_reason: Optional[str] = None,
    image_source: str = "pillow",
    reference_image: Optional[Path] = None,
    full_story_prompt: Optional[str] = None,
) -> None:
    payload = {
        "generated_at": ctx.now.isoformat(),
        "content_source": content_source,
        "openai_model": openai_model,
        "fallback_reason": fallback_reason,
        "image_source": image_source,
        "reference_image": str(reference_image) if reference_image else None,
        "requires_visual_review": image_source == "openai-full-story",
        "full_story_prompt": full_story_prompt,
        "weekday": ctx.weekday,
        "hour": ctx.hour,
        "weather": ctx.weather.label,
        "temperature_c": ctx.weather.temperature_c,
        "stock": ctx.business.stock_level,
        "template": content.template_name,
        "kicker": content.kicker,
        "headline": content.headline,
        "subheadline": content.subheadline,
        "cta": content.cta,
        "footer": content.footer,
        "badge": content.badge,
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generador automático de historias para Hielito")
    parser.add_argument("--weather", choices=["hot", "warm", "normal", "cold", "rainy"], default="normal")
    parser.add_argument("--temp", type=int, default=None, help="Temperatura en °C")
    parser.add_argument("--stock", choices=["high", "medium", "low"], default="medium")
    parser.add_argument("--hour", type=int, default=None, help="Hora simulada de 0 a 23")
    parser.add_argument("--day", type=str, default=None, help="Día simulado, ej: friday o viernes")
    parser.add_argument("--brand-name", type=str, default=None)
    parser.add_argument("--whatsapp-label", type=str, default=None)
    parser.add_argument(
        "--delivery-zones",
        type=str,
        default=None,
    )
    parser.add_argument(
        "--major-message",
        type=str,
        default=None,
    )
    parser.add_argument(
        "--generate-templates",
        action="store_true",
        help="Genera un pack de templates base en assets/templates y finaliza",
    )
    parser.add_argument(
        "--use-openai",
        action="store_true",
        help="Genera el contenido con OpenAI y usa el contenido local como respaldo si falla",
    )
    parser.add_argument(
        "--require-openai",
        action="store_true",
        help="Genera con OpenAI y finaliza con error si la API o la validación fallan",
    )
    parser.add_argument(
        "--openai-model",
        default=os.getenv("OPENAI_MODEL", DEFAULT_OPENAI_MODEL),
        help=f"Modelo de OpenAI (por defecto: {DEFAULT_OPENAI_MODEL})",
    )
    parser.add_argument(
        "--objective",
        default="Generar pedidos por WhatsApp sin inventar urgencia ni promociones",
        help="Objetivo comercial de la historia",
    )
    parser.add_argument(
        "--use-openai-image",
        action="store_true",
        help="Genera una fotografía publicitaria de fondo con OpenAI",
    )
    parser.add_argument(
        "--require-openai-image",
        action="store_true",
        help="Finaliza con error si OpenAI no puede generar la imagen",
    )
    parser.add_argument(
        "--openai-image-model",
        default=os.getenv("OPENAI_IMAGE_MODEL", DEFAULT_OPENAI_IMAGE_MODEL),
        help=f"Modelo de imágenes de OpenAI (por defecto: {DEFAULT_OPENAI_IMAGE_MODEL})",
    )
    parser.add_argument(
        "--cost-profile",
        choices=sorted(IMAGE_QUALITY_PROFILES),
        default="balanced",
        help="Perfil de costo: draft=barato, balanced=medio, final=alta calidad",
    )
    parser.add_argument(
        "--creative-concept",
        choices=sorted(CREATIVE_CONCEPTS),
        default="producto",
        help="Dirección creativa visual para la fotografía",
    )
    parser.add_argument(
        "--reference-image",
        type=Path,
        default=None,
        help="Imagen de referencia visual, por ejemplo un export de Pomelli",
    )
    parser.add_argument(
        "--auto-reference",
        action="store_true",
        help="Selecciona automáticamente una referencia compatible desde referencias/reference_library.json",
    )
    parser.add_argument(
        "--full-openai-story",
        action="store_true",
        help="OpenAI genera la historia completa con diseño, textos, logo y precio, sin overlay gráfico de Pillow",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    if args.generate_templates:
        generate_template_pack()
        return

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    ctx = build_context(args)
    content_source = "local"
    fallback_reason = None
    openai_model = None

    if args.use_openai or args.require_openai:
        try:
            facts = load_business_facts()
            content = generate_story_content_with_openai(ctx, facts, args.openai_model, args.objective)
            content_source = "openai"
            openai_model = args.openai_model
        except Exception as exc:
            if args.require_openai:
                raise RuntimeError(f"No se pudo generar la historia con OpenAI: {exc}") from exc
            fallback_reason = str(exc)
            print(f"OpenAI no disponible; usando contenido local: {fallback_reason}")
            content = build_story_content(ctx)
    else:
        content = build_story_content(ctx)

    image_source = "pillow"
    full_story_prompt = None
    selected_reference = args.reference_image
    if args.auto_reference and selected_reference is None:
        selected_reference = select_reference_image(args.creative_concept)
        if selected_reference:
            print(f"Referencia visual seleccionada: {selected_reference}")

    if args.full_openai_story:
        try:
            facts = load_business_facts()
            image, full_story_prompt = generate_complete_openai_story(
                ctx,
                content,
                facts,
                args.openai_image_model,
                args.objective,
                args.creative_concept,
                selected_reference,
                IMAGE_QUALITY_PROFILES[args.cost_profile],
            )
            image_source = "openai-full-story"
        except Exception as exc:
            raise RuntimeError(f"No se pudo generar la historia completa con OpenAI: {exc}") from exc
    elif args.use_openai_image or args.require_openai_image:
        try:
            facts = load_business_facts()
            background = generate_openai_background(
                ctx,
                facts,
                args.openai_image_model,
                args.objective,
                args.creative_concept,
                selected_reference,
                IMAGE_QUALITY_PROFILES[args.cost_profile],
            )
            image = render_story_on_ai_background(content, ctx, background)
            image_source = "openai"
        except Exception as exc:
            if args.require_openai_image:
                raise RuntimeError(f"No se pudo generar la imagen con OpenAI: {exc}") from exc
            print(f"Imagen de OpenAI no disponible; usando diseño local: {exc}")
            image = render_story(content, ctx)
    else:
        image = render_story(content, ctx)

    timestamp = ctx.now.strftime("%Y%m%d_%H%M")
    safe_headline = "_".join(content.headline.lower().split())[:40]
    image_path = OUTPUT_DIR / f"story_{timestamp}_{safe_headline}.png"
    meta_path = OUTPUT_DIR / f"story_{timestamp}_{safe_headline}.json"

    image.save(image_path, quality=95)
    save_debug_metadata(
        meta_path,
        ctx,
        content,
        content_source,
        openai_model,
        fallback_reason,
        image_source,
        selected_reference,
        full_story_prompt,
    )

    print("Historia generada correctamente")
    print(f"Archivo: {image_path}")
    print(f"Metadata: {meta_path}")
    print(f"Contenido: {content_source}")
    print(f"Imagen: {image_source}")
    print(f"Día: {ctx.weekday} | Hora: {ctx.hour} | Clima: {ctx.weather.label} | Stock: {ctx.business.stock_level}")


# ============================================================
# GENERADOR DE PACK DE TEMPLATES BASE (ESTÉTICA HIELITO)
# ============================================================
# Este módulo permite crear automáticamente backgrounds base
# que luego el sistema usa como templates reales.
# Ejecutar:
# python hielito_story_generator.py --generate-templates
# ============================================================


def create_gradient_background(color1: str, color2: str) -> Image.Image:
    return vertical_gradient(CANVAS_SIZE, color1, color2).convert("RGBA")


def add_ice_texture(img: Image.Image, density: int = 30):
    draw = ImageDraw.Draw(img, "RGBA")
    w, h = img.size
    for _ in range(density):
        r = random.randint(40, 120)
        x = random.randint(-50, w + 50)
        y = random.randint(-50, h + 50)
        draw.ellipse((x, y, x+r, y+r), fill=(255,255,255,random.randint(10,40)))


def create_template(name: str, top: str, bottom: str):
    """
    Template comercial minimalista:
    - gradiente limpio
    - leve profundidad
    - banda inferior sugerida
    - sin texturas invasivas
    """
    base = create_gradient_background(top, bottom)
    add_vignette(base, strength=50)

    overlay = Image.new("RGBA", CANVAS_SIZE, (0, 0, 0, 0))
    d = ImageDraw.Draw(overlay)

    # Glow central muy sutil para apoyar titular
    d.ellipse((180, 260, 980, 1220), fill=(255, 255, 255, 18))

    # Banda inferior sugerida, sobria
    d.rounded_rectangle((84, 1435, 996, 1755), radius=42, fill=(8, 22, 56, 118))

    # Mini marca superior izquierda
    d.rounded_rectangle((84, 70, 340, 126), radius=28, fill=(255, 255, 255, 34))

    overlay = overlay.filter(ImageFilter.GaussianBlur(16))
    base.alpha_composite(overlay)

    out = TEMPLATES_DIR / f"{name}.png"
    out.parent.mkdir(parents=True, exist_ok=True)
    base.convert("RGB").save(out, quality=95)


def generate_template_pack():
    palettes = {
        "intense-blue": ("#0D47A1", "#42A5F5"),
        "party-blue": ("#0B1F5E", "#2563EB"),
        "dark-blue": ("#071B45", "#1D4ED8"),
        "clean-blue": ("#1D4ED8", "#93C5FD"),
        "soft-blue": ("#1E3A8A", "#7DD3FC"),
        "minimal": ("#123A8F", "#60A5FA"),
        "default": ("#0D47A1", "#42A5F5")
    }

    for name,(c1,c2) in palettes.items():
        create_template(name,c1,c2)

    print("Pack de templates generado en assets/templates")


if __name__ == "__main__":
    main()
