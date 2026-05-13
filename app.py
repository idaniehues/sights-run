from flask import Flask, render_template, request, jsonify
import requests
import folium
import random
import json
import os
import math

from metro import get_all_metro_stations, get_random_metro_station
from sights import get_sights_near_route, calculate_distance

app = Flask(__name__)
ORS_API_KEY = "eyJvcmciOiI1YjNjZTM1OTc4NTExMTAwMDFjZjYyNDgiLCJpZCI6IjJkOTlhYjllMjUzYzRjMjVhOWJiZDNhZTUxZjMzYjE5IiwiaCI6Im11cm11cjY0In0="

# Bounding box for central Lisbon
LISBON_CENTER_BOUNDS = {
    "min_lat": 38.695,
    "max_lat": 38.775,
    "min_lon": -9.210,
    "max_lon": -9.100
}


# -------------------------------------------------------
# HOME
# -------------------------------------------------------
@app.route("/")
def home():
    stations = get_all_metro_stations()
    return render_template("index.html", stations=stations)


# -------------------------------------------------------
# STATIONS FILTERED BY DISTANCE (AJAX)
# -------------------------------------------------------
@app.route("/stations_for_distance/<float:distance_km>")
def stations_for_distance(distance_km):
    """Returns metro stations that have sights within range for the given distance"""
    stations = get_all_metro_stations(distance_km=distance_km)
    return jsonify(stations)


# -------------------------------------------------------
# GENERATE ROUTE
# -------------------------------------------------------
@app.route("/generate", methods=["POST"])
def generate():
    start_type = request.form.get("start_type")
    distance = float(request.form.get("distance", 5))
    route_type = request.form.get("route_type", "roundtrip")

    if start_type == "random":
        station = get_random_metro_station(distance_km=distance)
        start_lat = station["lat"]
        start_lon = station["lon"]
        start_name = f"🎲 {station['name']} (Random)"

    elif start_type == "metro":
        station_name = request.form.get("metro_station")
        stations = get_all_metro_stations()
        station = next((s for s in stations if s["name"] == station_name), None)
        if not station:
            return "Station not found", 400
        start_lat = station["lat"]
        start_lon = station["lon"]
        start_name = f"🚇 {station['name']}"

    elif start_type == "gps":
        start_lat = float(request.form.get("gps_lat"))
        start_lon = float(request.form.get("gps_lon"))
        start_name = "📍 Your Location"

    elif start_type == "address":
        address = request.form.get("address")
        coords = geocode_address(address)
        if not coords:
            return render_template("error.html", message="Address not found. Please try a different address.")
        start_lat, start_lon = coords
        if not is_in_central_lisbon(start_lat, start_lon):
            return render_template("error.html", message=(
                "This address is too far from the city centre. "
                "The sights are concentrated in central Lisbon. "
                "Please choose a starting point in the city centre."
            ))
        start_name = f"📬 {address}"

    else:
        return "Invalid starting point", 400

    # Get nearby sights
    sights = get_sights_near_route(start_lat, start_lon, distance)

    # Calculate route
    route_coords, sights, actual_distance, leg_distances = calculate_route(
        start_lat, start_lon, sights, distance, route_type
    )

    # Show error if no sights were found within range
    if not sights:
        return render_template("error.html", message=(
            "No sights found within range of this starting point. "
            "Try selecting a longer distance or a starting point closer to the city centre."
        ))

    # Attach real leg distances to each sight
    sights = attach_leg_distances(sights, leg_distances, actual_distance, route_type)

    # Build canonical ordered stop list (single source of truth for map + Google Maps)
    canonical_stops = build_canonical_stops(start_lat, start_lon, start_name, sights, route_type)

    # Build Google Maps URL from the same canonical stop list
    gmaps_url = build_google_maps_url(canonical_stops)

    # Build route summary for Open Run feature
    route_summary = build_route_summary(canonical_stops, route_type)

    # Create map using canonical stops
    map_html = create_map(canonical_stops, route_coords, route_type)

    # Debug: log stop list to verify map and Google Maps use same stops
    print("=== CANONICAL STOP LIST ===")
    for i, stop in enumerate(canonical_stops):
        print(f"  {i}: {stop['name']} ({stop['lat']:.5f}, {stop['lon']:.5f})")
    print(f"=== GOOGLE MAPS URL ===\n  {gmaps_url}")

    return render_template(
        "map.html",
        map_html=map_html,
        start_name=start_name,
        sights=sights,
        distance=distance,
        route_type=route_type,
        actual_distance=round(actual_distance / 1000, 2),
        gmaps_url=gmaps_url,
        route_summary=route_summary
    )


# -------------------------------------------------------
# RANDOM METRO STATION (AJAX)
# -------------------------------------------------------
@app.route("/random_station")
def random_station():
    station = get_random_metro_station()
    return jsonify(station)


# -------------------------------------------------------
# HELPER FUNCTIONS
# -------------------------------------------------------
def is_in_central_lisbon(lat, lon):
    """Checks if coordinates are within the central Lisbon bounding box"""
    return (
        LISBON_CENTER_BOUNDS["min_lat"] <= lat <= LISBON_CENTER_BOUNDS["max_lat"] and
        LISBON_CENTER_BOUNDS["min_lon"] <= lon <= LISBON_CENTER_BOUNDS["max_lon"]
    )


def geocode_address(address):
    """Converts an address to coordinates via Nominatim (OpenStreetMap)"""
    url = "https://nominatim.openstreetmap.org/search"
    params = {
        "q": f"{address}, Lisboa, Portugal",
        "format": "json",
        "limit": 1
    }
    headers = {"User-Agent": "SightsRunApp/1.0"}
    try:
        response = requests.get(url, params=params, headers=headers)
        data = response.json()
        if data:
            return float(data[0]["lat"]), float(data[0]["lon"])
    except Exception as e:
        print(f"Geocoding error: {e}")
    return None


def get_bearing(lat1, lon1, lat2, lon2):
    """
    Calculates the compass bearing from point 1 to point 2 in degrees (0-360).
    Used to sort sights clockwise around the start point.
    """
    d_lon = math.radians(lon2 - lon1)
    lat1_r = math.radians(lat1)
    lat2_r = math.radians(lat2)
    x = math.sin(d_lon) * math.cos(lat2_r)
    y = math.cos(lat1_r) * math.sin(lat2_r) - math.sin(lat1_r) * math.cos(lat2_r) * math.cos(d_lon)
    bearing = math.degrees(math.atan2(x, y))
    return (bearing + 360) % 360


def sort_sights_for_loop(start_lat, start_lon, sights):
    """
    Sorts sights clockwise by bearing from the start point.
    Ensures the route flows as a natural loop instead of zigzagging.
    """
    for sight in sights:
        sight["bearing"] = get_bearing(start_lat, start_lon, sight["lat"], sight["lon"])
    return sorted(sights, key=lambda s: s["bearing"])


def score_route(route_coords, actual_distance, target_distance_m):
    """
    Scores a route based on circularity and low backtracking.
    Distance filtering is handled separately before scoring.
    Lower score = better route.
    """
    if not route_coords or len(route_coords) < 2:
        return float("inf")

    start = route_coords[0]
    end = route_coords[-1]
    circularity = calculate_distance(start[0], start[1], end[0], end[1])
    circularity_score = circularity * 10

    backtrack_score = 0
    for i in range(2, len(route_coords)):
        p1 = route_coords[i - 2]
        p2 = route_coords[i - 1]
        p3 = route_coords[i]
        v1 = (p2[0] - p1[0], p2[1] - p1[1])
        v2 = (p3[0] - p2[0], p3[1] - p2[1])
        dot = v1[0] * v2[0] + v1[1] * v2[1]
        if dot < -0.00001:
            backtrack_score += 1

    backtrack_score = backtrack_score / max(len(route_coords), 1)
    return circularity_score + backtrack_score


def attach_leg_distances(sights, leg_distances, actual_distance_m, route_type):
    """
    Attaches real ORS leg distances to each sight.
    Calculates cumulative distance and distance back to start.
    """
    cumulative = 0.0

    for i, sight in enumerate(sights):
        if i < len(leg_distances):
            leg_km = round(leg_distances[i] / 1000, 2)
        else:
            leg_km = 0.0
        cumulative = round(cumulative + leg_km, 2)
        sight["distance_from_previous"] = leg_km
        sight["distance_cumulative"] = cumulative

    if route_type == "roundtrip" and len(leg_distances) > len(sights):
        back_km = round(leg_distances[len(sights)] / 1000, 2)
    else:
        back_km = 0.0

    if sights:
        sights[-1]["distance_back_to_start"] = back_km
        sights[-1]["total_km"] = round(actual_distance_m / 1000, 2)

    return sights


def calculate_route(start_lat, start_lon, sights, max_distance_km, route_type="roundtrip"):
    """
    Generates a smooth loop route:
    1. Tries 1-4 sights in both clockwise and counterclockwise order
    2. Only considers routes within +/- 500m of target distance
    3. From valid routes picks the one with best loop shape
    4. If no route is within tolerance, picks the closest to target
    Returns: route_coords, sights_on_route, distance_m, leg_distances
    """
    url_base = "https://api.openrouteservice.org/v2/directions/foot-walking/geojson"
    headers = {
        "Authorization": ORS_API_KEY,
        "Content-Type": "application/json"
    }

    if route_type == "roundtrip":
        max_radius = max_distance_km / 2.0
    else:
        max_radius = max_distance_km * 0.9

    nearby_sights = [s for s in sights if s["distance_from_start"] <= max_radius]

    if max_distance_km <= 3:
        min_sights = 1
    elif max_distance_km <= 5:
        min_sights = 2
    elif max_distance_km <= 8:
        min_sights = 3
    else:
        min_sights = 4

    min_sights = min(min_sights, len(nearby_sights))
    max_sights = min(5, len(nearby_sights))

    if not nearby_sights:
        print("⚠️ No sights within range")
        return [[start_lat, start_lon], [start_lat, start_lon]], [], 0, []

    clockwise = sort_sights_for_loop(start_lat, start_lon, nearby_sights.copy())
    counterclockwise = list(reversed(clockwise))

    def request_route(waypoints):
        coords = [[start_lon, start_lat]]
        for sight in waypoints:
            coords.append([sight["lon"], sight["lat"]])
        if route_type == "roundtrip":
            coords.append([start_lon, start_lat])
        body = {"coordinates": coords}
        response = requests.post(url_base, json=body, headers=headers)
        return response.json()

    def is_on_route(sight, route_coords, threshold_km=0.3):
        for coord in route_coords[::5]:
            dist = calculate_distance(sight["lat"], sight["lon"], coord[0], coord[1])
            if dist <= threshold_km:
                return True
        return False

    target_m = max_distance_km * 1000
    tolerance_m = 500

    valid_candidates = []   # within +/- 500m of target
    all_candidates = []     # all attempts

    for ordering_name, ordering in [("clockwise", clockwise), ("counterclockwise", counterclockwise)]:
        for n in range(min_sights, max_sights + 1):
            waypoints = ordering[:n]
            try:
                data = request_route(waypoints)
                actual_distance = data["features"][0]["properties"]["summary"]["distance"]
                raw_coords = data["features"][0]["geometry"]["coordinates"]
                route_coords_latlon = [[c[1], c[0]] for c in raw_coords]
                diff = abs(actual_distance - target_m)
                score = score_route(route_coords_latlon, actual_distance, target_m)
                print(f"{ordering_name} {n} sights: {actual_distance:.0f}m diff={diff:.0f}m score={score:.3f}")

                candidate = {
                    "data": data,
                    "sights": waypoints,
                    "coords": route_coords_latlon,
                    "distance": actual_distance,
                    "diff": diff,
                    "score": score
                }
                all_candidates.append(candidate)
                if diff <= tolerance_m:
                    valid_candidates.append(candidate)

            except Exception as e:
                print(f"Route error ({ordering_name}, {n} sights): {e}")
                continue

    # Pick best valid route (within tolerance, best loop shape)
    # Fall back to closest to target if none within tolerance
    if valid_candidates:
        best = min(valid_candidates, key=lambda c: c["score"])
        print(f"✅ Valid route: {best['distance']:.0f}m (diff={best['diff']:.0f}m)")
    elif all_candidates:
        best = min(all_candidates, key=lambda c: c["diff"])
        print(f"⚠️ No route within tolerance, using closest: {best['distance']:.0f}m")
    else:
        best = None

    if best is None:
        print("⚠️ All route attempts failed, using fallback")
        fallback = [[start_lat, start_lon]]
        for sight in nearby_sights[:min_sights]:
            fallback.append([sight["lat"], sight["lon"]])
        if route_type == "roundtrip":
            fallback.append([start_lat, start_lon])
        return fallback, nearby_sights[:min_sights], 0, []

    try:
        actual_distance = best["data"]["features"][0]["properties"]["summary"]["distance"]
        segments = best["data"]["features"][0]["properties"].get("segments", [])
        leg_distances = [seg["distance"] for seg in segments]
        print(f"✅ Best route: {actual_distance:.0f}m")
        sights_on_route = [s for s in best["sights"] if is_on_route(s, best["coords"])]
        print(f"✅ Sights on route: {len(sights_on_route)}")
        return best["coords"], sights_on_route, actual_distance, leg_distances
    except Exception as e:
        print(f"Route extraction error: {e}")
        fallback = [[start_lat, start_lon]]
        for sight in nearby_sights[:min_sights]:
            fallback.append([sight["lat"], sight["lon"]])
        if route_type == "roundtrip":
            fallback.append([start_lat, start_lon])
        return fallback, nearby_sights[:min_sights], 0, []


def build_canonical_stops(start_lat, start_lon, start_name, sights, route_type):
    """
    Builds the single canonical ordered stop list used for:
    map markers, route line, and Google Maps URL.
    """
    stops = []
    stops.append({"name": start_name, "lat": start_lat, "lon": start_lon, "role": "start"})
    for i, sight in enumerate(sights):
        stops.append({"name": sight["name"], "lat": sight["lat"], "lon": sight["lon"], "role": "sight", "index": i + 1})
    if route_type == "roundtrip":
        stops.append({"name": start_name, "lat": start_lat, "lon": start_lon, "role": "finish"})
    else:
        if sights:
            last = sights[-1]
            stops.append({"name": last["name"], "lat": last["lat"], "lon": last["lon"], "role": "finish"})
    return stops


def build_google_maps_url(canonical_stops):
    """Builds a Google Maps walking directions URL from the canonical stop list."""
    if len(canonical_stops) < 2:
        return ""
    origin = canonical_stops[0]
    destination = canonical_stops[-1]
    waypoints = canonical_stops[1:-1]
    origin_str = f"{origin['lat']},{origin['lon']}"
    destination_str = f"{destination['lat']},{destination['lon']}"
    waypoint_strs = [f"{s['lat']},{s['lon']}" for s in waypoints]
    base = "https://www.google.com/maps/dir/?api=1"
    url = f"{base}&origin={origin_str}&destination={destination_str}"
    if waypoint_strs:
        url += "&waypoints=" + "|".join(waypoint_strs)
    url += "&travelmode=walking"
    return url


def build_route_summary(canonical_stops, route_type):
    """Builds a compact text summary of the ordered route stops."""
    if not canonical_stops:
        return "Generated Lisbon running route."
    start_name = canonical_stops[0]["name"]
    sight_names = [stop["name"] for stop in canonical_stops if stop["role"] == "sight"]
    stops_text = " via " + ", ".join(sight_names) if sight_names else ""
    if route_type == "roundtrip":
        return f"Loop from {start_name}{stops_text}, finishing back at the start."
    finish_name = canonical_stops[-1]["name"]
    return f"Point-to-point route from {start_name}{stops_text}, finishing at {finish_name}."


def create_map(canonical_stops, route_coords, route_type="roundtrip"):
    """Creates an interactive folium map using the canonical stop list."""
    if not canonical_stops:
        return ""
    start = canonical_stops[0]
    m = folium.Map(location=[start["lat"], start["lon"]], zoom_start=14, tiles="CartoDB positron")

    sight_index = 1
    for stop in canonical_stops:
        if stop["role"] == "start":
            folium.Marker([stop["lat"], stop["lon"]], popup=stop["name"], tooltip=stop["name"],
                icon=folium.Icon(color="green", icon="play", prefix="fa")).add_to(m)
        elif stop["role"] == "sight":
            folium.Marker([stop["lat"], stop["lon"]], popup=f"<b>{stop['name']}</b>",
                tooltip=f"Stop {sight_index}: {stop['name']}",
                icon=folium.Icon(color="red", icon="camera", prefix="fa")).add_to(m)
            sight_index += 1
        elif stop["role"] == "finish" and route_type == "oneway":
            folium.Marker([stop["lat"], stop["lon"]], popup="🏁 Finish", tooltip="🏁 Finish",
                icon=folium.Icon(color="blue", icon="flag", prefix="fa")).add_to(m)

    if route_coords:
        folium.PolyLine(route_coords, color="#E8106A", weight=4, opacity=0.8).add_to(m)

    return m._repr_html_()


# -------------------------------------------------------
# START APP
# -------------------------------------------------------
if __name__ == "__main__":
    app.run(debug=True)