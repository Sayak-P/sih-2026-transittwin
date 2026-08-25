from django.contrib import admin
from django.urls import path, include, re_path
from django.conf import settings
from django.conf.urls.static import static
from rest_framework.routers import DefaultRouter
from core.api_state_views import StateView, VehiclesView, StopsView, SnapshotView, VersionView, SimulationBaselineView, SystemHealthView, DemoResetView
from core.api_health_views import TwinStatusView
from core.api_disruption_views import DisruptionListView, DisruptionSimulateView
from core.api_sandbox_views import SandboxGenerateView, SandboxApproveView

from core.views import StopViewSet, EdgeViewSet, RouteViewSet, VehicleViewSet, DisruptionViewSet
from prediction.views import ODDemandViewSet
from prediction.api_prediction_views import EarlyWarningView
from config.frontend_views import FrontendAppView

from core.api_navigation_views import BusListForNavigatorView, FindClearRouteView
from core.api_bus_availability_views import BusAvailabilityView
from optimization.api_rerouting_views import ReroutingScenariosView, ReroutingCalculateView

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
    path("api/v1/navigation/buses/", BusListForNavigatorView.as_view()),
    path("api/v1/navigation/find-clear-route/", FindClearRouteView.as_view()),
    path("api/v1/navigation/bus-availability/", BusAvailabilityView.as_view()),
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
    
    # Rerouting Pre-Action Sandbox APIs
    path("api/v1/rerouting/scenarios/", ReroutingScenariosView.as_view()),
    path("api/v1/rerouting/calculate/", ReroutingCalculateView.as_view()),
]

# Serve Vite's hashed assets (JS/CSS) from /assets/
urlpatterns += static("/assets/", document_root=settings.FRONTEND_DIST_DIR / "assets")

# Catch-all: serve the SPA shell for any remaining route
urlpatterns += [
    re_path(r"^(?!api/|admin/|ws/|static/|assets/).*$", FrontendAppView.as_view()),
]

