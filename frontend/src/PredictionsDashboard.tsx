import { useState, useEffect } from 'react';

interface PredictionsDashboardProps {
  onNavigate: (page: 'LANDING' | 'NAVIGATOR' | 'COMMAND_CENTER' | 'PREDICTIONS' | 'REROUTING') => void;
}

interface StationAlert {
  id: string | number;
  name: string;
  type: string;
  severity: 'CRITICAL' | 'WARNING' | 'NOMINAL' | 'INFO';
  etaMinutes: number;
  actionText: string;
  current_queue?: number;
  capacity?: number;
  lambda_base?: number;
  e_event?: number;
  mu_boarding?: number;
  net_arrival_rate?: number;
  predicted_crowd_15m?: number;
  predicted_crowd_60m?: number;
  incomingPax: number;
  incomingStatus: string;
  incomingRatio: number;
  departingPax: number;
  departingStatus: string;
  departingRatio: number;
  delayed_buses_count?: number;
}

const DEFAULT_STATIONS: StationAlert[] = [
  {
    id: 'north-park',
    name: 'North Park',
    type: 'Overcrowding Predicted',
    severity: 'CRITICAL',
    etaMinutes: 12,
    actionText: 'Redirect Bus',
    current_queue: 85,
    capacity: 120,
    lambda_base: 18.0,
    e_event: 3.56,
    mu_boarding: 0.0,
    net_arrival_rate: 64.08,
    predicted_crowd_15m: 450,
    predicted_crowd_60m: 890,
    incomingPax: 450,
    incomingStatus: 'High Volume',
    incomingRatio: 85,
    departingPax: 0,
    departingStatus: 'Blocked / Delayed',
    departingRatio: 5,
    delayed_buses_count: 2,
  },
  {
    id: 'central-station',
    name: 'Central Station',
    type: 'Platform Capacity Warning',
    severity: 'CRITICAL',
    etaMinutes: 18,
    actionText: 'Increase Frequency',
    current_queue: 110,
    capacity: 200,
    lambda_base: 24.0,
    e_event: 2.85,
    mu_boarding: 12.0,
    net_arrival_rate: 56.4,
    predicted_crowd_15m: 620,
    predicted_crowd_60m: 1150,
    incomingPax: 620,
    incomingStatus: 'Surge Capacity',
    incomingRatio: 92,
    departingPax: 280,
    departingStatus: 'High Volume',
    departingRatio: 65,
    delayed_buses_count: 1,
  },
  {
    id: 'westlake-hub',
    name: 'Westlake Hub',
    type: 'Elevated Load',
    severity: 'WARNING',
    etaMinutes: 45,
    actionText: 'Review Plan',
    current_queue: 45,
    capacity: 100,
    lambda_base: 12.0,
    e_event: 1.65,
    mu_boarding: 14.0,
    net_arrival_rate: 5.8,
    predicted_crowd_15m: 310,
    predicted_crowd_60m: 420,
    incomingPax: 310,
    incomingStatus: 'Moderate',
    incomingRatio: 55,
    departingPax: 190,
    departingStatus: 'Moderate',
    departingRatio: 45,
    delayed_buses_count: 0,
  },
];

export default function PredictionsDashboard({ onNavigate }: PredictionsDashboardProps) {
  const [currentTime, setCurrentTime] = useState<string>('');
  const [stations, setStations] = useState<StationAlert[]>(DEFAULT_STATIONS);
  const [selectedStation, setSelectedStation] = useState<StationAlert>(DEFAULT_STATIONS[0]);
  const [liveMode, setLiveMode] = useState(true);
  const [systemHealth, setSystemHealth] = useState('Nominal');
  const [activePredictionsCount, setActivePredictionsCount] = useState(14);
  const [criticalAlertsCount, setCriticalAlertsCount] = useState(2);
  const [showFormulaModal, setShowFormulaModal] = useState(false);

  // Live UTC Clock
  useEffect(() => {
    const updateTime = () => {
      const now = new Date();
      const utcString = now.toTimeString().split(' ')[0] + ' UTC';
      setCurrentTime(utcString);
    };
    updateTime();
    const interval = setInterval(updateTime, 1000);
    return () => clearInterval(interval);
  }, []);

  // Fetch real M/M/c and ML surge predictions from backend
  useEffect(() => {
    const fetchPredictions = () => {
      fetch('/api/v1/predictions/early-warnings/')
        .then(res => res.json())
        .then(data => {
          if (data.stations && data.stations.length > 0) {
            setStations(data.stations);
            if (data.system_health) setSystemHealth(data.system_health);
            if (data.active_predictions_count) setActivePredictionsCount(data.active_predictions_count);
            if (data.critical_alerts_count) setCriticalAlertsCount(data.critical_alerts_count);

            // Keep selected station up to date
            setSelectedStation(prev => {
              const matched = data.stations.find((s: StationAlert) => s.id === prev.id);
              return matched || data.stations[0];
            });
          }
        })
        .catch(err => console.log('Using default M/M/c stations data:', err));
    };

    fetchPredictions();
    const poll = setInterval(fetchPredictions, 10000);
    return () => clearInterval(poll);
  }, []);

  const handleAction = (st: StationAlert) => {
    if (st.actionText === 'Redirect Bus') {
      onNavigate('NAVIGATOR');
    } else {
      onNavigate('COMMAND_CENTER');
    }
  };

  return (
    <div className="bg-background text-on-surface font-body-md min-h-screen flex overflow-hidden select-none">
      {/* ========================================================= */}
      {/* Left Sidebar Rail (80px wide - Material Design 3) */}
      {/* ========================================================= */}
      <nav className="w-[80px] bg-surface-container-low/70 backdrop-blur-xl border-r border-outline-variant/20 shadow-2xl fixed left-0 top-0 h-full flex flex-col items-center py-6 z-50">
        {/* Top Logo */}
        <button
          onClick={() => onNavigate('LANDING')}
          className="mb-8 w-11 h-11 bg-primary-container rounded-2xl flex items-center justify-center hover:scale-105 transition-all shadow-[0_0_15px_rgba(211,227,253,0.3)] cursor-pointer border-none"
          title="Back to TransitTwin Home"
        >
          <span className="material-symbols-outlined text-on-primary-container text-2xl font-bold">transit_enterexit</span>
        </button>

        {/* Navigation Items */}
        <div className="flex-1 w-full flex flex-col items-center space-y-6">
          {/* Live Map / Navigator */}
          <button
            onClick={() => onNavigate('NAVIGATOR')}
            className="w-13 h-13 flex flex-col items-center justify-center text-on-surface-variant/60 hover:text-on-surface hover:bg-surface-bright/50 transition-all rounded-2xl cursor-pointer border-none bg-transparent p-3"
            title="Live Map & Smart Bus Navigator"
          >
            <span className="material-symbols-outlined text-[26px]">map</span>
          </button>

          {/* Predictions (Active item with pill glow) */}
          <button
            onClick={() => onNavigate('PREDICTIONS')}
            className="w-13 h-13 flex flex-col items-center justify-center bg-primary-container text-on-primary-container rounded-2xl shadow-[0_0_18px_rgba(169,200,251,0.4)] transition-all p-3 cursor-pointer border-none"
            title="Predictions Dashboard (Active)"
          >
            <span className="material-symbols-outlined text-[26px]">group_work</span>
          </button>

          {/* Disruptions */}
          <button
            onClick={() => onNavigate('COMMAND_CENTER')}
            className="w-13 h-13 flex flex-col items-center justify-center text-on-surface-variant/60 hover:text-on-surface hover:bg-surface-bright/50 transition-all rounded-2xl cursor-pointer border-none bg-transparent p-3"
            title="Command Center Disruptions"
          >
            <span className="material-symbols-outlined text-[26px]">warning</span>
          </button>

          {/* Rerouting Pre-Action Sandbox */}
          <button
            onClick={() => onNavigate('REROUTING')}
            className="w-13 h-13 flex flex-col items-center justify-center text-on-surface-variant/60 hover:text-on-surface hover:bg-surface-bright/50 transition-all rounded-2xl cursor-pointer border-none bg-transparent p-3"
            title="Rerouting Sandbox"
          >
            <span className="material-symbols-outlined text-[26px]">alt_route</span>
          </button>
        </div>

        {/* Bottom Settings Icon */}
        <div className="mt-auto flex flex-col items-center">
          <button
            onClick={() => setShowFormulaModal(!showFormulaModal)}
            className="w-11 h-11 flex items-center justify-center text-on-surface-variant/60 hover:text-on-surface hover:bg-surface-bright/50 transition-all rounded-full bg-surface-container-highest cursor-pointer border-none"
            title="View Queueing Dynamics & ML Model Specs"
          >
            <span className="material-symbols-outlined text-xl">functions</span>
          </button>
        </div>
      </nav>

      {/* ========================================================= */}
      {/* Top Navigation Bar */}
      {/* ========================================================= */}
      <header className="fixed top-0 left-0 right-0 h-16 flex justify-between items-center px-8 z-40 ml-[80px] bg-surface-container-lowest/70 backdrop-blur-lg border-b border-outline-variant/20">
        <div className="flex items-center gap-6">
          <div className="font-headline-sm text-lg font-black tracking-tight text-white flex items-center gap-2">
            <span>TransitTwin Digital Twin</span>
            <span className="text-[10px] bg-secondary/15 text-secondary border border-secondary/30 px-2 py-0.5 rounded-full font-mono font-medium">
              M/M/c + ML Engine
            </span>
          </div>
          <nav className="hidden lg:flex items-center gap-6 ml-6 h-full text-xs font-medium">
            <button
              onClick={() => onNavigate('NAVIGATOR')}
              className="text-on-surface-variant hover:text-primary transition-colors cursor-pointer bg-transparent border-none"
            >
              Network Overview
            </button>
            <button
              onClick={() => onNavigate('COMMAND_CENTER')}
              className="text-on-surface-variant hover:text-primary transition-colors cursor-pointer bg-transparent border-none"
            >
              Fleet Status
            </button>
          </nav>
        </div>

        <div className="flex items-center gap-5 font-mono">
          <span className="text-on-surface-variant text-xs tracking-wider">{currentTime || '12:45:02 UTC'}</span>
          <button
            onClick={() => setLiveMode(!liveMode)}
            className={`px-4 py-1.5 rounded-full text-xs font-bold transition-all flex items-center gap-2 border-none cursor-pointer ${
              liveMode
                ? 'bg-primary-container text-on-primary-container shadow-[0_0_12px_rgba(211,227,253,0.3)]'
                : 'bg-surface-container-high text-on-surface-variant'
            }`}
          >
            <span className={`w-2 h-2 rounded-full ${liveMode ? 'bg-secondary animate-pulse' : 'bg-zinc-500'}`}></span>
            Live Mode
          </button>
          <div className="flex items-center gap-3 text-on-surface-variant">
            <button className="hover:text-primary transition-colors cursor-pointer bg-transparent border-none p-1">
              <span className="material-symbols-outlined text-xl">notifications</span>
            </button>
            <button className="hover:text-primary transition-colors cursor-pointer bg-transparent border-none p-1">
              <span className="material-symbols-outlined text-xl">account_circle</span>
            </button>
          </div>
        </div>
      </header>

      {/* ========================================================= */}
      {/* Main Content Area */}
      {/* ========================================================= */}
      <main className="flex-1 ml-[80px] mt-16 p-6 lg:p-8 bg-surface overflow-y-auto w-full h-[calc(100vh-64px)]">
        <div className="max-w-[1550px] mx-auto flex flex-col gap-6">
          {/* Header & Math Info Strip */}
          <div className="flex flex-col md:flex-row justify-between items-start md:items-end gap-3">
            <div>
              <h1 className="text-2xl lg:text-3xl font-extrabold text-on-surface tracking-tight mb-1">
                Predictions Dashboard
              </h1>
              <p className="text-xs lg:text-sm text-on-surface-variant font-normal">
                System-wide forecast and priority actions for the next 60 minutes.
              </p>
            </div>

            {/* AI/ML & M/M/c Status Pill */}
            <div className="flex items-center gap-2 bg-surface-container px-3.5 py-1.5 rounded-full border border-outline-variant/20 text-[11px] font-mono text-on-surface-variant">
              <span className="w-1.5 h-1.5 rounded-full bg-secondary animate-pulse"></span>
              <span>Model: <b className="text-secondary">Random Forest (Scikit-Learn)</b></span>
              <span className="text-zinc-600">|</span>
              <span>Queue: <b className="text-primary">M/M/c Dynamic</b></span>
              <span className="text-zinc-600">|</span>
              <span>Cascade: <b className="text-success-tonal">NetworkX</b></span>
            </div>
          </div>

          {/* ===================================================== */}
          {/* Top Row: 3 High-Level Status Cards (MD3 Style) */}
          {/* ===================================================== */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            {/* Status Card 1: System Health */}
            <div className="bg-surface-container rounded-[24px] p-6 flex flex-col justify-between border border-outline-variant/10 relative overflow-hidden shadow-lg">
              <div className="absolute inset-0 bg-success-tonal/5"></div>
              <div className="flex justify-between items-start z-10">
                <span className="font-label-md text-xs font-mono text-on-surface-variant uppercase tracking-widest">
                  SYSTEM HEALTH
                </span>
                <div className="w-9 h-9 rounded-full bg-success-tonal/20 flex items-center justify-center">
                  <span className="material-symbols-outlined text-success-tonal text-lg">check_circle</span>
                </div>
              </div>
              <div className="mt-6 z-10">
                <div className="text-3xl lg:text-4xl font-normal text-success-tonal tracking-tight">
                  {systemHealth}
                </div>
                <div className="text-xs text-on-surface-variant mt-2 font-sans">
                  All major lines operating within capacity.
                </div>
              </div>
            </div>

            {/* Status Card 2: Active Predictions */}
            <div className="bg-surface-container rounded-[24px] p-6 flex flex-col justify-between border border-outline-variant/10 shadow-lg">
              <div className="flex justify-between items-start">
                <span className="font-label-md text-xs font-mono text-on-surface-variant uppercase tracking-widest">
                  ACTIVE PREDICTIONS
                </span>
                <div className="w-9 h-9 rounded-full bg-primary-container/20 flex items-center justify-center">
                  <span className="material-symbols-outlined text-primary-container text-lg">insights</span>
                </div>
              </div>
              <div className="mt-6">
                <div className="text-3xl lg:text-4xl font-normal text-on-surface tracking-tight">
                  {activePredictionsCount}
                </div>
                <div className="text-xs text-on-surface-variant mt-2 font-sans">
                  Potential crowding events in next hour.
                </div>
              </div>
            </div>

            {/* Status Card 3: Critical Alerts */}
            <div className="bg-surface-container rounded-[24px] p-6 flex flex-col justify-between border border-error/20 relative overflow-hidden shadow-lg">
              <div className="absolute inset-0 bg-error/5"></div>
              <div className="flex justify-between items-start z-10">
                <span className="font-label-md text-xs font-mono text-on-surface-variant uppercase tracking-widest">
                  CRITICAL ALERTS
                </span>
                <div className="w-9 h-9 rounded-full bg-error-tonal/20 flex items-center justify-center">
                  <span className="material-symbols-outlined text-error-tonal text-lg">warning</span>
                </div>
              </div>
              <div className="mt-6 z-10">
                <div className="text-3xl lg:text-4xl font-normal text-error tracking-tight">
                  {criticalAlertsCount}
                </div>
                <div className="text-xs text-error-tonal mt-2 font-sans font-medium">
                  Immediate action recommended.
                </div>
              </div>
            </div>
          </div>

          {/* ===================================================== */}
          {/* Middle Row: System Capacity Chart + Priority Action List */}
          {/* ===================================================== */}
          <div className="grid grid-cols-1 xl:grid-cols-3 gap-6 h-[410px]">
            {/* Occupancy Forecast Chart (Takes 2 Columns) */}
            <div className="xl:col-span-2 bg-surface-container rounded-[24px] p-6 border border-outline-variant/10 flex flex-col h-full shadow-lg">
              <div className="flex justify-between items-center mb-4">
                <div className="flex items-center gap-3">
                  <h2 className="text-base lg:text-lg font-medium text-on-surface">
                    System Capacity Forecast (60m)
                  </h2>
                  <span className="text-[10px] font-mono text-on-surface-variant/60 bg-surface-dim px-2 py-0.5 rounded border border-outline-variant/10">
                    M/M/c Step: Δt=15m
                  </span>
                </div>
                <div className="flex items-center gap-5 text-xs font-mono">
                  <div className="flex items-center gap-2">
                    <div className="w-2.5 h-2.5 rounded-full bg-secondary"></div>
                    <span className="text-on-surface-variant">Predicted Load</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <div className="w-6 h-0.5 border-t-2 border-dashed border-error-tonal"></div>
                    <span className="text-on-surface-variant">Safe Threshold</span>
                  </div>
                </div>
              </div>

              {/* Smooth Vector Forecast Chart Container */}
              <div className="flex-1 relative w-full rounded-2xl bg-surface-container-highest/30 border border-outline-variant/5 overflow-hidden flex items-center justify-center p-2">
                <div className="absolute inset-0 bg-gradient-to-t from-primary-container/5 to-transparent"></div>

                <svg className="w-full h-full" preserveAspectRatio="none" viewBox="0 0 800 240">
                  <defs>
                    <linearGradient id="areaGradient" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="0%" stopColor="#a9c8fb" stopOpacity="0.3" />
                      <stop offset="100%" stopColor="#a9c8fb" stopOpacity="0.02" />
                    </linearGradient>
                  </defs>

                  {/* Shaded Area */}
                  <path
                    d="M 0,180 C 120,165 200,90 320,110 C 440,130 520,200 640,160 C 720,120 760,85 800,70 L 800,240 L 0,240 Z"
                    fill="url(#areaGradient)"
                  />

                  {/* Smooth Forecast Wave matching screenshot */}
                  <path
                    d="M 0,180 C 120,165 200,90 320,110 C 440,130 520,200 640,160 C 720,120 760,85 800,70"
                    fill="none"
                    stroke="#a9c8fb"
                    strokeWidth="3.5"
                    strokeLinecap="round"
                  />

                  {/* Safe Threshold Horizontal Dashed Line */}
                  <line
                    x1="0"
                    y1="85"
                    x2="800"
                    y2="85"
                    stroke="#F2B8B5"
                    strokeWidth="2"
                    strokeDasharray="6,4"
                  />

                  {/* Grid Lines */}
                  <line x1="0" y1="160" x2="800" y2="160" stroke="#ffffff" strokeOpacity="0.04" strokeWidth="1" />
                  <line x1="200" y1="0" x2="200" y2="240" stroke="#ffffff" strokeOpacity="0.04" strokeWidth="1" />
                  <line x1="400" y1="0" x2="400" y2="240" stroke="#ffffff" strokeOpacity="0.04" strokeWidth="1" />
                  <line x1="600" y1="0" x2="600" y2="240" stroke="#ffffff" strokeOpacity="0.04" strokeWidth="1" />
                </svg>

                {/* Timeline axis labels */}
                <div className="absolute bottom-2 left-6 right-6 flex justify-between text-[10px] font-mono text-on-surface-variant/40">
                  <span>+0m (Now)</span>
                  <span>+15m (dt)</span>
                  <span>+30m</span>
                  <span>+45m</span>
                  <span>+60m (Horizon)</span>
                </div>
              </div>
            </div>

            {/* Top Priority Stations (Takes 1 Column) */}
            <div className="bg-surface-container rounded-[24px] p-6 border border-outline-variant/10 flex flex-col h-full overflow-hidden shadow-lg">
              <div className="flex justify-between items-center mb-4">
                <h2 className="text-base font-medium text-on-surface">
                  Top Priority Stations
                </h2>
                <span className="bg-error/15 text-error px-2.5 py-0.5 rounded-md text-[11px] font-mono font-bold">
                  {criticalAlertsCount} Critical
                </span>
              </div>

              <div className="flex-1 overflow-y-auto pr-1 space-y-3.5 custom-scrollbar">
                {stations.slice(0, 10).map(st => {
                  const isSelected = selectedStation?.id === st.id;
                  const isCritical = st.severity === 'CRITICAL';

                  return (
                    <div
                      key={st.id}
                      onClick={() => setSelectedStation(st)}
                      className={`rounded-2xl p-4 transition-all cursor-pointer border ${
                        isSelected
                          ? 'bg-surface-container-highest border-primary-container/50 shadow-md'
                          : isCritical
                          ? 'bg-surface-container-highest/80 border-error/30 hover:border-error/50'
                          : 'bg-surface-container-highest/50 border-outline-variant/20 hover:border-outline-variant/40'
                      }`}
                    >
                      <div className="flex justify-between items-start mb-2">
                        <div>
                          <div className="flex items-center gap-2">
                            <h3 className="text-sm font-semibold text-on-surface">{st.name}</h3>
                            {st.e_event && st.e_event > 1.5 && (
                              <span className="text-[9px] font-mono bg-secondary/15 text-secondary px-1.5 py-0.5 rounded">
                                {st.e_event}x Surge
                              </span>
                            )}
                          </div>
                          <p className={`text-xs mt-0.5 ${isCritical ? 'text-error-tonal' : 'text-warning-tonal'}`}>
                            {st.type}
                          </p>
                        </div>
                        <div className="bg-surface-dim/80 px-2.5 py-1 rounded-full border border-outline-variant/20 font-mono text-[10px] text-on-surface-variant">
                          In {st.etaMinutes} mins
                        </div>
                      </div>

                      {/* Action Button */}
                      <div className="mt-3">
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            handleAction(st);
                          }}
                          className="w-full bg-primary-container hover:bg-primary-fixed text-on-primary-container py-2 rounded-full text-xs font-bold font-sans transition-all flex items-center justify-center gap-1.5 shadow-sm active:scale-98 border-none cursor-pointer"
                        >
                          {st.actionText}
                        </button>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          </div>

          {/* ===================================================== */}
          {/* Bottom Row: Selected Station Detail Panel with M/M/c Equation */}
          {/* ===================================================== */}
          <div className="bg-surface-container rounded-[24px] p-6 border border-outline-variant/10 shadow-lg">
            <div className="flex flex-col lg:flex-row justify-between items-start lg:items-center gap-6">
              {/* Station Info & M/M/c Equation Breakdown */}
              <div className="lg:w-1/3">
                <div className="flex items-center gap-2 mb-1">
                  <span className="font-mono text-[10px] text-on-surface-variant uppercase tracking-widest block">
                    SELECTED DETAIL
                  </span>
                  <span className="text-[9px] font-mono bg-primary-container/20 text-primary-fixed-dim px-2 py-0.5 rounded">
                    M/M/c Formula
                  </span>
                </div>
                <h2 className="text-xl font-bold text-on-surface">{selectedStation.name}</h2>
                <p className="text-xs text-on-surface-variant mt-1">
                  Predicted flow breakdown over the next 15 minutes.
                </p>

                {/* Live Equation Parameters */}
                <div className="mt-3 grid grid-cols-3 gap-2 bg-surface-dim/70 p-2.5 rounded-xl border border-outline-variant/15 text-[11px] font-mono">
                  <div>
                    <div className="text-zinc-400 text-[10px]">λ_base</div>
                    <div className="text-white font-bold">{selectedStation.lambda_base || 18.0} <span className="text-[9px] text-zinc-500">pax/m</span></div>
                  </div>
                  <div>
                    <div className="text-zinc-400 text-[10px]">E_event (ML)</div>
                    <div className="text-secondary font-bold">{selectedStation.e_event || 3.56}x</div>
                  </div>
                  <div>
                    <div className="text-zinc-400 text-[10px]">μ_boarding</div>
                    <div className={selectedStation.mu_boarding === 0 ? "text-error font-bold" : "text-success-tonal font-bold"}>
                      {selectedStation.mu_boarding ?? 0.0} <span className="text-[9px] text-zinc-500">pax/m</span>
                    </div>
                  </div>
                </div>
              </div>

              {/* Progress Gauges Grid */}
              <div className="flex-1 grid grid-cols-1 md:grid-cols-2 gap-4 w-full">
                {/* Incoming Passengers Flow */}
                <div className="bg-surface-container-highest p-4 rounded-2xl border border-outline-variant/10">
                  <div className="flex justify-between items-center mb-2">
                    <span className="text-xs text-on-surface flex items-center gap-1.5 font-medium">
                      <span className="material-symbols-outlined text-warning-tonal text-base">login</span>
                      Incoming Passengers (λ · E_event · Δt)
                    </span>
                    <span className="text-[11px] font-mono text-warning-tonal font-medium">
                      {selectedStation.incomingStatus}
                    </span>
                  </div>
                  <div className="w-full bg-surface-dim rounded-full h-2.5 mb-1.5 overflow-hidden">
                    <div
                      className="bg-warning-tonal h-full rounded-full transition-all duration-500"
                      style={{ width: `${selectedStation.incomingRatio}%` }}
                    ></div>
                  </div>
                  <div className="flex justify-between items-center font-mono text-[10px] text-on-surface-variant">
                    <span>Rate: {((selectedStation.lambda_base || 18.0) * (selectedStation.e_event || 3.56)).toFixed(1)} pax/min</span>
                    <span>+{selectedStation.incomingPax} expected</span>
                  </div>
                </div>

                {/* Departing Passengers Flow */}
                <div className="bg-surface-container-highest p-4 rounded-2xl border border-outline-variant/10">
                  <div className="flex justify-between items-center mb-2">
                    <span className="text-xs text-on-surface flex items-center gap-1.5 font-medium">
                      <span className="material-symbols-outlined text-success-tonal text-base">logout</span>
                      Departing Passengers (μ · Δt)
                    </span>
                    <span className={`text-[11px] font-mono font-medium ${selectedStation.mu_boarding === 0 ? 'text-error' : 'text-success-tonal'}`}>
                      {selectedStation.departingStatus}
                    </span>
                  </div>
                  <div className="w-full bg-surface-dim rounded-full h-2.5 mb-1.5 overflow-hidden">
                    <div
                      className={`h-full rounded-full transition-all duration-500 ${selectedStation.mu_boarding === 0 ? 'bg-error' : 'bg-success-tonal'}`}
                      style={{ width: `${Math.max(5, selectedStation.departingRatio)}%` }}
                    ></div>
                  </div>
                  <div className="flex justify-between items-center font-mono text-[10px] text-on-surface-variant">
                    <span>{selectedStation.mu_boarding === 0 ? 'μ = 0 (Bus Delayed / Incident)' : `Rate: ${selectedStation.mu_boarding} pax/min`}</span>
                    <span>-{selectedStation.departingPax} expected</span>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </main>

      {/* ========================================================= */}
      {/* Formula & Architecture Modal (Click function button in sidebar) */}
      {/* ========================================================= */}
      {showFormulaModal && (
        <div className="fixed inset-0 z-50 bg-black/70 backdrop-blur-md flex items-center justify-center p-6">
          <div className="bg-surface-container border border-outline-variant/30 rounded-3xl p-8 max-w-2xl w-full shadow-2xl space-y-6">
            <div className="flex justify-between items-start">
              <div>
                <h3 className="text-xl font-bold text-white">Queueing Dynamics & AI/ML Specifications</h3>
                <p className="text-xs text-on-surface-variant mt-1">Mathematical formulations powering TransitTwin predictions</p>
              </div>
              <button
                onClick={() => setShowFormulaModal(false)}
                className="w-8 h-8 rounded-full bg-surface-container-high flex items-center justify-center text-zinc-400 hover:text-white cursor-pointer border-none"
              >
                ✕
              </button>
            </div>

            <div className="space-y-4 text-xs">
              <div className="bg-surface-dim p-4 rounded-2xl border border-outline-variant/20 space-y-2">
                <div className="font-bold text-secondary text-sm">1. Station Crowd Prediction (M/M/c Queueing Dynamic Formula)</div>
                <div className="font-mono text-primary bg-zinc-950 p-2.5 rounded-lg border border-zinc-800">
                  Crowd(t + Δt) = max( 0, Crowd(t) + (λ_base · E_event - μ_boarding) · Δt )
                </div>
                <ul className="list-disc pl-4 space-y-1 text-zinc-300">
                  <li><b>λ_base</b>: Baseline passenger arrival rate derived from time-of-day ticketing rates.</li>
                  <li><b>E_event</b>: Event surge multiplier predicted by the Scikit-learn Random Forest model.</li>
                  <li><b>μ_boarding</b>: Boarding throughput. Drops to <b>0</b> when buses are delayed, automatically spiking station crowd.</li>
                </ul>
              </div>

              <div className="bg-surface-dim p-4 rounded-2xl border border-outline-variant/20 space-y-2">
                <div className="font-bold text-success-tonal text-sm">2. Disruption Delay Cascade (NetworkX Speed Degradation)</div>
                <div className="font-mono text-primary bg-zinc-950 p-2.5 rounded-lg border border-zinc-800">
                  T_delay(v) = Σ_&#123;e ∈ Path(v)&#125; [ Distance(e)/V_congested(e) - Distance(e)/V_free_flow(e) ]
                </div>
                <p className="text-zinc-300">Propagates downstream traffic slowdowns across the route graph using NetworkX to compute arrival delays and boarding starvation.</p>
              </div>

              <div className="bg-surface-dim p-4 rounded-2xl border border-outline-variant/20 space-y-2">
                <div className="font-bold text-primary-fixed-dim text-sm">3. Lightweight AI/ML Random Forest Model</div>
                <p className="text-zinc-300">Trained on 1,000 synthetic transit observations with features: <code className="text-secondary bg-zinc-900 px-1 py-0.5 rounded">[hour_of_day, is_weekend, event_size_nearby, current_traffic_congestion_pct, scheduled_headway_min]</code></p>
              </div>
            </div>

            <div className="pt-2 flex justify-end">
              <button
                onClick={() => setShowFormulaModal(false)}
                className="bg-primary-container text-on-primary-container px-6 py-2.5 rounded-full font-bold text-xs cursor-pointer border-none hover:bg-primary-fixed"
              >
                Close Specifications
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
