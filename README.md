# TransitTwin

## Purpose
TransitTwin is a decision-intelligence platform that represents a public transport network as a live digital twin. It predicts disruptions, simulates interventions, quantifies consequences, ranks alternatives, and allows operator approval to maintain network health and accessibility.

## Architecture Overview
The system follows a Modular Monolith paradigm with strict boundaries to ensure the separation of LIVE STATE and SIMULATION STATE.

Key Top-Level Modules:
- `backend/`: Django/DRF/Channels handling APIs, WebSockets, and orchestration.
- `backend/simulation/`: Passenger flow, disruption propagation engine, and intervention evaluation sandbox.
- `backend/prediction/`: Demand forecasting, crowding forecasting, ETA/delay prediction.
- `backend/optimization/`: Google OR-Tools formulations for constraint filtering and intervention ranking.
- `frontend/`: React/TypeScript/Vite dashboard.
- `data/`: Ingestion pipelines and telemetry generation.

## Local Setup

### Infrastructure Prerequisites
- Docker & Docker Compose
- Python 3.11+
- Node.js 18+
- OSGeo4W/GDAL (Required for PostGIS in Django on Windows)

### Environment Setup
1. Copy the example environment variables:
   ```bash
   cp .env.example .env
   ```
2. Adjust `.env` as needed (do not commit secrets to source control).

### Starting Infrastructure
Run the following to start PostgreSQL (with PostGIS) and Redis:
```bash
docker-compose up -d
```

### Backend Database Setup & Migrations
1. Create and activate a virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: .\venv\Scripts\activate
   ```
2. Install dependencies:
   ```bash
   pip install -r backend/requirements.txt
   ```
3. Run database migrations:
   ```bash
   cd backend
   python manage.py makemigrations
   python manage.py migrate
   ```
4. Seed the deterministic demo network:
   ```bash
   python manage.py seed_demo_network
   ```
5. Validate network constraints:
   ```bash
   python manage.py validate_network
   ```

### Backend Development (Django Channels)
Start the ASGI server using Daphne to support WebSockets and the API (`/api/v1/`):
```bash
cd backend
daphne -b 0.0.0.0 -p 8000 config.asgi:application
```

### Telemetry Simulation
To start moving vehicles along the routes in real-time:
```bash
cd backend
python manage.py run_telemetry_simulator --ticks 100 --delay 1.0
```

### Frontend Development
The frontend fetches from `/api/v1/` to display the MapLibre network map.
1. Install dependencies:
   ```bash
   cd frontend
   npm install
   ```
2. Start the development server:
   ```bash
   npm run dev
   ```

## Testing Commands
**Backend:**
```bash
cd backend
pytest
```

**Frontend:**
```bash
cd frontend
npm run test
```
