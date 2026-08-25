from rest_framework.views import APIView
from rest_framework.response import Response
from prediction.queue_dynamics import QueueDynamicsEngine

class EarlyWarningView(APIView):
    """
    Returns real-time predictions powered by:
    1. M/M/c Station Crowd Dynamic Queueing formula:
       Crowd(t + dt) = max(0, Crowd(t) + (lambda_base * E_event - mu_boarding) * dt)
    2. NetworkX graph speed degradation delay cascade:
       T_delay(v) = sum_{e in Path(v)} ( Distance(e)/V_congested(e) - Distance(e)/V_free_flow(e) )
    3. Lightweight Scikit-learn Random Forest model predicting E_event surge multiplier.
    """
    def get(self, request):
        horizon = int(request.query_params.get('horizon', 60))
        dt = int(request.query_params.get('dt', 15))
        
        data = QueueDynamicsEngine.compute_station_crowd_predictions(
            horizon_minutes=horizon,
            dt_minutes=dt
        )
        
        # Format warnings list for backward compatibility as well as rich dashboard data
        warnings = []
        for st in data.get('stations', []):
            if st['severity'] in ['CRITICAL', 'WARNING']:
                warnings.append({
                    "stop_id": st['id'],
                    "stop_name": st['name'],
                    "current_queue": st['current_queue'],
                    "predicted_arrivals": st['incomingPax'],
                    "available_capacity": max(0, st['capacity'] - st['current_queue']),
                    "predicted_crowd": st['predicted_crowd_15m'],
                    "predicted_crowd_60m": st['predicted_crowd_60m'],
                    "crowding_ratio": st['crowding_ratio'],
                    "severity": st['severity'],
                    "minutes_to_impact": st['etaMinutes'],
                    "lambda_base": st['lambda_base'],
                    "e_event": st['e_event'],
                    "mu_boarding": st['mu_boarding'],
                    "net_arrival_rate": st['net_arrival_rate'],
                    "explanation": (
                        f"Crowd Spike (M/M/c): λ={st['lambda_base']} * E_event={st['e_event']} > μ={st['mu_boarding']}"
                        if st['severity'] == "CRITICAL"
                        else f"Elevated arrivals: λ={st['lambda_base']} * E_event={st['e_event']}"
                    ),
                    "action_text": st['actionText']
                })

        data['warnings'] = warnings
        return Response(data)
