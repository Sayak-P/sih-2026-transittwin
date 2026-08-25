import { useEffect, useState, useRef } from 'react';
import Map, { Source, Layer, Marker } from 'react-map-gl/maplibre';
import 'maplibre-gl/dist/maplibre-gl.css';
import './App.css';
import LandingPage from './LandingPage';
import SmartBusNavigator from './SmartBusNavigator';
import PredictionsDashboard from './PredictionsDashboard';
import ReroutingDashboard from './ReroutingDashboard';
import EmergencySOS from './EmergencySOS';

const MAP_STYLE = "https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json";

const getWebSocketUrl = (path: string) => {
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  return `${protocol}//${window.location.host}${path}`;
};

const mapTwinStateToDashboard = (data: any) => {
  const vList = Object.values(data.vehicles || {});
  const sList = Object.values(data.stops || {});

  const activeCount = vList.filter((v: any) => v.status === 'ACTIVE' || v.state === 'ACTIVE').length;
  const delayedCount = vList.filter((v: any) => v.status === 'DELAYED' || v.state === 'DELAYED').length;

  const vehiclePassengers = vList.reduce((acc: number, v: any) => acc + (Number(v.occupancy) || 0), 0) as number;
  const queuePassengers = sList.reduce((acc: number, s: any) => acc + (Number(s.queue_count) || 0), 0) as number;

  return {
    active: activeCount,
    delayed: delayedCount,
    passengers: vehiclePassengers + queuePassengers,
    avgWait: "—",
    maxCrowding: 0.0,
  };
};

function App() {
  const [stops, setStops] = useState<any[]>([]);
  const stopsRef = useRef<any[]>([]);
  const [edges, setEdges] = useState<any[]>([]);
  const [activeDisruptions, setActiveDisruptions] = useState<any[]>([]);
  const [vehicles, setVehicles] = useState<Record<string, any>>({});
  const [version, setVersion] = useState<number>(0);
  const [twinStatus, setTwinStatus] = useState<any>(null);

  // Navigation Page: 'LANDING', 'NAVIGATOR', 'COMMAND_CENTER', 'PREDICTIONS', or 'REROUTING'
  const [currentPage, setCurrentPage] = useState<'LANDING' | 'NAVIGATOR' | 'COMMAND_CENTER' | 'PREDICTIONS' | 'REROUTING'>('LANDING');

  // System Health
  const [health, setHealth] = useState<any>({ backend: 'OFFLINE', database: 'OFFLINE' });
  const [connectionError, setConnectionError] = useState<string | null>(null);
  const [wsStatus, setWsStatus] = useState<'CONNECTED' | 'RECONNECTING' | 'DISCONNECTED'>('DISCONNECTED');

  // KPI Metrics
  const [kpi, setKpi] = useState({
    active: 0,
    delayed: 0,
    passengers: 0,
    avgWait: "—" as string | number,
    maxCrowding: 0.0,
  });

  // Early Warnings & Selections
  const [warnings, setWarnings] = useState<any[]>([]);
  const [selectedStop, setSelectedStop] = useState<any>(null);
  const [selectedEdge, setSelectedEdge] = useState<any>(null);
  const [selectedVehicle, setSelectedVehicle] = useState<any>(null);
  const [disruptionType, setDisruptionType] = useState<string>('ROAD_BLOCK');
  const [disruptionDuration, setDisruptionDuration] = useState<number>(20);

  // Workflow State: NORMAL, WARNING, DISRUPTION, SANDBOX, APPROVE, VERIFIED
  const [workflowState, setWorkflowState] = useState<'NORMAL' | 'WARNING' | 'DISRUPTION' | 'SANDBOX' | 'APPROVE' | 'VERIFIED'>('NORMAL');

  const [blastRadius, setBlastRadius] = useState<any>(null);
  const [currentDisruptionId, setCurrentDisruptionId] = useState<number | null>(null);
  const [sandboxResult, setSandboxResult] = useState<any>(null);
  const [profile, setProfile] = useState('BALANCED');
  const [selectedCandidate, setSelectedCandidate] = useState<any>(null);

  const [isProcessing, setIsProcessing] = useState(false);

  const ws = useRef<WebSocket | null>(null);

  const fetchWarnings = () => {
    fetch('/api/v1/predictions/early-warnings/')
      .then(res => res.json())
      .then(data => {
        const currentWarnings = data.warnings || [];
        setWarnings(currentWarnings);

        // Auto-update workflow state if in Monitoring phase
        setWorkflowState(prev => {
          if (prev === 'NORMAL' || prev === 'WARNING') {
            if (currentWarnings.some((w: any) => w.severity === 'CRITICAL')) return 'WARNING';
            if (currentWarnings.length === 0) return 'NORMAL';
          }
          return prev;
        });
      })
      .catch(err => console.error("Warnings fetch failed:", err));
  };

  const fetchData = () => {
    fetch('/api/v1/stops/')
      .then(res => res.json())
      .then(data => {
        setStops(data);
        stopsRef.current = data;
      })
      .catch(err => console.error("Failed to fetch stops:", err));

    fetch('/api/v1/edges/')
      .then(res => res.json())
      .then(setEdges)
      .catch(err => console.error("Failed to fetch edges:", err));

    fetch('/api/v1/disruptions/')
      .then(res => res.json())
      .then(setActiveDisruptions)
      .catch(err => console.error("Failed to fetch disruptions:", err));

    fetch('/api/v1/twin/state/')
      .then(res => {
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        return res.json();
      })
      .then(data => {
        setConnectionError(null);
        if (data.vehicles) setVehicles(prev => ({ ...data.vehicles, ...prev }));
        if (data.version) setVersion(data.version);
        setKpi(mapTwinStateToDashboard(data));
      })
      .catch(err => {
        console.error("Twin state fetch failed:", err);
        setConnectionError("Backend API Unreachable");
      });
  };

  const fetchHealth = () => {
    fetch('/api/v1/system/health/')
      .then(res => {
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        return res.json();
      })
      .then(data => {
        setHealth(data);
        setConnectionError(null);
      })
      .catch(err => {
        console.error("Health check failed:", err);
        setHealth({ backend: 'OFFLINE', database: 'OFFLINE' });
        setConnectionError("Backend API Unreachable");
      });

    fetch('/api/v1/twin/status/')
      .then(res => res.json())
      .then(setTwinStatus)
      .catch(err => console.error("Failed to fetch twin status:", err));
  };

  useEffect(() => {
    fetchData();
    fetchHealth();
    fetchWarnings();
    const interval = setInterval(fetchHealth, 10000);
    const dataInterval = setInterval(fetchData, 1000);
    const warningInterval = setInterval(fetchWarnings, 10000);

    let reconnectTimeout: ReturnType<typeof setTimeout>;
    let retryDelay = 1000;

    const connectWs = () => {
      if (ws.current && (ws.current.readyState === WebSocket.OPEN || ws.current.readyState === WebSocket.CONNECTING)) {
        return;
      }
      ws.current = new WebSocket(getWebSocketUrl('/ws/twin/'));

      ws.current.onopen = () => {
        console.log("WebSocket connected");
        setWsStatus('CONNECTED');
        retryDelay = 1000;
      };

      ws.current.onerror = (err) => console.error("WebSocket error:", err);

      ws.current.onclose = () => {
        console.log(`WebSocket disconnected. Reconnecting in ${retryDelay}ms...`);
        setWsStatus('RECONNECTING');
        clearTimeout(reconnectTimeout);
        reconnectTimeout = setTimeout(connectWs, retryDelay);
        retryDelay = Math.min(retryDelay * 2, 10000);
      };

      ws.current.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          if (data.event === 'vehicle.updated') {
            setVehicles(prev => ({ ...prev, [data.vehicle_id]: data }));
            setVersion(data.state_version);
            // Recompute KPI locally instantly on vehicle update
            setVehicles(currentVehicles => {
              setKpi(mapTwinStateToDashboard({ vehicles: currentVehicles, stops: stopsRef.current }));
              return currentVehicles;
            });
          } else if (data.event === 'INTERVENTION_APPLIED') {
            setWorkflowState('VERIFIED');
          } else if (data.event === 'traffic_updated') {
            fetch('/api/v1/edges/').then(r => r.json()).then(setEdges);
            fetch('/api/v1/twin/status/').then(r => r.json()).then(setTwinStatus);
          } else if (data.event === 'incident_created') {
            fetch('/api/v1/disruptions/').then(r => r.json()).then(setActiveDisruptions);
          }
        } catch (e) {
          console.error("Failed to parse WebSocket message:", e);
        }
      };
    };

    connectWs();

    return () => {
      if (ws.current) {
        ws.current.onclose = null;
        ws.current.close();
      }
      clearTimeout(reconnectTimeout);
      clearInterval(interval);
      clearInterval(dataInterval);
      clearInterval(warningInterval);
    };
  }, []); // Removed dependency on stops; KPI utilizes stopsRef inside WebSocket closure.

  const triggerDemoReset = () => {
    if (!window.confirm("WARNING: This will reset the entire demo state. Continue?")) return;
    setIsProcessing(true);
    fetch('/api/v1/system/demo-reset/', { method: 'POST' })
      .then(res => res.json())
      .then(() => {
        setWorkflowState('NORMAL');
        setBlastRadius(null);
        setCurrentDisruptionId(null);
        setSandboxResult(null);
        setSelectedCandidate(null);
        setSelectedStop(null);
        setSelectedEdge(null);
        setSelectedVehicle(null);
        setWarnings([]);
        fetchData();
        fetchWarnings();
      })
      .catch(err => {
        console.error("Reset failed:", err);
        alert("Reset failed: " + err.message);
      })
      .finally(() => setIsProcessing(false));
  };

  const triggerDisruption = () => {
    let entity_id = "";
    if (selectedEdge && ['ROAD_BLOCK', 'WEATHER_HAZARD'].includes(disruptionType)) {
      entity_id = selectedEdge.id.toString();
    } else if (selectedStop && disruptionType === 'CROWD_SURGE') {
      entity_id = selectedStop.id.toString();
    } else if (selectedVehicle && disruptionType === 'VEHICLE_BREAKDOWN') {
      entity_id = selectedVehicle.vehicle_id.toString();
    } else {
      alert("Invalid disruption type for the selected entity.");
      return;
    }

    setIsProcessing(true);
    fetch('/api/v1/disruptions/', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        type: disruptionType,
        entity_id,
        severity: 4,
        duration_minutes: disruptionDuration,
        description: `Operator Initiated ${disruptionType.replace(/_/g, ' ')}`
      })
    })
      .then(res => {
        if (!res.ok) throw new Error("Failed to create disruption");
        return res.json();
      })
      .then(data => {
        setCurrentDisruptionId(data.id);
        return fetch(`/api/v1/disruptions/${data.id}/simulate/`, { method: 'POST' });
      })
      .then(res => {
        if (!res.ok) throw new Error("Simulation failed");
        return res.json();
      })
      .then(data => {
        setBlastRadius(data.blast_radius);
        setWorkflowState('DISRUPTION');
      })
      .catch(err => {
        console.error(err);
        alert(err.message);
      })
      .finally(() => setIsProcessing(false));
  };

  const runSandbox = () => {
    if (!currentDisruptionId) return;
    setIsProcessing(true);
    fetch('/api/v1/sandbox/generate/', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ disruption_id: currentDisruptionId, objective_profile: profile, horizon_minutes: 30 })
    })
      .then(res => {
        if (!res.ok) throw new Error("Sandbox generation failed");
        return res.json();
      })
      .then(data => {
        setSandboxResult(data);
        const feasibleCandidates = data.candidates?.filter((c: any) => c.feasibility_status === 'FEASIBLE') || [];
        if (feasibleCandidates.length > 0) {
          setSelectedCandidate(feasibleCandidates[0]);
        } else {
          setSelectedCandidate(null);
        }
        setWorkflowState('SANDBOX');
      })
      .catch(err => {
        console.error(err);
        alert(err.message);
      })
      .finally(() => setIsProcessing(false));
  };

  const approveIntervention = () => {
    if (!selectedCandidate) return;

    const age = (new Date().getTime() - new Date(sandboxResult.generated_at).getTime()) / 1000;
    if (age > 300) {
      alert("This simulation is stale because the live network changed. Recalculate before dispatch.");
      setSandboxResult(null);
      return;
    }

    if (!window.confirm(`Approve and dispatch ${selectedCandidate.type.replace(/_/g, ' ')}?`)) return;

    setIsProcessing(true);
    fetch(`/api/v1/sandbox/${selectedCandidate.id}/approve/`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ scenario_id: sandboxResult.scenario_id })
    })
      .then(res => {
        if (!res.ok) throw new Error("Approval failed");
        return res.json();
      })
      .then(data => {
        if (data.error) alert(data.error);
      })
      .catch(err => {
        console.error(err);
        alert(err.message);
      })
      .finally(() => setIsProcessing(false));
  };

  const edgesGeoJSON = {
    type: 'FeatureCollection',
    features: edges.map(edge => {
      let color = '#94a3b8'; // Default slate
      let width = 2;

      // Calculate traffic congestion color
      if (edge.free_flow_speed > 0 && edge.current_traffic_speed >= 0) {
        const ratio = edge.current_traffic_speed / edge.free_flow_speed;
        if (ratio < 0.3) {
          color = '#ef4444'; // Red (Severe)
          width = 3;
        } else if (ratio < 0.7) {
          color = '#eab308'; // Yellow (Moderate)
          width = 3;
        } else {
          color = '#22c55e'; // Green (Free flow)
        }
      }

      // Dim estimated, simulated, or stale TOMTOM data
      const isStale = edge.last_updated_at && (new Date().getTime() - new Date(edge.last_updated_at).getTime() > 300000);
      if (edge.data_source === 'ESTIMATED' || edge.data_source === 'SIMULATION' || (edge.data_source === 'TOMTOM' && isStale)) {
        if (color === '#ef4444') color = '#fca5a5';
        else if (color === '#eab308') color = '#fde047';
        else if (color === '#22c55e') color = '#86efac';
      }

      if (blastRadius && blastRadius.directly_affected_edges.includes(edge.id.toString())) {
        color = '#ef4444'; width = 6;
      } else if (selectedEdge && edge.id === selectedEdge.id) {
        color = '#3b82f6'; width = 5; // Selected edge highlight
      }
      return { type: 'Feature', geometry: { type: 'LineString', coordinates: edge.geometry }, properties: { id: edge.id, color, width } };
    })
  };

  if (currentPage === 'LANDING') {
    return (
      <LandingPage
        onEnterNavigator={() => setCurrentPage('NAVIGATOR')}
        onEnterCommandCenter={() => setCurrentPage('COMMAND_CENTER')}
        onEnterPredictions={() => setCurrentPage('PREDICTIONS')}
        onEnterRerouting={() => setCurrentPage('REROUTING')}
      />
    );
  }

  if (currentPage === 'PREDICTIONS') {
    return (
      <PredictionsDashboard
        onNavigate={(page) => setCurrentPage(page)}
      />
    );
  }

  if (currentPage === 'REROUTING') {
    return (
      <ReroutingDashboard
        onNavigate={(page) => setCurrentPage(page)}
      />
    );
  }

  if (currentPage === 'NAVIGATOR') {
    return (
      <SmartBusNavigator
        onEnterCommandCenter={() => setCurrentPage('COMMAND_CENTER')}
        onEnterLanding={() => setCurrentPage('LANDING')}
        onEnterPredictions={() => setCurrentPage('PREDICTIONS')}
        onEnterRerouting={() => setCurrentPage('REROUTING')}
      />
    );
  }

  return (
    <div className="w-screen h-screen flex flex-col font-sans bg-zinc-950 overflow-hidden text-zinc-100">
      {connectionError && (
        <div className="bg-red-600 text-white text-xs font-bold p-1 text-center">
          ⚠ CONNECTION ERROR: {connectionError}
        </div>
      )}
      {wsStatus === 'RECONNECTING' && (
        <div className="bg-orange-500 text-white text-xs font-bold p-1 text-center">
          ⚠ Live connection reconnecting...
        </div>
      )}
      <header className="absolute top-0 left-0 right-0 bg-zinc-950/80 backdrop-blur-md text-white p-3 flex justify-between items-center z-20 border-b border-zinc-800 shadow-lg">
        <div className="flex items-center gap-4">
          <button
            onClick={() => setCurrentPage('LANDING')}
            className="flex items-center gap-1 bg-zinc-800 hover:bg-zinc-700 text-zinc-300 px-2.5 py-1.5 rounded-lg text-xs font-bold border border-zinc-700 transition-all cursor-pointer"
            title="Return to Home Landing"
          >
            <span>🏠</span>
            <span>Home</span>
          </button>
          <button
            onClick={() => setCurrentPage('NAVIGATOR')}
            className="flex items-center gap-1.5 bg-gradient-to-r from-cyan-600 to-blue-600 hover:from-cyan-500 hover:to-blue-500 text-white px-3 py-1.5 rounded-lg text-xs font-bold shadow-md shadow-cyan-600/30 border border-cyan-400/40 transition-all cursor-pointer"
            title="Return to Smart Bus Hurdle-Free Navigator"
          >
            <span>←</span>
            <span>Bus Navigator</span>
          </button>
          <button
            onClick={() => setCurrentPage('PREDICTIONS')}
            className="flex items-center gap-1.5 bg-primary-container hover:bg-primary-fixed text-on-primary-container px-3 py-1.5 rounded-lg text-xs font-bold shadow-md shadow-blue-500/20 border border-secondary transition-all cursor-pointer"
            title="Open Predictions Dashboard"
          >
            <span>📊</span>
            <span>Predictions</span>
          </button>
          <button
            onClick={() => setCurrentPage('REROUTING')}
            className="flex items-center gap-1.5 bg-emerald-950/80 hover:bg-emerald-900/80 text-emerald-400 px-3 py-1.5 rounded-lg text-xs font-bold shadow-md shadow-emerald-500/20 border border-emerald-500/40 transition-all cursor-pointer"
            title="Open Rerouting Sandbox"
          >
            <span>🔀</span>
            <span>Rerouting Sandbox</span>
          </button>
          <h1 className="text-xl font-bold tracking-wider font-sans text-zinc-100">TRANSIT TWIN COMMAND CENTER</h1>
          {twinStatus && (
            <div className={`px-3 py-1 rounded text-xs font-bold tracking-wider border flex items-center gap-2 ${twinStatus.mode === 'LIVE' ? 'bg-emerald-900/30 text-emerald-400 border-emerald-800' :
              twinStatus.mode === 'HYBRID' ? 'bg-yellow-900/30 text-yellow-400 border-yellow-800' :
                'bg-cyan-900/30 text-cyan-400 border-cyan-800'
              }`}>
              <span className={`w-2 h-2 rounded-full shadow-lg ${twinStatus.mode === 'LIVE' ? 'bg-emerald-400 animate-pulse shadow-emerald-400/50' : twinStatus.mode === 'HYBRID' ? 'bg-yellow-400 shadow-yellow-400/50' : 'bg-cyan-400 shadow-cyan-400/50'}`}></span>
              {twinStatus.mode === 'LIVE' ? 'LIVE (REAL DATA ONLY)' :
                twinStatus.mode === 'HYBRID' ? 'HYBRID (REAL TRAFFIC + SIM FLEET)' :
                  'SIMULATION (FULL SIMULATION)'}
            </div>
          )}
        </div>
        <div className="flex gap-4 items-center text-xs font-bold">
          <div className="flex gap-2 font-mono">
            <span className={`px-2 py-1 rounded border ${health.backend === 'ONLINE' ? 'bg-emerald-900/30 text-emerald-400 border-emerald-800' : 'bg-rose-900/30 text-rose-400 border-rose-800'}`}>Backend: {health.backend}</span>
            <span className={`px-2 py-1 rounded border ${health.database === 'ONLINE' ? 'bg-emerald-900/30 text-emerald-400 border-emerald-800' : 'bg-rose-900/30 text-rose-400 border-rose-800'}`}>DB: {health.database}</span>
          </div>
          <button onClick={triggerDemoReset} disabled={isProcessing} className="bg-zinc-800 hover:bg-zinc-700 text-zinc-300 px-3 py-1 rounded border border-zinc-700 transition-colors">
            RESET DEMO
          </button>
        </div>
      </header>

      {/* Main Container */}
      <div className="flex-1 relative w-full h-full">
        {/* Full Bleed Map */}
        <div className="absolute inset-0 z-0">
          <Map
            initialViewState={{ longitude: 85.83, latitude: 20.29, zoom: 13 }}
            mapStyle={MAP_STYLE}
            style={{ width: '100%', height: '100%' }}
            interactiveLayerIds={['edges-layer']}
            onClick={(e) => {
              if (e.features && e.features.length > 0) {
                const edgeId = e.features[0].properties?.id;
                const edge = edges.find(ed => ed.id === edgeId);
                if (edge) {
                  setSelectedEdge(edge);
                  setSelectedStop(null);
                  setSelectedVehicle(null);
                  setDisruptionType('ROAD_BLOCK');
                }
              } else {
                setSelectedEdge(null);
              }
            }}
          >
            {edges.length > 0 && (
              <Source id="edges" type="geojson" data={edgesGeoJSON as any}>
                <Layer id="edges-layer" type="line" paint={{ 'line-color': ['get', 'color'], 'line-width': ['get', 'width'] }} />
              </Source>
            )}

            {selectedCandidate?.route && selectedCandidate.route.length > 0 && (
              <Source id="reroute" type="geojson" data={{
                type: 'Feature',
                properties: {},
                geometry: { type: 'LineString', coordinates: selectedCandidate.route }
              } as any}>
                <Layer id="reroute-layer" type="line" paint={{
                  'line-color': '#f97316',
                  'line-width': 6,
                  'line-dasharray': [2, 1]
                }} />
              </Source>
            )}

            {activeDisruptions.filter(d => d.source === 'EXTERNAL').map(disruption => {
              const edge = edges.find(e => e.id.toString() === disruption.affected_entity_id);
              if (!edge || !edge.geometry || edge.geometry.length === 0) return null;
              // Just place the marker at the start node of the edge for simplicity
              const [lon, lat] = edge.geometry[0];
              const ageMs = disruption.created_at ? (new Date().getTime() - new Date(disruption.created_at).getTime()) : 0;
              const isStale = ageMs > 3600000;
              return (
                <Marker key={disruption.id} longitude={lon} latitude={lat} onClick={(e) => {
                  e.originalEvent.stopPropagation();
                  setSelectedEdge(edge);
                  setSelectedStop(null);
                  setSelectedVehicle(null);
                  setDisruptionType(disruption.type || 'ROAD_BLOCK');
                }}>
                  <div className={`flex items-center justify-center w-6 h-6 rounded-full border-2 border-zinc-900 cursor-pointer shadow-lg ${isStale ? 'bg-zinc-600' : 'bg-rose-500 shadow-[0_0_12px_rgba(225,29,72,0.8)] animate-pulse'}`} title={`Incident: ${disruption.description} | Source: ${disruption.source}`}>
                    <span className="text-white text-xs font-black">!</span>
                  </div>
                </Marker>
              );
            })}

            {stops.map(stop => {
              let bgColor = 'bg-slate-400';
              if (blastRadius) {
                if (blastRadius.directly_affected_stops.includes(`STOP-${stop.id}`) || blastRadius.directly_affected_stops.includes(stop.id)) bgColor = 'bg-red-500 w-4 h-4';
                else if (blastRadius.indirectly_affected_stops.includes(`STOP-${stop.id}`) || blastRadius.indirectly_affected_stops.includes(stop.id)) bgColor = 'bg-orange-500 w-3 h-3';
              } else if (selectedStop && selectedStop.id === stop.id) {
                bgColor = 'bg-blue-500 w-4 h-4 border-blue-200 border-2 shadow-lg';
              } else if (warnings.some(w => w.stop_id === stop.id)) {
                const warn = warnings.find(w => w.stop_id === stop.id);
                bgColor = warn.severity === 'CRITICAL' ? 'bg-red-500 w-4 h-4 animate-pulse' : 'bg-orange-500 w-3 h-3';
              }
              return (
                <Marker key={stop.id} longitude={stop.lon} latitude={stop.lat} onClick={(e) => {
                  e.originalEvent.stopPropagation();
                  setSelectedStop(stop);
                  setSelectedEdge(null);
                  setSelectedVehicle(null);
                  setDisruptionType('CROWD_SURGE');
                }}>
                  <div className={`rounded-full border border-white cursor-pointer transition-all ${bgColor}`} title={stop.name} style={{ width: bgColor.includes('w-') ? undefined : '8px', height: bgColor.includes('h-') ? undefined : '8px' }} />
                </Marker>
              );
            })}
            {Object.values(vehicles).map(vehicle => {
              const isSim = vehicle.data_source === 'SIMULATION';
              const ageMs = vehicle.last_updated_at ? (new Date().getTime() - new Date(vehicle.last_updated_at).getTime()) : 0;
              const isStale = ageMs > 60000;
              const isOffline = ageMs > 900000; // 15 minutes

              if (isOffline) return null; // Cull offline vehicles

              const bgClass = isStale ? 'bg-zinc-500 shadow-none' : (isSim ? 'bg-cyan-950 border-dashed border-cyan-500 text-cyan-200' : 'bg-cyan-500 shadow-[0_0_10px_rgba(6,182,212,0.8)] text-zinc-900');
              const badgeText = isSim ? 'SIM' : 'REAL';

              return (
                <Marker key={vehicle.vehicle_id} longitude={vehicle.lon} latitude={vehicle.lat} onClick={(e) => {
                  e.originalEvent.stopPropagation();
                  setSelectedVehicle(vehicle);
                  setSelectedStop(null);
                  setSelectedEdge(null);
                  setDisruptionType('VEHICLE_BREAKDOWN');
                }}>
                  <div className={`w-7 h-4 rounded-full border-2 border-zinc-900 flex items-center justify-center text-[7px] font-bold cursor-pointer transition-colors ${bgClass} ${selectedVehicle?.vehicle_id === vehicle.vehicle_id ? 'ring-2 ring-cyan-200 ring-offset-2 ring-offset-zinc-900' : ''}`}>{badgeText}</div>
                </Marker>
              );
            })}
          </Map>

          {Object.keys(vehicles).length === 0 && !connectionError && (
            <div className="absolute top-1/2 left-1/2 transform -translate-x-1/2 -translate-y-1/2 bg-zinc-900/90 text-zinc-300 px-6 py-4 rounded-lg shadow-2xl text-center border border-zinc-700 z-10 backdrop-blur-sm">
              <div className="font-bold mb-3 font-sans">No live vehicles loaded.</div>
              <button onClick={triggerDemoReset} disabled={isProcessing} className="bg-cyan-600 hover:bg-cyan-500 text-white px-4 py-2 rounded font-bold text-sm transition-colors shadow-[0_0_15px_rgba(8,145,178,0.5)]">
                INITIALIZE DEMO
              </button>
            </div>
          )}

          {health.backend === 'OFFLINE' && (
            <div className="absolute inset-0 z-20 flex items-center justify-center bg-zinc-950/80 backdrop-blur-sm">
              <div className="bg-rose-950/90 border border-rose-900 text-white px-8 py-6 rounded-xl shadow-2xl text-center max-w-md">
                <h2 className="text-xl font-bold mb-2">SYSTEM OFFLINE</h2>
                <p className="text-sm text-rose-200 mb-4">Command Center cannot establish a connection to the primary API gateway. Please ensure backend services are running.</p>
                <div className="w-8 h-8 rounded-full border-4 border-rose-500 border-t-transparent animate-spin mx-auto"></div>
              </div>
            </div>
          )}
        </div>

        {/* Telemetry HUD (Left) */}
        <div className="absolute top-20 left-4 z-10 flex flex-col gap-3">
          <div className="bg-zinc-950/80 backdrop-blur-md border border-zinc-800 p-4 rounded-xl shadow-2xl w-48 font-mono">
            <div className="text-xs text-zinc-500 mb-1 uppercase tracking-wider">Active Buses</div>
            <div className="text-2xl text-cyan-400 font-bold">{kpi.active}</div>
          </div>
          <div className="bg-zinc-950/80 backdrop-blur-md border border-zinc-800 p-4 rounded-xl shadow-2xl w-48 font-mono">
            <div className="text-xs text-zinc-500 mb-1 uppercase tracking-wider">Passengers</div>
            <div className="text-2xl text-zinc-100 font-bold">{kpi.passengers}</div>
          </div>
          <div className="bg-zinc-950/80 backdrop-blur-md border border-zinc-800 p-4 rounded-xl shadow-2xl w-48 font-mono">
            <div className="text-xs text-zinc-500 mb-1 uppercase tracking-wider">Delayed</div>
            <div className="text-2xl text-rose-400 font-bold">{workflowState === 'DISRUPTION' || workflowState === 'SANDBOX' ? 2 : kpi.delayed}</div>
          </div>
          <div className="bg-zinc-950/80 backdrop-blur-md border border-zinc-800 p-4 rounded-xl shadow-2xl w-48 font-mono">
            <div className="text-xs text-zinc-500 mb-1 uppercase tracking-wider">Crit. Warnings</div>
            <div className={`text-2xl font-bold ${warnings.length > 0 ? 'text-amber-400' : 'text-zinc-100'}`}>{warnings.length}</div>
          </div>
        </div>

        {/* Command Center Sidebar (Right) */}
        <aside className="absolute top-20 right-4 bottom-4 w-[420px] bg-zinc-950/90 backdrop-blur-xl flex flex-col shadow-2xl z-10 border border-zinc-800 rounded-xl overflow-hidden">
          <div className="bg-zinc-900/50 p-4 border-b border-zinc-800 shrink-0">
            <h2 className="font-bold text-zinc-300 tracking-widest text-[10px] font-mono uppercase mb-1 flex items-center gap-2">
              <span className="w-1.5 h-1.5 rounded-full bg-cyan-500 shadow-[0_0_8px_rgba(6,182,212,0.8)]"></span>
              SYSTEM ONLINE
            </h2>
            <h1 className="font-black text-zinc-100 tracking-wide text-lg font-sans uppercase">TRANSIT COMMAND CENTER</h1>

            <div className="flex text-[10px] font-bold mt-4 gap-4 text-zinc-500 uppercase tracking-widest font-mono">
              <div className={`pb-1 transition-colors ${workflowState === 'NORMAL' || workflowState === 'WARNING' ? 'border-b-2 border-cyan-500 text-cyan-400' : 'border-transparent'}`}>MONITORING</div>
              <div className={`pb-1 transition-colors ${workflowState === 'DISRUPTION' ? 'border-b-2 border-rose-500 text-rose-400' : 'border-transparent'}`}>IMPACT ANALYSIS</div>
              <div className={`pb-1 transition-colors ${workflowState === 'SANDBOX' || workflowState === 'APPROVE' ? 'border-b-2 border-indigo-500 text-indigo-400' : 'border-transparent'}`}>PRE-ACTION</div>
            </div>
          </div>

          <div className="flex-1 overflow-y-auto p-4 space-y-4">
            {(workflowState === 'NORMAL' || workflowState === 'WARNING') && (
              <div className="space-y-4">
                {/* System Status */}
                <div className="bg-zinc-900/80 p-3 rounded border border-zinc-800 font-mono text-xs space-y-2">
                  <div className="text-zinc-500 uppercase tracking-widest border-b border-zinc-800 pb-1 mb-2">SYSTEM STATUS</div>
                  <div className="flex items-center gap-2 text-emerald-400"><span className="text-emerald-500">●</span> NETWORK OPERATIONAL</div>
                  <div className="flex items-center gap-2 text-emerald-400"><span className="text-emerald-500">●</span> TELEMETRY STREAM ACTIVE</div>
                  <div className="flex items-center gap-2 text-emerald-400"><span className="text-emerald-500">●</span> PREDICTION ENGINE ACTIVE</div>
                  <div className="flex items-center gap-2 text-emerald-400"><span className="text-emerald-500">●</span> SIMULATION ENGINE READY</div>

                  {twinStatus && twinStatus.providers && (
                    <div className="pt-2 mt-2 border-t border-zinc-800 space-y-1">
                      <div className="text-zinc-500 text-[10px] mb-2 uppercase tracking-widest">DATA PROVIDERS</div>

                      <div className="flex justify-between items-center text-[10px] uppercase font-mono">
                        <span className="text-zinc-400">TomTom Traffic</span>
                        <div className="flex items-center gap-2">
                          <span className="text-[8px] text-zinc-500">{twinStatus.providers.tomtom.last_update ? new Date(twinStatus.providers.tomtom.last_update).toLocaleTimeString() : ''}</span>
                          <span className={`font-bold ${twinStatus.providers.tomtom.status === 'ONLINE' ? 'text-emerald-400' : twinStatus.providers.tomtom.status === 'STALE' ? 'text-amber-400 animate-pulse' : 'text-zinc-500'}`}>{twinStatus.providers.tomtom.status}</span>
                        </div>
                      </div>

                      <div className="flex justify-between items-center text-[10px] uppercase font-mono">
                        <span className="text-zinc-400">TomTom Incidents</span>
                        <div className="flex items-center gap-2">
                          <span className="text-[8px] text-zinc-500">{twinStatus.providers.tomtom.last_update ? new Date(twinStatus.providers.tomtom.last_update).toLocaleTimeString() : ''}</span>
                          <span className={`font-bold ${twinStatus.providers.tomtom.status === 'ONLINE' ? 'text-emerald-400' : twinStatus.providers.tomtom.status === 'STALE' ? 'text-amber-400 animate-pulse' : 'text-zinc-500'}`}>{twinStatus.providers.tomtom.status}</span>
                        </div>
                      </div>

                      <div className="flex justify-between items-center text-[10px] uppercase font-mono">
                        <span className="text-zinc-400">CRUT Telemetry</span>
                        <div className="flex items-center gap-2">
                          <span className="text-[8px] text-zinc-500">{twinStatus.providers.crut.last_update ? new Date(twinStatus.providers.crut.last_update).toLocaleTimeString() : ''}</span>
                          <span className={`font-bold ${twinStatus.providers.crut.status === 'ONLINE' ? 'text-emerald-400' : twinStatus.providers.crut.status === 'STALE' ? 'text-amber-400 animate-pulse' : 'text-zinc-500'}`}>{twinStatus.providers.crut.status}</span>
                        </div>
                      </div>

                      <div className="flex justify-between items-center text-[10px] uppercase font-mono">
                        <span className="text-zinc-400">Simulation Fleet</span>
                        <div className="flex items-center gap-2">
                          <span className="text-[8px] text-zinc-500">{twinStatus.providers.simulation.last_update ? new Date(twinStatus.providers.simulation.last_update).toLocaleTimeString() : ''}</span>
                          <span className={`font-bold ${twinStatus.providers.simulation.status === 'ACTIVE' || twinStatus.providers.simulation.status === 'ONLINE' ? 'text-emerald-400' : twinStatus.providers.simulation.status === 'STALE' ? 'text-amber-400 animate-pulse' : twinStatus.providers.simulation.status === 'DISABLED' ? 'text-rose-500 line-through' : 'text-zinc-500'}`}>{twinStatus.providers.simulation.status}</span>
                        </div>
                      </div>
                    </div>
                  )}
                </div>

                {/* Warnings List */}
                {warnings.length === 0 ? (
                  <div className="bg-emerald-950/30 border border-emerald-900/50 p-4 rounded text-center">
                    <div className="text-emerald-400 font-bold uppercase tracking-wider text-sm mb-1">NO ACTIVE THREATS</div>
                    <p className="text-emerald-600/70 text-xs">Network operating within predicted thresholds.</p>
                  </div>
                ) : (
                  <div className="space-y-3 pb-4">
                    <h3 className="text-xs font-bold text-zinc-500 uppercase tracking-widest">Early Warning</h3>
                    {warnings.map((w, idx) => (
                      <div
                        key={idx}
                        className={`p-3 rounded bg-zinc-900 border-l-4 cursor-pointer transition-all hover:bg-zinc-800 ${w.severity === 'CRITICAL' ? 'border-rose-500 shadow-[inset_4px_0_0_rgba(244,63,94,1)]' : 'border-amber-500 shadow-[inset_4px_0_0_rgba(245,158,11,1)]'}`}
                        onClick={() => {
                          setSelectedStop(stops.find(s => s.id === w.stop_id));
                          setSelectedEdge(null);
                          setSelectedVehicle(null);
                          setDisruptionType('CROWD_SURGE');
                        }}
                      >
                        <div className="flex justify-between items-start mb-2 font-mono">
                          <span className={`text-[10px] font-bold px-1.5 py-0.5 rounded ${w.severity === 'CRITICAL' ? 'bg-rose-950 text-rose-400 border border-rose-900' : 'bg-amber-950 text-amber-400 border border-amber-900'}`}>{w.severity}</span>
                          <span className="text-xs text-zinc-400 font-bold">{w.minutes_to_impact}m to impact</span>
                        </div>
                        <h4 className="font-bold text-sm text-zinc-200">{w.stop_name}</h4>
                        <p className="text-xs text-zinc-500 mt-1">{w.explanation}</p>
                      </div>
                    ))}
                  </div>
                )}

                {/* Unified Target Panel */}
                {(selectedEdge || selectedStop || selectedVehicle) && (
                  <div className="bg-zinc-900 border border-zinc-800 p-4 rounded animate-fade-in font-sans mt-4">
                    {selectedEdge && <h3 className="text-xs font-mono text-zinc-500 uppercase tracking-widest mb-3 border-b border-zinc-800 pb-2">SELECTED INFRASTRUCTURE</h3>}
                    {selectedStop && <h3 className="text-xs font-mono text-zinc-500 uppercase tracking-widest mb-3 border-b border-zinc-800 pb-2">SELECTED STOP</h3>}
                    {selectedVehicle && <h3 className="text-xs font-mono text-zinc-500 uppercase tracking-widest mb-3 border-b border-zinc-800 pb-2">SELECTED VEHICLE</h3>}

                    {selectedEdge && (
                      <div className="mb-4">
                        <div className="font-black text-xl text-zinc-100 mb-1">EDGE {selectedEdge.id}</div>
                        <div className="text-sm text-zinc-400 mb-3">{selectedEdge.source_id} → {selectedEdge.target_id}</div>
                        <div className="grid grid-cols-2 gap-2 text-xs font-mono bg-zinc-950 p-2 rounded border border-zinc-800/50">
                          <div className="text-zinc-500">Distance</div>
                          <div className="text-zinc-300 text-right">{selectedEdge.distance}m</div>
                          <div className="text-zinc-500">Status</div>
                          <div className="text-emerald-400 text-right">CLEAR</div>
                        </div>
                      </div>
                    )}

                    {selectedStop && (
                      <div className="mb-4">
                        <div className="font-black text-xl text-zinc-100 mb-1">{selectedStop.name}</div>
                        <div className="text-sm font-mono text-zinc-500 mb-3">STOP {selectedStop.id}</div>
                        <div className="flex justify-between items-center text-xs font-mono bg-zinc-950 p-3 rounded border border-zinc-800/50">
                          <div className="text-zinc-500 flex flex-col justify-center">QUEUE<br />XX / CAPACITY</div>
                          <div className="text-right text-lg text-zinc-200">
                            <span className="font-bold">{selectedStop.queue_count || 0}</span> / {selectedStop.capacity}
                          </div>
                        </div>
                        {warnings.find(w => w.stop_id === selectedStop.id) ? (
                          <div className="mt-2 bg-amber-950/30 border border-amber-900/50 p-2 rounded text-amber-400 text-[10px] font-mono">
                            ⚠ PREDICTED CROWD: {warnings.find(w => w.stop_id === selectedStop.id).predicted_crowd} pax
                          </div>
                        ) : (
                          <div className="mt-2 text-zinc-600 text-xs italic font-mono">Prediction unavailable</div>
                        )}
                      </div>
                    )}

                    {selectedVehicle && (
                      <div className="mb-4">
                        <div className="font-black text-xl text-zinc-100 mb-1">BUS-{selectedVehicle.vehicle_id}</div>
                        <div className="grid grid-cols-2 gap-2 text-xs font-mono bg-zinc-950 p-3 rounded border border-zinc-800/50 mt-3">
                          <div className="text-zinc-500">STATUS</div>
                          <div className="text-right text-cyan-400">{selectedVehicle.status || selectedVehicle.state}</div>
                          <div className="text-zinc-500">OCCUPANCY</div>
                          <div className="text-right text-zinc-200"><span className="font-bold">{selectedVehicle.occupancy}</span> / {selectedVehicle.capacity}</div>
                          <div className="text-zinc-500">SOURCE</div>
                          <div className={`text-right font-bold ${selectedVehicle.data_source === 'SIMULATION' ? 'text-cyan-400' : 'text-emerald-400'}`}>{selectedVehicle.data_source === 'SIMULATION' ? 'SIMULATION' : 'REAL (CRUT)'}</div>
                          <div className="text-zinc-500">FRESHNESS</div>
                          <div className="text-right text-zinc-300">{selectedVehicle.last_updated_at ? Math.round((new Date().getTime() - new Date(selectedVehicle.last_updated_at).getTime()) / 1000) + 's ago' : 'Unknown'}</div>
                        </div>
                      </div>
                    )}

                    <div className="mt-6">
                      <h4 className="text-[10px] font-mono font-bold text-zinc-500 mb-2 uppercase tracking-widest">CREATE DISRUPTION</h4>
                      <select
                        className="w-full bg-zinc-950 border border-zinc-800 text-zinc-200 p-2 rounded text-sm mb-3 font-bold focus:ring-1 focus:ring-cyan-500 outline-none"
                        value={disruptionType}
                        onChange={e => setDisruptionType(e.target.value)}
                      >
                        {selectedEdge && <option value="ROAD_BLOCK">ROAD BLOCK</option>}
                        {selectedEdge && <option value="WEATHER_HAZARD">WEATHER HAZARD</option>}
                        {selectedStop && <option value="CROWD_SURGE">CROWD SURGE</option>}
                        {selectedVehicle && <option value="VEHICLE_BREAKDOWN">VEHICLE BREAKDOWN</option>}
                      </select>

                      <div className="flex gap-2 mb-4">
                        <div className="flex-1">
                          <label className="block text-[10px] font-mono text-zinc-500 mb-1 uppercase">DURATION (MIN)</label>
                          <input
                            type="number"
                            className="w-full bg-zinc-950 border border-zinc-800 text-zinc-200 p-2 rounded text-sm focus:ring-1 focus:ring-cyan-500 outline-none"
                            value={disruptionDuration}
                            onChange={e => setDisruptionDuration(Number(e.target.value))}
                          />
                        </div>
                      </div>

                      <button
                        onClick={triggerDisruption}
                        disabled={isProcessing}
                        className="w-full bg-rose-600 hover:bg-rose-500 text-white text-xs font-bold font-mono tracking-wider py-3 rounded transition-colors shadow-[0_0_15px_rgba(225,29,72,0.3)] disabled:opacity-50"
                      >
                        {isProcessing ? 'SIMULATING...' : `SIMULATE DISRUPTION`}
                      </button>
                    </div>
                  </div>
                )}
              </div>
            )}

            {workflowState === 'DISRUPTION' && blastRadius && (
              <div className="animate-fade-in space-y-4">
                <div className="bg-rose-950/30 border border-rose-900/50 p-4 rounded">
                  <div className="flex justify-between items-start mb-2">
                    <h3 className="font-bold text-rose-500 text-xs font-mono tracking-widest uppercase">ACTIVE INCIDENT</h3>
                    <span className="w-2 h-2 rounded-full bg-rose-500 shadow-[0_0_8px_rgba(225,29,72,0.8)] animate-pulse"></span>
                  </div>
                  <div className="font-black text-2xl text-zinc-100 uppercase mb-2">{disruptionType.replace(/_/g, ' ')}</div>
                  <div className="grid grid-cols-2 gap-2 text-xs font-mono bg-zinc-950/50 p-2 rounded border border-rose-900/30">
                    <div className="text-zinc-500">TARGET</div>
                    <div className="text-zinc-200 text-right">{currentDisruptionId ? blastRadius.causal_graph.find((n: any) => n.depth === 1)?.entity || 'Unknown' : 'Unknown'}</div>
                    <div className="text-zinc-500">DURATION</div>
                    <div className="text-zinc-200 text-right">{disruptionDuration} MIN</div>
                  </div>
                </div>

                <div className="bg-zinc-900 border border-zinc-800 p-4 rounded">
                  <h4 className="text-xs font-mono text-zinc-500 uppercase tracking-widest mb-3 border-b border-zinc-800 pb-2">IMPACT ANALYSIS</h4>
                  <div className="flex justify-between text-[10px] font-mono text-zinc-600 mb-2 px-2 uppercase">
                    <span>Baseline</span>
                    <span>Disrupted</span>
                  </div>

                  <div className="space-y-2 font-mono text-sm">
                    <div className="flex items-center justify-between bg-zinc-950 p-2 rounded border border-zinc-800/50">
                      <span className="text-zinc-400 text-[10px] uppercase">PASSENGER DELAY</span>
                      <div className="flex items-center gap-3">
                        <span className="text-zinc-500">{(blastRadius.baseline_metrics.total_waiting_seconds / 60).toFixed(0)}</span>
                        <span className="text-rose-500 font-bold text-xs">+{((blastRadius.disrupted_metrics.total_waiting_seconds - blastRadius.baseline_metrics.total_waiting_seconds) / 60).toFixed(0)}m</span>
                      </div>
                    </div>
                    <div className="flex items-center justify-between bg-zinc-950 p-2 rounded border border-zinc-800/50">
                      <span className="text-zinc-400 text-[10px] uppercase">MAX QUEUE</span>
                      <div className="flex items-center gap-3">
                        <span className="text-zinc-500">{blastRadius.baseline_metrics.max_queue_size}</span>
                        <span className="text-amber-500 font-bold text-xs">+{blastRadius.disrupted_metrics.max_queue_size - blastRadius.baseline_metrics.max_queue_size}</span>
                      </div>
                    </div>
                    <div className="flex items-center justify-between bg-zinc-950 p-2 rounded border border-zinc-800/50">
                      <span className="text-zinc-400 text-[10px] uppercase">AFFECTED VEHICLES</span>
                      <div className="flex items-center gap-3">
                        <span className="text-rose-400 font-bold text-xs">{blastRadius.affected_vehicles?.length || 0}</span>
                      </div>
                    </div>
                    <div className="flex items-center justify-between bg-zinc-950 p-2 rounded border border-zinc-800/50">
                      <span className="text-zinc-400 text-[10px] uppercase">AFFECTED STOPS</span>
                      <div className="flex items-center gap-3">
                        <span className="text-amber-400 font-bold text-xs">{blastRadius.directly_affected_stops?.length + blastRadius.indirectly_affected_stops?.length || 0}</span>
                      </div>
                    </div>
                  </div>
                </div>

                <button onClick={runSandbox} disabled={isProcessing} className="w-full bg-indigo-600 hover:bg-indigo-500 text-white font-bold font-mono tracking-wider py-3 rounded transition-all text-xs shadow-[0_0_15px_rgba(79,70,229,0.3)] disabled:opacity-50 mt-4">
                  {isProcessing ? 'GENERATING...' : 'OPEN PRE-ACTION SANDBOX'}
                </button>
              </div>
            )}

            {(workflowState === 'SANDBOX' || workflowState === 'APPROVE') && sandboxResult && (
              <div className="animate-fade-in space-y-4 pb-10">
                <div className="bg-indigo-950/30 border border-indigo-900/50 p-4 rounded text-center">
                  <h3 className="font-bold text-indigo-400 text-[10px] font-mono tracking-widest uppercase mb-1">PRE-ACTION SANDBOX</h3>
                  <div className="text-zinc-300 font-sans text-sm tracking-wide font-black">SIMULATION COMPLETE</div>
                </div>

                <div className="bg-zinc-900 border border-zinc-800 p-3 rounded">
                  <label className="block text-[10px] font-bold font-mono text-zinc-500 uppercase mb-2">OBJECTIVE PROFILE</label>
                  <select
                    className="w-full bg-zinc-950 border border-zinc-800 text-indigo-300 p-2 rounded text-sm font-bold focus:ring-1 focus:ring-indigo-500 outline-none"
                    value={profile}
                    onChange={e => setProfile(e.target.value)}
                  >
                    <option value="SAFETY_FIRST">SAFETY FIRST (Min Crowding)</option>
                    <option value="MINIMUM_DELAY">MINIMUM DELAY</option>
                    <option value="ENERGY_EFFICIENT">ENERGY EFFICIENT</option>
                    <option value="BALANCED">BALANCED</option>
                  </select>
                  <button onClick={runSandbox} disabled={isProcessing} className="w-full mt-3 bg-zinc-800 hover:bg-zinc-700 text-zinc-300 text-[10px] font-mono font-bold py-2 rounded transition-colors border border-zinc-700 tracking-widest">
                    {isProcessing ? 'EVALUATING ROUTES...' : 'RECALCULATE'}
                  </button>
                </div>

                <div className="space-y-3">
                  {sandboxResult.candidates.filter((c: any) => c.feasibility_status === 'FEASIBLE').length === 0 && (
                    <div className="text-rose-500 text-[10px] font-mono text-center p-3 bg-rose-950/20 border border-rose-900/50 rounded tracking-widest">
                      NO FEASIBLE REROUTE
                    </div>
                  )}
                  {sandboxResult.candidates.map((cand: any) => (
                    <div
                      key={cand.id}
                      className={`border rounded overflow-hidden cursor-pointer transition-all ${cand.feasibility_status === 'INFEASIBLE' ? 'opacity-40 grayscale' : ''} ${selectedCandidate?.id === cand.id ? 'border-indigo-500 bg-indigo-950/20 shadow-[0_0_15px_rgba(79,70,229,0.15)]' : 'bg-zinc-900 border-zinc-800 hover:border-zinc-600'}`}
                      onClick={() => cand.feasibility_status === 'FEASIBLE' && setSelectedCandidate(cand)}
                    >
                      <div className={`p-3 border-b flex justify-between items-center ${selectedCandidate?.id === cand.id ? 'border-indigo-900 bg-indigo-900/20' : 'border-zinc-800 bg-zinc-950/50'}`}>
                        <div className="flex gap-3 items-center">
                          <span className="font-bold font-mono text-xs text-zinc-500">#{cand.rank}</span>
                          <span className="font-bold text-sm text-zinc-200">{cand.type.replace(/_/g, ' ')}</span>
                        </div>
                        {cand.rank === 1 && <span className="text-[9px] font-bold text-emerald-400 bg-emerald-950/50 px-2 py-0.5 rounded border border-emerald-900 tracking-wider">RECOMMENDED</span>}
                      </div>

                      <div className="p-3">
                        <div className="flex justify-between items-center mb-3">
                          <span className={`text-[10px] font-mono px-1.5 py-0.5 rounded tracking-wider ${cand.feasibility_status === 'FEASIBLE' ? 'bg-emerald-950 text-emerald-400' : 'bg-rose-950 text-rose-400'}`}>{cand.feasibility_status}</span>
                          <span className="text-xs font-mono text-zinc-400">SCORE: {(cand.score * 100).toFixed(0)}</span>
                        </div>

                        {cand.feasibility_status === 'FEASIBLE' ? (
                          <div className="grid grid-cols-2 gap-2 text-xs font-mono">
                            <div className="bg-zinc-950 p-2 rounded border border-zinc-800/50">
                              <div className="text-zinc-500 text-[10px] uppercase mb-1">Delay</div>
                              <div className={`${cand.delta_metrics.waiting_minutes_saved > 0 ? 'text-emerald-400' : 'text-rose-400'}`}>
                                {cand.delta_metrics.waiting_minutes_saved > 0 ? '↓' : '↑'} {Math.abs(cand.delta_metrics.waiting_minutes_saved).toFixed(0)} min
                              </div>
                            </div>
                            <div className="bg-zinc-950 p-2 rounded border border-zinc-800/50">
                              <div className="text-zinc-500 text-[10px] uppercase mb-1">Energy</div>
                              <div className="text-amber-400">
                                +{cand.delta_metrics.energy_kwh.toFixed(1)} kWh
                              </div>
                            </div>
                          </div>
                        ) : (
                          <p className="text-rose-500 text-xs italic">{cand.explanation}</p>
                        )}
                      </div>
                    </div>
                  ))}
                </div>

                {selectedCandidate && (
                  <div className="mt-6 animate-fade-in border border-zinc-800 bg-zinc-900 rounded p-4">
                    <h4 className="text-[10px] font-mono text-zinc-500 uppercase tracking-widest mb-2 border-b border-zinc-800 pb-2">WHY THIS OPTION</h4>
                    <p className="text-sm text-zinc-300 font-sans mb-4 mt-3">{selectedCandidate.explanation}</p>

                    <div className="bg-rose-950/20 border border-rose-900/30 p-2 rounded mb-4 text-center">
                      <span className="text-[10px] font-mono text-rose-400/80 uppercase">Simulation state is isolated from live operations.</span>
                    </div>

                    <button
                      onClick={approveIntervention}
                      disabled={isProcessing}
                      className="w-full bg-emerald-600 hover:bg-emerald-500 text-white font-bold font-mono tracking-wider py-3 rounded transition-all text-xs shadow-[0_0_15px_rgba(5,150,105,0.3)] disabled:opacity-50"
                    >
                      {isProcessing ? 'DISPATCHING...' : 'APPROVE & DISPATCH'}
                    </button>
                  </div>
                )}
              </div>
            )}

            {workflowState === 'VERIFIED' && selectedCandidate && (
              <div className="animate-fade-in space-y-4">
                <div className="bg-emerald-950/30 border border-emerald-900/50 p-6 rounded-lg text-center shadow-[0_0_30px_rgba(5,150,105,0.1)]">
                  <div className="text-emerald-400 text-4xl mb-3 font-sans">✓</div>
                  <h3 className="font-black font-sans text-emerald-400 tracking-wide text-lg mb-1">INTERVENTION APPLIED</h3>
                  <div className="text-[10px] font-mono text-emerald-600 space-y-1 tracking-widest mt-3">
                    <p>LIVE STATE UPDATED</p>
                    <p>AUDIT LOGGED</p>
                  </div>
                </div>

                <div className="text-center mt-8">
                  <button onClick={triggerDemoReset} className="text-cyan-500 hover:text-cyan-400 hover:bg-cyan-950/50 text-[10px] font-mono uppercase tracking-widest border border-cyan-900/50 bg-cyan-950/30 px-4 py-2 rounded transition-colors">
                    ACKNOWLEDGE & RESET
                  </button>
                </div>
              </div>
            )}
          </div>
        </aside>
      </div>

      {/* Emergency SOS Button — always visible on Command Center */}
      <EmergencySOS />
    </div>
  );
}

export default App;
