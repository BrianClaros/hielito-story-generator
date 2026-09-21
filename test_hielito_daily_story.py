import unittest
from unittest.mock import patch

from hielito_story_generator_V2 import CREATIVE_CONCEPTS, IMAGE_QUALITY_PROFILES

from hielito_daily_story import ESTRATEGIA_POR_DIA, obtener_clima_del_dia, obtener_prompt_del_dia

WEEKDAYS = [
    "monday",
    "tuesday",
    "wednesday",
    "thursday",
    "friday",
    "saturday",
    "sunday",
]


class ObtenerPromptDelDiaTests(unittest.TestCase):
    def test_covers_every_weekday_with_a_valid_concept_and_cost_profile(self):
        for weekday in WEEKDAYS:
            variants, concept, cost_profile = ESTRATEGIA_POR_DIA[weekday]
            for variant in variants:
                self.assertTrue(variant.strip())
            self.assertIn(concept, CREATIVE_CONCEPTS)
            self.assertIn(cost_profile, IMAGE_QUALITY_PROFILES)
            objective, concept, cost_profile = obtener_prompt_del_dia(weekday)
            self.assertIn(objective, variants)
            self.assertIn(concept, CREATIVE_CONCEPTS)
            self.assertIn(cost_profile, IMAGE_QUALITY_PROFILES)

    def test_friday_pushes_asado_concept(self):
        objective, concept, cost_profile = obtener_prompt_del_dia("friday")
        self.assertEqual(concept, "asado")
        self.assertIn("finde", objective.lower())
        for variant in ESTRATEGIA_POR_DIA["friday"][0]:
            self.assertIn("finde", variant.lower())

    def test_friday_and_saturday_use_final_cost_profile(self):
        for weekday in ("friday", "saturday"):
            _, _, cost_profile = obtener_prompt_del_dia(weekday)
            self.assertEqual(cost_profile, "final")

    def test_rest_of_week_uses_balanced_cost_profile(self):
        for weekday in ("monday", "tuesday", "wednesday", "thursday", "sunday"):
            _, _, cost_profile = obtener_prompt_del_dia(weekday)
            self.assertEqual(cost_profile, "balanced")

    def test_unknown_day_falls_back_to_monday(self):
        objective, concept, cost_profile = obtener_prompt_del_dia("no-existe", seed="2026-07-24")
        monday_variants, monday_concept, monday_cost_profile = ESTRATEGIA_POR_DIA["monday"]
        self.assertIn(objective, monday_variants)
        self.assertEqual(concept, monday_concept)
        self.assertEqual(cost_profile, monday_cost_profile)


class ObtenerPromptDelDiaAngleRotationTests(unittest.TestCase):
    def test_same_weekday_and_seed_is_reproducible(self):
        first = obtener_prompt_del_dia("tuesday", seed="2026-07-21")
        second = obtener_prompt_del_dia("tuesday", seed="2026-07-21")
        self.assertEqual(first, second)

    def test_different_seeds_can_vary(self):
        results = {
            obtener_prompt_del_dia("tuesday", seed=f"2026-0{month}-21")[0]
            for month in range(1, 8)
        }
        self.assertGreater(len(results), 1)

    def test_result_stays_within_requested_weekday_variants(self):
        for weekday, (variants, _, _) in ESTRATEGIA_POR_DIA.items():
            objective, _, _ = obtener_prompt_del_dia(weekday, seed="2026-07-21")
            self.assertIn(objective, variants)


class ObtenerClimaDelDiaTests(unittest.TestCase):
    @patch("hielito_daily_story.obtener_clima_actual")
    def test_returns_real_weather_on_success(self, mock_obtener):
        mock_obtener.return_value = ("rainy", 19)
        self.assertEqual(obtener_clima_del_dia(), ("rainy", 19))

    @patch("hielito_daily_story.obtener_clima_actual")
    def test_falls_back_to_normal_when_fetch_fails(self, mock_obtener):
        mock_obtener.side_effect = RuntimeError("timeout")
        self.assertEqual(obtener_clima_del_dia(), ("normal", None))


if __name__ == "__main__":
    unittest.main()
