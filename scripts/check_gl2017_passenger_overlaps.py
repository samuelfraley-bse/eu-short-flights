from __future__ import annotations

from pathlib import Path

import geopandas as gpd
import pandas as pd
from shapely.geometry import GeometryCollection, LineString, MultiLineString


ROOT = Path(__file__).resolve().parents[1]
INPUT = ROOT / "data" / "raw" / "shapefiles" / "railways_GL2017_EU.shp"
OUTPUT_DIR = ROOT / "data" / "clean" / "outputs"
PAIR_CSV = OUTPUT_DIR / "gl2017_passenger_overlap_pairs.csv"
OVERLAP_GPKG = OUTPUT_DIR / "gl2017_passenger_overlap_segments.gpkg"
OVERLAP_LAYER = "overlap_segments"

PASSENGER_VALUES = {"Passenger", "Passenger and freight"}
MIN_OVERLAP_M = 1.0


def extract_linear_part(geom):
    if geom is None or geom.is_empty:
        return None
    if isinstance(geom, (LineString, MultiLineString)):
        return geom
    if isinstance(geom, GeometryCollection):
        linear_parts = [
            part for part in geom.geoms if isinstance(part, (LineString, MultiLineString))
        ]
        if not linear_parts:
            return None
        if len(linear_parts) == 1:
            return linear_parts[0]
        return MultiLineString(
            [line for part in linear_parts for line in getattr(part, "geoms", [part])]
        )
    return None


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    rail = gpd.read_file(INPUT)
    rail = rail.loc[rail["RAILWAYS_A"].isin(PASSENGER_VALUES)].copy()
    rail = rail.loc[~rail.geometry.is_empty & rail.geometry.notna()].copy()
    rail = rail.reset_index(drop=True)
    rail["segment_idx"] = rail.index

    spatial_index = rail.sindex
    pair_rows = []
    overlap_rows = []

    for idx, row in rail.iterrows():
        candidate_ids = spatial_index.query(row.geometry, predicate="intersects")
        for cand_idx in candidate_ids:
            if cand_idx <= idx:
                continue

            other = rail.iloc[cand_idx]
            inter = row.geometry.intersection(other.geometry)
            linear = extract_linear_part(inter)
            if linear is None:
                continue

            overlap_m = float(linear.length)
            if overlap_m < MIN_OVERLAP_M:
                continue

            pair_rows.append(
                {
                    "left_idx": int(row["segment_idx"]),
                    "right_idx": int(other["segment_idx"]),
                    "left_id": row["ID"],
                    "right_id": other["ID"],
                    "left_type": row["TYPE"],
                    "right_type": other["TYPE"],
                    "left_railways_a": row["RAILWAYS_A"],
                    "right_railways_a": other["RAILWAYS_A"],
                    "same_type": row["TYPE"] == other["TYPE"],
                    "overlap_m": round(overlap_m, 3),
                }
            )

            overlap_rows.append(
                {
                    "left_idx": int(row["segment_idx"]),
                    "right_idx": int(other["segment_idx"]),
                    "left_id": row["ID"],
                    "right_id": other["ID"],
                    "left_type": row["TYPE"],
                    "right_type": other["TYPE"],
                    "overlap_m": round(overlap_m, 3),
                    "geometry": linear,
                }
            )

    pairs = pd.DataFrame(pair_rows)
    overlaps = gpd.GeoDataFrame(overlap_rows, geometry="geometry", crs=rail.crs)

    if not pairs.empty:
        pairs = pairs.sort_values(["overlap_m", "left_type", "right_type"], ascending=[False, True, True])
    pairs.to_csv(PAIR_CSV, index=False)

    if OVERLAP_GPKG.exists():
        OVERLAP_GPKG.unlink()

    if overlaps.empty:
        empty = gpd.GeoDataFrame(
            {
                "left_idx": pd.Series(dtype="int64"),
                "right_idx": pd.Series(dtype="int64"),
                "left_id": pd.Series(dtype="object"),
                "right_id": pd.Series(dtype="object"),
                "left_type": pd.Series(dtype="object"),
                "right_type": pd.Series(dtype="object"),
                "overlap_m": pd.Series(dtype="float64"),
            },
            geometry=gpd.GeoSeries([], crs=rail.crs),
            crs=rail.crs,
        )
        empty.to_file(OVERLAP_GPKG, layer=OVERLAP_LAYER, driver="GPKG")
    else:
        overlaps.to_file(OVERLAP_GPKG, layer=OVERLAP_LAYER, driver="GPKG")

    mixed_type_pairs = 0 if pairs.empty else int((pairs["left_type"] != pairs["right_type"]).sum())

    print(f"Input: {INPUT}")
    print(f"Passenger-relevant segments: {len(rail)}")
    print(f"Overlapping line pairs: {len(pairs)}")
    print(f"Mixed-type overlaps (Conventional vs High speed): {mixed_type_pairs}")
    print(f"Pair table: {PAIR_CSV}")
    print(f"Overlap geometries: {OVERLAP_GPKG}")

    if not pairs.empty:
        print("\nTop 10 overlaps by shared length (m):")
        print(
            pairs.loc[:, ["left_id", "right_id", "left_type", "right_type", "overlap_m"]]
            .head(10)
            .to_string(index=False)
        )


if __name__ == "__main__":
    main()
