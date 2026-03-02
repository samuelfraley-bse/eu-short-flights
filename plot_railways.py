import geopandas as gpd
import matplotlib.pyplot as plt

shp_path = "data/railways_GL2017_EU.shp"

gdf = gpd.read_file(shp_path)

print("CRS:", gdf.crs)
print("Shape:", gdf.shape)
print("Columns:", list(gdf.columns))
print(gdf.head())

fig, ax = plt.subplots(figsize=(12, 10), facecolor="#1a1a2e")
ax.set_facecolor("#1a1a2e")

gdf.plot(ax=ax, color="#e94560", linewidth=0.5, alpha=0.7)

ax.set_title("European Railways (GL2017)", color="white", fontsize=16, pad=15)
ax.set_axis_off()

plt.tight_layout()
plt.savefig("data/railways_GL2017_EU.png", dpi=150, bbox_inches="tight", facecolor="#1a1a2e")
plt.show()
print("Saved to data/railways_GL2017_EU.png")
