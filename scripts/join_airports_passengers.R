library(sf)
library(dplyr)
library(tidyr)

source(file.path(
  if (length(.arg <- grep("^--file=", commandArgs(), value = TRUE)))
    dirname(normalizePath(sub("^--file=", "", .arg[1]), mustWork = FALSE))
  else "scripts",
  "paths.R"
))
rm(.arg)

YEAR <- "2019"

# ── 1. Airport totals (avia_paoa) ─────────────────────────────────────────────
main_airports <- st_read(file.path(data_clean, "main_airports.gpkg"), quiet = TRUE)
passengers    <- read.csv(file.path(data_raw, paste0("avia_paoa_", YEAR, ".csv")))

airports_with_pax <- main_airports %>%
  left_join(
    passengers %>% select(icao_code, value, country_code),
    by = c("ICAO" = "icao_code")
  ) %>%
  rename(passengers = value)

# Verification
match_rate <- sum(!is.na(airports_with_pax$passengers)) / nrow(airports_with_pax)
cat(sprintf("[paoa] Match rate: %.1f%% (%d / %d airports)\n",
    match_rate * 100,
    sum(!is.na(airports_with_pax$passengers)),
    nrow(airports_with_pax)))

unmatched <- filter(airports_with_pax, is.na(passengers))
if (nrow(unmatched) > 0) {
  cat("  Unmatched:", paste(unmatched$ICAO, collapse = ", "), "\n")
}

# Save spatial output
st_write(airports_with_pax, file.path(data_clean, paste0("airports_pax_", YEAR, ".gpkg")),
         delete_dsn = TRUE, quiet = TRUE)
cat(sprintf("[paoa] Saved → data/clean/airports_pax_%s.gpkg\n", YEAR))


# ── 2. Route data (avia_par) ──────────────────────────────────────────────────
routes_raw <- read.csv(file.path(data_raw, paste0("avia_par_routes_", YEAR, ".csv")))

# Parse airp_pr (format: "CC_ICAO_CC_ICAO", e.g. "AT_LOWW_DE_EDDF")
routes <- routes_raw %>%
  separate(airp_pr, into = c("origin_country", "origin_icao", "dest_country", "dest_icao"),
           sep = "_", extra = "drop", fill = "right") %>%
  select(origin_country, origin_icao, dest_country, dest_icao,
         passengers = value, reporting_country, year)

cat(sprintf("[par]  %d routes parsed\n", nrow(routes)))

# Save edge table
write.csv(routes, file.path(data_clean, paste0("routes_", YEAR, ".csv")), row.names = FALSE)
cat(sprintf("[par]  Saved → data/clean/routes_%s.csv\n", YEAR))


# ── 3. Master route table ─────────────────────────────────────────────────────
main_icao <- main_airports %>% st_drop_geometry() %>% pull(ICAO)

# Passenger totals lookup (icao → total passengers)
pax_lookup <- passengers %>% select(icao_code, value) %>% rename(total_pax = value)

all_icao <- st_read(file.path(data_clean, "all_airports.gpkg"), quiet = TRUE) %>%
  st_drop_geometry() %>% pull(ICAO)

master <- routes %>%
  # Only routes departing from one of the 15 main airports
  # and arriving at a European airport
  filter(origin_icao %in% main_icao, dest_icao %in% all_icao) %>%
  # Join start airport total passengers
  left_join(pax_lookup, by = c("origin_icao" = "icao_code")) %>%
  rename(start_pax_total = total_pax) %>%
  # Join end airport total passengers (NA if not a main airport or no Eurostat data)
  left_join(pax_lookup, by = c("dest_icao" = "icao_code")) %>%
  rename(end_pax_total = total_pax) %>%
  # Join start airport name
  left_join(
    main_airports %>% st_drop_geometry() %>% select(ICAO, AirportName),
    by = c("origin_icao" = "ICAO")
  ) %>%
  rename(start_airport = AirportName) %>%
  # Join end airport name from full airport dataset
  left_join(
    st_read(file.path(data_clean, "all_airports.gpkg"), quiet = TRUE) %>%
      st_drop_geometry() %>% select(ICAO, AirportName),
    by = c("dest_icao" = "ICAO")
  ) %>%
  rename(end_airport = AirportName) %>%
  # Final column selection, naming, and derived fields
  mutate(
    route_name    = paste(start_airport, end_airport, sep = " - "),
    start_pax_pct = round(passengers / start_pax_total * 100, 2)
  ) %>%
  select(
    start_airport,
    start_icao       = origin_icao,
    end_airport,
    end_icao         = dest_icao,
    route_name,
    route_passengers = passengers,
    start_pax_total,
    end_pax_total,
    start_pax_pct,
    year
  )

cat(sprintf("[master] %d routes from %d main airports\n",
    nrow(master), n_distinct(master$start_icao)))

write.csv(master, file.path(data_clean, paste0("master_routes_", YEAR, ".csv")), row.names = FALSE)
cat(sprintf("[master] Saved → data/clean/master_routes_%s.csv\n", YEAR))
