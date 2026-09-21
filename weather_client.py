from __future__ import annotations

import logging
from typing import Optional

import requests

logger = logging.getLogger("weather_client")

# Punto de referencia para Zona Sur GBA (Quilmes centro), entre las tres zonas de entrega.
LATITUDE = -34.72
LONGITUDE = -58.27

OPEN_METEO_URL = "https://api.open-meteo.com/v1/forecast"

# Códigos WMO que representan lluvia/llovizna/tormenta.
RAIN_WEATHER_CODES = {51, 53, 55, 56, 57, 61, 63, 65, 66, 67, 80, 81, 82, 95, 96, 99}


class WeatherFetchError(RuntimeError):
    """Error al consultar el clima real."""


def obtener_clima_actual(timeout_s: int = 10) -> tuple[str, Optional[int]]:
    """Consulta el clima actual en Zona Sur (Open-Meteo, sin API key) y lo mapea
    a una de las 5 etiquetas que usa el generador (hot/warm/normal/cold/rainy).

    Devuelve (label, temperature_c).
    """
    respuesta = requests.get(
        OPEN_METEO_URL,
        params={
            "latitude": LATITUDE,
            "longitude": LONGITUDE,
            "current_weather": "true",
            "timezone": "America/Argentina/Buenos_Aires",
        },
        timeout=timeout_s,
    )
    if not respuesta.ok:
        raise WeatherFetchError(f"No se pudo consultar el clima: {respuesta.text}")

    datos = respuesta.json().get("current_weather")
    if not datos:
        raise WeatherFetchError(f"Respuesta de clima sin 'current_weather': {respuesta.text}")

    temperatura = round(datos["temperature"])
    codigo = datos["weathercode"]

    if codigo in RAIN_WEATHER_CODES:
        label = "rainy"
    elif temperatura >= 30:
        label = "hot"
    elif temperatura >= 24:
        label = "warm"
    elif temperatura <= 10:
        label = "cold"
    else:
        label = "normal"

    return label, temperatura
