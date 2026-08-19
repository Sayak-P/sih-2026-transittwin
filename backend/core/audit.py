from core.models import AuditLog

class AuditService:
    @staticmethod
    def log_approval(scenario_id: str, candidate_id: str, operator_id: str, action: str):
        entry = AuditLog.objects.create(
            scenario_id=scenario_id,
            candidate_id=candidate_id,
            operator_identifier=operator_id,
            action=action
        )
        print(f"[AUDIT LOG] {operator_id} approved {action} for {candidate_id} in {scenario_id}")
        return {
            "id": entry.id,
            "timestamp": entry.timestamp,
            "scenario_id": scenario_id,
            "candidate_id": candidate_id,
            "operator_id": operator_id,
            "action": action
        }
