# TransitTwin: Failure Handling Guide

This document outlines how TransitTwin handles runtime failures, network degradation, and external API rate limits, ensuring operators are never misled by stale or erroneous intelligence.

## TomTom API Failures

- **TomTom Timeout / 500 Server Error**: The poller silently swallows the error, logs it, and skips the update. The data in `LiveStateEngine` ages. After 5 minutes, the Command Center HUD shifts to `STALE` (yellow pulse) and the map dims. After 15 minutes, the routing engine stops trusting the traffic data.
- **TomTom 401 (Unauthorized) / 403 (Forbidden)**: Same behavior as above. The frontend degrades gracefully to `OFFLINE` if no updates succeed.
- **TomTom 429 (Rate Limit)**: Specifically handled by exponential backoff (or simple skipping in the demo). Data ages out gracefully on the map.
- **Malformed JSON Response**: Swallowed by the backend JSON parser. Handled equivalently to a timeout.

## Internal Infrastructure Failures

- **Backend API Unavailable**: The frontend initiates a full-screen, unclosable red `SYSTEM OFFLINE` overlay, strictly blocking any operator interaction with a stale UI.
- **WebSocket Disconnect**: The frontend displays a top-banner indicating a connection loss (`RECONNECTING...`). `isProcessing` locks prevent accidental dispatch during downtime. Once reconnected, a bulk REST fetch `/api/v1/twin/state/` guarantees synchronization.
- **Unavailable CRUT Feed**: The `CRUT Telemetry` indicator in the Data Provider HUD remains definitively `OFFLINE`. No simulated data replaces it in `LIVE` mode.

## LIVE Mode Safety Protections

The system actively defends against data corruption when `TRANSIT_TWIN_MODE=LIVE`:
1. `run_telemetry_simulator` crashes explicitly and refuses to run.
2. The `/api/v1/system/demo-reset/` endpoint returns `403 Forbidden` protecting the `LiveStateEngine` cache from accidental clearance.
3. No fake fallback mock data is generated for Traffic or Incidents.

In all failures, the Command Center prioritizes **honesty over aesthetics**. It is better to show an empty, offline map than to hallucinate a false reality to the dispatch operator.
