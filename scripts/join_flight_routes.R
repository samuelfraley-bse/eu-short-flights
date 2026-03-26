library(tidyverse)
library(janitor)
library(sf)

source(file.path(
  if (length(.arg <- grep("^--file=", commandArgs(), value = TRUE)))
    dirname(normalizePath(sub("^--file=", "", .arg[1]), mustWork = FALSE))
  else "scripts",
  "paths.R"
))
rm(.arg)

# 1. IDENTIFY TOP 15 FROM PAOA
paoa_path <- file.path(data_raw, "avia_paoa_2019.csv")



t15_list <- read_csv(paoa_path) %>%
  group_by(rep_airp) %>%
  summarize(total = sum(value, na.rm = TRUE)) %>%
  arrange(desc(total)) %>%
  slice_head(n = 15) %>%
  pull(rep_airp)

# 2. LOAD AND SPLIT ROUTE DATA
target_dir <- file.path(data_raw, "avia_par")

# 2. Get a list of all CSV files in that folder
files <- list.files(path = target_dir, pattern = "*.csv", full.names = TRUE)

# 3. Read, filter, and combine
combined_data <- files %>%
  map_df(~ {
    read_csv(.x, show_col_types = FALSE) 
  })

flight_route <- combined_data %>%
  filter(TIME_PERIOD == "2019") %>%
  extract(
    airp_pr, 
    into = c("depart", "arrive"), 
    regex = "^([A-Z]{2}_[A-Z]{4})_([A-Z]{2}_[A-Z]{4})$", 
    remove = FALSE
  ) %>%
  filter(unit == "FLIGHT") %>%
  filter(tra_meas == "CAF_PAS")

flight_pax <- combined_data %>%
  filter(TIME_PERIOD == "2019") %>%
  extract(
    airp_pr, 
    into = c("depart", "arrive"), 
    regex = "^([A-Z]{2}_[A-Z]{4})_([A-Z]{2}_[A-Z]{4})$", 
    remove = FALSE
  ) %>%
  filter(unit == "PAS") %>%
  filter(tra_meas == "PAS_BRD")

flights_routes <- flight_route%>%
  filter(depart %in% t15_list) %>%
  rename("total_flights" = OBS_VALUE) %>%
  select(TIME_PERIOD, airp_pr, depart, arrive, total_flights)

flights_pax <- flight_pax %>%
  filter(depart %in% t15_list) %>%
  rename("total_pax" = OBS_VALUE) %>%
  select(TIME_PERIOD, airp_pr, depart, arrive, total_pax) %>%
  mutate(counter = 1) %>%
  group_by(airp_pr) %>%
  summarize_if(is.numeric, sum)

final_routes <- flights_routes %>%
  left_join(flights_pax, by = c("airp_pr")) %>%
  # Split the 'depart' column into two
  separate(depart, into = c("depart_country", "depart_airport"), sep = "_", remove = FALSE) %>%
  # Split the 'arrive' column into two
  separate(arrive, into = c("arrive_country", "arrive_airport"), sep = "_", remove = FALSE) %>%
  # Filter out US arrivals as requested earlier
  filter(!str_starts(arrive, "US_"))


airports_ref <- st_read(file.path(data_clean, "main_airports.gpkg")) %>%
  st_drop_geometry() %>%
  select(AirportName, ICAO)

# 2. Process the flight data
df_final <- final_routes %>%
  # Create the 4-letter ICAO codes needed for the join (extracting part after "_")
  mutate(
    dep_icao = str_split_i(depart, "_", 2), 
    arr_icao = str_split_i(arrive, "_", 2)
  ) %>%
  # Join for Departure Name
  left_join(airports_ref, by = c("dep_icao" = "ICAO")) %>%
  rename(depart_name = AirportName) %>%
  # Join for Arrival Name
  left_join(airports_ref, by = c("arr_icao" = "ICAO")) %>%
  rename(arrive_name = AirportName) %>%
  # Create the formatted Route Name
  mutate(route_name = paste(depart_name, "-", arrive_name)) %>%
  filter(!is.na(arrive_name)) %>%
  select(TIME_PERIOD, depart_country, depart_airport, arrive_country, arrive_airport, route_name, total_flights, total_pax)


# 1. Prepare reference with names AND spatial data
airports_ref <- st_read(file.path(data_clean, "main_airports.gpkg")) %>%
  st_drop_geometry() %>% # Drop if you only want the Lat/Lon numbers, keep if you want the 'geom' column
  select(AirportName, ICAO, GeoPointLat, GeoPointLong)

# 2. Complete Processing Chain
df_final <- final_routes %>%
  mutate(
    dep_icao = str_split_i(depart, "_", 2), 
    arr_icao = str_split_i(arrive, "_", 2)
  ) %>%
  # Join for Departure Info
  left_join(airports_ref, by = c("dep_icao" = "ICAO")) %>%
  rename(depart_name = AirportName, dep_lat = GeoPointLat, dep_lon = GeoPointLong) %>%
  # Join for Arrival Info
  left_join(airports_ref, by = c("arr_icao" = "ICAO")) %>%
  rename(arrive_name = AirportName, arr_lat = GeoPointLat, arr_lon = GeoPointLong) %>%
  # Create Route Name and Coord Strings
  mutate(
    route_name = paste(depart_name, "-", arrive_name),
    depart_coords = paste0(dep_lat, ", ", dep_lon),
    arrive_coords = paste0(arr_lat, ", ", arr_lon)
  ) %>%
  filter(!is.na(arrive_name)) %>%
  select(TIME_PERIOD, depart_country, depart_airport, arrive_country, arrive_airport, 
         route_name, depart_coords, arrive_coords, total_flights, total_pax)
