"""Tema `weather`: clima con Open-Meteo (https://open-meteo.com/en/docs).

- API documentada, gratuita y sin clave. La ubicación se configura a mano en settings.json
  (weather.city + latitude/longitude). Si faltan las coordenadas se resuelven una sola vez
  con la API de geocodificación de Open-Meteo y se guardan en caché.
- Caché en disco: no se repite la petición antes de weather.refresh_minutes.
- Si la red falla se muestran los últimos datos con un aviso de error.
"""
import asyncio
import json
import time
import urllib.parse
import urllib.request
from datetime import datetime

from .. import config, paths
from ..daemon import Source
from ..util import log

API = "https://api.open-meteo.com/v1/forecast"
GEO = "https://geocoding-api.open-meteo.com/v1/search"

# Código WMO -> (descripción, glifo de día, glifo de noche, color del tema)
WMO = {
    0: ("Despejado", "󰖙", "󰖔", "yellow"),
    1: ("Mayormente despejado", "󰖕", "󰼱", "yellow"),
    2: ("Parcialmente nublado", "󰖕", "󰼱", "lavender"),
    3: ("Nublado", "󰖐", "󰖐", "overlay2"),
    45: ("Niebla", "󰖑", "󰖑", "overlay2"), 48: ("Niebla helada", "󰖑", "󰖑", "overlay2"),
    51: ("Llovizna ligera", "󰖗", "󰖗", "sky"), 53: ("Llovizna", "󰖗", "󰖗", "sky"), 55: ("Llovizna intensa", "󰖗", "󰖗", "sky"),
    56: ("Llovizna helada", "󰙿", "󰙿", "sky"), 57: ("Llovizna helada", "󰙿", "󰙿", "sky"),
    61: ("Lluvia ligera", "󰖗", "󰖗", "blue"), 63: ("Lluvia", "󰖖", "󰖖", "blue"), 65: ("Lluvia intensa", "󰖖", "󰖖", "blue"),
    66: ("Lluvia helada", "󰙿", "󰙿", "blue"), 67: ("Lluvia helada", "󰙿", "󰙿", "blue"),
    71: ("Nevada ligera", "󰖘", "󰖘", "text"), 73: ("Nevada", "󰖘", "󰖘", "text"), 75: ("Nevada intensa", "󰼶", "󰼶", "text"),
    77: ("Granizo fino", "󰖒", "󰖒", "text"),
    80: ("Chubascos", "󰖗", "󰖗", "blue"), 81: ("Chubascos", "󰖖", "󰖖", "blue"), 82: ("Chubascos fuertes", "󰖖", "󰖖", "blue"),
    85: ("Chubascos de nieve", "󰖘", "󰖘", "text"), 86: ("Chubascos de nieve", "󰼶", "󰼶", "text"),
    95: ("Tormenta", "󰙾", "󰙾", "peach"), 96: ("Tormenta con granizo", "󰖓", "󰖓", "peach"), 99: ("Tormenta con granizo", "󰖓", "󰖓", "peach"),
}
DAYS = ["Lun", "Mar", "Mié", "Jue", "Vie", "Sáb", "Dom"]


def describe(code: int, is_day: bool = True) -> dict:
    desc, day, night, color = WMO.get(code, ("Desconocido", "󰖐", "󰖐", "overlay2"))
    return {"desc": desc, "glyph": day if is_day else night, "color": color}


def _get(url: str, params: dict) -> dict:
    full = url + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(full, headers={"User-Agent": "hyprland-desktop"})
    with urllib.request.urlopen(req, timeout=12) as r:
        return json.load(r)


class WeatherSource(Source):
    topic = "weather"

    def __init__(self, hub) -> None:
        super().__init__(hub)
        self.cache = paths.CACHE_DIR / "weather.json"
        self.loading = False

    async def start(self) -> None:
        cached = config.read_state(self.cache, {})
        if cached.get("data"):
            self._publish(cached["data"], error="")
        else:
            self.publish({"available": False, "loading": True})
        while True:
            cfg = config.load().get("weather", {})
            interval = 60 * float(cfg.get("refresh_minutes", 30))
            cached = config.read_state(self.cache, {})
            age = time.time() - cached.get("fetched", 0)
            if age >= interval or cached.get("key") != self._key(cfg):
                await self.fetch()
                age = 0
            await asyncio.sleep(max(60, interval - age))

    @staticmethod
    def _key(cfg: dict) -> str:
        return f"{cfg.get('city')}|{cfg.get('latitude')}|{cfg.get('longitude')}|{cfg.get('units')}"

    async def fetch(self) -> None:
        if self.loading:
            return
        self.loading = True
        current = self.hub.get(self.topic) or {}
        if current.get("available"):
            self.publish({**current, "loading": True})
        cfg = config.load().get("weather", {})
        cached = config.read_state(self.cache, {})
        try:
            lat, lon, city = await asyncio.to_thread(self._location, cfg)
            imperial = cfg.get("units") == "imperial"
            params = {
                "latitude": lat, "longitude": lon, "timezone": "auto", "forecast_days": 6,
                "current": "temperature_2m,apparent_temperature,relative_humidity_2m,weather_code,wind_speed_10m,is_day",
                "hourly": "temperature_2m,weather_code,precipitation_probability,is_day",
                "daily": "weather_code,temperature_2m_max,temperature_2m_min,precipitation_probability_max",
            }
            if imperial:
                params.update(temperature_unit="fahrenheit", wind_speed_unit="mph")
            raw = await asyncio.to_thread(_get, API, params)
            data = self._shape(raw, city, imperial)
            self.loading = False
            config.write_json(self.cache, {"fetched": time.time(), "key": self._key(cfg), "data": data})
            self._publish(data, error="")
        except Exception as e:
            log(f"clima: {e}")
            if cached.get("data"):
                self._publish(cached["data"], error="Sin conexión: mostrando datos guardados")
            else:
                self.publish({"available": False, "loading": False, "error": f"No se pudo obtener el clima: {e}"})
        finally:
            self.loading = False

    def _location(self, cfg: dict):
        if cfg.get("latitude") is not None and cfg.get("longitude") is not None:
            return cfg["latitude"], cfg["longitude"], cfg.get("city", "")
        geo = _get(GEO, {"name": cfg.get("city", ""), "count": 1, "language": "es"})
        if not geo.get("results"):
            raise RuntimeError(f"ciudad no encontrada: {cfg.get('city')}")
        r = geo["results"][0]
        return r["latitude"], r["longitude"], r.get("name", cfg.get("city", ""))

    def _shape(self, raw: dict, city: str, imperial: bool) -> dict:
        cur, hourly, daily = raw["current"], raw["hourly"], raw["daily"]
        now = datetime.fromisoformat(cur["time"])
        times = [datetime.fromisoformat(t) for t in hourly["time"]]
        start = next((i for i, t in enumerate(times) if t >= now.replace(minute=0)), 0)
        hours = []
        # cada 3 horas a partir de la próxima hora (como en el mockup)
        for i in range(start + 1, min(len(times), start + 16), 3):
            hours.append({"time": times[i].strftime("%H:%M"), "temp": round(hourly["temperature_2m"][i]),
                          "pop": hourly["precipitation_probability"][i] or 0,
                          **describe(hourly["weather_code"][i], bool(hourly["is_day"][i]))})
            if len(hours) == 5:
                break
        days = []
        for i, d in enumerate(daily["time"][:5]):
            dt = datetime.fromisoformat(d)
            days.append({"day": "Hoy" if i == 0 else DAYS[dt.weekday()], "max": round(daily["temperature_2m_max"][i]),
                         "min": round(daily["temperature_2m_min"][i]), "pop": daily["precipitation_probability_max"][i] or 0,
                         **describe(daily["weather_code"][i])})
        info = describe(cur["weather_code"], bool(cur["is_day"]))
        return {
            "city": city, "temp": round(cur["temperature_2m"]), "feels": round(cur["apparent_temperature"]),
            "humidity": cur["relative_humidity_2m"], "wind": round(cur["wind_speed_10m"]),
            "wind_unit": "mph" if imperial else "km/h", "unit": "°F" if imperial else "°C",
            "pop": hourly["precipitation_probability"][start] or 0, **info,
            "hours": hours, "days": days, "updated": now.strftime("%H:%M"),
        }

    def _publish(self, data: dict, error: str) -> None:
        self.publish({"available": True, "loading": self.loading, "error": error, **data})

    async def cmd_refresh(self) -> None:
        await self.fetch()
