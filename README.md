# TransitTwin — Real-Time Transit Digital Twin & Command Center

## Purpose
TransitTwin is a decision-intelligence platform that represents a public transport network as a live digital twin. It predicts disruptions, simulates interventions, quantifies consequences, ranks alternatives, and allows operator approval to maintain network health and accessibility.

## Quick Start

### Prerequisites
- Docker & Docker Compose
- Python 3.11+
- Node.js 18+
- OSGeo4W/GDAL (Required for PostGIS in Django on Windows)

### Environment Setup
1. Copy the example environment variables:
   ```bash
   cp .env.example .env
   ```
2. Adjust `.env` as needed (do not commit secrets to source control). Ensure `TRANSIT_TWIN_MODE=HYBRID` is set for the demo.

### Database
Run the following to start PostgreSQL (with PostGIS) and Redis:
```bash
docker-compose up -d
```

### Backend Setup
1. Create and activate a virtual environment:
   ```bash
   cd backend
   python -m venv venv
   # On Windows:
   .\venv\Scripts\activate
   # On Mac/Linux:
   source venv/bin/activate
   ```
2. Install dependencies and run migrations:
   ```bash
   pip install -r requirements.txt
   python manage.py migrate
   ```
3. Seed the deterministic demo network (Note: Wait 60s and retry if Overpass API returns 406 Rate Limit Error):
   ```bash
   python manage.py seed_demo_network
   ```
4. Start the ASGI Server (Daphne):
   ```bash
   daphne -b 0.0.0.0 -p 8000 config.asgi:application
   ```

### Frontend Setup
1. In a new terminal, install dependencies and run:
   ```bash
   cd frontend
   npm install
   npm run dev
   ```

### Real-Time Pollers & Simulation
Open three separate terminals (with the backend `venv` activated) to start the data feeds:
```bash
# Terminal 1: Real TomTom Traffic
python manage.py poll_tomtom_traffic

# Terminal 2: Real TomTom Incidents
python manage.py poll_tomtom_incidents

# Terminal 3: Simulation Fleet
python manage.py run_telemetry_simulator --ticks 1000 --delay 1.0
```

## Modes
The system strictly partitions real and fake data using `TRANSIT_TWIN_MODE`:
- **SIMULATION**: Fully mocked environment for testing and tuning.
- **HYBRID**: The SIH Demo Mode. Uses real TomTom Traffic and Incidents, but simulates the vehicle fleet (explicitly labeled "SIM").
- **LIVE**: True production mode. Strictly blocks all simulation telemetry and mock fallbacks.

## Demo Sequence
1. Start the Command Center (`http://localhost:5173`) in `HYBRID` mode.
2. Explain the Data Provenance (Real Traffic/Incidents vs Simulated Fleet).
3. Select a real TomTom incident on the map.
4. Click "Simulate Disruption" to show the blast radius.
5. Open the Pre-Action Sandbox.
6. Generate candidate interventions based on a Safety or Delay profile.
7. Review candidates and click "Approve & Dispatch".
8. Explain the Human-in-the-Loop architecture (the AI never acts alone).

## Architecture
TransitTwin is a modular monolith. A Django (Python) backend utilizes PostGIS for geospatial topologies and Redis/Channels for high-frequency WebSocket streaming. The Vite/React frontend consumes these streams, intelligently merging partial state updates into a LiveStateEngine clone without expensive re-renders. A localized Pre-Action Sandbox predicts intervention outcomes securely without mutating live reality.

## Safety Architecture
- **Provenance**: Every data point is tagged with its source (`REAL` / `SIMULATION`).
- **Freshness**: Data visibly ages. Traffic fades after 5 minutes; vehicles are culled after 15 minutes.
- **LIVE-Mode Isolation**: The system aggressively prevents simulation leakage in LIVE mode.
- **Human-in-the-Loop**: The engine can only suggest interventions; operator approval is strictly mandatory before LiveState mutation.

## Known Limitations
- **CRUT Blocker**: CRUT B2B live telemetry integration is structurally prepared but currently offline due to a lack of official credentials and API documentation.
- **Overpass Dependency**: Initializing the demo network depends on the public Overpass API, which heavily rate-limits traffic (406 errors).
- **Single-Machine Cache**: The `LiveStateEngine` uses `FileBasedCache` suitable for a laptop demo. A true distributed deployment requires a dedicated Redis cluster.
