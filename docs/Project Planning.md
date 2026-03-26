**Research question:** Which short-haul European flight routes are substitutable by existing high-speed rail, and what policy levers make that substitution welfare-improving (less carbon x time cost)?

**Current Data:**

* GL2017 EU Rail \- *European rail network shapefile (2017), HSR vs conventional segments*  
* OpenFlights \- *airports and routes (airports.txt, routes.txt)*  
* Eurostat avia\_paoa \- *quarterly airport-level passenger counts (not route-level)*

**Current Framework**

* We measure welfare as each airport's access to the rest of Europe, weighted by how many passengers travel to each destination and how costly that journey is.   
* Cost combines travel time and carbon emissions, where carbon is converted to time-equivalent units using a carbon price and a value of time.   
* When we substitute a flight with an HSR journey on a given route, we recompute that access score and the change tells us which airports gain or lose connectivity — and by how much.

**Analysis Steps**

* Build the European HSR network from OSM (replacing GL2017)  
* Build the European airport and flight route network from OpenFlights.  
* Join Eurostat avia\_par\_me route-level passenger data to flight routes.  
* Classify short-haul routes by estimated flight time  
* For each airport, compute actual transit access time to nearest HSR station via HAFAS (local metro/rail included)  
* Identify substitutable routes: short-haul \+ both endpoints have realistic HSR access within acceptable transfer time  
* For each substitutable route, query HAFAS for full door-to-door HSR journey time (airport → local transit → HSR → local transit → airport)  
* Compute carbon-adjusted market access and ΔMA under modal shift counterfactual (Allen & Arkolakis)  
* Sensitivity analysis across carbon prices and airport overhead assumptions  
* Rank airports and countries by number of substitutable outbound routes  
* Isochrone reachability comparison for key hubs

**Data we need to add**

1. **HSR** More current HSR network (right now its 2017\)  
2. **Local metro lines** to calculate true accessibility \- might be hard since so many lines/countries, maybe just OSM rail as proxy? Turbo OSM is a good option to batch export)  
3. **Stations** \- ensure we have HSR as well as local (similar to above)  
4. **Travel times** \- see if we can loop thru HAFAS (via pyhafas package if possible) to calculate rail times between airports \- this might be too much for the scope of the project but worth looking into  
   1. For local: [mobilitydatabase.org](http://mobilitydatabase.org) and OpenTripPlanner might be an option if we can’t do HAFAS

# Claude’s ideas

Here are 4 concrete next steps, roughly in order of payoff:

**1\. Replace uniform HSR speed with actual journey times**

* The model uses dist\_km / 250 km/h for all HSR routes, which ignores topology (the Pyrenees constraint you already noted for BCN), detours, and stops. A real network-based travel time would dramatically change which routes are competitive.  
* Best free source: Eurostat's GISCO railway network or the OSM railways layer via pyrosm/osmnx, which has maxspeed tags per segment  
* Build a weighted graph with networkx over the GL2017 shapefile (or OSM), use shortest-path travel times instead of straight-line estimates  
* This would make your flood-fill analysis much more principled \- currently connected HSR segments are treated as equally accessible regardless of actual route length

**2\. Replace the gravity proxy with route-level O-D data**

* Currently you compute gravity \= src\_pax × dst\_pax as a demand proxy because avia\_paoa only has airport-level totals. Eurostat has a route-level dataset: avia\_par\_me (Monthly air passenger transport by reporting country and routes) \- available via the same SDMX API you already use  
* This gives you actual passengers per city-pair, so your top-50 substitutable routes list becomes grounded in real demand rather than inferred  
* Also enables you to compute actual CO₂ reduction and revenue/welfare effects per route

**3\. Calibrate θ using the BCN-MAD natural experiment**

* You currently run θ ∈ {3, 5, 8} as sensitivity but don't pin down which is empirically correct. The AVE opening in 2008 gives you a clean quasi-experiment:  
* The \~60% air passenger drop you mention implies a specific θ given the change in relative costs  
* Back out the implied elasticity: ln(ΔPassengers) / ln(Δτ) gives you an estimate of θ specific to this corridor  
* You can then anchor your market access results to a calibrated θ rather than an arbitrary range  
* Pre/post AVE passenger data is available from AENA (Spanish airport authority) and Renfe press releases / academic papers (Albalate et al., 2015; de Rus & Nash, 2009\)

**4\. Add a country-level policy laye**r

* Your sensitivity analysis focuses on BCN-MAD as a single route, but the policy space is heterogeneous across Europe:  
* France's short-haul ban (in force since May 2023): routes where rail alternative \< 2.5h are banned — you can flag which of your substitutable routes already fall under this  
* EU ETS aviation inclusion: since 2024, all intra-EU flights are covered; you can plug in current ETS prices (\~€60-70/t in 2024-2025, much lower than your EUR 100/t baseline)  
* Map the overlap: substitutable routes × current policy coverage × ETS-implied carbon cost → which routes are already policy-targeted vs. which still need intervention  
* This turns your model from a purely spatial/economic exercise into a policy audit with direct relevance

