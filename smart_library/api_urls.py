from django.urls import include, path
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from catalog.views import BookViewSet, CopyViewSet
from circulation.views import HoldViewSet, LoanViewSet, circulation_actions
from policies.views import PolicyViewSet

router = DefaultRouter()
router.register(r"books", BookViewSet, basename="book")
router.register(r"copies", CopyViewSet, basename="copy")
router.register(r"loans", LoanViewSet, basename="loan")
router.register(r"holds", HoldViewSet, basename="hold")
router.register(r"policies", PolicyViewSet, basename="policy")

urlpatterns = [
    path("auth/token/", TokenObtainPairView.as_view(), name="token_obtain_pair"),
    path("auth/token/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
    path("", include(router.urls)),
    path("circulation/", include((circulation_actions, "circulation"))),
]

