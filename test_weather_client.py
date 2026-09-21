import unittest
from unittest.mock import Mock, patch

from weather_client import WeatherFetchError, obtener_clima_actual


def mock_response(ok: bool, json_data: dict, text: str = "") -> Mock:
    response = Mock()
    response.ok = ok
    response.json.return_value = json_data
    response.text = text
    return response


class ObtenerClimaActualTests(unittest.TestCase):
    @patch("weather_client.requests.get")
    def test_rain_weather_code_returns_rainy_regardless_of_temperature(self, mock_get):
        mock_get.return_value = mock_response(
            True, {"current_weather": {"temperature": 32.0, "weathercode": 61}}
        )
        label, temp = obtener_clima_actual()
        self.assertEqual(label, "rainy")
        self.assertEqual(temp, 32)

    @patch("weather_client.requests.get")
    def test_hot_temperature_without_rain(self, mock_get):
        mock_get.return_value = mock_response(
            True, {"current_weather": {"temperature": 31.4, "weathercode": 0}}
        )
        label, temp = obtener_clima_actual()
        self.assertEqual(label, "hot")
        self.assertEqual(temp, 31)

    @patch("weather_client.requests.get")
    def test_warm_temperature_without_rain(self, mock_get):
        mock_get.return_value = mock_response(
            True, {"current_weather": {"temperature": 26.0, "weathercode": 1}}
        )
        label, temp = obtener_clima_actual()
        self.assertEqual(label, "warm")

    @patch("weather_client.requests.get")
    def test_cold_temperature_without_rain(self, mock_get):
        mock_get.return_value = mock_response(
            True, {"current_weather": {"temperature": 8.0, "weathercode": 2}}
        )
        label, temp = obtener_clima_actual()
        self.assertEqual(label, "cold")

    @patch("weather_client.requests.get")
    def test_mild_temperature_without_rain_is_normal(self, mock_get):
        mock_get.return_value = mock_response(
            True, {"current_weather": {"temperature": 18.0, "weathercode": 3}}
        )
        label, temp = obtener_clima_actual()
        self.assertEqual(label, "normal")

    @patch("weather_client.requests.get")
    def test_raises_on_error_response(self, mock_get):
        mock_get.return_value = mock_response(False, {}, text="bad request")
        with self.assertRaises(WeatherFetchError):
            obtener_clima_actual()

    @patch("weather_client.requests.get")
    def test_raises_when_current_weather_missing(self, mock_get):
        mock_get.return_value = mock_response(True, {}, text="{}")
        with self.assertRaises(WeatherFetchError):
            obtener_clima_actual()


if __name__ == "__main__":
    unittest.main()
