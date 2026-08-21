# TransitTwin: Known Limitations

The current TransitTwin architecture, as configured for the SIH Demonstration, possesses the following known limitations. None are structurally fatal, but they represent boundaries of the current demo environment.

## 1. CRUT B2B Live Telemetry Blocker
**Status**: BLOCKED
**Impact**: The system currently runs in `HYBRID` mode utilizing simulated vehicle telemetry.
**Reason**: Official B2B API credentials, endpoint documentation, and payload schemas from CRUT (Capital Region Urban Transport) are unavailable. We refuse to scrape or spoof this data in `LIVE` mode.
**Mitigation**: The system relies on the internal `run_telemetry_simulator` which moves vehicles deterministically along actual OSM routes in Bhubaneswar, reacting to real TomTom traffic.

## 2. TomTom Point-Based Flow API Coverage
**Status**: MITIGATED / LIMITATION
**Impact**: 100% instantaneous coverage of the entire road network is impossible without exhausting API rate limits or incurring massive costs.
**Reason**: The TomTom Flow API requires polling specific coordinate pairs.
**Mitigation**: Traffic polling uses a rotating batch system (`BATCH_SIZE=25`) across critical nodes. Therefore, congestion data populates sequentially across the map rather than uniformly in a single instant. The UI naturally fades edges that have not received an update recently.

## 3. Overpass API 406 Rate Limiting
**Status**: EXTERNAL DEPENDENCY LIMITATION
**Impact**: Running `python manage.py import_osm_network` or `seed_demo_network` may occasionally fail with a `406 Not Acceptable` or `429 Too Many Requests`.
**Reason**: The public Overpass API severely throttles high-frequency queries.
**Mitigation**: Run the seed command again after waiting 60 seconds. This only affects initialization, not live operation.

## 4. Single-Machine Architecture (FileBasedCache)
**Status**: DEMO CONFIGURATION LIMITATION
**Impact**: The `LiveStateEngine` relies on Django's `FileBasedCache` or local Memory cache.
**Reason**: Optimal for a single-laptop SIH demonstration without requiring a dedicated cluster.
**Mitigation**: For a true multi-server production deployment, the cache backend MUST be swapped to a distributed Redis/Memcached cluster to ensure state consistency across web worker nodes.
