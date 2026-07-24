import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PIL import Image

import hielito_campaign_generator
from hielito_campaign_generator import calculate_call_plan, create_comparison_sheet, parse_args, safe_slug


class CampaignGeneratorTests(unittest.TestCase):
    def test_safe_slug(self):
        self.assertEqual(safe_slug("Bolsa 15 kg: eventos"), "bolsa-15-kg-eventos")

    def test_creates_comparison_sheet(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            paths = []
            for index, color in enumerate(("red", "blue")):
                path = root / f"{index}.png"
                Image.new("RGB", (1080, 1920), color).save(path)
                paths.append(path)

            output = create_comparison_sheet(paths, root / "comparativa.jpg")
            self.assertTrue(output.exists())
            with Image.open(output) as image:
                self.assertGreater(image.width, 700)
                self.assertGreater(image.height, 700)

    def test_cli_includes_brand_context_defaults(self):
        import sys
        from unittest.mock import patch

        with patch.object(sys, "argv", ["campaign", "--objective", "Prueba"]):
            args = parse_args()
        self.assertIsNone(args.brand_name)
        self.assertIsNone(args.whatsapp_label)
        self.assertEqual(args.cost_profile, "draft")
        self.assertFalse(args.unique_copy)
        self.assertFalse(args.local_copy)

    def test_call_plan_reuses_copy_by_default(self):
        self.assertEqual(
            calculate_call_plan(3, unique_copy=False, local_copy=False),
            {"text_calls": 1, "image_calls": 3},
        )
        self.assertEqual(
            calculate_call_plan(3, unique_copy=False, local_copy=True),
            {"text_calls": 0, "image_calls": 3},
        )

    def test_passes_distinct_variation_seed_per_variant(self):
        captured_seeds = []

        def fake_generate_complete_openai_story(*args, **kwargs):
            captured_seeds.append(kwargs.get("variation_seed"))
            return Image.new("RGB", (1080, 1920), "blue"), "prompt"

        fake_content = type(
            "FakeContent",
            (),
            {"kicker": "K", "headline": "H", "subheadline": "S", "cta": "C", "footer": "F"},
        )()

        with tempfile.TemporaryDirectory() as temp_dir, \
                patch.object(hielito_campaign_generator, "OUTPUT_DIR", Path(temp_dir)), \
                patch.object(hielito_campaign_generator, "CAMPAIGNS_DIR", Path(temp_dir) / "campaigns"), \
                patch.object(hielito_campaign_generator, "load_business_facts", return_value={}), \
                patch.object(hielito_campaign_generator, "select_reference_image", return_value=None), \
                patch.object(hielito_campaign_generator, "build_story_content", return_value=fake_content), \
                patch.object(
                    hielito_campaign_generator,
                    "generate_complete_openai_story",
                    side_effect=fake_generate_complete_openai_story,
                ), \
                patch.object(
                    sys,
                    "argv",
                    [
                        "campaign",
                        "--objective", "Prueba",
                        "--variants", "2",
                        "--concepts", "producto",
                        "--local-copy",
                    ],
                ):
            hielito_campaign_generator.main()

        self.assertEqual(len(captured_seeds), 2)
        self.assertNotEqual(captured_seeds[0], captured_seeds[1])


if __name__ == "__main__":
    unittest.main()
