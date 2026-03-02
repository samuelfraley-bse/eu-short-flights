"""
european_flights.py
===================
Maps European short-haul flight routes as an origin-destination network.

Data sources (local cache preferred, URL fallback):
  - data/airports.txt      (OpenFlights airports.dat)
  - data/routes.dat.txt    (OpenFlights routes.dat)

Output:
  - europe_flights.html    (interactive Plotly map)
  - europe_flights.png     (static image, requires kaleido)
"""

import io
import os
import sys

import numpy as np
import pandas as pd
import plotly.graph_objects as go

# ── Constants ─────────────────────────────────────────────────────────────────
AIRPORTS_LOCAL = "data/airports.txt"
ROUTES_LOCAL   = "data/routes.dat.txt"
AIRPORTS_URL   = "https://raw.githubusercontent.com/jpatokal/openflights/master/data/airports.dat"
ROUTES_URL     = "https://raw.githubusercontent.com/jpatokal/openflights/master/data/routes.dat"

# European bounding box
EU_LAT_MIN, EU_LAT_MAX = 35.0, 72.0
EU_LON_MIN, EU_LON_MAX = -25.0, 45.0

MAX_DISTANCE_KM = 1500.0

# Distance bins: thresholds, display labels, hex colours (green -> red)
DIST_BINS   = [0, 300, 600, 900, 1200, 1500]
DIST_LABELS = ["0-300 km", "301-600 km", "601-900 km", "901-1200 km", "1201-1500 km"]
DIST_COLORS = ["#00C878", "#96DC00", "#FFC800", "#FF7800", "#DC3232"]

# Frequency bins: thresholds, display labels, visual weight
FREQ_BINS   = [0, 1, 3, 7, 9999]
FREQ_LABELS = ["1 airline", "2-3 airlines", "4-7 airlines", "8+ airlines"]
FREQ_WIDTHS = [0.5, 1.0, 2.0, 3.5]
FREQ_ALPHAS = [0.20, 0.40, 0.65, 0.90]

# Static PNG: fixed line style (replaces per-freq width/opacity variation)
STATIC_LINE_WIDTH = 1.5
STATIC_LINE_ALPHA = 0.55

# Train-replacement map: 3 distance bands and colours
TRAIN_DIST_BINS   = [0, 200, 350, 500]
TRAIN_DIST_LABELS = ["<200 km  (most replaceable)", "200-350 km", "350-500 km"]
TRAIN_DIST_COLORS = ["#00C878", "#FFC800", "#FF7800"]

# Glow effect: wide faint halo underneath, narrow bright core on top
TRAIN_HALO_WIDTH = 4.0
TRAIN_HALO_ALPHA = 0.08
TRAIN_CORE_WIDTH = 1.0
TRAIN_CORE_ALPHA = 0.60

# Rail network map (OSM data)
RAIL_STATION_RADIUS_KM = 50.0    # max km: airport -> nearest OSM station counts as "has rail"
RAIL_LINE_COLOR        = "#00C878"  # green
OSM_REGION_DIR         = "data/osm_regions"
OSM_REGION_LON_DEG     = 12.0     # longitude width for regional Overpass pulls
OSM_REGION_PAUSE_S     = 1.0      # polite pause between region requests


# ── Helpers ───────────────────────────────────────────────────────────────────

def _read_text(local_path: str, url: str) -> str:
    """Return raw text from a local file, falling back to a URL download."""
    if os.path.exists(local_path):
        print(f"  Reading {local_path} (local cache)")
        with open(local_path, encoding="utf-8", errors="replace") as fh:
            return fh.read()
    print(f"  Downloading {url}")
    import requests
    resp = requests.get(url, timeout=30)
    resp.raise_for_status()
    return resp.text


def haversine_km(lat1, lon1, lat2, lon2) -> np.ndarray:
    """Vectorised haversine distance in kilometres."""
    R = 6371.0
    phi1, phi2 = np.radians(lat1), np.radians(lat2)
    dphi    = np.radians(lat2 - lat1)
    dlambda = np.radians(lon2 - lon1)
    a = np.sin(dphi / 2) ** 2 + np.cos(phi1) * np.cos(phi2) * np.sin(dlambda / 2) ** 2
    return 2 * R * np.arcsin(np.sqrt(a))


# ── Data loading ──────────────────────────────────────────────────────────────

def load_airports() -> pd.DataFrame:
    """Load OpenFlights airports and return a tidy DataFrame."""
    print("Loading airports...")
    text = _read_text(AIRPORTS_LOCAL, AIRPORTS_URL)
    cols = [
        "airport_id", "name", "city", "country",
        "iata", "icao", "lat", "lon",
        "altitude", "timezone", "dst", "tz_db", "type", "source",
    ]
    df = pd.read_csv(
        io.StringIO(text),
        header=None,
        names=cols,
        na_values=["\\N", ""],
        quotechar='"',
        low_memory=False,
    )
    df["lat"] = pd.to_numeric(df["lat"], errors="coerce")
    df["lon"] = pd.to_numeric(df["lon"], errors="coerce")
    df = df.dropna(subset=["lat", "lon"])
    df = df[df["iata"].notna() & (df["iata"].str.len() == 3)]
    print(f"  Total airports loaded: {len(df)}")
    return df.reset_index(drop=True)


def filter_european_airports(airports: pd.DataFrame) -> pd.DataFrame:
    """Keep only airports inside the European bounding box."""
    mask = (
        (airports["lat"] >= EU_LAT_MIN) & (airports["lat"] <= EU_LAT_MAX) &
        (airports["lon"] >= EU_LON_MIN) & (airports["lon"] <= EU_LON_MAX)
    )
    eu = airports[mask].copy()
    print(f"  European airports (bounding box): {len(eu)}")
    return eu.reset_index(drop=True)


def load_routes() -> pd.DataFrame:
    """Load OpenFlights routes and return a tidy DataFrame."""
    print("Loading routes...")
    text = _read_text(ROUTES_LOCAL, ROUTES_URL)
    cols = [
        "airline", "airline_id",
        "src_iata", "src_id",
        "dst_iata", "dst_id",
        "codeshare", "stops", "equipment",
    ]
    df = pd.read_csv(
        io.StringIO(text),
        header=None,
        names=cols,
        na_values=["\\N", ""],
        quotechar='"',
        low_memory=False,
    )
    df = df[df["stops"] == 0]                          # direct flights only
    df = df.dropna(subset=["src_iata", "dst_iata"])
    df = df[df["src_iata"].str.len() == 3]
    df = df[df["dst_iata"].str.len() == 3]
    print(f"  Total direct routes loaded: {len(df)}")
    return df.reset_index(drop=True)


# ── Route table ───────────────────────────────────────────────────────────────

def build_route_table(routes: pd.DataFrame, eu_airports: pd.DataFrame) -> pd.DataFrame:
    """
    Filter routes to intra-European short-haul pairs, add coordinates and
    great-circle distance, and count airline frequency as a volume proxy.
    Reverse duplicates (A->B == B->A) are collapsed and the higher frequency kept.
    """
    eu_iata = set(eu_airports["iata"])
    ap = eu_airports.set_index("iata")[["lat", "lon", "name", "city", "country"]]

    # EU-to-EU only
    mask = routes["src_iata"].isin(eu_iata) & routes["dst_iata"].isin(eu_iata)
    r = routes[mask].copy()

    # Count unique airlines per (src, dst) pair as frequency proxy
    freq = (
        r.groupby(["src_iata", "dst_iata"])
         .size()
         .reset_index(name="frequency")
    )

    # Attach coordinates
    freq = freq.merge(
        ap[["lat", "lon"]].rename(columns={"lat": "src_lat", "lon": "src_lon"}),
        left_on="src_iata", right_index=True,
    )
    freq = freq.merge(
        ap[["lat", "lon"]].rename(columns={"lat": "dst_lat", "lon": "dst_lon"}),
        left_on="dst_iata", right_index=True,
    )

    # Great-circle distance
    freq["distance_km"] = haversine_km(
        freq["src_lat"], freq["src_lon"],
        freq["dst_lat"], freq["dst_lon"],
    )

    # Short-haul filter + remove same-airport entries
    freq = freq[(freq["distance_km"] > 10) & (freq["distance_km"] <= MAX_DISTANCE_KM)].copy()

    # Collapse reverse duplicates: keep max frequency for undirected display
    freq["_pair"] = freq.apply(
        lambda row: tuple(sorted([row["src_iata"], row["dst_iata"]])), axis=1
    )
    freq = (
        freq.sort_values("frequency", ascending=False)
            .drop_duplicates("_pair")
            .drop(columns="_pair")
            .reset_index(drop=True)
    )

    print(f"  Intra-EU short-haul routes (<= {MAX_DISTANCE_KM:.0f} km): {len(freq)}")
    return freq


# ── Plotting ──────────────────────────────────────────────────────────────────

def _hex_to_rgb(hex_color: str) -> tuple:
    h = hex_color.lstrip("#")
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def _route_coords(subset: pd.DataFrame):
    """Return None-separated (lats, lons) arrays for a set of routes (vectorised)."""
    nan_col = np.full(len(subset), None)
    lats = np.column_stack([
        subset["src_lat"].values, subset["dst_lat"].values, nan_col
    ]).ravel().tolist()
    lons = np.column_stack([
        subset["src_lon"].values, subset["dst_lon"].values, nan_col
    ]).ravel().tolist()
    return lats, lons


# ── OSM / Overpass rail data ───────────────────────────────────────────────────

def fetch_overpass(cache_path: str, query: str, timeout: int = 90):
    """POST a query to the Overpass API, cache the JSON result locally."""
    import json
    import random
    import time
    import requests

    endpoints = [
        "https://overpass-api.de/api/interpreter",
        "https://overpass.kumi.systems/api/interpreter",
        "https://overpass.openstreetmap.fr/api/interpreter",
    ]

    if os.path.exists(cache_path):
        print(f"  Reading {cache_path} (local cache)")
        with open(cache_path, encoding="utf-8") as fh:
            return json.load(fh)
    max_attempts = 8
    for attempt in range(1, max_attempts + 1):
        endpoint = endpoints[(attempt - 1) % len(endpoints)]
        print(f"  Querying Overpass API... (attempt {attempt}/{max_attempts})")
        try:
            resp = requests.post(endpoint, data={"data": query}, timeout=timeout)
            status = resp.status_code
            if status == 429 or status >= 500:
                raise requests.HTTPError(f"{status} {resp.reason}", response=resp)
            resp.raise_for_status()
            data = resp.json()
            os.makedirs(os.path.dirname(cache_path) or ".", exist_ok=True)
            with open(cache_path, "w", encoding="utf-8") as fh:
                json.dump(data, fh)
            print(f"  Cached to {cache_path}")
            return data
        except requests.HTTPError as exc:
            status = exc.response.status_code if exc.response is not None else None
            retryable = status == 429 or (status is not None and status >= 500)
            if not retryable or attempt == max_attempts:
                print(f"  Overpass fetch failed: {exc}")
                return None
            wait_s = min(60, 2 ** attempt) + random.uniform(0.0, 1.0)
            print(f"    Rate-limited/server busy ({status}); retrying in {wait_s:.1f}s")
            time.sleep(wait_s)
        except requests.RequestException as exc:
            if attempt == max_attempts:
                print(f"  Overpass fetch failed: {exc}")
                return None
            wait_s = min(30, attempt * 3) + random.uniform(0.0, 1.0)
            print(f"    Network error; retrying in {wait_s:.1f}s")
            time.sleep(wait_s)
    return None


def load_osm_stations(eu_airports: pd.DataFrame, routes_train: pd.DataFrame) -> set:
    """
    For each airport in routes_train, check if a railway station/halt exists
    within RAIL_STATION_RADIUS_KM.

    To avoid many expensive around() filters, airports are grouped into a small
    number of longitude regions. Each region is fetched once via an Overpass bbox
    query, cached locally, then matched to airports in-memory.
    Returns a set of IATA codes confirmed to have nearby rail.
    """
    import time

    unique_iatas = sorted(set(routes_train["src_iata"]) | set(routes_train["dst_iata"]))
    ap_idx = eu_airports.set_index("iata")
    valid = [
        (iata, float(ap_idx.at[iata, "lat"]), float(ap_idx.at[iata, "lon"]))
        for iata in unique_iatas
        if iata in ap_idx.index
    ]
    if not valid:
        return set()

    lat_pad = RAIL_STATION_RADIUS_KM / 111.0
    lon_pad = max(lat_pad, 1.0)  # simple conservative padding for longitude
    os.makedirs(OSM_REGION_DIR, exist_ok=True)
    has_station: set = set()

    regions = {}
    for iata, lat, lon in valid:
        region_idx = int((lon - EU_LON_MIN) // OSM_REGION_LON_DEG)
        regions.setdefault(region_idx, []).append((iata, lat, lon))

    region_keys = sorted(regions.keys())
    n_regions = len(region_keys)

    for ri, region_idx in enumerate(region_keys, start=1):
        airports_region = regions[region_idx]
        lats = [a[1] for a in airports_region]
        lons = [a[2] for a in airports_region]

        south = max(EU_LAT_MIN - 2.0, min(lats) - lat_pad)
        north = min(EU_LAT_MAX + 2.0, max(lats) + lat_pad)
        west = max(EU_LON_MIN - 2.0, min(lons) - lon_pad)
        east = min(EU_LON_MAX + 2.0, max(lons) + lon_pad)

        cache_path = os.path.join(OSM_REGION_DIR, f"region_{region_idx:02d}.json")
        query = (
            "[out:json][timeout:120];\n"
            f'node["railway"~"station|halt"]({south:.4f},{west:.4f},{north:.4f},{east:.4f});\n'
            "out skel qt;"
        )

        data = fetch_overpass(cache_path, query, timeout=140)
        if ri < n_regions:
            time.sleep(OSM_REGION_PAUSE_S)
        if data is None:
            continue
        if "timed out" in data.get("remark", ""):
            print(f"    region {ri}/{n_regions}: timed out, will retry next run")
            try:
                os.remove(cache_path)
            except OSError:
                pass
            continue

        nodes = [
            (el["lat"], el["lon"])
            for el in data.get("elements", [])
            if el.get("type") == "node" and "lat" in el and "lon" in el
        ]
        if not nodes:
            continue

        node_lats = np.array([n[0] for n in nodes])
        node_lons = np.array([n[1] for n in nodes])
        for iata, lat, lon in airports_region:
            if haversine_km(lat, lon, node_lats, node_lons).min() <= RAIL_STATION_RADIUS_KM:
                has_station.add(iata)

    print(f"  Airports with nearby rail: {len(has_station)} / {len(unique_iatas)}")
    return has_station


def find_rail_connections(routes_train: pd.DataFrame,
                          has_station: set) -> pd.DataFrame:
    """
    Filter routes_train to pairs where both endpoints have confirmed rail service.
    Deduplicates undirected pairs and returns a DataFrame compatible with
    _route_coords() (needs src_lat, src_lon, dst_lat, dst_lon columns).
    """
    if not has_station:
        return pd.DataFrame()

    mask = (
        routes_train["src_iata"].isin(has_station) &
        routes_train["dst_iata"].isin(has_station)
    )
    connected = routes_train[mask].copy()
    connected["_pair"] = connected.apply(
        lambda r: tuple(sorted([r["src_iata"], r["dst_iata"]])), axis=1
    )
    return (
        connected.drop_duplicates("_pair")
                 .drop(columns="_pair")
                 .reset_index(drop=True)
    )


def plot_flight_network(
    routes: pd.DataFrame,
    eu_airports: pd.DataFrame,
    static: bool = False,
) -> go.Figure:
    """
    Build the Plotly figure.

    Route lines are bucketed by distance band -> colour (green to red).
    Interactive (static=False): further split by frequency band -> width/opacity.
    Static (static=True): one trace per distance band, fixed weight — much faster
    for kaleido PNG export.

    Airport nodes are sized by number of route connections (sqrt-scaled)
    and coloured by the same degree metric via the Viridis scale.
    """
    df = routes.copy()
    df["dist_bin"] = pd.cut(df["distance_km"], bins=DIST_BINS, labels=DIST_LABELS)

    fig = go.Figure()

    # ── 1. Route lines ─────────────────────────────────────────────────────
    if static:
        # One trace per distance band — 5 traces total, fast kaleido render
        for di, dlabel in enumerate(DIST_LABELS):
            subset = df[df["dist_bin"] == dlabel]
            if subset.empty:
                continue
            r, g, b = _hex_to_rgb(DIST_COLORS[di])
            lats, lons = _route_coords(subset)
            fig.add_trace(go.Scattergeo(
                lat=lats,
                lon=lons,
                mode="lines",
                line=dict(width=STATIC_LINE_WIDTH,
                          color=f"rgba({r},{g},{b},{STATIC_LINE_ALPHA})"),
                name=dlabel,
                legendgroup=dlabel,
                legendgrouptitle=dict(text="Distance") if di == 0 else {},
                showlegend=True,
                hoverinfo="skip",
            ))
    else:
        # One trace per dist_bin x freq_bin cell — full width/opacity variation
        df["freq_bin"] = pd.cut(df["frequency"], bins=FREQ_BINS, labels=FREQ_LABELS)
        for di, dlabel in enumerate(DIST_LABELS):
            r, g, b = _hex_to_rgb(DIST_COLORS[di])
            for fi, flabel in enumerate(FREQ_LABELS):
                subset = df[(df["dist_bin"] == dlabel) & (df["freq_bin"] == flabel)]
                if subset.empty:
                    continue
                lats, lons = _route_coords(subset)
                fig.add_trace(go.Scattergeo(
                    lat=lats,
                    lon=lons,
                    mode="lines",
                    line=dict(width=FREQ_WIDTHS[fi],
                              color=f"rgba({r},{g},{b},{FREQ_ALPHAS[fi]})"),
                    name=dlabel,
                    legendgroup=dlabel,
                    legendgrouptitle=dict(text="Distance") if (di == 0 and fi == 0) else {},
                    showlegend=(fi == 0),
                    hoverinfo="skip",
                ))

    # ── 2. Airport nodes ───────────────────────────────────────────────────
    degree = pd.concat([
        df[["src_iata"]].rename(columns={"src_iata": "iata"}),
        df[["dst_iata"]].rename(columns={"dst_iata": "iata"}),
    ]).value_counts().reset_index()
    degree.columns = ["iata", "degree"]

    ap_idx = eu_airports.set_index("iata")
    degree = degree[degree["iata"].isin(ap_idx.index)].copy()
    degree["lat"]     = degree["iata"].map(ap_idx["lat"])
    degree["lon"]     = degree["iata"].map(ap_idx["lon"])
    degree["ap_name"] = degree["iata"].map(ap_idx["name"])
    degree["city"]    = degree["iata"].map(ap_idx["city"])

    node_size = (np.sqrt(degree["degree"]) * 3.5).clip(lower=3, upper=28)

    fig.add_trace(go.Scattergeo(
        lat=degree["lat"],
        lon=degree["lon"],
        mode="markers",
        marker=dict(
            size=node_size,
            color=degree["degree"],
            colorscale="Viridis",
            cmin=1,
            cmax=int(degree["degree"].quantile(0.95)),
            colorbar=dict(
                title=dict(text="Route<br>connections", font=dict(color="#cccccc")),
                tickfont=dict(color="#cccccc"),
                x=1.01,
                len=0.45,
                thickness=12,
                bgcolor="rgba(0,0,0,0)",
                bordercolor="rgba(0,0,0,0)",
            ),
            line=dict(width=0.6, color="white"),
            opacity=0.92,
        ),
        text=degree.apply(
            lambda row: f"<b>{row['city']} ({row['iata']})</b><br>"
                        f"{row['ap_name']}<br>"
                        f"{row['degree']} connections",
            axis=1,
        ),
        hovertemplate="%{text}<extra></extra>",
        name="Airports",
        showlegend=True,
    ))

    # ── 3. Layout ──────────────────────────────────────────────────────────
    fig.update_layout(
        title=dict(
            text="European Short-Haul Flight Network  (<1,500 km)",
            x=0.5,
            xanchor="center",
            font=dict(size=20, color="#e0e0e0", family="Arial"),
        ),
        paper_bgcolor="#0d1117",
        plot_bgcolor="#0d1117",
        geo=dict(
            scope="europe",
            showland=True,         landcolor="#1c2333",
            showocean=True,        oceancolor="#0a0e1a",
            showlakes=True,        lakecolor="#111827",
            showcountries=True,    countrycolor="#2a3a55",
            showcoastlines=True,   coastlinecolor="#2a3a55",
            showsubunits=False,
            projection_type="natural earth",
            lataxis=dict(range=[EU_LAT_MIN - 3, EU_LAT_MAX + 2]),
            lonaxis=dict(range=[EU_LON_MIN - 2, EU_LON_MAX + 2]),
            bgcolor="#0d1117",
        ),
        legend=dict(
            font=dict(color="#cccccc", size=10),
            bgcolor="rgba(13,17,23,0.85)",
            bordercolor="#2a3a55",
            borderwidth=1,
            x=0.01,
            y=0.99,
            xanchor="left",
            yanchor="top",
        ),
        margin=dict(l=0, r=0, t=52, b=0),
        width=1400,
        height=860,
    )

    return fig


def plot_train_network(routes: pd.DataFrame, eu_airports: pd.DataFrame) -> go.Figure:
    """
    Interactive map of sub-500 km routes — potential train replacements.
    Routes coloured by distance band (green -> orange) with a glow effect.
    """
    df = routes.copy()
    df["dist_bin"] = pd.cut(
        df["distance_km"], bins=TRAIN_DIST_BINS, labels=TRAIN_DIST_LABELS
    )

    fig = go.Figure()

    # ── Route lines: halo + core per distance band ─────────────────────────
    for di, dlabel in enumerate(TRAIN_DIST_LABELS):
        subset = df[df["dist_bin"] == dlabel]
        if subset.empty:
            continue
        r, g, b = _hex_to_rgb(TRAIN_DIST_COLORS[di])
        lats, lons = _route_coords(subset)

        # Halo (wide, very faint)
        fig.add_trace(go.Scattergeo(
            lat=lats, lon=lons,
            mode="lines",
            line=dict(width=TRAIN_HALO_WIDTH,
                      color=f"rgba({r},{g},{b},{TRAIN_HALO_ALPHA})"),
            hoverinfo="skip",
            showlegend=False,
        ))
        # Core (narrow, opaque) — carries the legend entry
        fig.add_trace(go.Scattergeo(
            lat=lats, lon=lons,
            mode="lines",
            line=dict(width=TRAIN_CORE_WIDTH,
                      color=f"rgba({r},{g},{b},{TRAIN_CORE_ALPHA})"),
            name=dlabel,
            showlegend=True,
            hoverinfo="skip",
        ))

    # ── Airport nodes ──────────────────────────────────────────────────────
    eu_iata = set(routes["src_iata"]) | set(routes["dst_iata"])
    ap = eu_airports[eu_airports["iata"].isin(eu_iata)].copy()

    fig.add_trace(go.Scattergeo(
        lat=ap["lat"],
        lon=ap["lon"],
        mode="markers",
        marker=dict(size=4, color="rgba(220,220,220,0.6)", line=dict(width=0)),
        text=ap.apply(
            lambda r: f"<b>{r['city']} ({r['iata']})</b><br>{r['name']}", axis=1
        ),
        hovertemplate="%{text}<extra></extra>",
        name="Airport",
        showlegend=False,
    ))

    # ── Layout ─────────────────────────────────────────────────────────────
    fig.update_layout(
        title=dict(
            text="European Flights Under 500 km  —  Potential Train Replacements",
            x=0.5,
            xanchor="center",
            font=dict(size=18, color="#e0e0e0", family="Arial"),
        ),
        paper_bgcolor="#0d1117",
        geo=dict(
            scope="europe",
            showland=True,         landcolor="#1c2333",
            showocean=True,        oceancolor="#0a0e1a",
            showlakes=True,        lakecolor="#111827",
            showcountries=True,    countrycolor="#2a3a55",
            showcoastlines=True,   coastlinecolor="#2a3a55",
            showsubunits=False,
            projection_type="natural earth",
            lataxis=dict(range=[EU_LAT_MIN - 3, EU_LAT_MAX + 2]),
            lonaxis=dict(range=[EU_LON_MIN - 2, EU_LON_MAX + 2]),
            bgcolor="#0d1117",
        ),
        legend=dict(
            font=dict(color="#cccccc", size=10),
            bgcolor="rgba(13,17,23,0.85)",
            bordercolor="#2a3a55",
            borderwidth=1,
            x=0.01,
            y=0.99,
            xanchor="left",
            yanchor="top",
        ),
        margin=dict(l=0, r=0, t=48, b=0),
        width=1400,
        height=860,
    )

    return fig


def plot_rail_network(rail_connections: pd.DataFrame, eu_airports: pd.DataFrame,
                      routes_train: pd.DataFrame) -> go.Figure:
    """
    Interactive Mapbox map with:
      - carto-darkmatter base layer
      - OpenRailwayMap tile overlay (actual rail network as background)
      - Green arcs for city pairs that have rail coverage (OSM-verified)
      - Grey airport dots for all short-haul flight cities
    """
    fig = go.Figure()
    r, g, b = _hex_to_rgb(RAIL_LINE_COLOR)

    if len(rail_connections) > 0:
        all_lats, all_lons = _route_coords(rail_connections)

        fig.add_trace(go.Scattermapbox(
            lat=all_lats, lon=all_lons,
            mode="lines",
            line=dict(width=TRAIN_HALO_WIDTH,
                      color=f"rgba({r},{g},{b},{TRAIN_HALO_ALPHA})"),
            hoverinfo="skip",
            showlegend=False,
        ))
        fig.add_trace(go.Scattermapbox(
            lat=all_lats, lon=all_lons,
            mode="lines",
            line=dict(width=TRAIN_CORE_WIDTH,
                      color=f"rgba({r},{g},{b},{TRAIN_CORE_ALPHA})"),
            name="Rail connection",
            showlegend=True,
            hoverinfo="skip",
        ))

    # Airport dots — all cities in the short-haul flight set
    eu_iata = set(routes_train["src_iata"]) | set(routes_train["dst_iata"])
    ap = eu_airports[eu_airports["iata"].isin(eu_iata)].copy()

    fig.add_trace(go.Scattermapbox(
        lat=ap["lat"].tolist(),
        lon=ap["lon"].tolist(),
        mode="markers",
        marker=dict(size=5, color="rgba(220,220,220,0.7)"),
        text=ap.apply(
            lambda row: f"<b>{row['city']} ({row['iata']})</b><br>{row['name']}", axis=1
        ).tolist(),
        hovertemplate="%{text}<extra></extra>",
        name="Airport",
        showlegend=False,
    ))

    fig.update_layout(
        title=dict(
            text="European Short-Haul Rail Network  —  Train Alternatives to Flying",
            x=0.5,
            xanchor="center",
            font=dict(size=18, color="#e0e0e0", family="Arial"),
        ),
        paper_bgcolor="#0d1117",
        mapbox=dict(
            style="carto-darkmatter",
            center=dict(lat=50.5, lon=15.0),
            zoom=3.6,
            layers=[{
                "below": "traces",
                "sourcetype": "raster",
                "source": ["https://tiles.openrailwaymap.org/standard/{z}/{x}/{y}.png"],
                "opacity": 0.45,
            }],
        ),
        legend=dict(
            font=dict(color="#cccccc", size=10),
            bgcolor="rgba(13,17,23,0.85)",
            bordercolor="#2a3a55",
            borderwidth=1,
            x=0.01,
            y=0.99,
            xanchor="left",
            yanchor="top",
        ),
        margin=dict(l=0, r=0, t=48, b=0),
        width=1400,
        height=860,
    )

    return fig


# ── Summary stats ─────────────────────────────────────────────────────────────

def print_summary(routes: pd.DataFrame) -> None:
    print("\n--- Route summary ---")
    print(f"  Total routes displayed : {len(routes)}")
    print(f"  Median distance        : {routes['distance_km'].median():.0f} km")
    print(f"  Mean distance          : {routes['distance_km'].mean():.0f} km")
    print(f"  Max airline frequency  : {routes['frequency'].max()}")
    print(f"  Routes with 4+ airlines: {(routes['frequency'] >= 4).sum()}")

    top5 = (
        routes.sort_values("frequency", ascending=False)
              .head(5)[["src_iata", "dst_iata", "distance_km", "frequency"]]
    )
    print("\n  Top 5 routes by airline count:")
    for _, row in top5.iterrows():
        print(f"    {row['src_iata']} <-> {row['dst_iata']}  "
              f"{row['distance_km']:.0f} km  {row['frequency']} airlines")

    top10_short = (
        routes[routes["distance_km"] < 500]
              .sort_values("frequency", ascending=False)
              .head(10)[["src_iata", "dst_iata", "distance_km", "frequency"]]
    )
    print("\n  Top 10 routes under 500 km by airline count:")
    for i, (_, row) in enumerate(top10_short.iterrows(), 1):
        print(f"    {i:2}. {row['src_iata']} <-> {row['dst_iata']}  "
              f"{row['distance_km']:.0f} km  {row['frequency']} airlines")


# ── Entry point ───────────────────────────────────────────────────────────────

def main() -> None:
    # 1. Load
    airports    = load_airports()
    eu_airports = filter_european_airports(airports)
    routes_raw  = load_routes()

    # 2. Build route table
    routes = build_route_table(routes_raw, eu_airports)

    # 3. Diagnostics
    print_summary(routes)

    # 4. Build full figure and save interactive HTML
    print("\nBuilding figure (full routes)...")
    fig = plot_flight_network(routes, eu_airports)

    html_out = "europe_flights.html"
    fig.write_html(html_out, include_plotlyjs="cdn")
    print(f"Saved: {html_out}")

    # 5. Save train-replacement map — routes under 500 km only
    routes_train = routes[routes["distance_km"] < 500].copy()
    print(f"\nBuilding train-replacement figure ({len(routes_train)} routes < 500 km)...")
    fig_train = plot_train_network(routes_train, eu_airports)
    train_out = "europe_train_replacements.html"
    fig_train.write_html(train_out, include_plotlyjs="cdn")
    print(f"Saved: {train_out}")

    # 6. Build OSM rail network map
    print("\nLoading OSM rail data (cached after first run)...")
    has_station = load_osm_stations(eu_airports, routes_train)
    if has_station:
        rail_conns = find_rail_connections(routes_train, has_station)
        print(f"  Rail connections found: {len(rail_conns)} of {len(routes_train)} flight pairs")
        fig_rail = plot_rail_network(rail_conns, eu_airports, routes_train)
        fig_rail.write_html("europe_rail_network.html", include_plotlyjs="cdn")
        print("Saved: europe_rail_network.html")
    else:
        print("  OSM fetch failed -- skipping rail map")

    print("\nDone.")


if __name__ == "__main__":
    main()
