from __future__ import annotations

import argparse
import json
import re
from datetime import datetime
from pathlib import Path

from PIL import Image, ImageDraw

from hielito_story_generator_V2 import (
    CREATIVE_CONCEPTS,
    IMAGE_QUALITY_PROFILES,
    OUTPUT_DIR,
    TIMEZONE,
    build_context,
    build_story_content,
    generate_complete_openai_story,
    generate_story_content_with_openai,
    load_business_facts,
    load_font,
    select_reference_image,
)


CAMPAIGNS_DIR = OUTPUT_DIR / "campaigns"


def calculate_call_plan(variants: int, unique_copy: bool, local_copy: bool) -> dict[str, int]:
    text_calls = 0 if local_copy else variants if unique_copy else 1
    return {"text_calls": text_calls, "image_calls": variants}


def safe_slug(value: str) -> str:
    normalized = re.sub(r"[^a-zA-Z0-9áéíóúüñÁÉÍÓÚÜÑ]+", "-", value.strip().lower())
    return normalized.strip("-")[:60] or "campana"


def create_comparison_sheet(
    image_paths: list[Path],
    output_path: Path,
    labels: list[str] | None = None,
) -> Path:
    if not image_paths:
        raise ValueError("Se necesita al menos una imagen para crear la comparativa")

    thumb_size = (360, 640)
    gap = 28
    label_height = 64
    columns = min(3, len(image_paths))
    rows = (len(image_paths) + columns - 1) // columns
    sheet_width = gap + columns * (thumb_size[0] + gap)
    sheet_height = gap + rows * (thumb_size[1] + label_height + gap)
    sheet = Image.new("RGB", (sheet_width, sheet_height), "#061742")
    draw = ImageDraw.Draw(sheet)
    label_font = load_font(24, bold=True)

    for index, image_path in enumerate(image_paths):
        row, column = divmod(index, columns)
        x = gap + column * (thumb_size[0] + gap)
        y = gap + row * (thumb_size[1] + label_height + gap)
        with Image.open(image_path) as source:
            thumb = source.convert("RGB").resize(thumb_size, Image.Resampling.LANCZOS)
        sheet.paste(thumb, (x, y))
        label = labels[index] if labels else f"Propuesta {index + 1}"
        draw.text((x, y + thumb_size[1] + 16), label, font=label_font, fill="white")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(output_path, quality=95)
    return output_path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generador de campañas visuales para Hielito")
    parser.add_argument("--objective", required=True, help="Objetivo comercial de la campaña")
    parser.add_argument("--variants", type=int, default=3, choices=range(2, 7))
    parser.add_argument(
        "--concepts",
        nargs="+",
        choices=sorted(CREATIVE_CONCEPTS),
        default=["producto", "evento", "comercio"],
        help="Conceptos visuales que se alternarán entre propuestas",
    )
    parser.add_argument("--weather", choices=["hot", "warm", "normal", "cold", "rainy"], default="normal")
    parser.add_argument("--temp", type=int, default=None)
    parser.add_argument("--stock", choices=["high", "medium", "low"], default="medium")
    parser.add_argument("--hour", type=int, default=None)
    parser.add_argument("--day", type=str, default=None)
    parser.add_argument("--openai-model", default="gpt-5-mini")
    parser.add_argument("--openai-image-model", default="gpt-image-2")
    parser.add_argument("--no-auto-reference", action="store_true")
    parser.add_argument(
        "--cost-profile",
        choices=sorted(IMAGE_QUALITY_PROFILES),
        default="draft",
        help="draft para explorar barato, balanced para revisar, final para producir",
    )
    parser.add_argument(
        "--unique-copy",
        action="store_true",
        help="Genera copy distinto para cada propuesta; por defecto reutiliza uno para ahorrar",
    )
    parser.add_argument(
        "--local-copy",
        action="store_true",
        help="Usa copy local sin llamar a OpenAI; ideal para borradores económicos",
    )
    parser.add_argument(
        "--allow-expensive",
        action="store_true",
        help="Permite campañas final de más de dos propuestas",
    )
    parser.set_defaults(
        brand_name=None,
        whatsapp_label=None,
        delivery_zones=None,
        major_message=None,
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.cost_profile == "final" and args.variants > 2 and not args.allow_expensive:
        raise RuntimeError(
            "Una campaña final de más de dos propuestas es costosa. "
            "Usá --cost-profile draft o confirmá con --allow-expensive."
        )

    call_plan = calculate_call_plan(args.variants, args.unique_copy, args.local_copy)
    print(
        f"Plan de consumo: {call_plan['text_calls']} llamada(s) de texto + "
        f"{call_plan['image_calls']} llamada(s) de imagen ({args.cost_profile})"
    )

    campaign_id = f"{datetime.now(TIMEZONE).strftime('%Y%m%d_%H%M%S')}_{safe_slug(args.objective)}"
    campaign_dir = CAMPAIGNS_DIR / campaign_id
    campaign_dir.mkdir(parents=True, exist_ok=True)

    ctx = build_context(args)
    facts = load_business_facts()
    variants: list[dict] = []
    image_paths: list[Path] = []
    labels: list[str] = []
    shared_content = None
    if args.local_copy:
        shared_content = build_story_content(ctx)
    elif not args.unique_copy:
        shared_content = generate_story_content_with_openai(ctx, facts, args.openai_model, args.objective)

    for index in range(args.variants):
        concept = args.concepts[index % len(args.concepts)]
        reference = None if args.no_auto_reference else select_reference_image(concept)
        content = shared_content or generate_story_content_with_openai(ctx, facts, args.openai_model, args.objective)
        image, prompt = generate_complete_openai_story(
            ctx,
            content,
            facts,
            args.openai_image_model,
            args.objective,
            concept,
            reference,
            IMAGE_QUALITY_PROFILES[args.cost_profile],
        )

        image_path = campaign_dir / f"propuesta_{index + 1}_{concept}.png"
        metadata_path = campaign_dir / f"propuesta_{index + 1}_{concept}.json"
        image.save(image_path, quality=95)
        metadata = {
            "proposal": index + 1,
            "concept": concept,
            "reference_image": str(reference) if reference else None,
            "requires_visual_review": True,
            "cost_profile": args.cost_profile,
            "image_quality": IMAGE_QUALITY_PROFILES[args.cost_profile],
            "shared_copy": not args.unique_copy,
            "copy_source": "local" if args.local_copy else "openai",
            "content": {
                "kicker": content.kicker,
                "headline": content.headline,
                "subheadline": content.subheadline,
                "cta": content.cta,
                "footer": content.footer,
            },
            "full_story_prompt": prompt,
        }
        metadata_path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
        variants.append(metadata)
        image_paths.append(image_path)
        labels.append(f"{index + 1}. {concept}")
        print(f"Propuesta {index + 1}/{args.variants}: {image_path}")

    comparison_path = create_comparison_sheet(image_paths, campaign_dir / "comparativa.jpg", labels)
    campaign_metadata = {
        "campaign_id": campaign_id,
        "generated_at": datetime.now(TIMEZONE).isoformat(),
        "objective": args.objective,
        "cost_profile": args.cost_profile,
        "image_quality": IMAGE_QUALITY_PROFILES[args.cost_profile],
        "shared_copy": not args.unique_copy,
        "copy_source": "local" if args.local_copy else "openai",
        "call_plan": call_plan,
        "variants": variants,
        "comparison_sheet": str(comparison_path),
        "status": "pending_review",
    }
    (campaign_dir / "campaign.json").write_text(
        json.dumps(campaign_metadata, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print("Campaña generada correctamente")
    print(f"Carpeta: {campaign_dir}")
    print(f"Comparativa: {comparison_path}")


if __name__ == "__main__":
    main()
