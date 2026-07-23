import unittest
from datetime import datetime
from zoneinfo import ZoneInfo

from hielito_story_generator_V2 import (
    BusinessContext,
    StoryContent,
    StoryContext,
    WeatherContext,
    build_full_openai_story_prompt,
    clean_generated_text,
    clean_supporting_text_for_layout,
    format_zones,
    load_business_facts,
    safe_text,
    validate_story_content,
)


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
        self.assertIn("no essential text or logo in the top 250 px", prompt)
        self.assertIn("Do NOT render those role labels", prompt)
        self.assertIn("Render every provided copy item exactly once", prompt)
        self.assertIn("Image 1: previously approved Hielito Instagram Story", prompt)
        self.assertNotIn('- KICKER: "HIELITO"', prompt)


if __name__ == "__main__":
    unittest.main()
