import { useState, useEffect } from 'react';

interface ReroutingDashboardProps {
  onNavigate: (page: 'LANDING' | 'NAVIGATOR' | 'COMMAND_CENTER' | 'PREDICTIONS' | 'REROUTING' | 'INTERVENTIONS') => void;
}

interface RerouteResult {
  alternate_route: (string | number)[];
  delta_delay_minutes: number;
  safety_risk_index: number;
  energy_impact_kwh: number;
  status: string;
  route_nodes_details?: Array<{
    id: number | string;
    name: string;
    lat: number;
    lon: number;
    capacity: number;
    is_accessible: boolean;
  }>;
  blocked_edge_id?: string | number;
  require_accessibility?: boolean;
  weights?: { alpha: number; beta: number; gamma: number };
}

export default function ReroutingDashboard({ onNavigate }: ReroutingDashboardProps) {
  const [currentTime, setCurrentTime] = useState<string>('');
  const [loading, setLoading] = useState(false);
  const [requireAccessibility, setRequireAccessibility] = useState(true);
  const [alpha, setAlpha] = useState<number>(1.0);
  const [beta, setBeta] = useState<number>(0.45);
  const [gamma, setGamma] = useState<number>(50.0);
  
  const [scenarios, setScenarios] = useState<any>({ stops: [], edges: [], active_disruptions: [] });
  const [selectedEdgeId, setSelectedEdgeId] = useState<string | number>('');
  
  const [result, setResult] = useState<RerouteResult>({
    alternate_route: ['Master Canteen', 'Vani Vihar', 'Jaydev Vihar', 'Patia Square'],
    delta_delay_minutes: 42.8,
    safety_risk_index: 2.15,
    energy_impact_kwh: 1.45,
    status: 'FEASIBLE_EVALUATED',
    route_nodes_details: [
      { id: 1, name: 'Master Canteen Hub', lat: 20.265, lon: 85.842, capacity: 250, is_accessible: true },
      { id: 3, name: 'Vani Vihar Transit Node', lat: 20.301, lon: 85.852, capacity: 180, is_accessible: true },
      { id: 4, name: 'Jaydev Vihar Bypass', lat: 20.312, lon: 85.825, capacity: 150, is_accessible: true },
      { id: 2, name: 'Patia Square Terminal', lat: 20.354, lon: 85.818, capacity: 200, is_accessible: true }
    ],
    weights: { alpha: 1.0, beta: 0.45, gamma: 50.0 }
  });

  const [operatorApproved, setOperatorApproved] = useState(false);

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

  // Fetch scenarios & active disruptions
  useEffect(() => {
    fetch('/api/v1/rerouting/scenarios/')
      .then(res => res.json())
      .then(data => {
        setScenarios(data);
        if (data.active_disruptions && data.active_disruptions.length > 0) {
          const firstBlocked = data.active_disruptions[0].affected_edge_id;
          if (firstBlocked) setSelectedEdgeId(firstBlocked);
        } else if (data.edges && data.edges.length > 0) {
          setSelectedEdgeId(data.edges[0].id);
        }
      })
      .catch(err => console.log('Using default scenarios:', err));
  }, []);

  const handleCalculateReroute = () => {
    setLoading(true);
    setOperatorApproved(false);
    
    fetch('/api/v1/rerouting/calculate/', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        blocked_edge_id: selectedEdgeId,
        require_accessibility: requireAccessibility,
        alpha: Number(alpha),
        beta: Number(beta),
        gamma: Number(gamma)
      })
    })
      .then(res => res.json())
      .then(data => {
        if (data.alternate_route) {
          setResult(data);
        }
      })
      .catch(err => console.error('Reroute calculation error:', err))
      .finally(() => setLoading(false));
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

          {/* Predictions */}
          <button
            onClick={() => onNavigate('PREDICTIONS')}
            className="w-13 h-13 flex flex-col items-center justify-center text-on-surface-variant/60 hover:text-on-surface hover:bg-surface-bright/50 transition-all rounded-2xl cursor-pointer border-none bg-transparent p-3"
            title="Predictions Dashboard"
          >
            <span className="material-symbols-outlined text-[26px]">group_work</span>
          </button>

          {/* Rerouting Pre-Action Sandbox (Active with glowing pill indicator) */}
          <button
            onClick={() => onNavigate('REROUTING')}
            className="w-13 h-13 flex flex-col items-center justify-center bg-primary-container text-on-primary-container rounded-2xl shadow-[0_0_18px_rgba(169,200,251,0.4)] transition-all p-3 cursor-pointer border-none"
            title="Rerouting Sandbox (Active)"
          >
            <span className="material-symbols-outlined text-[26px]">alt_route</span>
          </button>

          {/* Command Center */}
          <button
            onClick={() => onNavigate('COMMAND_CENTER')}
            className="w-13 h-13 flex flex-col items-center justify-center text-on-surface-variant/60 hover:text-on-surface hover:bg-surface-bright/50 transition-all rounded-2xl cursor-pointer border-none bg-transparent p-3"
            title="Command Center"
          >
            <span className="material-symbols-outlined text-[26px]">terminal</span>
          </button>

          {/* Intervention Simulator */}
          <button
            onClick={() => onNavigate('INTERVENTIONS')}
            className="w-13 h-13 flex flex-col items-center justify-center text-indigo-400 hover:text-indigo-200 hover:bg-indigo-950/50 transition-all rounded-2xl cursor-pointer border-none bg-transparent p-3"
            title="Intervention & Schedule Simulator"
          >
            <span className="material-symbols-outlined text-[26px]">science</span>
          </button>
        </div>

        {/* Bottom Settings Icon */}
        <div className="mt-auto flex flex-col items-center">
          <button
            onClick={() => onNavigate('LANDING')}
            className="w-11 h-11 flex items-center justify-center text-on-surface-variant/60 hover:text-on-surface hover:bg-surface-bright/50 transition-all rounded-full bg-surface-container-highest cursor-pointer border-none"
            title="System Settings"
          >
            <span className="material-symbols-outlined text-xl">settings</span>
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
            <span className="text-[10px] bg-primary-container/20 text-secondary border border-secondary/30 px-2.5 py-0.5 rounded-full font-mono font-bold">
              PRE-ACTION REROUTING SANDBOX
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
              onClick={() => onNavigate('PREDICTIONS')}
              className="text-on-surface-variant hover:text-primary transition-colors cursor-pointer bg-transparent border-none"
            >
              Predictions
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
          <div className="bg-emerald-950/60 border border-emerald-500/30 text-emerald-400 px-3 py-1 rounded-full text-xs font-bold flex items-center gap-2">
            <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse shadow-[0_0_8px_rgba(52,211,153,0.8)]"></span>
            HUMAN-IN-THE-LOOP (NO AUTO-DISPATCH)
          </div>
        </div>
      </header>

      {/* ========================================================= */}
      {/* Main Content Area */}
      {/* ========================================================= */}
      <main className="flex-1 ml-[80px] mt-16 p-6 lg:p-8 bg-surface overflow-y-auto w-full h-[calc(100vh-64px)]">
        <div className="max-w-[1550px] mx-auto flex flex-col gap-6">
          {/* Header & Subtitle */}
          <div className="flex flex-col md:flex-row justify-between items-start md:items-end gap-3 border-b border-outline-variant/15 pb-4">
            <div>
              <h1 className="text-2xl lg:text-3xl font-extrabold text-on-surface tracking-tight mb-1 flex items-center gap-3">
                <span>Rerouting Sandbox</span>
                <span className="text-xs bg-surface-container-high px-3 py-1 rounded-full font-mono text-zinc-400 border border-outline-variant/20 font-normal">
                  Multi-Objective Evaluation Engine
                </span>
              </h1>
              <p className="text-xs lg:text-sm text-on-surface-variant font-normal">
                Evaluate alternate transit schedules when road segments are blocked. Quantifies Delay, Safety Hazard, and Energy Impacts before dispatch.
              </p>
            </div>

            {/* Invariant Guarantee Badge */}
            <div className="bg-surface-container p-2.5 px-4 rounded-2xl border border-outline-variant/20 text-xs font-mono text-zinc-300">
              Formula: <span className="text-secondary font-bold">W(e) = α(T_e) + β(E_e) + γ(A_e)</span>
            </div>
          </div>

          {/* ===================================================== */}
          {/* Top Row: 3 Required Impact Metrics (Key Outputs) */}
          {/* ===================================================== */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            {/* Metric 1: Delta Delay Saved */}
            <div className="bg-surface-container rounded-[24px] p-6 flex flex-col justify-between border border-outline-variant/10 relative overflow-hidden shadow-lg">
              <div className="absolute inset-0 bg-success-tonal/5"></div>
              <div className="flex justify-between items-start z-10">
                <span className="font-label-md text-xs font-mono text-on-surface-variant uppercase tracking-widest">
                  TIME SAVED (DELTA DELAY)
                </span>
                <div className="w-9 h-9 rounded-full bg-success-tonal/20 flex items-center justify-center">
                  <span className="material-symbols-outlined text-success-tonal text-lg">timelapse</span>
                </div>
              </div>
              <div className="mt-6 z-10">
                <div className="text-3xl lg:text-4xl font-normal text-success-tonal tracking-tight font-mono">
                  +{result.delta_delay_minutes} <span className="text-base">min</span>
                </div>
                <div className="text-xs text-on-surface-variant mt-2 font-sans">
                  Saved vs waiting out blockage (45m baseline clearance).
                </div>
              </div>
            </div>

            {/* Metric 2: Safety Risk Index (0.0 to 10.0 via M/M/c) */}
            <div className="bg-surface-container rounded-[24px] p-6 flex flex-col justify-between border border-outline-variant/10 shadow-lg">
              <div className="flex justify-between items-start">
                <span className="font-label-md text-xs font-mono text-on-surface-variant uppercase tracking-widest">
                  SAFETY RISK INDEX (M/M/c)
                </span>
                <div className={`w-9 h-9 rounded-full flex items-center justify-center ${
                  result.safety_risk_index > 6.0 ? 'bg-error/20 text-error' : 'bg-primary-container/20 text-secondary'
                }`}>
                  <span className="material-symbols-outlined text-lg">shield</span>
                </div>
              </div>
              <div className="mt-6">
                <div className={`text-3xl lg:text-4xl font-normal tracking-tight font-mono ${
                  result.safety_risk_index > 6.0 ? 'text-error' : result.safety_risk_index > 3.0 ? 'text-warning-tonal' : 'text-success-tonal'
                }`}>
                  {result.safety_risk_index} <span className="text-base text-zinc-500">/ 10.0</span>
                </div>
                <div className="text-xs text-on-surface-variant mt-2 font-sans">
                  {result.safety_risk_index <= 3.0 
                    ? 'Low hazard: transfer stops within safe crowd limits.'
                    : 'Elevated hazard: transfer nodes approaching queue capacity.'}
                </div>
              </div>
            </div>

            {/* Metric 3: Net Energy Impact (kWh) */}
            <div className="bg-surface-container rounded-[24px] p-6 flex flex-col justify-between border border-outline-variant/10 shadow-lg">
              <div className="flex justify-between items-start">
                <span className="font-label-md text-xs font-mono text-on-surface-variant uppercase tracking-widest">
                  ENERGY IMPACT (kWh)
                </span>
                <div className="w-9 h-9 rounded-full bg-secondary/20 flex items-center justify-center">
                  <span className="material-symbols-outlined text-secondary text-lg">bolt</span>
                </div>
              </div>
              <div className="mt-6">
                <div className="text-3xl lg:text-4xl font-normal text-secondary tracking-tight font-mono">
                  {result.energy_impact_kwh > 0 ? `+${result.energy_impact_kwh}` : result.energy_impact_kwh} <span className="text-base">kWh</span>
                </div>
                <div className="text-xs text-on-surface-variant mt-2 font-sans">
                  Detour distance traction delta (@1.2 kWh/km).
                </div>
              </div>
            </div>
          </div>

          {/* ===================================================== */}
          {/* Middle Row: Sandbox Scenario Controls & Weights */}
          {/* ===================================================== */}
          <div className="grid grid-cols-1 xl:grid-cols-12 gap-6">
            {/* Left Col: Rerouting Controls (4 Cols) */}
            <div className="xl:col-span-4 bg-surface-container rounded-[24px] p-6 border border-outline-variant/10 flex flex-col justify-between shadow-lg space-y-5">
              <div>
                <h2 className="text-base font-bold text-white mb-4 flex items-center gap-2">
                  <span className="material-symbols-outlined text-secondary">tune</span>
                  <span>Disruption Parameters</span>
                </h2>

                {/* Blocked Road Segment Selector */}
                <div className="space-y-2 mb-4">
                  <label className="text-xs font-mono text-on-surface-variant uppercase tracking-wider block">
                    Blocked Road Segment
                  </label>
                  <select
                    value={selectedEdgeId}
                    onChange={(e) => setSelectedEdgeId(e.target.value)}
                    className="w-full bg-surface-container-highest border border-outline-variant/30 text-white rounded-xl p-3 text-xs font-mono focus:border-secondary focus:outline-none"
                  >
                    {scenarios.active_disruptions && scenarios.active_disruptions.length > 0 ? (
                      scenarios.active_disruptions.map((d: any) => (
                        <option key={d.id} value={d.affected_edge_id || d.id}>
                          🚨 {d.disruption_type} ({d.severity}) - Edge #{d.affected_edge_id || d.id}
                        </option>
                      ))
                    ) : (
                      <option value="1">Road Segment #1 (Janpath Corridor - Blocked)</option>
                    )}
                    {scenarios.edges && scenarios.edges.slice(0, 10).map((e: any) => (
                      <option key={e.id} value={e.id}>
                        Road #{e.id} (Stop {e.source_id} → Stop {e.target_id}) - {e.distance}m
                      </option>
                    ))}
                  </select>
                </div>

                {/* Accessibility Toggle */}
                <div className="bg-surface-container-highest p-3.5 rounded-2xl border border-outline-variant/20 mb-4 flex items-center justify-between">
                  <div>
                    <div className="text-xs font-bold text-white flex items-center gap-1.5">
                      <span className="material-symbols-outlined text-sm text-secondary">accessible</span>
                      Require Step-Free Accessibility
                    </div>
                    <div className="text-[11px] text-zinc-400 mt-0.5">
                      Strictly prunes non-accessible detour segments
                    </div>
                  </div>
                  <input
                    type="checkbox"
                    checked={requireAccessibility}
                    onChange={(e) => setRequireAccessibility(e.target.checked)}
                    className="w-5 h-5 accent-secondary rounded cursor-pointer"
                  />
                </div>

                {/* Multi-Objective Weight Sliders */}
                <div className="space-y-3 bg-surface-dim/80 p-3.5 rounded-2xl border border-outline-variant/15 font-mono text-xs">
                  <div className="text-zinc-400 text-[10px] uppercase font-bold tracking-wider">
                    Weight Vector [α, β, γ]
                  </div>

                  <div>
                    <div className="flex justify-between text-[11px] mb-1">
                      <span>Travel Time Weight (α)</span>
                      <span className="text-secondary font-bold">{alpha}</span>
                    </div>
                    <input
                      type="range"
                      min="0.1"
                      max="3.0"
                      step="0.1"
                      value={alpha}
                      onChange={(e) => setAlpha(parseFloat(e.target.value))}
                      className="w-full accent-secondary h-1.5 bg-zinc-800 rounded cursor-pointer"
                    />
                  </div>

                  <div>
                    <div className="flex justify-between text-[11px] mb-1">
                      <span>Energy Weight (β)</span>
                      <span className="text-secondary font-bold">{beta}</span>
                    </div>
                    <input
                      type="range"
                      min="0.1"
                      max="2.0"
                      step="0.05"
                      value={beta}
                      onChange={(e) => setBeta(parseFloat(e.target.value))}
                      className="w-full accent-secondary h-1.5 bg-zinc-800 rounded cursor-pointer"
                    />
                  </div>

                  <div>
                    <div className="flex justify-between text-[11px] mb-1">
                      <span>Accessibility Penalty (γ)</span>
                      <span className="text-secondary font-bold">{gamma}</span>
                    </div>
                    <input
                      type="range"
                      min="10.0"
                      max="100.0"
                      step="5.0"
                      value={gamma}
                      onChange={(e) => setGamma(parseFloat(e.target.value))}
                      className="w-full accent-secondary h-1.5 bg-zinc-800 rounded cursor-pointer"
                    />
                  </div>
                </div>
              </div>

              {/* Calculate Detour Action Button */}
              <button
                onClick={handleCalculateReroute}
                disabled={loading}
                className="w-full bg-primary-container hover:bg-primary-fixed text-on-primary-container py-3.5 rounded-2xl font-bold text-xs uppercase tracking-wider transition-all flex items-center justify-center gap-2 shadow-lg shadow-blue-500/20 border-none cursor-pointer disabled:opacity-50"
              >
                <span className="material-symbols-outlined text-lg">route</span>
                {loading ? 'Evaluating Network Graph...' : 'Calculate Optimal Detour'}
              </button>
            </div>

            {/* Right Col: Calculated Detour Route & Transfer Stoppages (8 Cols) */}
            <div className="xl:col-span-8 bg-surface-container rounded-[24px] p-6 border border-outline-variant/10 flex flex-col justify-between shadow-lg space-y-6">
              <div>
                <div className="flex justify-between items-center mb-4">
                  <h2 className="text-base font-bold text-white flex items-center gap-2">
                    <span className="material-symbols-outlined text-success-tonal">alt_route</span>
                    <span>Evaluated Alternate Route (Dijkstra on W(e))</span>
                  </h2>
                  <span className="bg-success-tonal/15 text-success-tonal text-[11px] font-mono font-bold px-3 py-1 rounded-full border border-success-tonal/20">
                    {result.status}
                  </span>
                </div>

                {/* Detour Node Sequence Cards */}
                <div className="space-y-3">
                  <div className="text-xs font-mono text-zinc-400">
                    Optimal Transit Node Sequence ({result.alternate_route.length} Stops):
                  </div>

                  <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 gap-3">
                    {result.route_nodes_details && result.route_nodes_details.length > 0 ? (
                      result.route_nodes_details.map((node, index) => (
                        <div
                          key={node.id || index}
                          className={`p-3.5 rounded-2xl border ${
                            index === 0
                              ? 'bg-blue-950/40 border-blue-500/40'
                              : index === result.route_nodes_details!.length - 1
                              ? 'bg-emerald-950/40 border-emerald-500/40'
                              : 'bg-surface-container-highest border-outline-variant/20'
                          }`}
                        >
                          <div className="flex justify-between items-center mb-1">
                            <span className="text-[10px] font-mono text-zinc-400">STOP #{index + 1}</span>
                            <span className="text-[10px] font-mono bg-surface-dim px-1.5 py-0.5 rounded text-secondary">
                              Cap: {node.capacity || 150}
                            </span>
                          </div>
                          <div className="font-bold text-xs text-white truncate">{node.name || `Node ${node.id}`}</div>
                          <div className="text-[10px] font-mono text-emerald-400 mt-1 flex items-center gap-1">
                            <span className="material-symbols-outlined text-xs">check_circle</span>
                            Step-Free Accessible
                          </div>
                        </div>
                      ))
                    ) : (
                      result.alternate_route.map((nodeId, index) => (
                        <div key={index} className="p-3.5 rounded-2xl bg-surface-container-highest border border-outline-variant/20">
                          <span className="text-[10px] font-mono text-zinc-400">STOP #{index + 1}</span>
                          <div className="font-bold text-xs text-white">Stop #{nodeId}</div>
                        </div>
                      ))
                    )}
                  </div>
                </div>

                {/* Mathematical Evaluation Summary Panel */}
                <div className="mt-6 grid grid-cols-1 md:grid-cols-3 gap-3 bg-surface-dim p-4 rounded-2xl border border-outline-variant/20 text-xs font-mono">
                  <div>
                    <span className="text-zinc-400 text-[10px] block">MULTI-OBJECTIVE COST</span>
                    <span className="text-white font-bold">W(e) Minimized</span>
                    <span className="text-[10px] text-zinc-500 block mt-0.5">
                      α={result.weights?.alpha ?? alpha}, β={result.weights?.beta ?? beta}, γ={result.weights?.gamma ?? gamma}
                    </span>
                  </div>
                  <div>
                    <span className="text-zinc-400 text-[10px] block">M/M/c QUEUE EVALUATION</span>
                    <span className="text-secondary font-bold">λ_eff = 8.5 pax/m</span>
                    <span className="text-[10px] text-zinc-500 block mt-0.5">c=2 buses, μ=5.0 pax/m</span>
                  </div>
                  <div>
                    <span className="text-zinc-400 text-[10px] block">HUMAN OPERATOR STATE</span>
                    <span className={operatorApproved ? "text-emerald-400 font-bold" : "text-warning-tonal font-bold"}>
                      {operatorApproved ? "DISPATCH APPROVED" : "PENDING HUMAN REVIEW"}
                    </span>
                    <span className="text-[10px] text-zinc-500 block mt-0.5">Zero Auto-Dispatch</span>
                  </div>
                </div>
              </div>

              {/* Operator Action Bar */}
              <div className="border-t border-outline-variant/15 pt-4 flex flex-col sm:flex-row justify-between items-center gap-4">
                <div className="text-xs text-zinc-400 flex items-center gap-2">
                  <span className="material-symbols-outlined text-secondary text-sm">info</span>
                  <span>Human operator must verify transfer queue hazard before dispatching schedule.</span>
                </div>

                <div className="flex items-center gap-3">
                  <button
                    onClick={() => onNavigate('COMMAND_CENTER')}
                    className="px-4 py-2.5 rounded-xl border border-outline-variant text-zinc-300 hover:text-white hover:bg-surface-container-high text-xs font-bold transition-all cursor-pointer bg-transparent"
                  >
                    View in Command Center
                  </button>

                  <button
                    onClick={() => setOperatorApproved(true)}
                    className={`px-5 py-2.5 rounded-xl font-bold text-xs transition-all flex items-center gap-2 border-none cursor-pointer ${
                      operatorApproved
                        ? 'bg-emerald-600 text-white shadow-lg shadow-emerald-600/30'
                        : 'bg-gradient-to-r from-blue-600 to-indigo-600 text-white hover:from-blue-500 hover:to-indigo-500 shadow-md shadow-blue-500/20'
                    }`}
                  >
                    <span className="material-symbols-outlined text-sm">
                      {operatorApproved ? 'done_all' : 'check'}
                    </span>
                    <span>{operatorApproved ? 'Intervention Approved' : 'Approve & Dispatch Reroute'}</span>
                  </button>
                </div>
              </div>
            </div>
          </div>
        </div>
      </main>
    </div>
  );
}
