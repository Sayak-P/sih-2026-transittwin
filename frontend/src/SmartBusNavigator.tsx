import { useState, useEffect, useRef } from 'react';
import Map, { Source, Layer, Marker } from 'react-map-gl/maplibre';
import EmergencySOS from './EmergencySOS';
import 'maplibre-gl/dist/maplibre-gl.css';
import { 
  Bus, 
  Navigation, 
  ShieldCheck, 
  AlertTriangle, 
  Clock, 
  Gauge, 
  CheckCircle2, 
  ArrowRight, 
  Layers, 
  Compass, 
  Sparkles, 
  RefreshCw,
  Send,
  Zap,
  MapPin,
  TrendingDown,
  Search,
  MapPinned,
  Users,
  Timer,
  Route,
  ChevronDown,
  ChevronUp,
  Radio,
  Footprints
} from 'lucide-react';

const MAP_STYLE = "https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json";

interface BusItem {
  identifier: string;
  vehicle_type: string;
  route_id: number | null;
  route_name: string;
  lat: number;
  lon: number;
  speed_kmh: number;
  occupancy: number;
  capacity: number;
  status: string;
  current_stop: { id: number; name: string; lat: number; lon: number } | null;
  next_stop: { id: number; name: string; lat: number; lon: number } | null;
}

interface StopItem {
  id: number;
  name: string;
  lat: number;
  lon: number;
}

interface ApproachingBus {
  identifier: string;
  status: string;
  occupancy: number;
  capacity: number;
  speed_kmh: number;
  lat: number;
  lon: number;
  current_stop: string;
  eta_minutes: number;
  distance_remaining_km: number;
  stops_away: number;
  intermediate_stops: string[];
}

interface RouteAvailability {
  route_id: number;
  route_name: string;
  total_stops: number;
  buses: ApproachingBus[];
}

interface AvailabilityResult {
  stop: { id: number; name: string; lat: number; lon: number };
  routes_serving: RouteAvailability[];
  total_buses_approaching: number;
  next_bus_eta_minutes: number | null;
  next_bus: ApproachingBus | null;
}

interface SmartBusNavigatorProps {
  onEnterCommandCenter: () => void;
  onEnterLanding?: () => void;
  onEnterPredictions?: () => void;
  onEnterRerouting?: () => void;
}

export default function SmartBusNavigator({ onEnterCommandCenter, onEnterLanding, onEnterPredictions, onEnterRerouting }: SmartBusNavigatorProps) {
  // ---- Tab State ----
  const [activeTab, setActiveTab] = useState<'ROUTE_PLANNER' | 'BUS_TRACKER'>('ROUTE_PLANNER');

  // ---- Route Planner State (existing) ----
  const [buses, setBuses] = useState<BusItem[]>([]);
  const [allStops, setAllStops] = useState<StopItem[]>([]);
  const [selectedBusId, setSelectedBusId] = useState<string>('');
  const [currentStopId, setCurrentStopId] = useState<number | ''>('');
  const [targetStopId, setTargetStopId] = useState<number | ''>('');
  
  // Options
  const [avoidRoadBlocks, setAvoidRoadBlocks] = useState(true);
  const [avoidCongestion, setAvoidCongestion] = useState(true);
  const [priority, setPriority] = useState('FASTEST'); // FASTEST, SHORTEST, LEAST_CONGESTED, ACCESSIBLE

  // Results
  const [isLoading, setIsLoading] = useState(false);
  const [routeResult, setRouteResult] = useState<any>(null);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [dispatchSuccess, setDispatchSuccess] = useState(false);

  // ---- Bus Tracker State (new) ----
  const [trackerStopId, setTrackerStopId] = useState<number | ''>('');
  const [trackerSearchQuery, setTrackerSearchQuery] = useState('');
  const [trackerLoading, setTrackerLoading] = useState(false);
  const [trackerResult, setTrackerResult] = useState<AvailabilityResult | null>(null);
  const [trackerError, setTrackerError] = useState<string | null>(null);
  const [expandedRoutes, setExpandedRoutes] = useState<Set<number>>(new Set());

  // Map view
  const [viewState, setViewState] = useState({
    longitude: 85.83,
    latitude: 20.28,
    zoom: 13
  });

  const mapRef = useRef<any>(null);

  // 1. Fetch Buses and Stops on Mount
  useEffect(() => {
    fetchBuses();
    fetchStops();
    const interval = setInterval(fetchBuses, 3000);
    return () => clearInterval(interval);
  }, []);

  // Auto-refresh bus tracker every 10 seconds
  useEffect(() => {
    if (activeTab !== 'BUS_TRACKER' || !trackerStopId) return;
    const interval = setInterval(() => {
      fetchBusAvailability(trackerStopId as number, true);
    }, 10000);
    return () => clearInterval(interval);
  }, [activeTab, trackerStopId]);

  const fetchBuses = () => {
    fetch('/api/v1/navigation/buses/')
      .then(res => res.json())
      .then((data: BusItem[]) => {
        setBuses(data);
        if (!selectedBusId && data.length > 0) {
          // Auto select first bus
          const firstBus = data[0];
          setSelectedBusId(firstBus.identifier);
          if (firstBus.current_stop) setCurrentStopId(firstBus.current_stop.id);
          if (firstBus.next_stop) setTargetStopId(firstBus.next_stop.id);
        }
      })
      .catch(err => console.error("Error fetching buses:", err));
  };

  const fetchStops = () => {
    fetch('/api/v1/stops/')
      .then(res => res.json())
      .then((data: any[]) => {
        setAllStops(data.map(s => ({ id: s.id, name: s.name, lat: s.lat, lon: s.lon })));
      })
      .catch(err => console.error("Error fetching stops:", err));
  };

  // Handle bus selection change
  const handleBusSelect = (busId: string) => {
    setSelectedBusId(busId);
    setDispatchSuccess(false);
    const bus = buses.find(b => b.identifier === busId);
    if (bus) {
      if (bus.current_stop) setCurrentStopId(bus.current_stop.id);
      if (bus.next_stop) setTargetStopId(bus.next_stop.id);

      if (bus.lat && bus.lon) {
        setViewState({
          longitude: bus.lon,
          latitude: bus.lat,
          zoom: 14
        });
      }
    }
  };

  // 2. Compute Route
  const computeClearRoute = () => {
    if (!currentStopId || !targetStopId) {
      setErrorMsg("Please select both a current stop and target destination stop.");
      return;
    }

    if (currentStopId === targetStopId) {
      setErrorMsg("Current stop and Target stop cannot be the same.");
      return;
    }

    setIsLoading(true);
    setErrorMsg(null);
    setDispatchSuccess(false);

    fetch('/api/v1/navigation/find-clear-route/', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        bus_id: selectedBusId,
        current_stop_id: currentStopId,
        target_stop_id: targetStopId,
        avoid_road_blocks: avoidRoadBlocks,
        avoid_congestion: avoidCongestion,
        priority: priority
      })
    })
      .then(async res => {
        const data = await res.json();
        if (!res.ok) {
          throw new Error(data.error || "Route computation failed");
        }
        return data;
      })
      .then(data => {
        setRouteResult(data);
        // Center map on route
        if (data.route_geometry && data.route_geometry.length > 0) {
          const midIdx = Math.floor(data.route_geometry.length / 2);
          const midPoint = data.route_geometry[midIdx];
          setViewState({
            longitude: midPoint[0],
            latitude: midPoint[1],
            zoom: 13.5
          });
        }
      })
      .catch(err => {
        console.error(err);
        setErrorMsg(err.message);
      })
      .finally(() => {
        setIsLoading(false);
      });
  };

  // Auto compute initial route when buses load
  useEffect(() => {
    if (selectedBusId && currentStopId && targetStopId && !routeResult) {
      computeClearRoute();
    }
  }, [selectedBusId, currentStopId, targetStopId]);

  // Dispatch route to live digital twin
  const handleDispatch = () => {
    setDispatchSuccess(true);
    setTimeout(() => {
      onEnterCommandCenter();
    }, 1200);
  };

  // ---- Bus Tracker Methods ----
  const fetchBusAvailability = (stopId: number, silent = false) => {
    if (!silent) setTrackerLoading(true);
    setTrackerError(null);

    fetch(`/api/v1/navigation/bus-availability/?stop_id=${stopId}`)
      .then(async res => {
        const data = await res.json();
        if (!res.ok) throw new Error(data.error || "Failed to fetch availability");
        return data;
      })
      .then((data: AvailabilityResult) => {
        setTrackerResult(data);
        // Expand all routes by default
        const routeIds = new Set(data.routes_serving.map(r => r.route_id));
        setExpandedRoutes(routeIds);
        // Center map on this stop
        if (data.stop) {
          setViewState({
            longitude: data.stop.lon,
            latitude: data.stop.lat,
            zoom: 14
          });
        }
      })
      .catch(err => {
        console.error(err);
        setTrackerError(err.message);
      })
      .finally(() => {
        if (!silent) setTrackerLoading(false);
      });
  };

  const handleTrackerStopSelect = (stopId: number) => {
    setTrackerStopId(stopId);
    setTrackerResult(null);
    if (stopId) {
      fetchBusAvailability(stopId);
    }
  };

  const toggleRouteExpand = (routeId: number) => {
    setExpandedRoutes(prev => {
      const next = new Set(prev);
      if (next.has(routeId)) next.delete(routeId);
      else next.add(routeId);
      return next;
    });
  };

  const filteredStops = trackerSearchQuery
    ? allStops.filter(s => s.name.toLowerCase().includes(trackerSearchQuery.toLowerCase()))
    : allStops;

  const getOccupancyColor = (occ: number, cap: number) => {
    const ratio = occ / cap;
    if (ratio >= 0.9) return 'text-rose-400';
    if (ratio >= 0.7) return 'text-amber-400';
    if (ratio >= 0.4) return 'text-yellow-400';
    return 'text-emerald-400';
  };

  const getOccupancyBg = (occ: number, cap: number) => {
    const ratio = occ / cap;
    if (ratio >= 0.9) return 'bg-rose-500';
    if (ratio >= 0.7) return 'bg-amber-500';
    if (ratio >= 0.4) return 'bg-yellow-500';
    return 'bg-emerald-500';
  };

  const getStatusBadge = (status: string) => {
    switch (status) {
      case 'ACTIVE': return 'bg-emerald-500/20 text-emerald-400 border-emerald-500/40';
      case 'DELAYED': return 'bg-amber-500/20 text-amber-400 border-amber-500/40';
      case 'BROKEN': return 'bg-rose-500/20 text-rose-400 border-rose-500/40';
      default: return 'bg-zinc-500/20 text-zinc-400 border-zinc-500/40';
    }
  };

  const getEtaBadgeStyle = (eta: number) => {
    if (eta <= 5) return 'from-emerald-600 to-emerald-700 shadow-emerald-600/40';
    if (eta <= 10) return 'from-cyan-600 to-blue-600 shadow-cyan-600/40';
    if (eta <= 20) return 'from-amber-600 to-orange-600 shadow-amber-600/40';
    return 'from-zinc-600 to-zinc-700 shadow-zinc-600/40';
  };

  const selectedBus = buses.find(b => b.identifier === selectedBusId);

  // GeoJSON for optimal route
  const optimalRouteGeoJSON: any = routeResult?.route_geometry ? {
    type: 'FeatureCollection',
    features: [{
      type: 'Feature',
      geometry: {
        type: 'LineString',
        coordinates: routeResult.route_geometry
      },
      properties: {}
    }]
  } : null;

  // GeoJSON for direct comparison route if available
  const directRouteGeoJSON: any = routeResult?.direct_route_geometry ? {
    type: 'FeatureCollection',
    features: [{
      type: 'Feature',
      geometry: {
        type: 'LineString',
        coordinates: routeResult.direct_route_geometry
      },
      properties: {}
    }]
  } : null;

  return (
    <div className="w-screen h-screen flex flex-col font-sans bg-zinc-950 text-zinc-100 overflow-hidden select-none">
      {/* Top Navbar */}
      <header className="h-16 bg-zinc-900/90 backdrop-blur-md border-b border-zinc-800 px-6 flex items-center justify-between z-30 shadow-xl">
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-xl bg-gradient-to-tr from-cyan-500 to-blue-600 flex items-center justify-center shadow-lg shadow-cyan-500/30">
            <Compass className="w-5 h-5 text-white animate-spin-slow" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h1 className="text-base font-extrabold tracking-wide text-white uppercase">Transit Twin</h1>
              <span className="text-[10px] bg-cyan-500/20 text-cyan-400 border border-cyan-500/30 px-2 py-0.5 rounded-full font-mono font-semibold">
                SMART BUS NAVIGATOR
              </span>
            </div>
            <p className="text-xs text-zinc-400">Optimal Hurdle-Free Bus Routing & Dispatch Engine (Bhubaneswar Mo Bus Network)</p>
          </div>
        </div>

        <div className="flex items-center gap-3">
          <div className="hidden md:flex items-center gap-2 bg-zinc-800/80 px-3 py-1.5 rounded-lg border border-zinc-700 text-xs font-mono">
            <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse shadow-emerald-400/50"></span>
            <span className="text-zinc-300">Active Fleet: <b className="text-emerald-400">{buses.length} Buses</b></span>
          </div>

          {onEnterLanding && (
            <button
              onClick={onEnterLanding}
              className="bg-zinc-800 hover:bg-zinc-700 text-zinc-300 font-medium text-xs px-3 py-2 rounded-lg border border-zinc-700 transition-all cursor-pointer"
              title="Return to Home"
            >
              🏠 Home
            </button>
          )}

          {onEnterPredictions && (
            <button
              onClick={onEnterPredictions}
              className="bg-primary-container hover:bg-primary-fixed text-on-primary-container font-medium text-xs px-3 py-2 rounded-lg border border-secondary shadow-md shadow-blue-500/20 transition-all cursor-pointer"
              title="Open Predictions Dashboard"
            >
              📊 Predictions
            </button>
          )}

          {onEnterRerouting && (
            <button
              onClick={onEnterRerouting}
              className="bg-emerald-950/80 hover:bg-emerald-900/80 text-emerald-400 font-medium text-xs px-3 py-2 rounded-lg border border-emerald-600/40 shadow-md shadow-emerald-500/20 transition-all cursor-pointer flex items-center gap-1.5"
              title="Open Rerouting Sandbox"
            >
              <span>🔀</span>
              <span>Rerouting</span>
            </button>
          )}

          <button
            onClick={onEnterCommandCenter}
            className="flex items-center gap-2 bg-gradient-to-r from-blue-600 to-indigo-600 hover:from-blue-500 hover:to-indigo-500 text-white font-medium text-xs px-4 py-2 rounded-lg shadow-lg shadow-blue-600/30 border border-blue-400/30 transition-all transform hover:scale-[1.02] cursor-pointer"
          >
            <Layers className="w-4 h-4" />
            <span>Command Center</span>
            <ArrowRight className="w-3.5 h-3.5" />
          </button>
        </div>
      </header>

      {/* Main Body */}
      <div className="flex-1 flex flex-col md:flex-row relative overflow-hidden">
        {/* Left Interactive Control & Results Sidebar */}
        <div className="w-full md:w-[480px] lg:w-[520px] bg-zinc-900/95 backdrop-blur-xl border-r border-zinc-800 flex flex-col z-20 shadow-2xl overflow-y-auto custom-scrollbar">
          
          {/* Tab Switcher */}
          <div className="flex border-b border-zinc-800">
            <button
              onClick={() => setActiveTab('ROUTE_PLANNER')}
              className={`flex-1 py-3 px-4 flex items-center justify-center gap-2 text-xs font-bold uppercase tracking-wider transition-all ${
                activeTab === 'ROUTE_PLANNER'
                  ? 'text-cyan-400 border-b-2 border-cyan-400 bg-cyan-500/5'
                  : 'text-zinc-500 hover:text-zinc-300 hover:bg-zinc-800/50'
              }`}
            >
              <Navigation className="w-4 h-4" />
              Route Planner
            </button>
            <button
              onClick={() => setActiveTab('BUS_TRACKER')}
              className={`flex-1 py-3 px-4 flex items-center justify-center gap-2 text-xs font-bold uppercase tracking-wider transition-all ${
                activeTab === 'BUS_TRACKER'
                  ? 'text-emerald-400 border-b-2 border-emerald-400 bg-emerald-500/5'
                  : 'text-zinc-500 hover:text-zinc-300 hover:bg-zinc-800/50'
              }`}
            >
              <Radio className="w-4 h-4" />
              Bus Tracker
            </button>
          </div>

          {/* ============================================ */}
          {/* TAB: ROUTE PLANNER (existing functionality) */}
          {/* ============================================ */}
          {activeTab === 'ROUTE_PLANNER' && (
            <>
              {/* Section 1: Bus Selector */}
              <div className="p-5 border-b border-zinc-800 space-y-4">
                <div className="flex items-center justify-between">
                  <label className="text-xs font-bold text-zinc-300 uppercase tracking-wider flex items-center gap-2">
                    <Bus className="w-4 h-4 text-cyan-400" />
                    Select Bus / Vehicle
                  </label>
                  <button 
                    onClick={fetchBuses} 
                    className="text-[11px] text-zinc-400 hover:text-cyan-400 flex items-center gap-1 font-mono transition-colors"
                    title="Refresh live fleet"
                  >
                    <RefreshCw className="w-3 h-3" /> Refresh
                  </button>
                </div>

                <select
                  value={selectedBusId}
                  onChange={(e) => handleBusSelect(e.target.value)}
                  className="w-full bg-zinc-950 border border-zinc-700 text-zinc-100 text-sm rounded-xl p-3 focus:outline-none focus:border-cyan-500 font-mono shadow-inner cursor-pointer"
                >
                  {buses.map((b) => (
                    <option key={b.identifier} value={b.identifier}>
                      {b.identifier} — {b.route_name} ({b.status} | {b.occupancy} pax)
                    </option>
                  ))}
                </select>

                {/* Selected Bus Live Telemetry HUD */}
                {selectedBus && (
                  <div className="bg-zinc-950/80 rounded-xl p-3.5 border border-zinc-800 grid grid-cols-3 gap-2 text-center text-xs font-mono">
                    <div className="bg-zinc-900/60 p-2 rounded-lg border border-zinc-800/80">
                      <div className="text-[10px] text-zinc-400">ROUTE</div>
                      <div className="text-cyan-400 font-bold truncate">{selectedBus.route_name.replace('Mo Bus ', '')}</div>
                    </div>
                    <div className="bg-zinc-900/60 p-2 rounded-lg border border-zinc-800/80">
                      <div className="text-[10px] text-zinc-400">SPEED</div>
                      <div className="text-emerald-400 font-bold">{selectedBus.speed_kmh} km/h</div>
                    </div>
                    <div className="bg-zinc-900/60 p-2 rounded-lg border border-zinc-800/80">
                      <div className="text-[10px] text-zinc-400">OCCUPANCY</div>
                      <div className="text-yellow-400 font-bold">{selectedBus.occupancy}/{selectedBus.capacity}</div>
                    </div>
                  </div>
                )}
              </div>

              {/* Section 2: Journey Path & Hurdle Avoidance Settings */}
              <div className="p-5 border-b border-zinc-800 space-y-4">
                <h2 className="text-xs font-bold text-zinc-300 uppercase tracking-wider flex items-center gap-2">
                  <Navigation className="w-4 h-4 text-blue-400" />
                  Origin & Next Stop Corridor
                </h2>

                <div className="space-y-3">
                  <div>
                    <label className="text-[11px] text-zinc-400 mb-1 block flex items-center gap-1.5">
                      <span className="w-2 h-2 rounded-full bg-cyan-400"></span> Current Bus Location / Stop:
                    </label>
                    <select
                      value={currentStopId}
                      onChange={(e) => setCurrentStopId(Number(e.target.value))}
                      className="w-full bg-zinc-950 border border-zinc-700 text-zinc-100 text-xs rounded-lg p-2.5 focus:border-cyan-500"
                    >
                      {allStops.map(s => (
                        <option key={`curr-${s.id}`} value={s.id}>{s.name}</option>
                      ))}
                    </select>
                  </div>

                  <div>
                    <label className="text-[11px] text-zinc-400 mb-1 block flex items-center gap-1.5">
                      <span className="w-2 h-2 rounded-full bg-emerald-400"></span> Target Destination / Next Stop:
                    </label>
                    <select
                      value={targetStopId}
                      onChange={(e) => setTargetStopId(Number(e.target.value))}
                      className="w-full bg-zinc-950 border border-zinc-700 text-zinc-100 text-xs rounded-lg p-2.5 focus:border-emerald-500"
                    >
                      {allStops.map(s => (
                        <option key={`target-${s.id}`} value={s.id}>{s.name}</option>
                      ))}
                    </select>
                  </div>
                </div>

                {/* Smart Hurdle Avoidance Toggles */}
                <div className="bg-zinc-950/60 rounded-xl p-3.5 border border-zinc-800 space-y-2.5">
                  <div className="text-[11px] font-bold text-zinc-300 uppercase tracking-wider flex items-center gap-1.5">
                    <ShieldCheck className="w-3.5 h-3.5 text-cyan-400" />
                    Hurdle Avoidance Engine
                  </div>

                  <div className="space-y-2 text-xs">
                    <label className="flex items-center justify-between p-2 rounded-lg bg-zinc-900/50 hover:bg-zinc-900 border border-zinc-800/80 cursor-pointer transition-colors">
                      <span className="flex items-center gap-2 text-zinc-300">
                        <AlertTriangle className="w-3.5 h-3.5 text-rose-400" />
                        Bypass Roadblocks & Hazards
                      </span>
                      <input
                        type="checkbox"
                        checked={avoidRoadBlocks}
                        onChange={(e) => setAvoidRoadBlocks(e.target.checked)}
                        className="w-4 h-4 rounded text-cyan-500 bg-zinc-800 border-zinc-600 focus:ring-0 cursor-pointer"
                      />
                    </label>

                    <label className="flex items-center justify-between p-2 rounded-lg bg-zinc-900/50 hover:bg-zinc-900 border border-zinc-800/80 cursor-pointer transition-colors">
                      <span className="flex items-center gap-2 text-zinc-300">
                        <TrendingDown className="w-3.5 h-3.5 text-yellow-400" />
                        Avoid Severe Traffic Jams (TomTom Live)
                      </span>
                      <input
                        type="checkbox"
                        checked={avoidCongestion}
                        onChange={(e) => setAvoidCongestion(e.target.checked)}
                        className="w-4 h-4 rounded text-cyan-500 bg-zinc-800 border-zinc-600 focus:ring-0 cursor-pointer"
                      />
                    </label>
                  </div>

                  {/* Priority Select */}
                  <div className="pt-1">
                    <label className="text-[10px] text-zinc-400 block mb-1">Routing Strategy:</label>
                    <div className="grid grid-cols-3 gap-1.5 text-[10px] font-mono">
                      {['FASTEST', 'SHORTEST', 'LEAST_CONGESTED'].map((p) => (
                        <button
                          key={p}
                          onClick={() => setPriority(p)}
                          className={`p-1.5 rounded border transition-all ${priority === p ? 'bg-cyan-950 text-cyan-300 border-cyan-500 font-bold' : 'bg-zinc-900 text-zinc-400 border-zinc-800 hover:bg-zinc-800'}`}
                        >
                          {p.replace('_', ' ')}
                        </button>
                      ))}
                    </div>
                  </div>
                </div>

                {/* Calculate Button */}
                <button
                  onClick={computeClearRoute}
                  disabled={isLoading}
                  className="w-full py-3 px-4 rounded-xl bg-gradient-to-r from-cyan-500 via-blue-600 to-indigo-600 hover:from-cyan-400 hover:to-indigo-500 text-white font-bold text-xs tracking-wider uppercase shadow-lg shadow-cyan-500/25 flex items-center justify-center gap-2 transition-all transform active:scale-98 disabled:opacity-50"
                >
                  {isLoading ? (
                    <>
                      <RefreshCw className="w-4 h-4 animate-spin" />
                      Calculating Hurdle-Free Path...
                    </>
                  ) : (
                    <>
                      <Zap className="w-4 h-4" />
                      Calculate Best Clear Route
                    </>
                  )}
                </button>

                {errorMsg && (
                  <div className="p-3 rounded-lg bg-rose-950/50 border border-rose-800 text-rose-300 text-xs flex items-center gap-2">
                    <AlertTriangle className="w-4 h-4 flex-shrink-0" />
                    <span>{errorMsg}</span>
                  </div>
                )}
              </div>

              {/* Section 3: Computed Clear Route & Driver Guidance */}
              {routeResult && (
                <div className="p-5 space-y-4 flex-1">
                  {/* Hurdle Clearance Status Banner */}
                  <div className={`p-4 rounded-2xl border ${routeResult.hurdle_clearance?.hurdles_bypassed_count > 0 ? 'bg-gradient-to-r from-emerald-950/80 to-cyan-950/80 border-emerald-500/60 shadow-emerald-900/30' : 'bg-gradient-to-r from-blue-950/80 to-cyan-950/80 border-cyan-500/60'} shadow-lg`}>
                    <div className="flex items-center gap-3">
                      <div className="w-10 h-10 rounded-full bg-emerald-500/20 border border-emerald-500/40 flex items-center justify-center text-emerald-400">
                        <CheckCircle2 className="w-6 h-6" />
                      </div>
                      <div>
                        <div className="text-xs font-bold text-emerald-400 tracking-wider font-mono">
                          {routeResult.hurdle_clearance?.status}
                        </div>
                        <p className="text-xs text-zinc-300 mt-0.5">
                          {routeResult.hurdle_clearance?.hurdles_bypassed_count > 0 ? (
                            <>Successfully detoured around <b>{routeResult.hurdle_clearance.hurdles_bypassed_count} roadblock/hazard</b> without passenger delay.</>
                          ) : (
                            <>All road segments clear of obstacles and high congestion.</>
                          )}
                        </p>
                      </div>
                    </div>
                  </div>

                  {/* Key Journey Metrics Grid */}
                  <div className="grid grid-cols-2 gap-2.5">
                    <div className="bg-zinc-950/70 p-3 rounded-xl border border-zinc-800">
                      <div className="flex items-center gap-1.5 text-[10px] text-zinc-400 uppercase font-mono">
                        <Clock className="w-3.5 h-3.5 text-cyan-400" />
                        Est. Travel Time
                      </div>
                      <div className="text-xl font-extrabold text-white mt-1">
                        {routeResult.metrics?.estimated_travel_time_min} <span className="text-xs font-normal text-zinc-400">min</span>
                      </div>
                      {routeResult.metrics?.time_saved_min > 0 && (
                        <div className="text-[10px] text-emerald-400 font-mono mt-0.5">
                          ⚡ Saves ~{routeResult.metrics.time_saved_min} min vs blocked path
                        </div>
                      )}
                    </div>

                    <div className="bg-zinc-950/70 p-3 rounded-xl border border-zinc-800">
                      <div className="flex items-center gap-1.5 text-[10px] text-zinc-400 uppercase font-mono">
                        <Navigation className="w-3.5 h-3.5 text-blue-400" />
                        Distance
                      </div>
                      <div className="text-xl font-extrabold text-white mt-1">
                        {routeResult.metrics?.total_distance_km} <span className="text-xs font-normal text-zinc-400">km</span>
                      </div>
                      <div className="text-[10px] text-cyan-400 font-mono mt-0.5">
                        Avg {routeResult.metrics?.average_speed_kmh} km/h
                      </div>
                    </div>

                    <div className="bg-zinc-950/70 p-3 rounded-xl border border-zinc-800">
                      <div className="flex items-center gap-1.5 text-[10px] text-zinc-400 uppercase font-mono">
                        <Gauge className="w-3.5 h-3.5 text-yellow-400" />
                        Corridor Flow
                      </div>
                      <div className="text-sm font-bold text-emerald-400 mt-1">
                        {routeResult.metrics?.traffic_congestion_level}
                      </div>
                      <div className="text-[10px] text-zinc-500 font-mono">TomTom Real-Time</div>
                    </div>

                    <div className="bg-zinc-950/70 p-3 rounded-xl border border-zinc-800">
                      <div className="flex items-center gap-1.5 text-[10px] text-zinc-400 uppercase font-mono">
                        <ShieldCheck className="w-3.5 h-3.5 text-emerald-400" />
                        Safety Score
                      </div>
                      <div className="text-sm font-bold text-emerald-400 mt-1">
                        {routeResult.metrics?.safety_score}/100
                      </div>
                      <div className="text-[10px] text-emerald-400/80 font-mono">Zero Collision Risk</div>
                    </div>
                  </div>

                  {/* Turn-by-Turn Driver Instructions */}
                  <div className="bg-zinc-950/80 rounded-xl p-4 border border-zinc-800 space-y-3">
                    <div className="text-xs font-bold text-zinc-300 uppercase tracking-wider flex items-center gap-2">
                      <Sparkles className="w-4 h-4 text-cyan-400" />
                      Turn-by-Turn Driver Guidance
                    </div>

                    <div className="space-y-2 text-xs">
                      {routeResult.turn_by_turn?.map((step: any) => (
                        <div key={step.step} className="p-2.5 rounded-lg bg-zinc-900/60 border border-zinc-800/80 flex items-start gap-2.5">
                          <span className="w-5 h-5 rounded-full bg-cyan-500/20 text-cyan-400 border border-cyan-500/40 text-[10px] font-bold flex items-center justify-center flex-shrink-0 mt-0.5">
                            {step.step}
                          </span>
                          <div className="flex-1">
                            <p className="text-zinc-200">{step.instruction}</p>
                            <div className="flex gap-3 text-[10px] font-mono text-zinc-400 mt-1">
                              <span>Dist: {step.distance_m}m</span>
                              <span>Speed: {step.speed_kmh} km/h</span>
                              <span className="text-emerald-400">✓ Free flow</span>
                            </div>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>

                  {/* Dispatch Action */}
                  <div className="pt-2">
                    <button
                      onClick={handleDispatch}
                      className={`w-full py-3.5 px-4 rounded-xl font-bold text-xs tracking-wider uppercase flex items-center justify-center gap-2 transition-all shadow-lg ${
                        dispatchSuccess 
                          ? 'bg-emerald-600 text-white shadow-emerald-600/30' 
                          : 'bg-emerald-500 hover:bg-emerald-400 text-zinc-950 shadow-emerald-500/30 hover:shadow-emerald-500/50 transform hover:scale-[1.01]'
                      }`}
                    >
                      {dispatchSuccess ? (
                        <>
                          <CheckCircle2 className="w-4 h-4 text-white" />
                          Dispatched! Transferring to Command Center...
                        </>
                      ) : (
                        <>
                          <Send className="w-4 h-4" />
                          Dispatch Hurdle-Free Route to Bus Driver
                        </>
                      )}
                    </button>
                  </div>
                </div>
              )}
            </>
          )}

          {/* ============================================ */}
          {/* TAB: BUS TRACKER (new functionality)        */}
          {/* ============================================ */}
          {activeTab === 'BUS_TRACKER' && (
            <>
              {/* Stop Selector */}
              <div className="p-5 border-b border-zinc-800 space-y-4">
                <div className="flex items-center justify-between">
                  <label className="text-xs font-bold text-zinc-300 uppercase tracking-wider flex items-center gap-2">
                    <MapPinned className="w-4 h-4 text-emerald-400" />
                    Select Stop / Area
                  </label>
                  {trackerResult && (
                    <button
                      onClick={() => trackerStopId && fetchBusAvailability(trackerStopId as number)}
                      className="text-[11px] text-zinc-400 hover:text-emerald-400 flex items-center gap-1 font-mono transition-colors"
                      title="Refresh availability"
                    >
                      <RefreshCw className="w-3 h-3" /> Refresh
                    </button>
                  )}
                </div>

                {/* Search input */}
                <div className="relative">
                  <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-zinc-500" />
                  <input
                    type="text"
                    value={trackerSearchQuery}
                    onChange={(e) => setTrackerSearchQuery(e.target.value)}
                    placeholder="Search stops by name..."
                    className="w-full bg-zinc-950 border border-zinc-700 text-zinc-100 text-sm rounded-xl pl-10 pr-4 py-3 focus:outline-none focus:border-emerald-500 font-mono shadow-inner placeholder:text-zinc-600"
                  />
                </div>

                {/* Stop Dropdown */}
                <select
                  value={trackerStopId}
                  onChange={(e) => handleTrackerStopSelect(Number(e.target.value))}
                  className="w-full bg-zinc-950 border border-zinc-700 text-zinc-100 text-sm rounded-xl p-3 focus:outline-none focus:border-emerald-500 font-mono shadow-inner cursor-pointer"
                >
                  <option value="">— Choose a bus stop —</option>
                  {filteredStops.map(s => (
                    <option key={`tracker-${s.id}`} value={s.id}>{s.name}</option>
                  ))}
                </select>

                {/* Quick Info */}
                {trackerResult && (
                  <div className="bg-gradient-to-r from-emerald-950/60 to-cyan-950/60 rounded-2xl p-4 border border-emerald-500/40 shadow-lg">
                    <div className="flex items-center gap-3">
                      <div className="w-11 h-11 rounded-full bg-emerald-500/20 border-2 border-emerald-500/50 flex items-center justify-center shadow-lg shadow-emerald-600/20">
                        <MapPin className="w-5 h-5 text-emerald-400" />
                      </div>
                      <div className="flex-1">
                        <div className="text-sm font-bold text-white">{trackerResult.stop.name}</div>
                        <div className="text-[11px] text-zinc-400 font-mono mt-0.5">
                          {trackerResult.routes_serving.length} route{trackerResult.routes_serving.length !== 1 ? 's' : ''} serving • {trackerResult.total_buses_approaching} bus{trackerResult.total_buses_approaching !== 1 ? 'es' : ''} approaching
                        </div>
                      </div>
                    </div>

                    {/* Next Bus Highlight */}
                    {trackerResult.next_bus && (
                      <div className="mt-3 bg-zinc-950/60 rounded-xl p-3 border border-emerald-500/30">
                        <div className="flex items-center justify-between">
                          <div className="flex items-center gap-2">
                            <div className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse"></div>
                            <span className="text-[10px] font-bold text-emerald-400 uppercase tracking-wider">Next Bus Arriving</span>
                          </div>
                          <div className={`px-3 py-1 rounded-full bg-gradient-to-r ${getEtaBadgeStyle(trackerResult.next_bus.eta_minutes)} text-white text-sm font-extrabold shadow-lg font-mono`}>
                            ~{trackerResult.next_bus.eta_minutes} min
                          </div>
                        </div>
                        <div className="flex items-center gap-3 mt-2 text-xs">
                          <span className="text-zinc-300 font-mono">{trackerResult.next_bus.identifier}</span>
                          <span className="text-zinc-500">•</span>
                          <span className="text-zinc-400">{trackerResult.next_bus.stops_away} stop{trackerResult.next_bus.stops_away !== 1 ? 's' : ''} away</span>
                          <span className="text-zinc-500">•</span>
                          <span className={getOccupancyColor(trackerResult.next_bus.occupancy, trackerResult.next_bus.capacity)}>
                            {trackerResult.next_bus.occupancy}/{trackerResult.next_bus.capacity} pax
                          </span>
                        </div>
                      </div>
                    )}

                    {trackerResult.total_buses_approaching === 0 && (
                      <div className="mt-3 bg-zinc-950/60 rounded-xl p-3 border border-amber-500/30 text-center">
                        <div className="text-xs text-amber-400 font-mono">No buses currently approaching this stop</div>
                        <div className="text-[10px] text-zinc-500 mt-1">Buses may have already passed or are at the terminus</div>
                      </div>
                    )}
                  </div>
                )}

                {trackerLoading && (
                  <div className="flex items-center justify-center gap-2 py-6 text-zinc-400">
                    <RefreshCw className="w-5 h-5 animate-spin text-emerald-400" />
                    <span className="text-xs font-mono">Loading bus availability...</span>
                  </div>
                )}

                {trackerError && (
                  <div className="p-3 rounded-lg bg-rose-950/50 border border-rose-800 text-rose-300 text-xs flex items-center gap-2">
                    <AlertTriangle className="w-4 h-4 flex-shrink-0" />
                    <span>{trackerError}</span>
                  </div>
                )}
              </div>

              {/* Route Cards with Bus ETAs */}
              {trackerResult && trackerResult.routes_serving.length > 0 && (
                <div className="p-5 space-y-3 flex-1">
                  <div className="text-xs font-bold text-zinc-300 uppercase tracking-wider flex items-center gap-2">
                    <Route className="w-4 h-4 text-cyan-400" />
                    Routes & Approaching Buses
                  </div>

                  {trackerResult.routes_serving.map((route) => (
                    <div key={route.route_id} className="bg-zinc-950/70 rounded-xl border border-zinc-800 overflow-hidden transition-all hover:border-zinc-700">
                      {/* Route Header */}
                      <button
                        onClick={() => toggleRouteExpand(route.route_id)}
                        className="w-full p-3.5 flex items-center justify-between text-left transition-colors hover:bg-zinc-900/50"
                      >
                        <div className="flex items-center gap-3">
                          <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-cyan-600 to-blue-700 flex items-center justify-center shadow-md shadow-cyan-700/30">
                            <Bus className="w-4 h-4 text-white" />
                          </div>
                          <div>
                            <div className="text-sm font-bold text-white">{route.route_name}</div>
                            <div className="text-[10px] text-zinc-500 font-mono">{route.total_stops} stops • {route.buses.length} bus{route.buses.length !== 1 ? 'es' : ''} approaching</div>
                          </div>
                        </div>
                        <div className="flex items-center gap-2">
                          {route.buses.length > 0 && (
                            <div className={`px-2.5 py-1 rounded-full bg-gradient-to-r ${getEtaBadgeStyle(route.buses[0].eta_minutes)} text-white text-[11px] font-bold shadow font-mono`}>
                              ~{route.buses[0].eta_minutes}m
                            </div>
                          )}
                          {expandedRoutes.has(route.route_id) ? (
                            <ChevronUp className="w-4 h-4 text-zinc-500" />
                          ) : (
                            <ChevronDown className="w-4 h-4 text-zinc-500" />
                          )}
                        </div>
                      </button>

                      {/* Expanded Bus List */}
                      {expandedRoutes.has(route.route_id) && (
                        <div className="border-t border-zinc-800/80 bg-zinc-900/30">
                          {route.buses.length === 0 ? (
                            <div className="p-4 text-center text-xs text-zinc-500 font-mono">
                              No buses currently approaching on this route
                            </div>
                          ) : (
                            <div className="divide-y divide-zinc-800/50">
                              {route.buses.map((bus, busIdx) => (
                                <div key={bus.identifier} className="p-3.5 hover:bg-zinc-800/30 transition-colors">
                                  <div className="flex items-center justify-between">
                                    <div className="flex items-center gap-2.5">
                                      {/* Bus Index Badge */}
                                      <div className={`w-7 h-7 rounded-full flex items-center justify-center text-[10px] font-bold ${
                                        busIdx === 0 
                                          ? 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/40' 
                                          : 'bg-zinc-800 text-zinc-400 border border-zinc-700'
                                      }`}>
                                        {busIdx + 1}
                                      </div>
                                      <div>
                                        <div className="flex items-center gap-2">
                                          <span className="text-xs font-bold text-white font-mono">{bus.identifier}</span>
                                          <span className={`text-[9px] px-1.5 py-0.5 rounded-full border font-bold ${getStatusBadge(bus.status)}`}>
                                            {bus.status}
                                          </span>
                                        </div>
                                        <div className="text-[10px] text-zinc-500 mt-0.5 flex items-center gap-1.5">
                                          <MapPin className="w-3 h-3" />
                                          Near {bus.current_stop}
                                        </div>
                                      </div>
                                    </div>

                                    {/* ETA Badge */}
                                    <div className={`px-3 py-1.5 rounded-xl bg-gradient-to-r ${getEtaBadgeStyle(bus.eta_minutes)} text-white font-extrabold shadow-lg text-sm font-mono flex items-center gap-1.5`}>
                                      <Timer className="w-3.5 h-3.5" />
                                      ~{bus.eta_minutes}m
                                    </div>
                                  </div>

                                  {/* Bus Details Row */}
                                  <div className="mt-2.5 grid grid-cols-3 gap-2 text-[10px] font-mono">
                                    <div className="bg-zinc-950/60 rounded-lg p-2 border border-zinc-800/60">
                                      <div className="text-zinc-500 uppercase">Distance</div>
                                      <div className="text-cyan-400 font-bold mt-0.5">{bus.distance_remaining_km} km</div>
                                    </div>
                                    <div className="bg-zinc-950/60 rounded-lg p-2 border border-zinc-800/60">
                                      <div className="text-zinc-500 uppercase">Stops Away</div>
                                      <div className="text-blue-400 font-bold mt-0.5 flex items-center gap-1">
                                        <Footprints className="w-3 h-3" />
                                        {bus.stops_away}
                                      </div>
                                    </div>
                                    <div className="bg-zinc-950/60 rounded-lg p-2 border border-zinc-800/60">
                                      <div className="text-zinc-500 uppercase">Occupancy</div>
                                      <div className={`font-bold mt-0.5 flex items-center gap-1 ${getOccupancyColor(bus.occupancy, bus.capacity)}`}>
                                        <Users className="w-3 h-3" />
                                        {bus.occupancy}/{bus.capacity}
                                      </div>
                                    </div>
                                  </div>

                                  {/* Occupancy Bar */}
                                  <div className="mt-2">
                                    <div className="w-full h-1.5 bg-zinc-800 rounded-full overflow-hidden">
                                      <div
                                        className={`h-full rounded-full transition-all duration-500 ${getOccupancyBg(bus.occupancy, bus.capacity)}`}
                                        style={{ width: `${Math.min(100, (bus.occupancy / bus.capacity) * 100)}%` }}
                                      ></div>
                                    </div>
                                  </div>

                                  {/* Intermediate Stops (collapsible) */}
                                  {bus.intermediate_stops.length > 0 && (
                                    <div className="mt-2 text-[10px] text-zinc-500">
                                      <span className="text-zinc-400">Via: </span>
                                      {bus.intermediate_stops.join(' → ')} → <span className="text-emerald-400 font-bold">{trackerResult.stop.name}</span>
                                    </div>
                                  )}
                                </div>
                              ))}
                            </div>
                          )}
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </>
          )}
        </div>

        {/* Right Map Canvas */}
        <div className="flex-1 relative w-full h-[400px] md:h-full bg-zinc-950">
          <Map
            ref={mapRef}
            {...viewState}
            onMove={evt => setViewState(evt.viewState)}
            mapStyle={MAP_STYLE}
            style={{ width: '100%', height: '100%' }}
          >
            {/* === ROUTE PLANNER MAP LAYERS === */}
            {activeTab === 'ROUTE_PLANNER' && (
              <>
                {/* Direct Route (Shown in dotted red/amber if available for contrast) */}
                {directRouteGeoJSON && routeResult?.hurdle_clearance?.hurdles_bypassed_count > 0 && (
                  <Source id="direct-route" type="geojson" data={directRouteGeoJSON}>
                    <Layer
                      id="direct-route-line"
                      type="line"
                      paint={{
                        'line-color': '#f43f5e',
                        'line-width': 3,
                        'line-dasharray': [2, 2],
                        'line-opacity': 0.7
                      }}
                    />
                  </Source>
                )}

                {/* Optimal Hurdle-Free Route (Glow & Cyan Line) */}
                {optimalRouteGeoJSON && (
                  <Source id="optimal-route" type="geojson" data={optimalRouteGeoJSON}>
                    {/* Glow layer */}
                    <Layer
                      id="optimal-route-glow"
                      type="line"
                      paint={{
                        'line-color': '#06b6d4',
                        'line-width': 8,
                        'line-opacity': 0.4,
                        'line-blur': 3
                      }}
                    />
                    {/* Core line */}
                    <Layer
                      id="optimal-route-core"
                      type="line"
                      paint={{
                        'line-color': '#22d3ee',
                        'line-width': 4,
                        'line-opacity': 1.0
                      }}
                    />
                  </Source>
                )}

                {/* Active Hurdles / Hazard Markers */}
                {routeResult?.hurdle_clearance?.active_network_hurdles?.map((h: any) => (
                  <Marker key={h.id} longitude={h.location[0]} latitude={h.location[1]} anchor="center">
                    <div className="flex flex-col items-center group cursor-pointer">
                      <div className="w-8 h-8 rounded-full bg-rose-600/90 text-white flex items-center justify-center shadow-lg shadow-rose-600/50 border-2 border-white animate-bounce">
                        <AlertTriangle className="w-4 h-4" />
                      </div>
                      <div className="bg-zinc-900 border border-rose-600 text-rose-300 text-[10px] font-bold px-2 py-0.5 rounded shadow mt-1 whitespace-nowrap">
                        ROAD BLOCK
                      </div>
                    </div>
                  </Marker>
                ))}

                {/* Selected Bus Marker */}
                {selectedBus && selectedBus.lat && selectedBus.lon && (
                  <Marker longitude={selectedBus.lon} latitude={selectedBus.lat} anchor="center">
                    <div className="relative flex flex-col items-center">
                      <span className="absolute -top-1 w-9 h-9 rounded-full bg-cyan-400/40 animate-ping"></span>
                      <div className="relative w-8 h-8 rounded-full bg-cyan-500 text-zinc-950 border-2 border-white flex items-center justify-center shadow-lg shadow-cyan-500/50">
                        <Bus className="w-4 h-4 text-zinc-950" />
                      </div>
                      <div className="bg-zinc-900/90 text-cyan-300 text-[10px] font-mono font-bold px-2 py-0.5 rounded-full border border-cyan-500/40 shadow mt-1 whitespace-nowrap">
                        {selectedBus.identifier}
                      </div>
                    </div>
                  </Marker>
                )}

                {/* Start Stop Marker */}
                {routeResult?.start_stop && (
                  <Marker longitude={routeResult.start_stop.lon} latitude={routeResult.start_stop.lat} anchor="bottom">
                    <div className="flex flex-col items-center">
                      <div className="w-6 h-6 rounded-full bg-blue-500 text-white flex items-center justify-center border-2 border-white shadow-lg">
                        <MapPin className="w-3.5 h-3.5" />
                      </div>
                      <div className="bg-zinc-900/90 text-blue-300 text-[10px] font-bold px-1.5 py-0.5 rounded border border-blue-500/40 mt-0.5 whitespace-nowrap">
                        Start: {routeResult.start_stop.name}
                      </div>
                    </div>
                  </Marker>
                )}

                {/* Target Stop Marker */}
                {routeResult?.target_stop && (
                  <Marker longitude={routeResult.target_stop.lon} latitude={routeResult.target_stop.lat} anchor="bottom">
                    <div className="flex flex-col items-center">
                      <div className="w-7 h-7 rounded-full bg-emerald-500 text-white flex items-center justify-center border-2 border-white shadow-lg shadow-emerald-500/50">
                        <CheckCircle2 className="w-4 h-4" />
                      </div>
                      <div className="bg-zinc-900/90 text-emerald-300 text-[10px] font-bold px-2 py-0.5 rounded border border-emerald-500/40 mt-0.5 whitespace-nowrap">
                        Destination: {routeResult.target_stop.name}
                      </div>
                    </div>
                  </Marker>
                )}
              </>
            )}

            {/* === BUS TRACKER MAP LAYERS === */}
            {activeTab === 'BUS_TRACKER' && trackerResult && (
              <>
                {/* Selected Stop — Pulsing Marker */}
                <Marker longitude={trackerResult.stop.lon} latitude={trackerResult.stop.lat} anchor="center">
                  <div className="relative flex flex-col items-center">
                    <span className="absolute w-14 h-14 rounded-full bg-emerald-400/20 animate-ping"></span>
                    <span className="absolute w-10 h-10 rounded-full bg-emerald-400/30 animate-pulse"></span>
                    <div className="relative w-9 h-9 rounded-full bg-gradient-to-br from-emerald-500 to-cyan-500 text-white border-2 border-white flex items-center justify-center shadow-lg shadow-emerald-500/50 z-10">
                      <MapPinned className="w-5 h-5" />
                    </div>
                    <div className="bg-zinc-900/95 text-emerald-300 text-[11px] font-bold px-3 py-1 rounded-lg border border-emerald-500/50 shadow-lg mt-1.5 whitespace-nowrap z-10">
                      📍 {trackerResult.stop.name}
                    </div>
                  </div>
                </Marker>

                {/* Approaching Buses Markers */}
                {trackerResult.routes_serving.flatMap(route =>
                  route.buses.map((bus) => (
                    <Marker key={`tracker-bus-${bus.identifier}`} longitude={bus.lon} latitude={bus.lat} anchor="center">
                      <div className="relative flex flex-col items-center group cursor-pointer">
                        <div className="relative w-8 h-8 rounded-full bg-cyan-600 text-white border-2 border-white flex items-center justify-center shadow-lg shadow-cyan-600/40 group-hover:scale-110 transition-transform">
                          <Bus className="w-4 h-4" />
                        </div>
                        <div className="bg-zinc-900/95 text-cyan-300 text-[9px] font-mono font-bold px-2 py-0.5 rounded-full border border-cyan-500/40 shadow mt-1 whitespace-nowrap flex items-center gap-1">
                          {bus.identifier}
                          <span className={`px-1 py-0 rounded text-[8px] ${
                            bus.eta_minutes <= 5 ? 'bg-emerald-500/30 text-emerald-300' : 'bg-blue-500/30 text-blue-300'
                          }`}>
                            ~{bus.eta_minutes}m
                          </span>
                        </div>
                      </div>
                    </Marker>
                  ))
                )}
              </>
            )}
          </Map>

          {/* Map Overlay Legend & Quick Stats */}
          <div className="absolute top-4 right-4 bg-zinc-950/80 backdrop-blur-md p-3 rounded-xl border border-zinc-800 text-xs font-mono space-y-1.5 shadow-xl">
            {activeTab === 'ROUTE_PLANNER' ? (
              <>
                <div className="text-[10px] font-bold text-zinc-400 uppercase tracking-wider mb-1">Route Legend</div>
                <div className="flex items-center gap-2">
                  <span className="w-3.5 h-1 bg-cyan-400 rounded"></span>
                  <span className="text-zinc-300 text-[11px]">Optimal Hurdle-Free Route</span>
                </div>
                {routeResult?.hurdle_clearance?.hurdles_bypassed_count > 0 && (
                  <div className="flex items-center gap-2">
                    <span className="w-3.5 h-1 bg-rose-500 rounded border-dashed"></span>
                    <span className="text-rose-400 text-[11px]">Blocked Direct Path (Detoured)</span>
                  </div>
                )}
                <div className="flex items-center gap-2">
                  <span className="w-2.5 h-2.5 rounded-full bg-rose-500"></span>
                  <span className="text-zinc-400 text-[11px]">Road Block / Hazard</span>
                </div>
              </>
            ) : (
              <>
                <div className="text-[10px] font-bold text-zinc-400 uppercase tracking-wider mb-1">Bus Tracker Legend</div>
                <div className="flex items-center gap-2">
                  <span className="w-3 h-3 rounded-full bg-gradient-to-br from-emerald-500 to-cyan-500 border border-white/50"></span>
                  <span className="text-emerald-300 text-[11px]">Selected Stop</span>
                </div>
                <div className="flex items-center gap-2">
                  <span className="w-3 h-3 rounded-full bg-cyan-600 border border-white/50"></span>
                  <span className="text-cyan-300 text-[11px]">Approaching Bus</span>
                </div>
                {trackerResult && (
                  <div className="mt-1 pt-1 border-t border-zinc-700/50 text-[10px] text-zinc-400">
                    {trackerResult.total_buses_approaching} bus{trackerResult.total_buses_approaching !== 1 ? 'es' : ''} en route
                  </div>
                )}
              </>
            )}
          </div>

          {/* Bus Tracker Auto-Refresh Indicator */}
          {activeTab === 'BUS_TRACKER' && trackerStopId && (
            <div className="absolute bottom-4 right-4 bg-zinc-950/80 backdrop-blur-md px-3 py-1.5 rounded-lg border border-zinc-800 text-[10px] font-mono text-zinc-400 flex items-center gap-1.5">
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse"></span>
              Auto-refreshing every 10s
            </div>
          )}
        </div>
      </div>

      {/* Emergency SOS Button — always visible on Navigator */}
      <EmergencySOS />
    </div>
  );
}
