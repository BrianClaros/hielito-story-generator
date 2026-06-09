from __future__ import annotations

import argparse
import json
import math
import random
import textwrap
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional
from zoneinfo import ZoneInfo

from PIL import Image, ImageDraw, ImageFilter, ImageFont


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


def draw_badge(draw: ImageDraw.ImageDraw, text: str, x: int, y: int) -> None:
    badge_font = load_font(34, bold=True)
    bbox = draw.textbbox((x, y), text, font=badge_font)
    pad_x = 24
    pad_y = 14
    box = (bbox[0] - pad_x, bbox[1] - pad_y, bbox[2] + pad_x, bbox[3] + pad_y)
    draw.rounded_rectangle(box, radius=26, fill=(255, 255, 255, 235))
    draw.text((x, y), text, font=badge_font, fill="#0D47A1")


def render_story(content: StoryContent, ctx: StoryContext) -> Image.Image:
    template_palette = {
        "intense-blue": ("#0D47A1", "#42A5F5"),
        "soft-blue": ("#1E3A8A", "#7DD3FC"),
        "party-blue": ("#0B1F5E", "#2563EB"),
        "dark-blue": ("#071B45", "#1D4ED8"),
        "clean-blue": ("#1D4ED8", "#93C5FD"),
        "minimal": ("#123A8F", "#60A5FA"),
    }

    top, bottom = template_palette.get(content.template_name, ("#0D47A1", "#42A5F5"))
    base = vertical_gradient(CANVAS_SIZE, top, bottom).convert("RGBA")
    add_ice_circles(base, count=22)
    add_glow_box(base, (60, 210, 1020, 1550), radius=50)

    draw = ImageDraw.Draw(base)
    width, height = base.size

    title_font = load_font(96, bold=True)
    sub_font = load_font(54, bold=False)
    kicker_font = load_font(34, bold=True)
    cta_font = load_font(48, bold=True)
    footer_font = load_font(30, bold=False)
    brand_font = load_font(42, bold=True)

    # Marca superior
    draw.text((80, 80), ctx.business.brand_name.upper(), font=brand_font, fill=(255, 255, 255, 235))

    # Kicker
    draw.text((80, 185), content.kicker.upper(), font=kicker_font, fill=(224, 242, 254, 255))

    # Badge
    if content.badge:
        draw_badge(draw, content.badge, 80, 250)

    # Título principal
    title = wrap_text(content.headline.upper(), 17)
    draw.multiline_text((80, 390), title, font=title_font, fill="white", spacing=8)

    # Subtítulo
    sub = wrap_text(content.subheadline, 28)
    draw.multiline_text((80, 760), sub, font=sub_font, fill=(241, 245, 249, 245), spacing=12)

    # Botón CTA falso
    cta_box = (80, 1190, 760, 1310)
    draw.rounded_rectangle(cta_box, radius=34, fill=(255, 255, 255, 235))
    draw.text((118, 1220), content.cta, font=cta_font, fill="#0D47A1")

    # Bloque inferior
    draw.rounded_rectangle((80, 1450, 1000, 1750), radius=36, fill=(10, 25, 66, 105))
    draw.text((110, 1495), "Cobertura", font=footer_font, fill=(191, 219, 254, 255))
    draw.multiline_text((110, 1540), wrap_text(content.footer, 34), font=brand_font, fill="white", spacing=8)

    # Mini círculo decorativo tipo hielo
    for angle in (0, 35, 70):
        r = 90
        cx = width - 170
        cy = 180
        x = cx + int(math.cos(math.radians(angle)) * 28)
        y = cy + int(math.sin(math.radians(angle)) * 28)
        draw.ellipse((x - r, y - r, x + r, y + r), outline=(255, 255, 255, 120), width=4)

    # Logo opcional
    if LOGO_PATH.exists():
        try:
            logo = Image.open(LOGO_PATH).convert("RGBA")
            logo.thumbnail((180, 180))
            base.alpha_composite(logo, dest=(width - logo.width - 80, height - logo.height - 90))
        except OSError:
            pass

    return base.convert("RGB")


# ----------------------------
# Entrada / salida
# ----------------------------

def build_context(args: argparse.Namespace) -> StoryContext:
    now = get_now(hour=args.hour, day=args.day)
    weather = WeatherContext(label=args.weather, temperature_c=args.temp)
    business = BusinessContext(
        brand_name=args.brand_name,
        whatsapp_label=args.whatsapp_label,
        delivery_zones=args.delivery_zones,
        stock_level=args.stock,
        major_message=args.major_message,
    )
    return StoryContext(
        now=now,
        weekday=weekday_slug(now),
        hour=now.hour,
        weather=weather,
        business=business,
    )


def save_debug_metadata(path: Path, ctx: StoryContext, content: StoryContent) -> None:
    payload = {
        "generated_at": ctx.now.isoformat(),
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
    parser.add_argument("--brand-name", type=str, default="Hielito")
    parser.add_argument("--whatsapp-label", type=str, default="Pedinos por WhatsApp")
    parser.add_argument(
        "--delivery-zones",
        type=str,
        default="Berazategui • Quilmes • Florencio Varela",
    )
    parser.add_argument(
        "--major-message",
        type=str,
        default="Consultanos por pedidos grandes, eventos y comercios",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    ctx = build_context(args)
    content = build_story_content(ctx)
    image = render_story(content, ctx)

    timestamp = ctx.now.strftime("%Y%m%d_%H%M")
    safe_headline = "_".join(content.headline.lower().split())[:40]
    image_path = OUTPUT_DIR / f"story_{timestamp}_{safe_headline}.png"
    meta_path = OUTPUT_DIR / f"story_{timestamp}_{safe_headline}.json"

    image.save(image_path, quality=95)
    save_debug_metadata(meta_path, ctx, content)

    print("Historia generada correctamente")
    print(f"Archivo: {image_path}")
    print(f"Metadata: {meta_path}")
    print(f"Día: {ctx.weekday} | Hora: {ctx.hour} | Clima: {ctx.weather.label} | Stock: {ctx.business.stock_level}")


if __name__ == "__main__":
    main()
