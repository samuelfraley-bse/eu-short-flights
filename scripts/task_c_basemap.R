#!/usr/bin/env Rscript

suppressPackageStartupMessages({
  library(sf)
  library(dplyr)
  library(ggplot2)
})

source(file.path(
  if (length(.arg <- grep("^--file=", commandArgs(), value = TRUE)))
    dirname(normalizePath(sub("^--file=", "", .arg[1]), mustWork = FALSE))
  else "scripts",
  "paths.R"
))
rm(.arg)

map_crs <- 4326

countries <- st_read(file.path(data_clean, "ne_10m_countries.gpkg"), quiet = TRUE) %>%
  st_make_valid() %>%
  st_transform(map_crs)

conventional_rail <- st_read(
  file.path(data_clean, "ne_10m_conventional_western_eu.gpkg"),
  quiet = TRUE
) %>%
  st_make_valid() %>%
  st_transform(map_crs)

hsr <- st_read(file.path(data_clean, "hsr_western_eu.gpkg"), quiet = TRUE) %>%
  st_make_valid() %>%
  st_transform(map_crs) %>%
  mutate(
    speed_tier = factor(
      speed_tier,
      levels = c(
        "HSR (speed untagged)",
        "200–239 km/h",
        "240–269 km/h",
        "270–309 km/h",
        "310+ km/h"
      )
    )
  )

hub_airports <- st_read(file.path(data_clean, "main_airports.gpkg"), quiet = TRUE) %>%
  st_make_valid() %>%
  st_transform(map_crs) %>%
  mutate(label = IATA)

speed_palette <- c(
  "HSR (speed untagged)" = "#64748B",
  "200–239 km/h" = "#E9C46A",
  "240–269 km/h" = "#F4A261",
  "270–309 km/h" = "#E76F51",
  "310+ km/h" = "#B22222"
)

speed_labels <- c(
  "HSR (speed untagged)" = "HSR (speed untagged)",
  "200–239 km/h" = "200-239 km/h",
  "240–269 km/h" = "240-269 km/h",
  "270–309 km/h" = "270-309 km/h",
  "310+ km/h" = "310+ km/h"
)

map_xlim <- c(-11.5, 21.5)
map_ylim <- c(35.0, 61.8)

base_map <- ggplot() +
  geom_sf(data = countries, fill = "#F8F8F6", color = "#B9BDC1", linewidth = 0.25) +
  geom_sf(data = conventional_rail, color = "#E9CFC4", linewidth = 0.14, alpha = 0.18) +
  geom_sf(data = hsr, aes(color = speed_tier), linewidth = 0.52, alpha = 0.95) +
  geom_sf(
    data = hub_airports,
    shape = 21,
    size = 2.6,
    stroke = 0.35,
    fill = "#7DE3EA",
    color = "#143C54"
  ) +
  scale_color_manual(
    values = speed_palette,
    labels = speed_labels,
    drop = FALSE,
    name = "HSR speed tier"
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
    title = "Countries, HSR Network, and Major Airports",
    subtitle = "Base map for the short-haul substitution project; substitutable routes and carbon cost layers come later"
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
    legend.position = "right",
    legend.background = element_rect(fill = scales::alpha("white", 0.92), color = NA),
    legend.title = element_text(face = "bold", size = 9.5),
    legend.text = element_text(size = 8.5),
    plot.margin = margin(10, 12, 10, 12)
  ) +
  guides(color = guide_legend(override.aes = list(linewidth = 1.5, alpha = 1)))

png_path <- file.path(outputs, "countries_hsr_airports_map.png")
pdf_path <- file.path(outputs, "countries_hsr_airports_map.pdf")

ggsave(png_path, base_map, width = 11, height = 8.2, dpi = 320, bg = "#FBFAF7")
ggsave(pdf_path, base_map, width = 11, height = 8.2, bg = "#FBFAF7")

message("Saved: ", png_path)
message("Saved: ", pdf_path)
