import unittest

from hielito_story_generator_V2 import CREATIVE_CONCEPTS, IMAGE_QUALITY_PROFILES

from hielito_daily_story import ESTRATEGIA_POR_DIA, obtener_prompt_del_dia

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
            objective, concept, cost_profile = obtener_prompt_del_dia(weekday)
            self.assertTrue(objective.strip())
            self.assertIn(concept, CREATIVE_CONCEPTS)
            self.assertIn(cost_profile, IMAGE_QUALITY_PROFILES)

    def test_friday_pushes_asado_concept(self):
        objective, concept, cost_profile = obtener_prompt_del_dia("friday")
        self.assertEqual(concept, "asado")
        self.assertIn("finde", objective.lower())

    def test_friday_and_saturday_use_final_cost_profile(self):
        for weekday in ("friday", "saturday"):
            _, _, cost_profile = obtener_prompt_del_dia(weekday)
            self.assertEqual(cost_profile, "final")

    def test_rest_of_week_uses_balanced_cost_profile(self):
        for weekday in ("monday", "tuesday", "wednesday", "thursday", "sunday"):
            _, _, cost_profile = obtener_prompt_del_dia(weekday)
            self.assertEqual(cost_profile, "balanced")

    def test_unknown_day_falls_back_to_monday(self):
        self.assertEqual(obtener_prompt_del_dia("no-existe"), ESTRATEGIA_POR_DIA["monday"])


if __name__ == "__main__":
    unittest.main()
