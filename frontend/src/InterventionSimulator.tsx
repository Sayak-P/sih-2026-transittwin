import { useState, useEffect } from 'react';

interface InterventionSimulatorProps {
  onNavigate: (page: 'LANDING' | 'NAVIGATOR' | 'COMMAND_CENTER' | 'PREDICTIONS' | 'REROUTING' | 'INTERVENTIONS') => void;
}

interface InterventionType {
  type: string;
  label: string;
}

interface ScenarioType {
  type: string;
  label: string;
}

interface ComparisonResult {
  scenario_id: string;
  baseline_metrics: any;
  intervention_results: any[];
  recommended_index: number;
  recommendation_explanation: string;
  objective_profile: string;
}

interface ScenarioResult {
  scenario_id: string;
  scenario_type: string;
  scenario_label: string;
  baseline_metrics: any;
  scenario_metrics: any;
  delta_metrics: any;
  impact_summary: string;
  severity: string;
}

const API_BASE = '/api/v1';

const PROFILES = [
  { id: 'BALANCED', label: 'Balanced', icon: '⚖️' },
  { id: 'MINIMUM_DELAY', label: 'Min Delay', icon: '⏱️' },
  { id: 'SAFETY_FIRST', label: 'Safety First', icon: '🛡️' },
  { id: 'ENERGY_EFFICIENT', label: 'Energy Efficient', icon: '🔋' },
];

const SEVERITY_COLORS: Record<string, string> = {
  CRITICAL: '#ff4757',
  SIGNIFICANT: '#ff6b35',
  MODERATE: '#ffa502',
  MINIMAL: '#2ed573',
};

export default function InterventionSimulator({ onNavigate }: InterventionSimulatorProps) {
  // State
  const [interventionTypes, setInterventionTypes] = useState<InterventionType[]>([]);
  const [scenarioTypes, setScenarioTypes] = useState<ScenarioType[]>([]);
  const [activeTab, setActiveTab] = useState<'SCHEDULE' | 'SCENARIO' | 'EVENTS'>('SCHEDULE');
  const [isLoading, setIsLoading] = useState(false);

  // Schedule Simulation State
  const [selectedInterventions, setSelectedInterventions] = useState<any[]>([
    { intervention_type: 'INCREASE_FREQUENCY', parameters: { route_id: 1, new_headway_minutes: 10 }, label: 'Increase Frequency on Route 1' },
  ]);
  const [profile, setProfile] = useState('BALANCED');
  const [horizonMinutes, setHorizonMinutes] = useState(30);
  const [comparison, setComparison] = useState<ComparisonResult | null>(null);

  // Scenario State
  const [selectedScenario, setSelectedScenario] = useState('ROAD_BLOCKED');
  const [scenarioParams, setScenarioParams] = useState<Record<string, any>>({ edge_id: '1', severity: 4 });
  const [scenarioResult, setScenarioResult] = useState<ScenarioResult | null>(null);

  // Events State
  const [events, setEvents] = useState<any[]>([]);
  const [newEvent, setNewEvent] = useState({
    event_type: 'CONCERT',
    name: '',
    duration_hours: 3,
    intensity: 2.0,
    location_stop_id: 1,
    radius_km: 2.0,
  });

  // Load available types
  useEffect(() => {
    fetch(`${API_BASE}/scenarios/simulate/`)
      .then(r => r.json())
      .then(data => {
        setInterventionTypes(data.intervention_types || []);
        setScenarioTypes(data.scenario_types || []);
      })
      .catch(console.error);

    fetch(`${API_BASE}/events/`)
      .then(r => r.json())
      .then(data => setEvents(data.events || []))
      .catch(console.error);
  }, []);

  // ── Schedule Comparison ──
  const runComparison = async () => {
    setIsLoading(true);
    try {
      const res = await fetch(`${API_BASE}/schedules/compare/`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          interventions: selectedInterventions,
          horizon_minutes: horizonMinutes,
          objective_profile: profile,
        }),
      });
      const data = await res.json();
      setComparison(data);
    } catch (err) {
      console.error('Schedule comparison failed:', err);
    }
    setIsLoading(false);
  };

  // ── Scenario Simulation ──
  const runScenario = async () => {
    setIsLoading(true);
    try {
      const res = await fetch(`${API_BASE}/scenarios/simulate/`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          scenario_type: selectedScenario,
          parameters: scenarioParams,
          horizon_minutes: horizonMinutes,
        }),
      });
      const data = await res.json();
      setScenarioResult(data);
    } catch (err) {
      console.error('Scenario simulation failed:', err);
    }
    setIsLoading(false);
  };

  // ── Event Creation ──
  const createEvent = async () => {
    try {
      const res = await fetch(`${API_BASE}/events/`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(newEvent),
      });
      const data = await res.json();
      if (data.event) {
        setEvents([...events, data.event]);
      }
    } catch (err) {
      console.error('Event creation failed:', err);
    }
  };

  const addIntervention = () => {
    setSelectedInterventions([
      ...selectedInterventions,
      { intervention_type: 'HOLD_BUS', parameters: { vehicle_id: 'BUS-1001', hold_seconds: 300 }, label: '' },
    ]);
  };

  const removeIntervention = (index: number) => {
    setSelectedInterventions(selectedInterventions.filter((_, i) => i !== index));
  };

  const updateIntervention = (index: number, field: string, value: any) => {
    const updated = [...selectedInterventions];
    if (field === 'intervention_type') {
      updated[index].intervention_type = value;
    } else {
      updated[index].parameters = { ...updated[index].parameters, [field]: value };
    }
    setSelectedInterventions(updated);
  };

  return (
    <div style={{
      minHeight: '100vh',
      background: 'linear-gradient(135deg, #0a0a1a 0%, #1a1a3e 50%, #0d1b2a 100%)',
      color: '#e0e0e0',
      fontFamily: "'Inter', 'Segoe UI', sans-serif",
    }}>
      {/* Header */}
      <div style={{
        background: 'rgba(20, 20, 40, 0.95)',
        borderBottom: '1px solid rgba(99, 102, 241, 0.3)',
        padding: '16px 32px',
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
        backdropFilter: 'blur(20px)',
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
          <button
            onClick={() => onNavigate('COMMAND_CENTER')}
            style={{
              background: 'rgba(99, 102, 241, 0.2)',
              border: '1px solid rgba(99, 102, 241, 0.4)',
              borderRadius: 8,
              padding: '8px 16px',
              color: '#a5b4fc',
              cursor: 'pointer',
              fontSize: 14,
            }}
          >
            ← Command Center
          </button>
          <h1 style={{ margin: 0, fontSize: 22, fontWeight: 700, color: '#f1f5f9' }}>
            🧪 Intervention Simulator
          </h1>
          <span style={{
            fontSize: 11,
            background: 'rgba(34, 197, 94, 0.2)',
            color: '#4ade80',
            padding: '3px 10px',
            borderRadius: 10,
            border: '1px solid rgba(34, 197, 94, 0.3)',
          }}>
            SIMULATION DATA
          </span>
        </div>

        {/* Profile Selector */}
        <div style={{ display: 'flex', gap: 8 }}>
          {PROFILES.map(p => (
            <button
              key={p.id}
              onClick={() => setProfile(p.id)}
              style={{
                background: profile === p.id ? 'rgba(99, 102, 241, 0.4)' : 'rgba(30, 30, 60, 0.6)',
                border: `1px solid ${profile === p.id ? '#6366f1' : 'rgba(99, 102, 241, 0.2)'}`,
                borderRadius: 8,
                padding: '6px 14px',
                color: profile === p.id ? '#fff' : '#94a3b8',
                cursor: 'pointer',
                fontSize: 12,
                transition: 'all 0.2s',
              }}
            >
              {p.icon} {p.label}
            </button>
          ))}
        </div>
      </div>

      {/* Tabs */}
      <div style={{
        display: 'flex',
        gap: 0,
        padding: '0 32px',
        background: 'rgba(15, 15, 35, 0.8)',
        borderBottom: '1px solid rgba(99, 102, 241, 0.15)',
      }}>
        {[
          { id: 'SCHEDULE' as const, label: '📋 Schedule Comparison', desc: 'Test alternate schedules' },
          { id: 'SCENARIO' as const, label: '🔮 What-If Scenarios', desc: 'Predict disruption impact' },
          { id: 'EVENTS' as const, label: '🎪 Event Manager', desc: 'Create demand events' },
        ].map(tab => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id)}
            style={{
              background: 'transparent',
              border: 'none',
              borderBottom: activeTab === tab.id ? '2px solid #6366f1' : '2px solid transparent',
              padding: '14px 24px',
              color: activeTab === tab.id ? '#e0e7ff' : '#64748b',
              cursor: 'pointer',
              fontSize: 14,
              fontWeight: activeTab === tab.id ? 600 : 400,
              transition: 'all 0.2s',
            }}
          >
            {tab.label}
          </button>
        ))}
      </div>

      <div style={{ padding: '24px 32px' }}>
        {/* ── SCHEDULE TAB ── */}
        {activeTab === 'SCHEDULE' && (
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1.5fr', gap: 24 }}>
            {/* Left: Intervention Builder */}
            <div style={{
              background: 'rgba(20, 20, 50, 0.7)',
              borderRadius: 16,
              border: '1px solid rgba(99, 102, 241, 0.2)',
              padding: 24,
            }}>
              <h3 style={{ margin: '0 0 16px', color: '#c7d2fe', fontSize: 16 }}>Build Interventions</h3>

              {selectedInterventions.map((intv, i) => (
                <div key={i} style={{
                  background: 'rgba(30, 30, 60, 0.6)',
                  borderRadius: 12,
                  padding: 16,
                  marginBottom: 12,
                  border: '1px solid rgba(99, 102, 241, 0.15)',
                }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 10 }}>
                    <span style={{ fontSize: 12, color: '#818cf8' }}>Option {String.fromCharCode(65 + i)}</span>
                    {selectedInterventions.length > 1 && (
                      <button onClick={() => removeIntervention(i)} style={{
                        background: 'rgba(239, 68, 68, 0.2)',
                        border: '1px solid rgba(239, 68, 68, 0.3)',
                        borderRadius: 6,
                        padding: '2px 8px',
                        color: '#f87171',
                        cursor: 'pointer',
                        fontSize: 11,
                      }}>×</button>
                    )}
                  </div>

                  <select
                    value={intv.intervention_type}
                    onChange={e => updateIntervention(i, 'intervention_type', e.target.value)}
                    style={{
                      width: '100%',
                      background: 'rgba(15, 15, 35, 0.8)',
                      border: '1px solid rgba(99, 102, 241, 0.3)',
                      borderRadius: 8,
                      padding: '8px 12px',
                      color: '#e0e7ff',
                      fontSize: 13,
                      marginBottom: 8,
                    }}
                  >
                    {interventionTypes.map(t => (
                      <option key={t.type} value={t.type}>{t.label}</option>
                    ))}
                  </select>

                  <input
                    type="text"
                    placeholder="Label (optional)"
                    value={intv.label || ''}
                    onChange={e => {
                      const u = [...selectedInterventions];
                      u[i].label = e.target.value;
                      setSelectedInterventions(u);
                    }}
                    style={{
                      width: '100%',
                      background: 'rgba(15, 15, 35, 0.8)',
                      border: '1px solid rgba(99, 102, 241, 0.2)',
                      borderRadius: 8,
                      padding: '8px 12px',
                      color: '#e0e7ff',
                      fontSize: 12,
                      boxSizing: 'border-box',
                    }}
                  />
                </div>
              ))}

              <div style={{ display: 'flex', gap: 8, marginTop: 16 }}>
                <button onClick={addIntervention} style={{
                  flex: 1,
                  background: 'rgba(99, 102, 241, 0.15)',
                  border: '1px solid rgba(99, 102, 241, 0.3)',
                  borderRadius: 10,
                  padding: '10px',
                  color: '#a5b4fc',
                  cursor: 'pointer',
                  fontSize: 13,
                }}>
                  + Add Option
                </button>
                <button onClick={runComparison} disabled={isLoading} style={{
                  flex: 2,
                  background: isLoading ? 'rgba(99, 102, 241, 0.3)' : 'linear-gradient(135deg, #6366f1, #8b5cf6)',
                  border: 'none',
                  borderRadius: 10,
                  padding: '10px 20px',
                  color: '#fff',
                  cursor: isLoading ? 'wait' : 'pointer',
                  fontSize: 14,
                  fontWeight: 600,
                }}>
                  {isLoading ? '⏳ Simulating...' : '▶ Run Comparison'}
                </button>
              </div>

              <div style={{ marginTop: 16 }}>
                <label style={{ fontSize: 12, color: '#94a3b8' }}>Horizon: {horizonMinutes} min</label>
                <input
                  type="range" min="10" max="120" step="10"
                  value={horizonMinutes}
                  onChange={e => setHorizonMinutes(Number(e.target.value))}
                  style={{ width: '100%', accentColor: '#6366f1' }}
                />
              </div>
            </div>

            {/* Right: Results */}
            <div>
              {comparison ? (
                <div>
                  {/* Baseline Card */}
                  <div style={{
                    background: 'rgba(20, 20, 50, 0.7)',
                    borderRadius: 16,
                    border: '1px solid rgba(99, 102, 241, 0.2)',
                    padding: 20,
                    marginBottom: 16,
                  }}>
                    <h4 style={{ margin: '0 0 12px', color: '#94a3b8', fontSize: 13, textTransform: 'uppercase', letterSpacing: 1 }}>
                      Baseline (No Intervention)
                    </h4>
                    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 12 }}>
                      {[
                        { label: 'Avg Wait', value: `${(comparison.baseline_metrics.average_waiting_minutes || 0).toFixed(1)} min` },
                        { label: 'Max Queue', value: comparison.baseline_metrics.max_queue_size || 0 },
                        { label: 'Max Crowding', value: `${((comparison.baseline_metrics.max_crowding_ratio || 0) * 100).toFixed(0)}%` },
                        { label: 'Served', value: comparison.baseline_metrics.passengers_served || 0 },
                      ].map(m => (
                        <div key={m.label} style={{
                          background: 'rgba(30, 30, 60, 0.5)',
                          borderRadius: 10,
                          padding: '10px 14px',
                          textAlign: 'center',
                        }}>
                          <div style={{ fontSize: 11, color: '#64748b', marginBottom: 4 }}>{m.label}</div>
                          <div style={{ fontSize: 18, fontWeight: 700, color: '#e2e8f0' }}>{m.value}</div>
                        </div>
                      ))}
                    </div>
                  </div>

                  {/* Intervention Results */}
                  {comparison.intervention_results.map((r: any, i: number) => (
                    <div key={i} style={{
                      background: i === comparison.recommended_index
                        ? 'rgba(34, 197, 94, 0.08)'
                        : 'rgba(20, 20, 50, 0.7)',
                      borderRadius: 16,
                      border: i === comparison.recommended_index
                        ? '1px solid rgba(34, 197, 94, 0.4)'
                        : '1px solid rgba(99, 102, 241, 0.2)',
                      padding: 20,
                      marginBottom: 12,
                      position: 'relative' as const,
                    }}>
                      {i === comparison.recommended_index && (
                        <div style={{
                          position: 'absolute' as const,
                          top: -10,
                          right: 16,
                          background: 'linear-gradient(135deg, #22c55e, #16a34a)',
                          color: '#fff',
                          fontSize: 11,
                          fontWeight: 700,
                          padding: '3px 12px',
                          borderRadius: 10,
                        }}>
                          ✓ RECOMMENDED
                        </div>
                      )}

                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
                        <div>
                          <span style={{ fontSize: 14, fontWeight: 600, color: '#e2e8f0' }}>
                            Option {String.fromCharCode(65 + i)}: {r.intervention?.label || r.intervention?.intervention_type}
                          </span>
                          {!r.is_feasible && (
                            <span style={{
                              marginLeft: 8,
                              fontSize: 11,
                              background: 'rgba(239, 68, 68, 0.2)',
                              color: '#f87171',
                              padding: '2px 8px',
                              borderRadius: 6,
                            }}>INFEASIBLE</span>
                          )}
                        </div>
                        <span style={{
                          fontSize: 13,
                          color: r.score < 0.5 ? '#4ade80' : r.score < 1.0 ? '#fbbf24' : '#f87171',
                          fontWeight: 600,
                        }}>
                          Score: {r.score.toFixed(3)}
                        </span>
                      </div>

                      {r.is_feasible && r.delta_vs_baseline && (
                        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 10 }}>
                          {[
                            { label: 'Wait Saved', value: `${(r.delta_vs_baseline.waiting_minutes_saved || 0).toFixed(1)} min`, good: (r.delta_vs_baseline.waiting_minutes_saved || 0) > 0 },
                            { label: 'Queue Δ', value: r.delta_vs_baseline.queue_size_delta || 0, good: (r.delta_vs_baseline.queue_size_delta || 0) <= 0 },
                            { label: 'Crowding Δ', value: `${((r.delta_vs_baseline.crowding_ratio_delta || 0) * 100).toFixed(0)}%`, good: (r.delta_vs_baseline.crowding_ratio_delta || 0) <= 0 },
                            { label: 'Served Δ', value: `+${r.delta_vs_baseline.passengers_served_delta || 0}`, good: (r.delta_vs_baseline.passengers_served_delta || 0) >= 0 },
                          ].map(m => (
                            <div key={m.label} style={{
                              background: 'rgba(30, 30, 60, 0.5)',
                              borderRadius: 8,
                              padding: '8px 12px',
                              textAlign: 'center',
                            }}>
                              <div style={{ fontSize: 10, color: '#64748b', marginBottom: 3 }}>{m.label}</div>
                              <div style={{
                                fontSize: 16, fontWeight: 700,
                                color: m.good ? '#4ade80' : '#f87171',
                              }}>{m.value}</div>
                            </div>
                          ))}
                        </div>
                      )}

                      {r.explanation && (
                        <p style={{ fontSize: 12, color: '#94a3b8', margin: '10px 0 0', fontStyle: 'italic' }}>
                          {r.explanation}
                        </p>
                      )}
                    </div>
                  ))}
                </div>
              ) : (
                <div style={{
                  background: 'rgba(20, 20, 50, 0.5)',
                  borderRadius: 16,
                  border: '1px dashed rgba(99, 102, 241, 0.3)',
                  padding: '80px 40px',
                  textAlign: 'center',
                }}>
                  <div style={{ fontSize: 48, marginBottom: 16 }}>📊</div>
                  <h3 style={{ color: '#94a3b8', margin: '0 0 8px' }}>No Results Yet</h3>
                  <p style={{ color: '#64748b', fontSize: 13, maxWidth: 400, margin: '0 auto' }}>
                    Configure interventions on the left and click "Run Comparison" to see
                    side-by-side results. The system will simulate baseline vs your options
                    and recommend the best intervention.
                  </p>
                </div>
              )}
            </div>
          </div>
        )}

        {/* ── SCENARIO TAB ── */}
        {activeTab === 'SCENARIO' && (
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1.5fr', gap: 24 }}>
            <div style={{
              background: 'rgba(20, 20, 50, 0.7)',
              borderRadius: 16,
              border: '1px solid rgba(99, 102, 241, 0.2)',
              padding: 24,
            }}>
              <h3 style={{ margin: '0 0 16px', color: '#c7d2fe', fontSize: 16 }}>What-If Scenario</h3>

              <label style={{ fontSize: 12, color: '#94a3b8', display: 'block', marginBottom: 4 }}>Scenario Type</label>
              <select
                value={selectedScenario}
                onChange={e => setSelectedScenario(e.target.value)}
                style={{
                  width: '100%',
                  background: 'rgba(15, 15, 35, 0.8)',
                  border: '1px solid rgba(99, 102, 241, 0.3)',
                  borderRadius: 8,
                  padding: '10px 12px',
                  color: '#e0e7ff',
                  fontSize: 13,
                  marginBottom: 16,
                }}
              >
                {scenarioTypes.map(t => (
                  <option key={t.type} value={t.type}>{t.label}</option>
                ))}
              </select>

              {/* Dynamic parameter inputs based on scenario type */}
              <div style={{ marginBottom: 16 }}>
                {selectedScenario === 'ROAD_BLOCKED' && (
                  <>
                    <label style={{ fontSize: 12, color: '#94a3b8', display: 'block', marginBottom: 4 }}>Edge ID</label>
                    <input type="number" value={scenarioParams.edge_id || ''} onChange={e => setScenarioParams({ ...scenarioParams, edge_id: e.target.value })} style={inputStyle} />
                    <label style={{ fontSize: 12, color: '#94a3b8', display: 'block', marginTop: 8, marginBottom: 4 }}>Severity (1-5)</label>
                    <input type="number" min={1} max={5} value={scenarioParams.severity || 4} onChange={e => setScenarioParams({ ...scenarioParams, severity: Number(e.target.value) })} style={inputStyle} />
                  </>
                )}
                {selectedScenario === 'DEMAND_SURGE' && (
                  <>
                    <label style={{ fontSize: 12, color: '#94a3b8', display: 'block', marginBottom: 4 }}>Stop ID</label>
                    <input type="number" value={scenarioParams.stop_id || ''} onChange={e => setScenarioParams({ ...scenarioParams, stop_id: Number(e.target.value) })} style={inputStyle} />
                    <label style={{ fontSize: 12, color: '#94a3b8', display: 'block', marginTop: 8, marginBottom: 4 }}>Surge Multiplier</label>
                    <input type="number" step="0.5" value={scenarioParams.surge_multiplier || 2.0} onChange={e => setScenarioParams({ ...scenarioParams, surge_multiplier: Number(e.target.value) })} style={inputStyle} />
                  </>
                )}
                {selectedScenario === 'BUS_DELAYED' && (
                  <>
                    <label style={{ fontSize: 12, color: '#94a3b8', display: 'block', marginBottom: 4 }}>Vehicle ID</label>
                    <input type="text" value={scenarioParams.vehicle_id || ''} onChange={e => setScenarioParams({ ...scenarioParams, vehicle_id: e.target.value })} style={inputStyle} />
                    <label style={{ fontSize: 12, color: '#94a3b8', display: 'block', marginTop: 8, marginBottom: 4 }}>Delay (seconds)</label>
                    <input type="number" value={scenarioParams.delay_seconds || 600} onChange={e => setScenarioParams({ ...scenarioParams, delay_seconds: Number(e.target.value) })} style={inputStyle} />
                  </>
                )}
                {selectedScenario === 'EVENT_STARTS' && (
                  <>
                    <label style={{ fontSize: 12, color: '#94a3b8', display: 'block', marginBottom: 4 }}>Stop ID</label>
                    <input type="number" value={scenarioParams.stop_id || ''} onChange={e => setScenarioParams({ ...scenarioParams, stop_id: Number(e.target.value) })} style={inputStyle} />
                    <label style={{ fontSize: 12, color: '#94a3b8', display: 'block', marginTop: 8, marginBottom: 4 }}>Event Intensity</label>
                    <input type="number" step="0.5" value={scenarioParams.intensity || 2.0} onChange={e => setScenarioParams({ ...scenarioParams, intensity: Number(e.target.value) })} style={inputStyle} />
                  </>
                )}
              </div>

              <button onClick={runScenario} disabled={isLoading} style={{
                width: '100%',
                background: isLoading ? 'rgba(249, 115, 22, 0.3)' : 'linear-gradient(135deg, #f97316, #ea580c)',
                border: 'none',
                borderRadius: 10,
                padding: '12px 20px',
                color: '#fff',
                cursor: isLoading ? 'wait' : 'pointer',
                fontSize: 14,
                fontWeight: 600,
              }}>
                {isLoading ? '⏳ Simulating...' : '🔮 Simulate Scenario'}
              </button>
            </div>

            {/* Scenario Results */}
            <div>
              {scenarioResult ? (
                <div style={{
                  background: 'rgba(20, 20, 50, 0.7)',
                  borderRadius: 16,
                  border: `1px solid ${SEVERITY_COLORS[scenarioResult.severity] || '#64748b'}40`,
                  padding: 24,
                }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
                    <h3 style={{ margin: 0, fontSize: 18, color: '#e2e8f0' }}>
                      {scenarioResult.scenario_label}
                    </h3>
                    <span style={{
                      background: `${SEVERITY_COLORS[scenarioResult.severity]}20`,
                      color: SEVERITY_COLORS[scenarioResult.severity],
                      padding: '4px 14px',
                      borderRadius: 10,
                      fontSize: 12,
                      fontWeight: 700,
                      border: `1px solid ${SEVERITY_COLORS[scenarioResult.severity]}40`,
                    }}>
                      {scenarioResult.severity}
                    </span>
                  </div>

                  <p style={{ color: '#94a3b8', fontSize: 13, marginBottom: 20 }}>
                    {scenarioResult.impact_summary}
                  </p>

                  <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 12, marginBottom: 20 }}>
                    {Object.entries(scenarioResult.delta_metrics).map(([key, value]: [string, any]) => {
                      const isGood = value <= 0;
                      const label = key.replace('delta_', '').replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase());
                      return (
                        <div key={key} style={{
                          background: 'rgba(30, 30, 60, 0.5)',
                          borderRadius: 10,
                          padding: '12px 14px',
                          textAlign: 'center',
                        }}>
                          <div style={{ fontSize: 10, color: '#64748b', marginBottom: 4 }}>{label}</div>
                          <div style={{
                            fontSize: 18, fontWeight: 700,
                            color: isGood ? '#4ade80' : '#f87171',
                          }}>
                            {value > 0 ? '+' : ''}{typeof value === 'number' ? value.toFixed(1) : value}
                          </div>
                        </div>
                      );
                    })}
                  </div>
                </div>
              ) : (
                <div style={{
                  background: 'rgba(20, 20, 50, 0.5)',
                  borderRadius: 16,
                  border: '1px dashed rgba(249, 115, 22, 0.3)',
                  padding: '80px 40px',
                  textAlign: 'center',
                }}>
                  <div style={{ fontSize: 48, marginBottom: 16 }}>🔮</div>
                  <h3 style={{ color: '#94a3b8', margin: '0 0 8px' }}>What-If Analysis</h3>
                  <p style={{ color: '#64748b', fontSize: 13, maxWidth: 400, margin: '0 auto' }}>
                    Select a disruption scenario to simulate. The system will compare
                    baseline operations against the scenario and quantify the impact.
                  </p>
                </div>
              )}
            </div>
          </div>
        )}

        {/* ── EVENTS TAB ── */}
        {activeTab === 'EVENTS' && (
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1.5fr', gap: 24 }}>
            <div style={{
              background: 'rgba(20, 20, 50, 0.7)',
              borderRadius: 16,
              border: '1px solid rgba(99, 102, 241, 0.2)',
              padding: 24,
            }}>
              <h3 style={{ margin: '0 0 16px', color: '#c7d2fe', fontSize: 16 }}>Create Event</h3>

              <label style={labelStyle}>Event Type</label>
              <select
                value={newEvent.event_type}
                onChange={e => setNewEvent({ ...newEvent, event_type: e.target.value })}
                style={{ ...inputStyle, marginBottom: 12 }}
              >
                <option value="CONCERT">🎵 Concert</option>
                <option value="SPORTS_EVENT">⚽ Sports Event</option>
                <option value="FESTIVAL">🎉 Festival</option>
                <option value="EXAMINATION">📝 Examination</option>
                <option value="PUBLIC_GATHERING">📢 Public Gathering</option>
                <option value="RELIGIOUS_EVENT">🕌 Religious Event</option>
                <option value="MARKET_DAY">🛒 Market Day</option>
              </select>

              <label style={labelStyle}>Event Name</label>
              <input
                type="text"
                placeholder="e.g., Kalinga Stadium Concert"
                value={newEvent.name}
                onChange={e => setNewEvent({ ...newEvent, name: e.target.value })}
                style={{ ...inputStyle, marginBottom: 12 }}
              />

              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12, marginBottom: 12 }}>
                <div>
                  <label style={labelStyle}>Duration (hrs)</label>
                  <input type="number" step="0.5" value={newEvent.duration_hours} onChange={e => setNewEvent({ ...newEvent, duration_hours: Number(e.target.value) })} style={inputStyle} />
                </div>
                <div>
                  <label style={labelStyle}>Intensity</label>
                  <input type="number" step="0.5" min="0" max="3" value={newEvent.intensity} onChange={e => setNewEvent({ ...newEvent, intensity: Number(e.target.value) })} style={inputStyle} />
                </div>
              </div>

              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12, marginBottom: 16 }}>
                <div>
                  <label style={labelStyle}>Near Stop ID</label>
                  <input type="number" value={newEvent.location_stop_id} onChange={e => setNewEvent({ ...newEvent, location_stop_id: Number(e.target.value) })} style={inputStyle} />
                </div>
                <div>
                  <label style={labelStyle}>Radius (km)</label>
                  <input type="number" step="0.5" value={newEvent.radius_km} onChange={e => setNewEvent({ ...newEvent, radius_km: Number(e.target.value) })} style={inputStyle} />
                </div>
              </div>

              <button onClick={createEvent} style={{
                width: '100%',
                background: 'linear-gradient(135deg, #8b5cf6, #a855f7)',
                border: 'none',
                borderRadius: 10,
                padding: '12px',
                color: '#fff',
                cursor: 'pointer',
                fontSize: 14,
                fontWeight: 600,
              }}>
                🎪 Create Event
              </button>
            </div>

            {/* Events List */}
            <div>
              <h3 style={{ margin: '0 0 16px', color: '#c7d2fe', fontSize: 16 }}>Active Events ({events.length})</h3>
              {events.length === 0 ? (
                <div style={{
                  background: 'rgba(20, 20, 50, 0.5)',
                  borderRadius: 16,
                  border: '1px dashed rgba(139, 92, 246, 0.3)',
                  padding: '60px 40px',
                  textAlign: 'center',
                }}>
                  <div style={{ fontSize: 48, marginBottom: 12 }}>🎪</div>
                  <p style={{ color: '#64748b', fontSize: 13 }}>
                    No events created yet. Events modify passenger demand at nearby stops
                    through the event engine's distance-decay model.
                  </p>
                </div>
              ) : (
                <div style={{ display: 'grid', gap: 12 }}>
                  {events.map((evt: any) => (
                    <div key={evt.id} style={{
                      background: 'rgba(20, 20, 50, 0.7)',
                      borderRadius: 12,
                      border: '1px solid rgba(139, 92, 246, 0.25)',
                      padding: 16,
                    }}>
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                        <span style={{ fontWeight: 600, color: '#e2e8f0' }}>
                          {evt.name || evt.label}
                        </span>
                        <span style={{
                          fontSize: 11,
                          background: 'rgba(139, 92, 246, 0.2)',
                          color: '#c4b5fd',
                          padding: '2px 10px',
                          borderRadius: 8,
                        }}>
                          {evt.event_type}
                        </span>
                      </div>
                      <div style={{ fontSize: 12, color: '#64748b', marginTop: 6 }}>
                        Intensity: <strong style={{ color: '#fbbf24' }}>{evt.intensity}x</strong> · 
                        Radius: {evt.radius_km} km · 
                        Duration: {evt.duration_hours}h · 
                        Stop: #{evt.location_stop_id}
                      </div>
                      <div style={{ fontSize: 11, color: '#475569', marginTop: 4 }}>
                        {evt.data_source}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

const inputStyle: React.CSSProperties = {
  width: '100%',
  background: 'rgba(15, 15, 35, 0.8)',
  border: '1px solid rgba(99, 102, 241, 0.3)',
  borderRadius: 8,
  padding: '8px 12px',
  color: '#e0e7ff',
  fontSize: 13,
  boxSizing: 'border-box' as const,
};

const labelStyle: React.CSSProperties = {
  fontSize: 12,
  color: '#94a3b8',
  display: 'block',
  marginBottom: 4,
};
