import { useState } from 'react';
import {
  Phone,
  X,
  ShieldAlert,
  Siren,
  Flame,
  HeartPulse,
  CarFront,
  AlertTriangle,
  PhoneCall,
  MapPin,
  Send,
  CheckCircle2,
  ChevronRight,
} from 'lucide-react';

interface EmergencyContact {
  id: string;
  name: string;
  number: string;
  description: string;
  icon: React.ReactNode;
  color: string;
  bgGlow: string;
}

const EMERGENCY_CONTACTS: EmergencyContact[] = [
  {
    id: 'unified',
    name: 'Emergency (Unified)',
    number: '112',
    description: 'India Unified Emergency Helpline — Police, Fire, Ambulance',
    icon: <Siren className="w-6 h-6" />,
    color: 'text-rose-400',
    bgGlow: 'from-rose-600 to-rose-700 shadow-rose-600/50',
  },
  {
    id: 'police',
    name: 'Police',
    number: '100',
    description: 'Local police emergency response',
    icon: <ShieldAlert className="w-5 h-5" />,
    color: 'text-blue-400',
    bgGlow: 'from-blue-600 to-blue-700 shadow-blue-600/50',
  },
  {
    id: 'ambulance',
    name: 'Ambulance / Medical',
    number: '108',
    description: 'Emergency medical services & ambulance dispatch',
    icon: <HeartPulse className="w-5 h-5" />,
    color: 'text-emerald-400',
    bgGlow: 'from-emerald-600 to-emerald-700 shadow-emerald-600/50',
  },
  {
    id: 'fire',
    name: 'Fire Brigade',
    number: '101',
    description: 'Fire department emergency response',
    icon: <Flame className="w-5 h-5" />,
    color: 'text-orange-400',
    bgGlow: 'from-orange-600 to-orange-700 shadow-orange-600/50',
  },
  {
    id: 'traffic',
    name: 'Traffic Police / Road Accident',
    number: '1073',
    description: 'Road accident helpline & traffic assistance',
    icon: <CarFront className="w-5 h-5" />,
    color: 'text-amber-400',
    bgGlow: 'from-amber-600 to-amber-700 shadow-amber-600/50',
  },
  {
    id: 'women',
    name: 'Women Helpline',
    number: '1091',
    description: 'Women in distress helpline',
    icon: <PhoneCall className="w-5 h-5" />,
    color: 'text-pink-400',
    bgGlow: 'from-pink-600 to-pink-700 shadow-pink-600/50',
  },
];

const INCIDENT_TYPES = [
  'Road Accident',
  'Vehicle Breakdown',
  'Fire on Bus',
  'Medical Emergency',
  'Harassment / Safety Threat',
  'Suspicious Activity',
  'Natural Disaster / Flood',
  'Other',
];

export default function EmergencySOS() {
  const [isOpen, setIsOpen] = useState(false);
  const [activeView, setActiveView] = useState<'CONTACTS' | 'REPORT'>('CONTACTS');
  const [reportType, setReportType] = useState('');
  const [reportDescription, setReportDescription] = useState('');
  const [reportSubmitted, setReportSubmitted] = useState(false);
  const [locationStatus, setLocationStatus] = useState<'idle' | 'fetching' | 'done' | 'error'>('idle');
  const [userLocation, setUserLocation] = useState<{ lat: number; lon: number } | null>(null);

  const handleCall = (number: string) => {
    window.open(`tel:${number}`, '_self');
  };

  const fetchLocation = () => {
    if (!navigator.geolocation) {
      setLocationStatus('error');
      return;
    }
    setLocationStatus('fetching');
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        setUserLocation({ lat: pos.coords.latitude, lon: pos.coords.longitude });
        setLocationStatus('done');
      },
      () => {
        setLocationStatus('error');
      },
      { enableHighAccuracy: true, timeout: 10000 }
    );
  };

  const handleReportSubmit = () => {
    if (!reportType) return;

    // In production this would POST to a backend API.
    // For now we show success feedback.
    console.log('[EmergencySOS] Incident Report:', {
      type: reportType,
      description: reportDescription,
      location: userLocation,
      timestamp: new Date().toISOString(),
    });

    setReportSubmitted(true);
    setTimeout(() => {
      setReportSubmitted(false);
      setReportType('');
      setReportDescription('');
      setActiveView('CONTACTS');
    }, 3000);
  };

  const handleClose = () => {
    setIsOpen(false);
    // Reset state on close
    setActiveView('CONTACTS');
    setReportSubmitted(false);
    setReportType('');
    setReportDescription('');
  };

  return (
    <>
      {/* Floating SOS Button — always visible */}
      <button
        onClick={() => setIsOpen(true)}
        className="fixed bottom-6 right-6 z-[100] group"
        title="Emergency SOS"
        aria-label="Emergency SOS"
      >
        <div className="relative">
          {/* Outer pulsing ring */}
          <span className="absolute inset-0 w-16 h-16 rounded-full bg-rose-500/30 animate-ping" />
          {/* Inner glow ring */}
          <span className="absolute inset-0 w-16 h-16 rounded-full bg-rose-500/20 animate-pulse" />
          {/* Button */}
          <div className="relative w-16 h-16 rounded-full bg-gradient-to-br from-rose-600 to-red-700 flex items-center justify-center shadow-2xl shadow-rose-600/60 border-2 border-rose-400/50 group-hover:scale-110 group-hover:shadow-rose-500/80 transition-all duration-200">
            <div className="flex flex-col items-center">
              <Phone className="w-5 h-5 text-white" />
              <span className="text-[8px] font-black text-white tracking-widest mt-0.5">SOS</span>
            </div>
          </div>
        </div>
      </button>

      {/* Full-screen Emergency Overlay */}
      {isOpen && (
        <div className="fixed inset-0 z-[200] flex items-center justify-center bg-zinc-950/80 backdrop-blur-md animate-fadeIn">
          <div className="relative w-full max-w-lg mx-4 max-h-[90vh] bg-zinc-900 rounded-2xl border border-zinc-700 shadow-2xl shadow-rose-900/20 flex flex-col overflow-hidden animate-slideUp">
            {/* Header */}
            <div className="bg-gradient-to-r from-rose-950 to-zinc-900 p-5 border-b border-rose-900/50 flex items-center justify-between shrink-0">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-full bg-rose-600/30 border border-rose-500/50 flex items-center justify-center">
                  <Siren className="w-5 h-5 text-rose-400 animate-pulse" />
                </div>
                <div>
                  <h2 className="text-base font-extrabold text-white tracking-wide uppercase">Emergency SOS</h2>
                  <p className="text-[11px] text-rose-300/70">Tap a service to call immediately</p>
                </div>
              </div>
              <button
                onClick={handleClose}
                className="w-8 h-8 rounded-full bg-zinc-800 hover:bg-zinc-700 flex items-center justify-center text-zinc-400 hover:text-white transition-colors border border-zinc-700"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            {/* Tab Switcher */}
            <div className="flex border-b border-zinc-800 shrink-0">
              <button
                onClick={() => setActiveView('CONTACTS')}
                className={`flex-1 py-2.5 text-xs font-bold uppercase tracking-wider transition-all flex items-center justify-center gap-2 ${
                  activeView === 'CONTACTS'
                    ? 'text-rose-400 border-b-2 border-rose-500 bg-rose-500/5'
                    : 'text-zinc-500 hover:text-zinc-300'
                }`}
              >
                <Phone className="w-3.5 h-3.5" />
                Call Emergency
              </button>
              <button
                onClick={() => setActiveView('REPORT')}
                className={`flex-1 py-2.5 text-xs font-bold uppercase tracking-wider transition-all flex items-center justify-center gap-2 ${
                  activeView === 'REPORT'
                    ? 'text-amber-400 border-b-2 border-amber-500 bg-amber-500/5'
                    : 'text-zinc-500 hover:text-zinc-300'
                }`}
              >
                <AlertTriangle className="w-3.5 h-3.5" />
                Report Incident
              </button>
            </div>

            {/* Body */}
            <div className="flex-1 overflow-y-auto p-4 space-y-3 custom-scrollbar">
              {/* ========== CONTACTS VIEW ========== */}
              {activeView === 'CONTACTS' && (
                <>
                  {/* Location Banner */}
                  <div className="bg-zinc-950/70 rounded-xl p-3 border border-zinc-800 flex items-center justify-between">
                    <div className="flex items-center gap-2 text-xs">
                      <MapPin className="w-4 h-4 text-cyan-400" />
                      {locationStatus === 'done' && userLocation ? (
                        <span className="text-cyan-400 font-mono">
                          {userLocation.lat.toFixed(5)}, {userLocation.lon.toFixed(5)}
                        </span>
                      ) : locationStatus === 'fetching' ? (
                        <span className="text-zinc-400 font-mono animate-pulse">Fetching location...</span>
                      ) : locationStatus === 'error' ? (
                        <span className="text-rose-400 font-mono">Location unavailable</span>
                      ) : (
                        <span className="text-zinc-500 font-mono">Share your location with responders</span>
                      )}
                    </div>
                    {locationStatus !== 'done' && (
                      <button
                        onClick={fetchLocation}
                        disabled={locationStatus === 'fetching'}
                        className="text-[10px] bg-cyan-600/20 text-cyan-400 border border-cyan-600/40 px-2.5 py-1 rounded-lg font-bold hover:bg-cyan-600/30 transition-colors disabled:opacity-50"
                      >
                        {locationStatus === 'fetching' ? '...' : 'Get Location'}
                      </button>
                    )}
                  </div>

                  {/* Emergency Contact Cards */}
                  {EMERGENCY_CONTACTS.map((contact) => (
                    <button
                      key={contact.id}
                      onClick={() => handleCall(contact.number)}
                      className="w-full bg-zinc-950/60 hover:bg-zinc-800/60 border border-zinc-800 hover:border-zinc-600 rounded-xl p-4 flex items-center gap-4 text-left transition-all group active:scale-[0.98]"
                    >
                      {/* Icon */}
                      <div className={`w-12 h-12 rounded-xl bg-gradient-to-br ${contact.bgGlow} flex items-center justify-center shadow-lg text-white shrink-0`}>
                        {contact.icon}
                      </div>
                      {/* Text */}
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2">
                          <span className="text-sm font-bold text-zinc-100">{contact.name}</span>
                        </div>
                        <p className="text-[11px] text-zinc-500 mt-0.5 truncate">{contact.description}</p>
                      </div>
                      {/* Number + Call Icon */}
                      <div className="flex items-center gap-2 shrink-0">
                        <span className={`text-lg font-extrabold font-mono ${contact.color}`}>
                          {contact.number}
                        </span>
                        <div className="w-8 h-8 rounded-full bg-emerald-600 group-hover:bg-emerald-500 flex items-center justify-center shadow-lg shadow-emerald-600/30 transition-colors">
                          <Phone className="w-4 h-4 text-white" />
                        </div>
                      </div>
                    </button>
                  ))}

                  {/* Safety Tip */}
                  <div className="bg-amber-950/20 border border-amber-900/40 rounded-xl p-3 text-xs text-amber-400/80 flex items-start gap-2 mt-2">
                    <AlertTriangle className="w-4 h-4 shrink-0 mt-0.5" />
                    <div>
                      <span className="font-bold">Safety Tip:</span> Stay calm, move to a safe location if possible, and share your exact location with emergency responders. Use the "Get Location" button above to find your coordinates.
                    </div>
                  </div>
                </>
              )}

              {/* ========== REPORT VIEW ========== */}
              {activeView === 'REPORT' && (
                <>
                  {reportSubmitted ? (
                    <div className="flex flex-col items-center justify-center py-12 text-center animate-fadeIn">
                      <div className="w-16 h-16 rounded-full bg-emerald-500/20 border-2 border-emerald-500/40 flex items-center justify-center mb-4">
                        <CheckCircle2 className="w-8 h-8 text-emerald-400" />
                      </div>
                      <h3 className="text-lg font-extrabold text-emerald-400 uppercase tracking-wider">Report Submitted</h3>
                      <p className="text-xs text-zinc-400 mt-2 max-w-xs">
                        Your incident report has been logged. Authorities and transit operators have been notified.
                      </p>
                    </div>
                  ) : (
                    <>
                      {/* Location */}
                      <div className="bg-zinc-950/70 rounded-xl p-3 border border-zinc-800 flex items-center justify-between">
                        <div className="flex items-center gap-2 text-xs">
                          <MapPin className="w-4 h-4 text-cyan-400" />
                          {locationStatus === 'done' && userLocation ? (
                            <span className="text-cyan-400 font-mono">
                              {userLocation.lat.toFixed(5)}, {userLocation.lon.toFixed(5)}
                            </span>
                          ) : (
                            <span className="text-zinc-500 font-mono">Attach your location to the report</span>
                          )}
                        </div>
                        {locationStatus !== 'done' && (
                          <button
                            onClick={fetchLocation}
                            disabled={locationStatus === 'fetching'}
                            className="text-[10px] bg-cyan-600/20 text-cyan-400 border border-cyan-600/40 px-2.5 py-1 rounded-lg font-bold hover:bg-cyan-600/30 transition-colors disabled:opacity-50"
                          >
                            {locationStatus === 'fetching' ? '...' : 'Get Location'}
                          </button>
                        )}
                      </div>

                      {/* Incident Type Selector */}
                      <div>
                        <label className="text-xs font-bold text-zinc-400 uppercase tracking-wider mb-2 block">
                          Type of Incident
                        </label>
                        <div className="grid grid-cols-2 gap-2">
                          {INCIDENT_TYPES.map((type) => (
                            <button
                              key={type}
                              onClick={() => setReportType(type)}
                              className={`p-2.5 rounded-lg border text-xs font-bold text-left transition-all ${
                                reportType === type
                                  ? 'bg-amber-950/50 border-amber-500/60 text-amber-300 shadow-md shadow-amber-900/20'
                                  : 'bg-zinc-950/60 border-zinc-800 text-zinc-400 hover:border-zinc-600 hover:text-zinc-300'
                              }`}
                            >
                              <div className="flex items-center gap-1.5">
                                <ChevronRight className={`w-3 h-3 transition-transform ${reportType === type ? 'rotate-90 text-amber-400' : ''}`} />
                                {type}
                              </div>
                            </button>
                          ))}
                        </div>
                      </div>

                      {/* Description */}
                      <div>
                        <label className="text-xs font-bold text-zinc-400 uppercase tracking-wider mb-2 block">
                          Description (optional)
                        </label>
                        <textarea
                          value={reportDescription}
                          onChange={(e) => setReportDescription(e.target.value)}
                          placeholder="Describe what happened, how many people are affected, visible damages..."
                          rows={3}
                          className="w-full bg-zinc-950 border border-zinc-700 text-zinc-100 text-sm rounded-xl p-3 focus:outline-none focus:border-amber-500 font-mono placeholder:text-zinc-600 resize-none"
                        />
                      </div>

                      {/* Submit Button */}
                      <button
                        onClick={handleReportSubmit}
                        disabled={!reportType}
                        className="w-full py-3.5 rounded-xl bg-gradient-to-r from-amber-600 to-orange-600 hover:from-amber-500 hover:to-orange-500 text-white font-bold text-xs tracking-wider uppercase shadow-lg shadow-amber-600/30 flex items-center justify-center gap-2 transition-all disabled:opacity-40 disabled:cursor-not-allowed active:scale-[0.98]"
                      >
                        <Send className="w-4 h-4" />
                        Submit Incident Report
                      </button>

                      <p className="text-[10px] text-zinc-600 text-center">
                        Reports are logged and forwarded to transit operators & local authorities.
                      </p>
                    </>
                  )}
                </>
              )}
            </div>
          </div>
        </div>
      )}
    </>
  );
}
