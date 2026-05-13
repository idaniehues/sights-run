import random

# All coordinates converted from official DMS coordinates (Wikipedia Metro Lisboa)
# Verified against official Metro Lisboa network map 2025
# Conversion: decimal = degrees + minutes/60 + seconds/3600, longitude is negative (West)

METRO_STATIONS = [
    # 🔵 Linha Azul
    {"name": "Jardim Zoológico",  "lat": 38.741944, "lon": -9.168611, "line": "blue"},
    {"name": "Praça de Espanha",  "lat": 38.737500, "lon": -9.159167, "line": "blue"},
    {"name": "São Sebastião",     "lat": 38.734444, "lon": -9.154444, "line": "blue"},
    {"name": "Parque",            "lat": 38.729444, "lon": -9.150278, "line": "blue"},
    {"name": "Marquês de Pombal", "lat": 38.724167, "lon": -9.149167, "line": "blue"},
    {"name": "Avenida",           "lat": 38.720000, "lon": -9.145833, "line": "blue"},
    {"name": "Restauradores",     "lat": 38.715833, "lon": -9.141667, "line": "blue"},
    {"name": "Rossio",            "lat": 38.713889, "lon": -9.139444, "line": "blue"},
    {"name": "Baixa-Chiado",      "lat": 38.710278, "lon": -9.140278, "line": "blue"},
    {"name": "Terreiro do Paço",  "lat": 38.706667, "lon": -9.135278, "line": "blue"},
    {"name": "Santa Apolónia",    "lat": 38.713889, "lon": -9.122500, "line": "blue"},

    # 🟡 Linha Amarela
    {"name": "Rato",                 "lat": 38.720000, "lon": -9.155833, "line": "yellow"},
    {"name": "Picoas",               "lat": 38.731111, "lon": -9.146389, "line": "yellow"},
    {"name": "Saldanha",             "lat": 38.735000, "lon": -9.145278, "line": "yellow"},
    {"name": "Campo Pequeno",        "lat": 38.741667, "lon": -9.146667, "line": "yellow"},
    {"name": "Entre Campos",         "lat": 38.747778, "lon": -9.148611, "line": "yellow"},
    {"name": "Cidade Universitária", "lat": 38.751667, "lon": -9.158889, "line": "yellow"},
    {"name": "Campo Grande",         "lat": 38.760278, "lon": -9.157778, "line": "yellow"},

    # 🟢 Linha Verde
    {"name": "Cais do Sodré", "lat": 38.706944, "lon": -9.146389, "line": "green"},
    {"name": "Martim Moniz",  "lat": 38.716944, "lon": -9.135556, "line": "green"},
    {"name": "Intendente",    "lat": 38.722500, "lon": -9.135000, "line": "green"},
    {"name": "Anjos",         "lat": 38.726111, "lon": -9.135000, "line": "green"},
    {"name": "Arroios",       "lat": 38.732778, "lon": -9.134722, "line": "green"},
    {"name": "Alameda",       "lat": 38.736667, "lon": -9.133889, "line": "green"},

    # 🔴 Linha Vermelha
    {"name": "Alameda",    "lat": 38.736667, "lon": -9.133889, "line": "red"},
    {"name": "Olaias",     "lat": 38.739167, "lon": -9.123889, "line": "red"},
    {"name": "Bela Vista", "lat": 38.746944, "lon": -9.116944, "line": "red"},
    {"name": "Chelas",     "lat": 38.754722, "lon": -9.117500, "line": "red"},
    {"name": "Oriente",    "lat": 38.767778, "lon": -9.099167, "line": "red"},
]


# Minimum sights count per station per distance, based on fallback sights analysis
# Stations with 0 sights for a given distance are excluded from the dropdown
STATION_SIGHT_COUNTS = {
    "Jardim Zoológico":   {3: 1, 5: 4,  8: 9,  12: 19},
    "Praça de Espanha":   {3: 3, 5: 5,  8: 16, 12: 18},
    "São Sebastião":      {3: 4, 5: 8,  8: 17, 12: 18},
    "Parque":             {3: 5, 5: 13, 8: 18, 12: 18},
    "Marquês de Pombal":  {3: 8, 5: 15, 8: 18, 12: 19},
    "Avenida":            {3: 10,5: 15, 8: 17, 12: 19},
    "Restauradores":      {3: 9, 5: 14, 8: 17, 12: 19},
    "Rossio":             {3: 9, 5: 14, 8: 17, 12: 18},
    "Baixa-Chiado":       {3: 8, 5: 13, 8: 17, 12: 19},
    "Terreiro do Paço":   {3: 6, 5: 12, 8: 17, 12: 18},
    "Santa Apolónia":     {3: 6, 5: 10, 8: 16, 12: 19},
    "Rato":               {3: 7, 5: 14, 8: 17, 12: 19},
    "Picoas":             {3: 5, 5: 13, 8: 18, 12: 21},
    "Saldanha":           {3: 4, 5: 9,  8: 17, 12: 21},
    "Campo Pequeno":      {3: 2, 5: 6,  8: 17, 12: 21},
    "Entre Campos":       {3: 3, 5: 4,  8: 13, 12: 21},
    "Cidade Universitária":{3:1, 5: 3,  8: 6,  12: 21},
    "Campo Grande":       {3: 1, 5: 1,  8: 4,  12: 18},
    "Cais do Sodré":      {3: 8, 5: 12, 8: 17, 12: 19},
    "Martim Moniz":       {3: 10,5: 15, 8: 17, 12: 18},
    "Intendente":         {3: 7, 5: 16, 8: 16, 12: 21},
    "Anjos":              {3: 7, 5: 14, 8: 16, 12: 21},
    "Arroios":            {3: 2, 5: 11, 8: 17, 12: 21},
    "Alameda":            {3: 2, 5: 9,  8: 17, 12: 21},
    "Olaias":             {3: 1, 5: 6,  8: 18, 12: 20},
    "Bela Vista":         {3: 0, 5: 1,  8: 14, 12: 20},
    "Chelas":             {3: 0, 5: 3,  8: 8,  12: 20},
    "Oriente":            {3: 3, 5: 3,  8: 3,  12: 9},
}


def get_all_metro_stations(distance_km=None):
    """
    Returns all central metro stations sorted by name, without duplicates.
    If distance_km is provided, only returns stations that have at least
    one sight within range for that distance.
    """
    seen = set()
    unique = []
    for station in METRO_STATIONS:
        if station["name"] not in seen:
            seen.add(station["name"])
            # Filter by distance if provided
            if distance_km is not None:
                counts = STATION_SIGHT_COUNTS.get(station["name"], {})
                # Find closest distance key
                dist_key = min([3, 5, 8, 12], key=lambda d: abs(d - distance_km))
                if counts.get(dist_key, 0) == 0:
                    continue
            unique.append(station)
    return sorted(unique, key=lambda s: s["name"])


# Stations with sights within ~1.5km - safe for Surprise Me
CITY_CENTRE_STATIONS = [
    "Avenida",
    "Baixa-Chiado",
    "Cais do Sodré",
    "Intendente",
    "Martim Moniz",
    "Marquês de Pombal",
    "Parque",
    "Picoas",
    "Rato",
    "Restauradores",
    "Rossio",
    "Santa Apolónia",
    "São Sebastião",
    "Terreiro do Paço",
]


def get_random_metro_station(distance_km=None):
    """
    Returns a random city centre metro station for Surprise Me.
    Only picks from stations with sights reliably within range.
    """
    all_stations = get_all_metro_stations()
    centre_stations = [s for s in all_stations if s["name"] in CITY_CENTRE_STATIONS]
    if not centre_stations:
        return random.choice(all_stations)
    return random.choice(centre_stations)


def get_station_by_name(name):
    """Returns a station by name"""
    for station in METRO_STATIONS:
        if station["name"] == name:
            return station
    return None