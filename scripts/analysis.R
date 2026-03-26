install.packages(("tmap")) # tmap is great for quick interactive maps
library(sf)
library(tidyverse)
library(tmap)

source(file.path(
  if (length(.arg <- grep("^--file=", commandArgs(), value = TRUE)))
    dirname(normalizePath(sub("^--file=", "", .arg[1]), mustWork = FALSE))
  else "scripts",
  "paths.R"
))
rm(.arg)

# Load the base layers
countries <- st_read(file.path(data_clean, "ne_10m_countries.gpkg"))
conv_rail <- st_read(file.path(data_clean, "ne_10m_conventional_western_eu.gpkg"))
hsr_rail  <- st_read(file.path(data_clean, "hsr_western_eu.gpkg"))

# Load the airport layers
main_airports <- st_read(file.path(data_clean, "main_airports.gpkg"))
all_airports  <- st_read(file.path(data_clean, "all_airports.gpkg"))
pax_data      <- st_read(file.path(data_clean, "airports_pax_2019.gpkg")) # This is your 'Size' variable for Market Access!


# Project everything to the European standard
target_crs <- 3035

countries <- st_transform(countries, target_crs)
hsr_rail  <- st_transform(hsr_rail, target_crs)
conv_rail <- st_transform(conv_rail, target_crs)
pax_data  <- st_transform(pax_data, target_crs)
