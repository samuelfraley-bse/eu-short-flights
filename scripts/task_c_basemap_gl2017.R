#!/usr/bin/env Rscript

suppressPackageStartupMessages({
  library(sf)
  library(dplyr)
  library(ggplot2)
})

script_dir <- if (length(.arg <- grep("^--file=", commandArgs(), value = TRUE))) {
  dirname(normalizePath(sub("^--file=", "", .arg[1]), mustWork = FALSE))
} else if (file.exists(file.path("scripts", "paths.R"))) {
  "scripts"
} else {
  "."
}

source(file.path(script_dir, "paths.R"))
rm(.arg, script_dir)

map_crs <- 4326

countries <- st_read(file.path(data_clean, "ne_10m_countries.gpkg"), quiet = TRUE) %>%
  st_make_valid() %>%
  st_transform(map_crs)

countries_mask <- st_union(countries)

conventional_rail <- st_read(
  file.path(data_clean, "ne_10m_conventional_western_eu.gpkg"),
  quiet = TRUE
) %>%
  st_make_valid() %>%
  st_transform(map_crs)

hsr <- st_read(
  file.path(data_raw, "shapefiles", "railways_GL2017_EU.shp"),
  quiet = TRUE
) %>%
  st_make_valid() %>%
  st_transform(map_crs) %>%
  st_intersection(countries_mask) %>%
  mutate(
    rail_type = case_when(
      "TYPE" %in% names(.) & TYPE == "High speed" ~ "High speed rail",
      "TYPE" %in% names(.) ~ as.character(TYPE),
      TRUE ~ "GL2017 rail"
    )
  )

hub_airports <- st_read(file.path(data_clean, "main_airports.gpkg"), quiet = TRUE) %>%
  st_make_valid() %>%
  st_transform(map_crs) %>%
  mutate(label = IATA)

map_xlim <- c(-11.5, 21.5)
map_ylim <- c(35.0, 61.8)

base_map <- ggplot() +
  geom_sf(data = countries, fill = "#F8F8F6", color = "#B9BDC1", linewidth = 0.25) +
  geom_sf(data = conventional_rail, color = "#E9CFC4", linewidth = 0.14, alpha = 0.16) +
  geom_sf(data = hsr, color = "#C84C2A", linewidth = 0.4, alpha = 0.9) +
  geom_sf(
    data = hub_airports,
    shape = 21,
    size = 2.6,
    stroke = 0.35,
    fill = "#7DE3EA",
    color = "#143C54"
  ) +
  coord_sf(
    xlim = map_xlim,
    ylim = map_ylim,
    datum = st_crs(4326),
    label_axes = list(bottom = "E", left = "N"),
    expand = FALSE,
    clip = "on"
  ) +
  labs(
    title = "Countries, GL2017 Rail Network, and Major Airports",
    subtitle = "Basemap using the GL2017 rail shapefile from data/raw/shapefiles/railways_GL2017_EU.shp"
  ) +
  theme_minimal(base_size = 11) +
  theme(
    plot.background = element_rect(fill = "white", color = NA),
    panel.background = element_rect(fill = "#EAF3FB", color = NA),
    panel.grid.major = element_line(color = "#D4DDE8", linewidth = 0.28),
    panel.grid.minor = element_blank(),
    axis.title = element_blank(),
    axis.text = element_text(size = 9.5, color = "#65758B"),
    plot.title = element_text(face = "bold", size = 16, color = "#111111"),
    plot.subtitle = element_text(size = 10.5, color = "#222222", margin = margin(b = 10)),
    plot.margin = margin(10, 12, 10, 12)
  )

png_path <- file.path(outputs, "countries_gl2017_rail_airports_map.png")
pdf_path <- file.path(outputs, "countries_gl2017_rail_airports_map.pdf")

ggsave(png_path, base_map, width = 11, height = 8.2, dpi = 320, bg = "#FBFAF7")
ggsave(pdf_path, base_map, width = 11, height = 8.2, bg = "#FBFAF7")

message("Saved: ", png_path)
message("Saved: ", pdf_path)
