interface LandingPageProps {
  onEnterNavigator: () => void;
  onEnterCommandCenter: () => void;
  onEnterPredictions: () => void;
  onEnterRerouting: () => void;
  onEnterInterventions?: () => void;
}

export default function LandingPage({ onEnterNavigator, onEnterCommandCenter, onEnterPredictions, onEnterRerouting, onEnterInterventions }: LandingPageProps) {
  return (
    <div className="landing-page bg-background text-on-surface antialiased font-body-md selection:bg-surface-tint/30 selection:text-surface-tint relative min-h-screen">
      {/* Noise Overlay */}
      <div className="noise-bg"></div>

      {/* HUD Side Decoration */}
      <div className="fixed left-4 top-1/2 -translate-y-1/2 -rotate-90 origin-left z-40 hidden xl:flex gap-8 items-center text-on-surface-variant font-label-sm tracking-[0.2em] opacity-60">
        <span>SYSTEM_ID: TT-X1</span>
        <span className="w-1 h-1 bg-on-surface-variant/50 rounded-full"></span>
        <span>LATENCY: 12ms</span>
        <span className="w-1 h-1 bg-on-surface-variant/50 rounded-full"></span>
        <span className="flex items-center gap-2">
          <span className="w-1.5 h-1.5 bg-success-tonal rounded-full blinking-dot"></span>
          UPTIME: 99.9%
        </span>
      </div>

      {/* Top NavBar */}
      <nav className="fixed top-0 w-full z-50 flex justify-between items-center h-20 px-6 lg:px-12 bg-background/60 backdrop-blur-2xl border-b border-white/5">
        <div className="flex items-center gap-12">
          <div className="font-display-lg text-lg font-bold tracking-tighter flex items-center gap-2">
            <span className="material-symbols-outlined text-primary text-xl">layers</span>
            <span className="text-white">Transit<span className="text-secondary font-medium">Twin</span></span>
          </div>
          <div className="hidden md:flex gap-8 items-center">
            <button onClick={onEnterNavigator} className="font-label-sm text-on-surface-variant hover:text-white transition-colors tracking-wide bg-transparent border-none cursor-pointer">Live Map</button>
            <button onClick={onEnterPredictions} className="font-label-sm text-on-surface-variant hover:text-white transition-colors tracking-wide bg-transparent border-none cursor-pointer">Predictions</button>
            <button onClick={onEnterRerouting} className="font-label-sm text-on-surface-variant hover:text-white transition-colors tracking-wide bg-transparent border-none cursor-pointer">Rerouting</button>
            {onEnterInterventions && (
              <button onClick={onEnterInterventions} className="font-label-sm text-secondary hover:text-white transition-colors tracking-wide bg-transparent border-none cursor-pointer">Interventions</button>
            )}
            <button onClick={onEnterCommandCenter} className="font-label-sm text-on-surface-variant hover:text-white transition-colors tracking-wide bg-transparent border-none cursor-pointer">Analytics</button>
          </div>
        </div>
        <div className="flex items-center gap-6">
          <button className="font-label-sm text-on-surface-variant hover:text-white transition-colors uppercase tracking-wider bg-transparent border-none cursor-pointer">Log In</button>
          <button
            onClick={onEnterCommandCenter}
            className="bg-surface-container-high border border-outline-variant hover:border-surface-tint hover:bg-surface-container-highest text-white px-5 py-2.5 rounded font-label-sm tracking-wider uppercase transition-all duration-300 flex items-center gap-2 cursor-pointer"
          >
            <span className="w-1.5 h-1.5 rounded-full bg-secondary blinking-dot"></span>
            Command Center
          </button>
        </div>
      </nav>

      <main className="relative z-10">
        {/* Hero Section */}
        <section className="min-h-screen relative flex items-center pt-20 overflow-hidden">
          {/* Full bleed map visual on right */}
          <div
            className="absolute inset-y-0 right-0 w-full lg:w-[65%] hero-map-overlay z-0 opacity-80 mix-blend-lighten"
            style={{
              backgroundImage: `url('https://lh3.googleusercontent.com/aida-public/AB6AXuCMIPRDRhAQLWFTxICY0_oU7WF9XKSc6qKHjI7uyPH11rKfOWpmj85hHQutVhY288Zq1MK1NeShzUvV5aqXvz4kzSV54_XYWOinHsX840dxWF6HPQ2pkrN_qayQQHWjuvQVoMCH1MXwNN4J3tG2zLi9dSPmcobao66OwgNEBr6mVMUlvx1JO_hqm0QQ_iSRWZxa-e7u5YF3ghvztWGUB329YqPByG5gYLa5DW49BtcsaTpm7c8xacsqHg')`,
              backgroundSize: 'cover',
              backgroundPosition: 'center',
            }}
          >
            <div className="absolute inset-0 bg-background/60"></div>
          </div>

          <div className="w-full px-6 lg:px-12 mx-auto max-w-[1600px] flex flex-col lg:flex-row items-center justify-between gap-12 relative z-10">
            {/* Left Content */}
            <div className="w-full lg:w-[45%] flex flex-col gap-8">
              <div className="flex items-center gap-4 font-label-sm text-on-surface-variant tracking-[0.15em] uppercase">
                <span>Systems</span>
                <span className="w-px h-3 bg-white/20"></span>
                <span className="text-surface-tint flex items-center gap-2">
                  <span className="w-1.5 h-1.5 rounded-full bg-surface-tint animate-pulse"></span>
                  Platform v2.4 Active
                </span>
              </div>

              <div className="font-display-lg text-4xl md:text-5xl font-bold tracking-tighter flex items-center gap-3 mb-2">
                <span className="material-symbols-outlined text-surface-tint text-4xl">layers</span>
                <span className="text-white">Transit<span className="text-secondary">Twin</span></span>
              </div>

              <h1 className="font-display-lg text-white leading-[1.1] tracking-tight text-4xl md:text-5xl">
                The Future of <br /> Urban Transit, <br />
                <span className="custom-gradient-text font-semibold">Decoded.</span>
              </h1>

              <p className="font-body-lg text-on-surface-variant max-w-lg leading-relaxed border-l-[3px] border-surface-container-highest pl-6 py-2">
                TransitTwin is a sophisticated digital twin platform for public transport networks. Predict crowding, analyze disruptions, and simulate interventions in real-time.
              </p>

              <div className="glass-panel-deep p-6 rounded-xl mt-4 max-w-md tech-border-top">
                <div className="flex flex-col gap-4">
                  <div className="flex justify-between items-center pb-4 border-b border-white/5">
                    <span className="font-label-md text-on-surface-variant">SYS_READY</span>
                    <span className="font-label-sm text-surface-tint bg-surface-tint/10 px-2 py-1 rounded">SECURE CONNECTION</span>
                  </div>
                  <div className="flex items-center gap-4 pt-2">
                    <button
                      onClick={onEnterNavigator}
                      className="flex-1 bg-white text-surface hover:bg-surface-tint px-6 py-3.5 rounded font-label-md tracking-wider uppercase transition-colors font-bold flex justify-center items-center gap-2 cursor-pointer border-none"
                    >
                      Initialize Dashboard
                      <span className="material-symbols-outlined text-[18px]">arrow_forward</span>
                    </button>
                    <button
                      onClick={onEnterCommandCenter}
                      className="p-3.5 rounded border border-white/10 hover:bg-white/5 text-on-surface transition-colors flex items-center justify-center group cursor-pointer bg-transparent"
                    >
                      <span className="material-symbols-outlined text-[20px] group-hover:text-surface-tint">terminal</span>
                    </button>
                  </div>
                </div>
              </div>
            </div>

            {/* Right Overlays (Floating Data) */}
            <div className="w-full lg:w-[45%] h-full min-h-[500px] relative hidden lg:block">
              <div className="absolute top-20 right-10 glass-panel-light p-4 rounded-lg min-w-[200px]">
                <div className="font-label-sm text-on-surface-variant mb-2">ACTIVE NODES</div>
                <div className="font-headline-lg text-white font-medium">14,293</div>
                <div className="data-stream mt-2">STREAM: 0x4F2A... [OK]</div>
              </div>
              <div className="absolute bottom-32 right-32 glass-panel-light p-4 rounded-lg flex items-center gap-4">
                <div className="w-10 h-10 rounded bg-success-tonal/10 flex items-center justify-center border border-success-tonal/20">
                  <span className="material-symbols-outlined text-success-tonal text-lg">wifi_tethering</span>
                </div>
                <div>
                  <div className="font-label-sm text-on-surface-variant">NETWORK LATENCY</div>
                  <div className="font-headline-sm text-success-tonal font-medium">12ms</div>
                </div>
              </div>
            </div>
          </div>
        </section>

        {/* Features Section */}
        <section className="py-32 px-6 lg:px-12 max-w-[1600px] mx-auto relative">
          <div className="flex flex-col md:flex-row justify-between items-end mb-16 gap-8 border-b border-white/5 pb-8">
            <div className="max-w-2xl">
              <h2 className="font-headline-lg text-white mb-4">Platform Capabilities</h2>
              <p className="font-body-md text-on-surface-variant">
                Mission-critical tools for modern transit authorities, designed for precision and rapid response across complex networks.
              </p>
            </div>
            <div className="font-label-sm text-surface-tint tracking-widest uppercase border border-surface-tint/20 px-4 py-2 rounded bg-surface-tint/5">
              Modules 01 - 03
            </div>
          </div>

          {/* Dynamic Grid Layout */}
          <div className="grid grid-cols-1 md:grid-cols-12 gap-6 auto-rows-[minmax(300px,auto)]">
            {/* Live Command (Large) */}
            <div className="md:col-span-8 glass-panel-deep rounded-2xl p-8 lg:p-10 flex flex-col justify-between group overflow-hidden relative tech-border-top min-h-[480px]">
              <div className="relative z-10 flex flex-col md:flex-row justify-between gap-8 h-full">
                <div className="md:w-5/12 flex flex-col justify-between">
                  <div>
                    <div className="w-10 h-10 rounded bg-primary-fixed-dim/10 border border-primary-fixed-dim/20 flex items-center justify-center text-primary-fixed-dim mb-6">
                      <span className="material-symbols-outlined text-lg">my_location</span>
                    </div>
                    <h3 className="font-headline-md text-white mb-4">Live Command</h3>
                    <p className="font-body-md text-on-surface-variant leading-relaxed">
                      Real-time network oversight with granular vehicle tracking. Monitor schedule adherence, vehicle health, and crew status from a single unified interface.
                    </p>
                  </div>
                  <button
                    onClick={onEnterCommandCenter}
                    className="font-label-sm text-white uppercase tracking-wider hover:text-surface-tint mt-8 flex items-center gap-2 transition-colors w-max group-hover:gap-3 bg-transparent border-none cursor-pointer"
                  >
                    Explore Module <span className="material-symbols-outlined text-sm">arrow_forward</span>
                  </button>
                </div>
                <div className="md:w-7/12 relative h-full min-h-[200px] rounded-xl border border-white/10 overflow-hidden bg-surface-container-lowest">
                  <div
                    className="absolute inset-0 bg-cover bg-center opacity-60 group-hover:opacity-90 transition-opacity duration-700"
                    style={{
                      backgroundImage: `url('https://lh3.googleusercontent.com/aida-public/AB6AXuAbf1X6wJEyltjMBNHdhzIZOGM-AxnmHsjMZq82ROF0BmtmNtl-aSb2YuUJINr_SE2Ec_3cvYJrCTDExEskgjxz-rGT34tweHETUXCKprkLgBZjoumq0wV1ZQUtZXH2kRZv0IF_WYgm38Kv5BZJnhgKKk4iFq5zj7bKFpunMrV4dQZaNq_3OFjLTS0yq5hyDU-UHaCDuaYbsLlOU1laAwB5K5QNvL43aW6JpbSUq1TIBD3rFbzWs5g5yQ')`,
                    }}
                  ></div>
                  <div className="absolute top-4 left-4 bg-background/80 backdrop-blur-md px-3 py-1.5 rounded border border-white/10 font-label-sm flex items-center gap-2">
                    <span className="w-1.5 h-1.5 bg-error rounded-full blinking-dot"></span>
                    3 MINOR DELAYS
                  </div>
                </div>
              </div>
            </div>

            {/* Predictive Analytics (Vertical) */}
            <div
              onClick={onEnterPredictions}
              className="md:col-span-4 glass-panel-light hover:border-surface-tint rounded-2xl p-8 lg:p-10 flex flex-col justify-between group tech-border-top cursor-pointer transition-all"
            >
              <div>
                <div className="flex justify-between items-start mb-6">
                  <div className="w-10 h-10 rounded bg-tertiary-fixed-dim/10 border border-tertiary-fixed-dim/20 flex items-center justify-center text-tertiary-fixed-dim">
                    <span className="material-symbols-outlined text-lg">insights</span>
                  </div>
                  <span className="font-label-sm text-on-surface-variant/50">MOD_02</span>
                </div>
                <h3 className="font-headline-sm text-white mb-3 flex items-center justify-between">
                  <span>Predictive Analytics</span>
                  <span className="material-symbols-outlined text-sm opacity-0 group-hover:opacity-100 transition-opacity">arrow_forward</span>
                </h3>
                <p className="font-body-md text-on-surface-variant leading-relaxed">
                  Anticipate crowd surges and capacity breaches before they happen using machine learning models trained on historical data.
                </p>
              </div>
              <div className="mt-8 flex items-end h-32 gap-1.5 opacity-70 group-hover:opacity-100 transition-opacity">
                <div className="w-full bg-surface-container-high h-[20%] rounded-t-sm"></div>
                <div className="w-full bg-surface-container-high h-[40%] rounded-t-sm"></div>
                <div className="w-full bg-surface-container-high h-[70%] rounded-t-sm"></div>
                <div className="w-full bg-surface-tint/30 h-[95%] rounded-t-sm border-t-2 border-surface-tint relative group-hover:bg-surface-tint/50 transition-colors">
                  <div className="absolute -top-7 left-1/2 -translate-x-1/2 font-label-sm text-surface-tint bg-background px-2 py-0.5 rounded border border-surface-tint/30">95%</div>
                </div>
                <div className="w-full bg-surface-container-high h-[50%] rounded-t-sm"></div>
                <div className="w-full bg-surface-container-high h-[30%] rounded-t-sm"></div>
              </div>
            </div>

            {/* Rerouting Sandbox (Wide Bottom) */}
            <div className="md:col-span-12 glass-panel-deep rounded-2xl p-8 lg:p-10 flex flex-col md:flex-row items-center gap-10 tech-border-top">
              <div className="md:w-[35%] flex flex-col">
                <div className="flex items-center gap-4 mb-6">
                  <div className="w-10 h-10 rounded bg-secondary-fixed-dim/10 border border-secondary-fixed-dim/20 flex items-center justify-center text-secondary-fixed-dim">
                    <span className="material-symbols-outlined text-lg">alt_route</span>
                  </div>
                  <span className="font-label-sm text-on-surface-variant/50">MOD_03</span>
                </div>
                <h3 className="font-headline-sm text-white mb-4">Rerouting Sandbox</h3>
                <p className="font-body-md text-on-surface-variant leading-relaxed mb-8">
                  Evaluate multi-objective alternate transit paths when road segments are blocked. Quantifies delay savings, M/M/c safety hazard index, and energy impacts without auto-dispatching.
                </p>
                <button
                  onClick={onEnterRerouting}
                  className="font-label-sm text-white border border-secondary/30 bg-primary-container/20 hover:bg-primary-container/40 px-6 py-3 rounded tracking-wider uppercase transition-colors flex items-center gap-2 w-max cursor-pointer text-secondary"
                >
                  <span className="material-symbols-outlined text-[16px]">alt_route</span>
                  Evaluate Rerouting
                </button>
              </div>
              <div className="md:w-[65%] w-full h-[300px] glass-panel-light rounded-xl border border-white/5 relative overflow-hidden p-2">
                <div
                  className="absolute inset-2 rounded-lg bg-cover bg-center opacity-70"
                  style={{
                    backgroundImage: `url('https://lh3.googleusercontent.com/aida-public/AB6AXuA-vGXRkxe57YCUCAbR-x1yqS1ga7VgMbpd8fMdxeP4AzJqphEcDRPBnetEOOJkf-6kGxT1qO4u28tdFsEFvWVL5hU_r55hnNh7XDesClcY9EoqusYTiSemzvoCKoAbmiAV2HksvIiO-0qLp9GbSQ2w4PmhCyDpdMxGmT6WIPuomWa3xvziTfN_kM6IdM2Eo5PxBflnX0GrmTs2UMistuUiU7QIms5tbnJbl6QoQpjlvidRV5ykLyH4IA')`,
                  }}
                ></div>
                <div className="absolute top-4 left-4 font-label-sm text-on-surface-variant bg-background/90 px-3 py-1 rounded border border-white/10 flex items-center gap-2">
                  <span className="w-1.5 h-1.5 rounded-full bg-secondary animate-pulse"></span>
                  PRE-ACTION REROUTING: W(e) = α(T_e) + β(E_e) + γ(A_e)
                </div>
              </div>
            </div>
          </div>
        </section>
      </main>

      {/* Footer */}
      <footer className="border-t border-white/10 bg-surface-container-lowest py-10 px-6 lg:px-12 relative z-10">
        <div className="max-w-[1600px] mx-auto flex flex-col md:flex-row justify-between items-center gap-6">
          <div className="font-display-lg text-lg font-bold tracking-tighter flex items-center gap-2 opacity-50">
            <span className="material-symbols-outlined text-xl">layers</span>
            <span>TransitTwin</span>
          </div>
          <div className="flex gap-8">
            <button className="font-label-sm text-on-surface-variant hover:text-white transition-colors uppercase tracking-wider bg-transparent border-none cursor-pointer">Privacy</button>
            <button className="font-label-sm text-on-surface-variant hover:text-white transition-colors uppercase tracking-wider bg-transparent border-none cursor-pointer">Terms</button>
            <button className="font-label-sm text-on-surface-variant hover:text-white transition-colors uppercase tracking-wider bg-transparent border-none cursor-pointer">System Status</button>
          </div>
          <div className="font-label-sm text-on-surface-variant/40 font-mono">
            © 2024 TRANSITTWIN SYSTEMS. BUILD: 2.4.1
          </div>
        </div>
      </footer>
    </div>
  );
}
