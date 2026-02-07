from rest_framework.permissions import SAFE_METHODS, BasePermission

from .access import can_edit_asset, can_view_asset
from .models import Asset


class AssetObjectPermission(BasePermission):
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated)

    def has_object_permission(self, request, view, obj):
        if not isinstance(obj, Asset):
            return False
        if request.method in SAFE_METHODS:
            return can_view_asset(request.user, obj)
        return can_edit_asset(request.user, obj)
