from rest_framework.routers import DefaultRouter
from .views import StopViewSet, RouteViewSet, TripViewSet, StopTimeViewSet

router = DefaultRouter()
router.register("stops", StopViewSet)
router.register("routes", RouteViewSet)
router.register("trips", TripViewSet)
router.register("stop_times", StopTimeViewSet)

urlpatterns = router.urls
