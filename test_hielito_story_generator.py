import unittest

from hielito_story_generator_V2 import (
    StoryContent,
    clean_generated_text,
    load_business_facts,
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


if __name__ == "__main__":
    unittest.main()
