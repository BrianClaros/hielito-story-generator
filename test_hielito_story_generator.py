import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import patch
from zoneinfo import ZoneInfo

from PIL import Image

from hielito_story_generator_V2 import (
    CREATIVE_CONCEPTS,
    BusinessContext,
    StoryContent,
    StoryContext,
    WeatherContext,
    build_full_openai_story_prompt,
    clean_generated_text,
    clean_supporting_text_for_layout,
    format_zones,
    load_brand_identity,
    load_business_facts,
    safe_text,
    select_background_image,
    select_creative_variation,
    validate_story_content,
)
import hielito_story_generator_V2


class StoryContentValidationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.facts = load_business_facts()

    def make_content(self, text: str) -> StoryContent:
        return StoryContent(
            template_name="clean-blue",
            kicker="HIELITO",
            headline=text,
            subheadline="Pedidos por WhatsApp.",
            cta="Escribinos",
            footer="Berazategui, Quilmes y Florencio Varela",
        )

    def test_accepts_confirmed_product_and_price(self):
        content = self.make_content("Bolsa de 15 kg a $6500")
        self.assertEqual(validate_story_content(content, self.facts), [])

    def test_rejects_free_delivery(self):
        content = self.make_content("Envío gratis")
        self.assertTrue(validate_story_content(content, self.facts))

    def test_rejects_unconfirmed_certification(self):
        content = self.make_content("Calidad certificada")
        self.assertTrue(validate_story_content(content, self.facts))

    def test_rejects_unknown_price(self):
        content = self.make_content("Bolsa a $7000")
        self.assertTrue(validate_story_content(content, self.facts))

    def test_rejects_unknown_weight(self):
        content = self.make_content("Bolsa de 10 kg")
        self.assertTrue(validate_story_content(content, self.facts))

    def test_rejects_incomplete_whatsapp_number(self):
        content = self.make_content("Mandanos WhatsApp al 11 7062-813")
        self.assertTrue(validate_story_content(content, self.facts))

    def test_removes_dangling_final_word(self):
        self.assertEqual(
            clean_generated_text("Pedí por WhatsApp y coordinamos entregas desde"),
            "Pedí por WhatsApp y coordinamos entregas.",
        )

    def test_safe_text_normalizes_values(self):
        self.assertEqual(safe_text("  Hielo   en cubos  "), "Hielo en cubos")
        self.assertEqual(safe_text(None), "")

    def test_format_zones_limits_long_lists(self):
        zones = [f"Zona {index}" for index in range(8)]
        self.assertEqual(
            format_zones(zones),
            "Zona 0, Zona 1, Zona 2, Zona 3, Zona 4, Zona 5 y alrededores",
        )

    def test_supporting_text_removes_repeated_commercial_blocks(self):
        self.assertEqual(
            clean_supporting_text_for_layout(
                "Hielo en cubos. Pedí por WhatsApp. Entregas coordinadas desde 45 kg."
            ),
            "Hielo en cubos.",
        )

    def test_full_story_prompt_has_exact_copy_and_safe_areas(self):
        ctx = StoryContext(
            now=datetime.now(ZoneInfo("America/Argentina/Buenos_Aires")),
            weekday="friday",
            hour=18,
            weather=WeatherContext(label="normal", temperature_c=22),
            business=BusinessContext(
                brand_name="Hielito",
                whatsapp_label="WhatsApp: 11 7062-8132",
                delivery_zones="Berazategui • Quilmes • Florencio Varela",
                stock_level="medium",
                major_message="Entregas coordinadas desde 45 kg",
            ),
        )
        content = self.make_content("Bolsa de 15 kg a $6500")
        prompt = build_full_openai_story_prompt(
            ctx,
            content,
            self.facts,
            "Promocionar bolsa de 15 kg",
            "producto",
            has_reference=True,
        )
        self.assertIn('MAIN_HEADLINE: "Bolsa de 15 kg a $6500"', prompt)
        self.assertIn("the top ~13% of the image (roughly the top 250 px)", prompt)
        self.assertIn("the bottom ~20% of the image (roughly the\n  bottom 380 px)", prompt)
        self.assertIn("Do NOT render those role labels", prompt)
        self.assertIn("Render every provided copy item exactly once", prompt)
        self.assertIn("Image 1: previously approved Hielito Instagram Story", prompt)
        self.assertNotIn('- KICKER: "HIELITO"', prompt)

    def test_full_story_prompt_varies_creative_direction_by_date_but_keeps_copy_fixed(self):
        content = self.make_content("Bolsa de 15 kg a $6500")
        prompts = []
        for day in (24, 31):  # dos viernes de semanas distintas (julio 2026)
            ctx = StoryContext(
                now=datetime(2026, 7, day, 18, tzinfo=ZoneInfo("America/Argentina/Buenos_Aires")),
                weekday="friday",
                hour=18,
                weather=WeatherContext(label="normal", temperature_c=22),
                business=BusinessContext(
                    brand_name="Hielito",
                    whatsapp_label="WhatsApp: 11 7062-8132",
                    delivery_zones="Berazategui • Quilmes • Florencio Varela",
                    stock_level="medium",
                    major_message="Entregas coordinadas desde 45 kg",
                ),
            )
            prompts.append(
                build_full_openai_story_prompt(
                    ctx,
                    content,
                    self.facts,
                    "Promocionar bolsa de 15 kg",
                    "producto",
                    has_reference=True,
                )
            )

        visible_copy_blocks = [p.split("VISIBLE COPY TO RENDER:")[1] for p in prompts]
        self.assertEqual(visible_copy_blocks[0], visible_copy_blocks[1])

        creative_directions = [p.split("CREATIVE DIRECTION:")[1].split("BRAND FEEL:")[0] for p in prompts]
        self.assertNotEqual(creative_directions[0], creative_directions[1])

    def test_full_story_prompt_reflects_brand_identity_overrides(self):
        ctx = StoryContext(
            now=datetime.now(ZoneInfo("America/Argentina/Buenos_Aires")),
            weekday="friday",
            hour=18,
            weather=WeatherContext(label="normal", temperature_c=22),
            business=BusinessContext(
                brand_name="Hielito",
                whatsapp_label="WhatsApp: 11 7062-8132",
                delivery_zones="Berazategui • Quilmes • Florencio Varela",
                stock_level="medium",
                major_message="Entregas coordinadas desde 45 kg",
            ),
        )
        content = self.make_content("Bolsa de 15 kg a $6500")
        prompt = build_full_openai_story_prompt(
            ctx,
            content,
            self.facts,
            "Promocionar bolsa de 15 kg",
            "producto",
            has_reference=True,
            brand_identity={
                "visual_aesthetics": ["retro-futurista"],
                "tone_of_voice": ["juguetón"],
                "brand_values": ["velocidad"],
                "fonts": ["Comic Sans"],
            },
        )
        self.assertIn("retro-futurista", prompt)
        self.assertIn("juguetón", prompt)
        self.assertIn("velocidad", prompt)
        self.assertIn("Comic Sans", prompt)


class SelectCreativeVariationTests(unittest.TestCase):
    def test_same_seed_is_reproducible(self):
        first = select_creative_variation("asado", "2026-07-24")
        second = select_creative_variation("asado", "2026-07-24")
        self.assertEqual(first, second)

    def test_different_seeds_can_vary(self):
        results = {select_creative_variation("asado", f"2026-0{month}-24") for month in range(1, 8)}
        self.assertGreater(len(results), 1)

    def test_result_stays_within_requested_concept(self):
        for concept, scenes in CREATIVE_CONCEPTS.items():
            result = select_creative_variation(concept, "2026-07-24")
            self.assertTrue(any(scene in result for scene in scenes))

    def test_unknown_concept_falls_back_to_default_text(self):
        self.assertEqual(
            select_creative_variation("no-existe", "2026-07-24"),
            "Clean, cold, realistic, high-conversion local Instagram Story ad.",
        )


class LoadBrandIdentityTests(unittest.TestCase):
    def test_returns_lists_for_known_fields(self):
        identity = load_brand_identity()
        for key in ("visual_aesthetics", "tone_of_voice", "brand_values", "fonts"):
            self.assertIn(key, identity)
            self.assertIsInstance(identity[key], list)


class SelectBackgroundImageTests(unittest.TestCase):
    def test_returns_none_when_directory_missing(self):
        with patch.object(hielito_story_generator_V2, "BACKGROUNDS_DIR", Path("/no/existe/assets/backgrounds")):
            self.assertIsNone(select_background_image())

    def test_returns_none_when_directory_empty(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch.object(hielito_story_generator_V2, "BACKGROUNDS_DIR", Path(temp_dir)):
                self.assertIsNone(select_background_image())

    def test_picks_one_of_the_available_photos(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            expected = set()
            for name in ("uno.jpg", "dos.PNG", "tres.jpeg"):
                path = root / name
                Image.new("RGB", (10, 10)).save(path)
                expected.add(path)
            (root / "notas.txt").write_text("no es una imagen")

            with patch.object(hielito_story_generator_V2, "BACKGROUNDS_DIR", root):
                for _ in range(10):
                    self.assertIn(select_background_image(), expected)


class BuildFullOpenaiStoryPromptWithBackgroundTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.facts = load_business_facts()

    def make_content(self, text: str) -> StoryContent:
        return StoryContent(
            template_name="clean-blue",
            kicker="HIELITO",
            headline=text,
            subheadline="Pedidos por WhatsApp.",
            cta="Escribinos",
            footer="Berazategui, Quilmes y Florencio Varela",
        )

    def build_ctx(self) -> StoryContext:
        return StoryContext(
            now=datetime.now(ZoneInfo("America/Argentina/Buenos_Aires")),
            weekday="friday",
            hour=18,
            weather=WeatherContext(label="normal", temperature_c=22),
            business=BusinessContext(
                brand_name="Hielito",
                whatsapp_label="WhatsApp: 11 7062-8132",
                delivery_zones="Berazategui • Quilmes • Florencio Varela",
                stock_level="medium",
                major_message="Entregas coordinadas desde 45 kg",
            ),
        )

    def test_background_photo_is_described_as_image_one_and_kept_authentic(self):
        content = self.make_content("Bolsa de 15 kg a $6500")
        prompt = build_full_openai_story_prompt(
            self.build_ctx(),
            content,
            self.facts,
            "Promocionar bolsa de 15 kg",
            "producto",
            has_reference=True,
            has_background=True,
        )
        self.assertIn("Image 1: an authentic real photograph taken by the Hielito team", prompt)
        self.assertIn("actual visual base and main scene", prompt)
        self.assertIn("Image 2: previously approved Hielito Instagram Story", prompt)
        self.assertIn("Do NOT use this image as the scene/background", prompt)
        self.assertIn("Image 3: current Hielito logo", prompt)

    def test_background_only_without_style_reference(self):
        content = self.make_content("Bolsa de 15 kg a $6500")
        prompt = build_full_openai_story_prompt(
            self.build_ctx(),
            content,
            self.facts,
            "Promocionar bolsa de 15 kg",
            "producto",
            has_reference=False,
            has_background=True,
        )
        self.assertIn("Image 1: an authentic real photograph taken by the Hielito team", prompt)
        self.assertIn("Image 2: current Hielito logo", prompt)
        self.assertNotIn("previously approved Hielito Instagram Story", prompt)

    def test_includes_safe_area_reminder_near_visible_copy(self):
        content = self.make_content("Bolsa de 15 kg a $6500")
        prompt = build_full_openai_story_prompt(
            self.build_ctx(),
            content,
            self.facts,
            "Promocionar bolsa de 15 kg",
            "producto",
            has_reference=False,
        )
        self.assertIn("SAFE AREA REMINDER FOR THE ITEMS ABOVE", prompt)
        self.assertIn("top 250 px or bottom 380 px exclusion zones", prompt)


if __name__ == "__main__":
    unittest.main()
