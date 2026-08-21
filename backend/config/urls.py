from django.contrib import admin
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from core.api_state_views import StateView, VehiclesView, StopsView, SnapshotView, VersionView, SimulationBaselineView, SystemHealthView, DemoResetView
from core.api_health_views import TwinStatusView
from core.api_disruption_views import DisruptionListView, DisruptionSimulateView
from core.api_sandbox_views import SandboxGenerateView, SandboxApproveView

from core.views import StopViewSet, EdgeViewSet, RouteViewSet, VehicleViewSet, DisruptionViewSet
from prediction.views import ODDemandViewSet
from prediction.api_prediction_views import EarlyWarningView

router = DefaultRouter()
router.register(r'stops', StopViewSet)
router.register(r'edges', EdgeViewSet)
router.register(r'routes', RouteViewSet)
router.register(r'vehicles', VehicleViewSet)
router.register(r'disruptions', DisruptionViewSet)
router.register(r'demand', ODDemandViewSet)

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/v1/disruptions/", DisruptionListView.as_view()),
    path("api/v1/disruptions/<int:pk>/simulate/", DisruptionSimulateView.as_view()),
    path("api/v1/", include(router.urls)),
    
    # Prediction APIs
    path("api/v1/predictions/early-warnings/", EarlyWarningView.as_view()),
    
    # Live State APIs
    path("api/v1/twin/state/", StateView.as_view()),
    path("api/v1/twin/vehicles/", VehiclesView.as_view()),
    path("api/v1/twin/vehicles/<str:vehicle_id>/", VehiclesView.as_view()),
    path("api/v1/twin/stops/", StopsView.as_view()),
    path("api/v1/twin/version/", VersionView.as_view()),
    path("api/v1/twin/snapshots/", SnapshotView.as_view()),
    path("api/v1/twin/simulate-baseline/", SimulationBaselineView.as_view()),
    path("api/v1/twin/status/", TwinStatusView.as_view()),
    path("api/v1/sandbox/generate/", SandboxGenerateView.as_view()),
    path("api/v1/sandbox/<str:candidate_id>/approve/", SandboxApproveView.as_view()),
    path("api/v1/system/health/", SystemHealthView.as_view()),
    path("api/v1/system/demo-reset/", DemoResetView.as_view()),
]
