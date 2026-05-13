import requests
import math


def get_sights_near_route(lat, lon, distance_km=5):
    """
    Fetches sights near a starting point via OpenStreetMap Overpass API.
    Falls back to known Lisbon sights if the API fails.
    """
    radius_m = int(distance_km * 400)
    overpass_url = "https://overpass-api.de/api/interpreter"
    query = f"""
    [out:json][timeout:60];
    (
      node["tourism"="attraction"](around:{radius_m},{lat},{lon});
      node["tourism"="museum"](around:{radius_m},{lat},{lon});
      node["historic"="monument"](around:{radius_m},{lat},{lon});
      node["historic"="memorial"](around:{radius_m},{lat},{lon});
      node["leisure"="park"](around:{radius_m},{lat},{lon});
      node["amenity"="fountain"](around:{radius_m},{lat},{lon});
    );
    out body;
    """

    try:
        response = requests.post(overpass_url, data=query, timeout=60)
        if response.status_code != 200:
            print(f"Overpass status: {response.status_code}")
            return get_fallback_sights(lat, lon, distance_km)

        data = response.json()
        elements = data.get("elements", [])

        sights = []
        for el in elements:
            tags = el.get("tags", {})
            name = tags.get("name") or tags.get("name:pt") or tags.get("name:en")
            if not name:
                continue

            # Try to get a longer description from Wikipedia
            wiki_tag = tags.get("wikipedia") or tags.get("wikidata")
            description_short, description_long, _ = get_wiki_info(name, wiki_tag)

            sight = {
                "name": name,
                "lat": el["lat"],
                "lon": el["lon"],
                "type": get_sight_type(tags),
                "description": description_short,
                "description_long": description_long,
                "distance_from_start": calculate_distance(lat, lon, el["lat"], el["lon"])
            }
            sights.append(sight)

        sights = filter_and_sort_sights(sights, distance_km)
        return sights

    except Exception as e:
        print(f"Overpass API error: {e}")
        return get_fallback_sights(lat, lon, distance_km)


def get_wiki_info(name, wiki_tag=None):
    """
    Fetches a short description, long description and photo from Wikipedia.
    Uses the Wikipedia search API to find the best matching article.
    Returns (short_description, long_description, photo_url).
    """
    try:
        # First try a direct page lookup with the name + Lisboa
        search_terms = [name, name + " Lisboa", name + " Lisbon"]
        if wiki_tag and ":" in wiki_tag:
            search_terms.insert(0, wiki_tag.split(":")[1])

        for term in search_terms:
            encoded = requests.utils.quote(term.replace(" ", "_"))
            url = f"https://en.wikipedia.org/api/rest_v1/page/summary/{encoded}"
            response = requests.get(url, timeout=5, headers={"User-Agent": "SightsRunApp/1.0"})

            if response.status_code == 200:
                data = response.json()
                short = data.get("description", "")
                long_text = data.get("extract", "")
                sentences = long_text.split(". ")
                long_desc = ". ".join(sentences[:3]) + ("." if len(sentences) >= 3 else "")
                # Get the highest resolution thumbnail available
                thumb = data.get("originalimage", {}).get("source") or data.get("thumbnail", {}).get("source", "")
                if short or long_desc:
                    return short, long_desc, thumb

    except Exception as e:
        print(f"Wikipedia error for {name}: {e}")

    return "", "", ""


def get_sight_type(tags):
    """Determines the type of a sight"""
    if tags.get("tourism") == "museum":
        return "🏛️ Museum"
    elif tags.get("tourism") == "attraction":
        return "⭐ Attraction"
    elif tags.get("historic"):
        return "🏰 Historic"
    elif tags.get("leisure") == "park":
        return "🌳 Park"
    elif tags.get("amenity") == "fountain":
        return "⛲ Fountain"
    return "📍 Sight"


def calculate_distance(lat1, lon1, lat2, lon2):
    """Calculates the distance between two coordinates in km (Haversine formula)"""
    R = 6371
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (math.sin(dlat/2)**2 +
         math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) *
         math.sin(dlon/2)**2)
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
    return round(R * c, 2)


def filter_and_sort_sights(sights, max_distance_km):
    """Filters and sorts sights within half the total distance (round trip logic)"""
    max_radius = max_distance_km / 2.2
    filtered = [s for s in sights if s["distance_from_start"] <= max_radius]
    filtered.sort(key=lambda s: s["distance_from_start"])
    selected = []
    total_distance = 0
    for sight in filtered:
        if total_distance + sight["distance_from_start"] <= max_distance_km * 0.8:
            selected.append(sight)
            total_distance += sight["distance_from_start"]
    return selected[:8]


def get_fallback_sights(lat, lon, max_distance_km=5):
    """Well-known Lisbon sights with short and long descriptions"""
    known_sights = [
        {
            "name": "Torre de Belém",
            "lat": 38.6916, "lon": -9.2160,
            "type": "🏰 Historic",
            "description": "Iconic 16th century watchtower on the Tagus",
            "description_long": "The Torre de Belém is a fortified tower located in the civil parish of Santa Maria de Belém in Lisbon. Built in the early 16th century, it is a prominent example of the Portuguese Manueline style. It was originally built as a ceremonial gateway to Lisbon and as a defensive fortification, and is now one of Portugal's most iconic landmarks and a UNESCO World Heritage Site.",
            "photo_url": "https://upload.wikimedia.org/wikipedia/commons/thumb/1/1b/Lisboa_-_Torre_de_Belém_%2836830576365%29.jpg/320px-Lisboa_-_Torre_de_Belém_%2836830576365%29.jpg"
        },
        {
            "name": "Mosteiro dos Jerónimos",
            "lat": 38.6978, "lon": -9.2067,
            "type": "🏛️ Museum",
            "description": "UNESCO World Heritage monastery in Belém",
            "description_long": "The Jerónimos Monastery is a monastery of the Order of Saint Jerome located in the Belém district of Lisbon. Commissioned by King Manuel I in the early 16th century, it is considered a masterpiece of Late Gothic Manueline architecture. It was classified as a UNESCO World Heritage Site in 1983 and is one of the most visited monuments in all of Portugal.",
            "photo_url": "https://upload.wikimedia.org/wikipedia/commons/7/7a/Jeronimos_mostra.jpg"
        },
        {
            "name": "Castelo de São Jorge",
            "lat": 38.7139, "lon": -9.1334,
            "type": "🏰 Historic",
            "description": "Historic Moorish castle with panoramic views over Lisbon",
            "description_long": "São Jorge Castle is a Moorish castle occupying a commanding hilltop in the historic centre of Lisbon. Its strategic position offers panoramic views over the city and the Tagus estuary. The site has been inhabited since at least the 7th century BC, and the castle itself has served as a royal residence and military fortress. Today it is one of Lisbon's most popular tourist attractions.",
            "photo_url": "https://upload.wikimedia.org/wikipedia/commons/9/9d/Castelo_de_S.Jorge_2.jpg"
        },
        {
            "name": "Praça do Comércio",
            "lat": 38.7075, "lon": -9.1364,
            "type": "⭐ Attraction",
            "description": "Grand waterfront square at the heart of Lisbon",
            "description_long": "Praça do Comércio, also known as Terreiro do Paço, is a large square in the city of Lisbon facing the Tagus River. It was the main point of entry to Lisbon from the river and is considered one of the finest and largest plazas in Europe. The square is surrounded by elegant arcaded yellow buildings and is home to the iconic triumphal arch, the Arco da Rua Augusta.",
            "photo_url": "https://upload.wikimedia.org/wikipedia/commons/2/2c/Lisbon_prac%CC%A7a_comercio_May_2009-2.jpg"
        },
        {
            "name": "Parque das Nações",
            "lat": 38.7630, "lon": -9.0950,
            "type": "🌳 Park",
            "description": "Modern riverside district built for Expo 98",
            "description_long": "Parque das Nações is a modern district in Lisbon that was developed for the 1998 World Exposition. Located along the Tagus River, the area is characterised by its contemporary architecture, wide promenades, and open green spaces. It is home to the Oceanarium, the Pavilion of Portugal by Álvaro Siza Vieira, and the iconic cable car that runs along the riverside.",
            "photo_url": "https://upload.wikimedia.org/wikipedia/commons/0/05/Lisboa_-_Parque_das_Na%C3%A7%C3%B5es_%2836568037963%29.jpg"
        },
        {
            "name": "LX Factory",
            "lat": 38.7037, "lon": -9.1762,
            "type": "⭐ Attraction",
            "description": "Creative industrial district with food, art and shops",
            "description_long": "LX Factory is a creative hub located in a former industrial complex in the Alcântara neighbourhood of Lisbon. The space hosts a diverse mix of restaurants, bars, boutique shops, art galleries, and creative studios. Every Sunday it transforms into a popular market attracting thousands of visitors. The industrial architecture and street art murals give it a distinctive bohemian atmosphere.",
            "photo_url": "https://upload.wikimedia.org/wikipedia/commons/e/e7/LxFactory_Lisboa.jpg"
        },
        {
            "name": "Miradouro da Graça",
            "lat": 38.7176, "lon": -9.1309,
            "type": "⭐ Attraction",
            "description": "One of Lisbon's best viewpoints with castle views",
            "description_long": "Miradouro da Graça is one of Lisbon's most beloved viewpoints, offering stunning panoramic views over the city's rooftops, the Tagus River, and the nearby São Jorge Castle. Located in the Graça neighbourhood, it is a favourite meeting spot for both locals and visitors, particularly at sunset when the light turns the city golden. A small kiosk serves drinks and snacks.",
            "photo_url": "https://upload.wikimedia.org/wikipedia/commons/8/87/Lisboa_-_Miradouro_da_Gra%C3%A7a_%2814035657213%29.jpg"
        },
        {
            "name": "Alfama",
            "lat": 38.7100, "lon": -9.1300,
            "type": "🏰 Historic",
            "description": "Lisbon's oldest and most atmospheric neighbourhood",
            "description_long": "Alfama is the oldest district of Lisbon, spreading from the São Jorge Castle down to the Tagus River. Its name derives from the Arabic word for fountains or baths. The neighbourhood is characterised by a labyrinth of narrow alleys, traditional houses with colourful tiles, and the haunting sound of Fado music drifting from its bars and restaurants. It survived the 1755 earthquake largely intact.",
            "photo_url": "https://upload.wikimedia.org/wikipedia/commons/3/36/Lisboa_Alfama.jpg"
        },
        {
            "name": "Parque Eduardo VII",
            "lat": 38.7272, "lon": -9.1536,
            "type": "🌳 Park",
            "description": "Lisbon's main central park with great city views",
            "description_long": "Parque Eduardo VII is the largest park in central Lisbon, named after King Edward VII of the United Kingdom who visited the city in 1902. The park features a formal French-style garden and a large open esplanade that offers sweeping views over the Baixa district and the Tagus River. At its northern end are the famous Estufa Fria greenhouses, home to exotic plants from around the world.",
            "photo_url": "https://upload.wikimedia.org/wikipedia/commons/8/89/Parque_Eduardo_VII_%28Lisbon%29.jpg"
        },
        {
            "name": "Marquês de Pombal",
            "lat": 38.7226, "lon": -9.1499,
            "type": "⭐ Attraction",
            "description": "Iconic roundabout with a monument to Lisbon's great reformer",
            "description_long": "The Marquis of Pombal Square is one of Lisbon's most important public spaces, centred around a tall column topped by a statue of the Marquis of Pombal. Pombal was the powerful prime minister who rebuilt Lisbon after the devastating 1755 earthquake and tsunami. The square serves as a key junction between the Avenida da Liberdade and Parque Eduardo VII.",
            "photo_url": "https://upload.wikimedia.org/wikipedia/commons/e/e0/Marquis_of_Pombal_Square_-_Lisbon.jpg"
        },
        {
            "name": "Jardim da Estrela",
            "lat": 38.7137, "lon": -9.1601,
            "type": "🌳 Park",
            "description": "Charming romantic garden in the Estrela neighbourhood",
            "description_long": "Jardim da Estrela is one of Lisbon's most charming public gardens, located in the upscale Estrela neighbourhood opposite the Basílica da Estrela. Dating back to 1852, the garden features beautiful Victorian bandstands, a small lake with ducks, tropical trees, and a popular café kiosk. It is a favourite spot for families, joggers, and those wanting a peaceful break from the city.",
            "photo_url": "https://upload.wikimedia.org/wikipedia/commons/3/39/Jardim_da_Estrela_%28Lisbon%29.jpg"
        },
        {
            "name": "Palácio de Belém",
            "lat": 38.6985, "lon": -9.2010,
            "type": "🏰 Historic",
            "description": "Official residence of the President of Portugal",
            "description_long": "The Palácio de Belém is the official residence of the President of Portugal and is located in the Belém district of Lisbon. Originally built in the 17th century as a summer retreat, it became the official presidential palace in 1910 following the establishment of the Portuguese Republic. The palace is surrounded by beautiful gardens and is home to the Museum of the Presidency.",
            "photo_url": "https://upload.wikimedia.org/wikipedia/commons/b/b2/Pal%C3%A1cio_de_Bel%C3%A9m_Lisboa.jpg"
        },
        {
            "name": "Miradouro de Santa Catarina",
            "lat": 38.7092, "lon": -9.1467,
            "type": "⭐ Attraction",
            "description": "Popular bohemian viewpoint overlooking the Tagus",
            "description_long": "Miradouro de Santa Catarina, also known as Adamastor, is one of Lisbon's most popular and lively viewpoints. Located in the Bica neighbourhood, it offers sweeping views over the Tagus River and the 25 de Abril Bridge. The viewpoint is famous for its relaxed, bohemian atmosphere and is a favourite gathering spot for young locals, musicians and street artists, especially at sunset.",
            "photo_url": "https://upload.wikimedia.org/wikipedia/commons/1/10/Miradouro_Santa_Catarina_Lisboa.jpg"
        },
        {
            "name": "Museu Nacional do Azulejo",
            "lat": 38.7241, "lon": -9.1102,
            "type": "🏛️ Museum",
            "description": "National tile museum dedicated to Portugal's iconic azulejo art",
            "description_long": "The Museu Nacional do Azulejo is housed in a former convent and is entirely dedicated to the art of the azulejo, the decorative tin-glazed ceramic tile that is deeply embedded in Portuguese culture and architecture. The collection spans five centuries of tile-making history, from the earliest geometric Moorish influences to contemporary works. The convent's baroque church and cloister are themselves spectacular examples of azulejo decoration.",
            "photo_url": "https://upload.wikimedia.org/wikipedia/commons/1/1a/Museu_do_Azulejo_Lisboa.jpg"
        },
        {
            "name": "Praça do Príncipe Real",
            "lat": 38.7152, "lon": -9.1499,
            "type": "🌳 Park",
            "description": "Elegant garden square in the trendy Príncipe Real district",
            "description_long": "Praça do Príncipe Real is a beautiful tree-lined garden square in one of Lisbon's most fashionable neighbourhoods. The square is famous for its enormous century-old cedar tree whose branches spread out to form a natural canopy. The area is surrounded by antique shops, independent boutiques, and excellent restaurants. A popular farmers market takes place here on Saturdays.",
            "photo_url": "https://upload.wikimedia.org/wikipedia/commons/3/3e/Praca_do_Principe_Real_Lisboa.jpg"
        },
        {
            "name": "Museu Calouste Gulbenkian",
            "lat": 38.7369, "lon": -9.1526,
            "type": "🏛️ Museum",
            "description": "One of Europe's finest private art collections",
            "description_long": "The Calouste Gulbenkian Museum houses the extraordinary private art collection of the Armenian-British oil magnate Calouste Gulbenkian, who left it to Portugal upon his death in 1955. The collection spans 5,000 years of art history and includes ancient Egyptian artefacts, Islamic art, Japanese prints, European paintings and sculpture, and the famous Art Nouveau jewellery of René Lalique. The surrounding gardens are also considered among Lisbon's most beautiful.",
            "photo_url": "https://upload.wikimedia.org/wikipedia/commons/f/f9/Museu_Calouste_Gulbenkian.jpg"
        },
        {
            "name": "Oceanário de Lisboa",
            "lat": 38.7633, "lon": -9.0934,
            "type": "⭐ Attraction",
            "description": "One of Europe's largest and most impressive aquariums",
            "description_long": "The Lisbon Oceanarium is one of the largest aquariums in Europe, located in the Parque das Nações district. Designed by American architect Peter Chermayeff for the 1998 World Exposition, it sits in the middle of the Tagus estuary and is surrounded by water on all sides. Its central ocean tank holds four million litres of seawater and is home to sharks, rays, sunfish and thousands of other marine species.",
            "photo_url": "https://upload.wikimedia.org/wikipedia/commons/8/8d/Oceanarium_Lisbon_2.jpg"
        },
        {
            "name": "Pavilhão de Portugal",
            "lat": 38.7651, "lon": -9.0960,
            "type": "🏰 Historic",
            "description": "Iconic pavilion by Álvaro Siza Vieira from Expo 98",
            "description_long": "The Portugal Pavilion was designed by the Pritzker Prize-winning architect Álvaro Siza Vieira for the 1998 World Exposition in Lisbon. Its most striking feature is a vast concrete canopy suspended between two porticos, creating the illusion of a thin stone sheet hanging in the air. The pavilion now serves as a venue for state ceremonies and is considered one of the finest examples of contemporary Portuguese architecture.",
            "photo_url": "https://upload.wikimedia.org/wikipedia/commons/a/a0/Pavilh%C3%A3o_de_Portugal_%28Lisbon%29.jpg"
        },
        {
            "name": "Jardim do Campo Grande",
            "lat": 38.7577, "lon": -9.1573,
            "type": "🌳 Park",
            "description": "Large urban park in northern Lisbon with a lake",
            "description_long": "Campo Grande is one of Lisbon's largest urban parks, featuring a scenic lake, walking paths, and plenty of greenery. It is popular with joggers, families, and students from the nearby university. The park hosts occasional outdoor events and has a pleasant café by the waterside.",
            "photo_url": ""
        },
        {
            "name": "Miradouro da Penha de França",
            "lat": 38.7261, "lon": -9.1261,
            "type": "⭐ Attraction",
            "description": "Quiet hilltop viewpoint with views over eastern Lisbon",
            "description_long": "Miradouro da Penha de França is a lesser-known but beautiful viewpoint in eastern Lisbon, offering panoramic views over the city's rooftops and the Tagus River. It is a favourite among locals who want to avoid the crowds of the more famous viewpoints, and has a peaceful, neighbourhood atmosphere.",
            "photo_url": ""
        },
        {
            "name": "Jardim do Arco do Cego",
            "lat": 38.7344, "lon": -9.1463,
            "type": "🌳 Park",
            "description": "Charming neighbourhood garden near Saldanha",
            "description_long": "Jardim do Arco do Cego is a peaceful public garden located in the Arco do Cego neighbourhood near Saldanha. It features tree-lined paths, benches, and a relaxed atmosphere popular with local residents. The area is surrounded by attractive early 20th century architecture.",
            "photo_url": ""
        },
        {
            "name": "Basílica da Estrela",
            "lat": 38.7138, "lon": -9.1596,
            "type": "🏰 Historic",
            "description": "18th century baroque basilica with stunning dome views",
            "description_long": "The Basílica da Estrela is an 18th century neoclassical church located opposite the Jardim da Estrela in Lisbon. Built between 1779 and 1790 by order of Queen Maria I, it was the first church in Portugal dedicated to the Sacred Heart of Jesus. Visitors can climb to the rooftop dome for sweeping panoramic views over the city.",
            "photo_url": ""
        },
        {
            "name": "Avenida da Liberdade",
            "lat": 38.7180, "lon": -9.1430,
            "type": "⭐ Attraction",
            "description": "Lisbon's grand tree-lined boulevard inspired by the Champs-Élysées",
            "description_long": "Avenida da Liberdade is Lisbon's most elegant boulevard, stretching from Praça dos Restauradores to the Marquês de Pombal roundabout. Lined with mosaic pavements, sculptures, fountains, and luxury shops, it was inspired by Paris's Champs-Élysées and remains one of the most prestigious addresses in the Portuguese capital.",
            "photo_url": ""
        },
        {
            "name": "Miradouro da Senhora do Monte",
            "lat": 38.7196, "lon": -9.1301,
            "type": "⭐ Attraction",
            "description": "Lisbon's highest viewpoint with unbeatable panoramic views",
            "description_long": "Miradouro da Senhora do Monte is the highest viewpoint in Lisbon, offering the most complete panoramic view of the city, including the castle, the Tagus River, and the 25 de Abril Bridge. It is a hidden gem compared to the more touristy viewpoints and is beloved by locals for its tranquil atmosphere and stunning sunsets.",
            "photo_url": ""
        },
    ]

    for sight in known_sights:
        sight["distance_from_start"] = calculate_distance(
            lat, lon, sight["lat"], sight["lon"]
        )

    max_radius = max_distance_km / 2.2
    filtered = [s for s in known_sights if s["distance_from_start"] <= max_radius]
    filtered.sort(key=lambda s: s["distance_from_start"])
    return filtered[:6]