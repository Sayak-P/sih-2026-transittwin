from simulation.models import SimulationScenario
from .live_state import LiveStateEngine
from .simulation_state import SimulationState

class StateSnapshotManager:
    @classmethod
    def create_snapshot(cls):
        # 1. Grab current Live State (which is just a dict from cache)
        current_state = LiveStateEngine.get_current_state()
        version = current_state['version']

        # 2. Persist snapshot metadata to PostgreSQL
        scenario = SimulationScenario.objects.create(
            status='INITIALIZED',
            snapshot_timestamp=current_state.get('timestamp')
        )

        # 3. Create isolated SimulationState in memory
        sim_state = SimulationState(current_state)

        return scenario, sim_state
