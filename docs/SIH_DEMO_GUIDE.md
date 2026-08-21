# TransitTwin: SIH Demo Guide

This guide provides the exact sequence of commands and steps to perform the final SIH presentation. Follow these instructions precisely.

## 1. Environment Preparation
Ensure you have Docker, Python 3.11+, and Node.js 18+ installed.

1. Prepare the environment variables (Do not expose your TomTom API key in public):
   ```bash
   cp .env.example .env
   # Ensure TRANSIT_TWIN_MODE=HYBRID is set in .env
   ```

2. Start the database (PostgreSQL/PostGIS & Redis):
   ```bash
   docker-compose up -d
   ```

## 2. Backend Startup & Initialization
Initialize the Django environment and seed the network.

1. Activate virtual environment and run migrations:
   ```bash
   cd backend
   python -m venv venv
   # Windows
   .\venv\Scripts\activate
   # Linux/Mac
   source venv/bin/activate
   pip install -r requirements.txt
   python manage.py migrate
   ```

2. Seed the deterministic Demo Network (Wait 60s if Overpass 406 Error occurs):
   ```bash
   python manage.py seed_demo_network
   ```

3. Start the ASGI Server (Daphne) for WebSockets and REST:
   ```bash
   daphne -b 0.0.0.0 -p 8000 config.asgi:application
   ```

## 3. Start Data Pollers & Simulation
Open three separate terminal windows (with the `venv` activated in the `backend` folder) to start the real-time feeds.

**Terminal 1 (Real TomTom Traffic):**
```bash
python manage.py poll_tomtom_traffic
```

**Terminal 2 (Real TomTom Incidents):**
```bash
python manage.py poll_tomtom_incidents
```

**Terminal 3 (Simulation Fleet for HYBRID mode):**
```bash
python manage.py run_telemetry_simulator --ticks 1000 --delay 1.0
```

## 4. Frontend Startup
In a new terminal window:
```bash
cd frontend
npm install
npm run dev
```

## 5. The Demo Narrative

1. **Open the Command Center**: Navigate to `http://localhost:5173`.
2. **Explain Provenance**: Direct the judges to the Data Provider HUD. Explain that the environment is in `HYBRID` mode. Point out that TomTom Traffic and Incidents are updating in real-time with explicit timestamps, while the Fleet is simulated (explicitly badged "SIM") due to the lack of official CRUT API keys.
3. **Show Live Incident**: Identify a real incident `!` marker provided by TomTom on the map. Click it to view its details (Time, Severity, Source).
4. **Demonstrate Blast Radius**: Click "Simulate Disruption". Show how the causal graph maps the incident to the physical road edges (highlighted in red) and determines indirectly affected stops.
5. **Open Pre-Action Sandbox**: Click "Open Pre-Action Sandbox". Explain that this clones the live state into a safe environment.
6. **Generate Candidates**: Select an objective profile (e.g., Minimum Delay) and click Generate Candidates. Explain that the AI has generated detours or spare vehicle deployments and ranked them.
7. **Approve & Dispatch (Human-in-the-Loop)**: Select the highest-ranked `FEASIBLE` candidate. Click "Approve & Dispatch". Explain that the system NEVER acts autonomously without this explicit operator consent.
8. **Explain Failure Handling (Optional)**: Mention that if the WebSocket drops or an API times out, data visibly ages on the map (fading edges, yellow HUD alerts), preventing the operator from making decisions on stale data.
