# Short-Haul Flight Substitution by High-Speed Rail in Europe
### A Spatial Market Access Analysis

**Context:** GIS & Data Analysis Portfolio Project — 2025/2026
**Tools:** Python, GeoPandas, Shapely, Contextily, Eurostat API
**Framework:** Allen & Arkolakis (2014) Market Access

---

## 1. Motivation

Aviation accounts for roughly 2.5% of global CO₂ emissions, but its total climate impact — including radiative forcing from contrails and NOx at altitude — is estimated to be 2–4× larger. Within Europe, a substantial share of flights operate on routes that are, in principle, substitutable by existing high-speed rail (HSR). This project quantifies *where* and *under what conditions* that substitution is welfare-improving, using a spatial market access framework calibrated to real infrastructure data.

The central question: **which short-haul European flight routes should be replaced by HSR, and what policy levers determine this?**

---

## 2. Data

| Dataset | Source | Coverage | Key Variables |
|---|---|---|---|
| Railway network | GL2017 EU Shapefile | 3,361 segments, EPSG:3857 | Geometry, `TYPE` (Conventional / High speed) |
| Airport locations | OpenFlights `airports.txt` | Global → filtered to Europe | IATA, ICAO, lat/lon |
| Flight routes | OpenFlights `routes.txt` | ~67,000 global routes | Origin/destination airport IDs |
| Passenger traffic | Eurostat `avia_paoa` (API) | EU airports, quarterly | Passengers on board by airport |

**Filtering decisions:**
- Airports restricted to bounding box (lat 34–72°N, lon 25°W–45°E), `type == "airport"`, and IATA code present (removes military/private airfields)
- Further restricted to airports appearing in `routes.txt` (commercially active)
- Passenger data joined via ICAO code from Eurostat's `CC_ICAO` airport identifiers

---

## 3. Methods

### Step 1 — HSR Network and Airport Access

The HSR sub-network (660 of 3,361 rail segments) was isolated and airports were buffered by **5 km** to identify those with direct HSR access. A **flood-fill algorithm** then expanded outward — iteratively buffering accessible HSR segments by 200 m to capture endpoint connections — until convergence. This identifies the full connected HSR sub-network reachable from any airport within the catchment, not just the immediately adjacent segment.

**Result:** The vast majority of European HSR forms a single connected component accessible from airports. Key finding: London Heathrow (LHR) has **zero** substitutable routes due to lack of HSR integration, while Paris CDG has **21**, reflecting its integrated TGV terminal.

### Step 2 — Short-Haul Route Identification

Great-circle distances were computed via the Haversine formula. A simplified flight time model was applied:

```
flight_time = dist_km / 800 km/h  +  0.75h overhead
```

The 0.75h captures boarding, taxi, and arrival procedures — acknowledged as a conservative lower bound (see Limitations). Routes with estimated flight time ≤ 2.5h were classified as short-haul. Of these, routes where **both** endpoint airports lie within 5 km of HSR were identified as substitutable.

### Step 3 — Carbon-Adjusted Market Access

Following Allen & Arkolakis (2014), each airport's market access is defined as:

```
MA_i = Σ_j  Y_j · τ_ij^(−θ)
```

where `Y_j` is annual passengers at airport `j` (Eurostat), `τ_ij` is the carbon-adjusted bilateral cost, and `θ` is the trade elasticity (tested at 3, 5, 8).

The bilateral cost incorporates both time and carbon:

```
τ_ij = t_ij + λ · CO₂_ij
```

where `λ = carbon price / value of travel time = €100/t ÷ €30/hr = 0.0033 hr/kg CO₂`.

**CO₂ parameters:**
- Aviation (short-haul, incl. radiative forcing): 255 g/pax-km
- High-speed rail (European average): 14 g/pax-km

The **counterfactual** replaces aviation cost with HSR cost on all substitutable routes. The change in market access (`ΔMA_i`) identifies airports that gain or lose clean connectivity.

### Step 4 — Sensitivity Analysis

Two policy levers were varied to map the conditions under which substitution is beneficial:
1. **Carbon price** (€50–300/tonne) — the fiscal instrument
2. **Airport overhead** (0.75–2.0h) — a proxy for infrastructure investment in airport-rail integration

---

## 4. Findings

### 4.1 The Break-Even Distance

At baseline parameters (€100/tonne carbon, 0.75h overhead), HSR has a lower carbon-adjusted cost than flying for routes **below approximately 385 km**. Of 187 substitutable routes, 34 fall below this threshold.

### 4.2 Barcelona–Madrid: The Canonical Case

The BCN-MAD route (483 km) is the most studied example of air-rail competition in Europe. The AVE opened in 2008 and reduced air passengers by ~60% (Eurostat). However, at baseline model parameters, BCN-MAD sits **above** the 385 km threshold — the model predicts flight is cheaper in carbon-adjusted terms.

The resolution lies in the overhead assumption:

| Airport overhead | Break-even distance | BCN-MAD outcome |
|---|---|---|
| 0.75h (model baseline) | 385 km | Flight wins |
| 1.00h | 514 km | HSR wins |
| 1.50h (realistic) | 771 km | HSR wins |
| 2.00h (conservative) | 1,028 km | HSR wins |

At just 15 minutes more overhead than the baseline assumption, BCN-MAD flips. This aligns with the real-world outcome and confirms that *airport access friction — not the carbon price — is the decisive variable* for the routes most commonly discussed in modal shift policy.

### 4.3 Carbon Price Break-Even (BCN-MAD)

The carbon price at which BCN-MAD substitution becomes beneficial under baseline overhead:

- **~€150/tonne** (incl. radiative forcing, 14 g/pax-km rail)
- **~€241/tonne** (direct CO₂ only, 4 g/pax-km rail — Spanish/French nuclear grid)

The current EU ETS price (~€65/tonne) and stated 2030 targets (~€100–130/tonne) fall below both thresholds, suggesting carbon pricing alone is insufficient without accompanying reductions in airport access time.

### 4.4 Market Access Winners and Losers

Under the baseline counterfactual (θ = 5):

- **Largest absolute ΔMA:** Brussels (BRU), Stuttgart (STR), Düsseldorf (DUS) — central European hubs with short substitutable connections
- **Largest % ΔMA:** Peripheral airports (Jerez, Graz, Liège) — small baseline MA amplifies percentage gains
- **Losers:** BCN, MAD (ΔMA ≈ −11%) — airports whose substitutable routes are dominated by longer pairs where HSR time penalty exceeds carbon savings

### 4.5 Infrastructure Gap: LHR

London Heathrow — Europe's busiest airport by passengers — has **zero substitutable routes** under the 5 km HSR buffer criterion. This reflects the absence of a direct airport-HSR connection, in contrast to CDG's integrated TGV station. This is not a data artefact: it is the model correctly identifying a structural infrastructure gap with direct policy implications.

---

## 5. Limitations

| Limitation | Impact | Direction of bias |
|---|---|---|
| 5 km buffer as HSR access proxy | Ignores ground transport time to nearest HSR station | Overstates accessibility for some airports |
| Flat 0.75h flight overhead | Understates airport access friction for short-haul | Understates HSR competitiveness (conservative) |
| `Y_j` = airport passengers | Includes transfer passengers; city-level GDP or population would be preferable | Biases toward hub airports |
| Gravity proxy for route demand | No actual O-D passenger data | Rankings approximate only |
| Uniform HSR speed (250 km/h) | Actual speeds vary by line and country | Minor |
| Radiative forcing multiplier | Scientifically supported but excluded from some policy frameworks | Affects break-even carbon price by ~60% |
| OpenFlights route data | May be incomplete or dated; no frequency data | Understates network density for some carriers |
| Partial equilibrium | No demand response, induced traffic, or second-round effects | First-order substitution only |

---

## 6. Policy Implications

Three conclusions are robust across parameter choices:

1. **Airport-rail integration is the first-order intervention.** Reducing effective airport overhead from 1.5h to 0.75h shifts the break-even distance from ~770 km to ~385 km — achievable through infrastructure investment rather than pricing, and relevant to airports serving routes that carbon pricing alone cannot reach.

2. **Carbon pricing is necessary but not sufficient at current ETS levels.** BCN-MAD requires €150–240/tonne to flip under realistic assumptions — roughly 2–4× the current EU ETS price. This supports calls for aviation-specific carbon pricing above the general ETS rate.

3. **The infrastructure gap is spatial and uneven.** LHR's zero substitutable routes contrast sharply with CDG's 21, despite LHR being the larger airport. Modal shift policy that ignores this spatial heterogeneity will be ineffective.

---

## 7. References

- Allen, T. & Arkolakis, C. (2014). Trade and the Topography of the Spatial Economy. *Quarterly Journal of Economics*, 129(3), 1085–1140.
- Eaton, J. & Kortum, S. (2002). Technology, Geography, and Trade. *Econometrica*, 70(5), 1741–1779.
- Givoni, M. & Dobruszkes, F. (2013). A Review of Ex-Post Evidence for Mode Substitution and Induced Demand Following the Introduction of High-Speed Rail. *Transport Reviews*, 33(6), 720–742.
- European Environment Agency (2023). *Transport and Environment Report*.
- Eurostat (2025). *Air Transport Statistics: avia_paoa*. Retrieved via Eurostat SDMX API.
- Earth.org (2024). What Can Europe Learn from Spain's High-Speed Rail's Success at Slashing Transport-Related Emissions.
