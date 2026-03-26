import eurostat
import pandas as pd
import re

# ── Configuration ────────────────────────────────────────────────────────────
TARGET_YEAR = "2019"
COUNTRY_CODES = ["AT", "DE", "NL", "ES", "FR", "CH", "BE", "UK", "DK", "IT"]
OUTPUT_DIR = "."  # save CSVs in the current working directory


def sanitize_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Strip geo\\ / \\TIME_PERIOD artefacts and whitespace from column names."""
    df = df.reset_index()
    df.columns = [
        re.sub(r"\\+TIME_PERIOD|geo\\+|\\+", "", str(c)).strip()
        for c in df.columns
    ]
    return df


TIME_COL = re.compile(r"\d{4}(-\d{2}|-Q\d)?$")  # matches 1993, 1993-01, 1993-Q1, etc.
DROP_DIMS = {"index", "freq", "unit", "tra_meas", "schedule", "tra_cov"}  # constant after filtering

def filter_year(df: pd.DataFrame, year: str) -> pd.DataFrame:
    """Keep only the target year value plus meaningful dimension columns."""
    if year not in df.columns:
        raise KeyError(f"Year column '{year}' not found. Available: {list(df.columns)}")
    dim_cols = [c for c in df.columns if not TIME_COL.match(str(c)) and c not in DROP_DIMS]
    return df[dim_cols + [year]].rename(columns={year: "value"})


# ── Step 1: Structural Probe ─────────────────────────────────────────────────
PROBE_DATASETS = {
    "Airport Totals": "avia_paoa",
    "Spain Routes":   "avia_par_es",
    "Germany Routes": "avia_par_de",
}

print("=" * 60)
print("STEP 1 — Structural Probe")
print("=" * 60)

PROBE_DIM_COLS = ["unit", "schedule", "tra_cov", "tra_meas", "freq"]

for label, code in PROBE_DATASETS.items():
    print(f"\n[{code}] {label}")
    try:
        df = eurostat.get_data_df(code)
        if df is None:
            print("  > Returned None — dataset unavailable.")
            continue
        df = sanitize_columns(df)
        print(f"  > Columns (first 10): {list(df.columns[:10])}")
        for col in PROBE_DIM_COLS:
            if col in df.columns:
                try:
                    vals = list(df[col].dropna().unique())
                    print(f"  > {col} unique values: {vals}")
                except Exception as col_exc:
                    print(f"  > {col} ERROR: {col_exc}")
            else:
                print(f"  > {col}: NOT IN COLUMNS")
    except Exception as exc:
        print(f"  > ERROR: {exc}")


# ── Step 2: Data Extraction & Cleaning ───────────────────────────────────────
print("\n" + "=" * 60)
print("STEP 2 — Data Extraction & Cleaning")
print("=" * 60)

# ── Dataset A: Airport Totals (avia_paoa) ────────────────────────────────────
print("\n[avia_paoa] Fetching airport totals …")
try:
    df_totals_raw = eurostat.get_data_df("avia_paoa")
    df_totals = sanitize_columns(df_totals_raw)

    # Identify the geo/airport column (first non-numeric dimension column)
    geo_col = next(
        (c for c in df_totals.columns if not re.fullmatch(r"\d{4}", c) and c.lower() in ("geo", "airp_pr", "rep_airp", "airp")),
        None,
    )
    if geo_col is None:
        # Fall back: pick the last dimension column
        geo_col = [c for c in df_totals.columns if not re.fullmatch(r"\d{4}", c)][-1]

    # Filter to annual scheduled passenger totals (one clean number per airport)
    df_totals = df_totals[
        (df_totals["freq"]     == "A")        &
        (df_totals["unit"]     == "PAS")      &
        (df_totals["tra_meas"] == "PAS_CRD")  &
        (df_totals["schedule"] == "SCHED")    &
        (df_totals["tra_cov"]  == "TOTAL")
    ]

    df_totals = filter_year(df_totals, TARGET_YEAR)

    # Filter to rows whose airport code starts with one of our country codes
    mask = df_totals[geo_col].str[:2].isin(COUNTRY_CODES)
    df_totals = df_totals[mask].copy()
    # Extract country code and ICAO from rep_airp (format: "AT_LOWW")
    df_totals["country_code"] = df_totals[geo_col].str[:2]
    df_totals["icao_code"]    = df_totals[geo_col].str.split("_").str[-1]
    df_totals["year"] = TARGET_YEAR

    out_totals = f"{OUTPUT_DIR}/avia_paoa_{TARGET_YEAR}.csv"
    df_totals.to_csv(out_totals, index=False)
    print(f"  > Saved {len(df_totals)} rows → {out_totals}")
except Exception as exc:
    print(f"  > ERROR fetching avia_paoa: {exc}")
    df_totals = pd.DataFrame()

# ── Dataset B: Routes per country (avia_par_{cc}) ────────────────────────────
print("\n[avia_par_*] Fetching route data for each country …")
route_frames = []

for cc in COUNTRY_CODES:
    dataset_code = f"avia_par_{cc.lower()}"
    try:
        df_raw = eurostat.get_data_df(dataset_code)
        if df_raw is None:
            print(f"  [{dataset_code}] Returned None — skipping.")
            continue

        df = sanitize_columns(df_raw)

        # Filter to annual passenger rows (route datasets have no schedule/tra_cov cols)
        if "freq" in df.columns:
            df = df[df["freq"] == "A"]
        if "unit" in df.columns:
            df = df[df["unit"] == "PAS"]
        if "tra_meas" in df.columns and "PAS_CRD" in df["tra_meas"].values:
            df = df[df["tra_meas"] == "PAS_CRD"]
        if "schedule" in df.columns:
            df = df[df["schedule"] == "SCHED"]

        df = filter_year(df, TARGET_YEAR)
        df["reporting_country"] = cc
        df["year"] = TARGET_YEAR
        route_frames.append(df)
        print(f"  [{dataset_code}] {len(df)} rows")
    except KeyError as exc:
        print(f"  [{dataset_code}] Year column missing: {exc} — skipping.")
    except Exception as exc:
        print(f"  [{dataset_code}] ERROR: {exc}")

if route_frames:
    df_routes = pd.concat(route_frames, ignore_index=True)
    out_routes = f"{OUTPUT_DIR}/avia_par_routes_{TARGET_YEAR}.csv"
    df_routes.to_csv(out_routes, index=False)
    print(f"\n  > Merged route data: {len(df_routes)} rows → {out_routes}")
else:
    print("\n  > No route data retrieved.")
    df_routes = pd.DataFrame()

print("\nDone.")
