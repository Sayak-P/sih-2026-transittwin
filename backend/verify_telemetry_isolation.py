import os
import django
from django.conf import settings
from django.core.management import call_command

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from simulation.state.live_state import LiveStateEngine
from django.core.cache import cache

def verify():
    print("--- Starting Phase 16.6 Verification ---")
    
    # Force LIVE mode
    settings.TRANSIT_TWIN_MODE = 'LIVE'
    print(f"Set TRANSIT_TWIN_MODE = {settings.TRANSIT_TWIN_MODE}")
    
    # 1. Clear cache
    cache.clear()
    
    # 2. Try running telemetry simulator
    print("Attempting to run telemetry simulator...")
    try:
        call_command('run_telemetry_simulator', ticks=1)
    except SystemExit:
        pass
        
    state = LiveStateEngine.get_current_state()
    vehicles = state.get('vehicles', {})
    print(f"Vehicles in LiveState after simulator: {len(vehicles)}")
    assert len(vehicles) == 0, "Simulator injected telemetry in LIVE mode!"
    
    # 3. Try Demo Reset endpoint logic directly
    print("Attempting Demo Reset via API view...")
    from django.test import RequestFactory
    from core.api_state_views import DemoResetView
    
    factory = RequestFactory()
    request = factory.post('/api/v1/system/demo-reset/')
    view = DemoResetView.as_view()
    
    response = view(request)
    print(f"Demo Reset Response: {response.status_code}")
    
    state = LiveStateEngine.get_current_state()
    vehicles = state.get('vehicles', {})
    print(f"Vehicles in LiveState after DemoReset: {len(vehicles)}")
    
    assert len(vehicles) == 0, "DemoResetView injected mock telemetry in LIVE mode!"
    
    print("--- SUCCESS: No mock telemetry leaked into LiveStateEngine in LIVE mode! ---")

if __name__ == "__main__":
    verify()
