from rest_framework.permissions import SAFE_METHODS, BasePermission
from rest_framework.viewsets import ModelViewSet

from accounts.permissions import IsAdmin, IsNotLocked, IsStaffOrAdmin
from policies.models import LibraryPolicy
from policies.serializers import LibraryPolicySerializer


class PolicyPermissions(BasePermission):
    def has_permission(self, request, view) -> bool:
        if request.method in SAFE_METHODS:
            return IsStaffOrAdmin().has_permission(request, view) and IsNotLocked().has_permission(request, view)
        return IsAdmin().has_permission(request, view) and IsNotLocked().has_permission(request, view)


class PolicyViewSet(ModelViewSet):
    serializer_class = LibraryPolicySerializer
    permission_classes = [PolicyPermissions]
    queryset = LibraryPolicy.objects.all().order_by("name")

    def list(self, request, *args, **kwargs):
        # ensure default exists for MVP
        LibraryPolicy.objects.get_or_create(name="default")
        return super().list(request, *args, **kwargs)
