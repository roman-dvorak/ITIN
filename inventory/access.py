from django.db.models import Q

from .models import Asset


def visible_assets_for_user(user):
    queryset = Asset.objects.filter(asset_type=Asset.AssetType.COMPUTER)
    if not user.is_authenticated:
        return queryset.none()
    if user.is_superuser:
        return queryset
    return queryset.filter(Q(owner=user) | Q(groups__admins=user)).distinct()


def can_view_asset(user, asset: Asset) -> bool:
    if not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    return asset.owner_id == user.id or asset.groups.filter(id__in=user.asset_admin_groups.values("id")).exists()


def can_edit_asset(user, asset: Asset) -> bool:
    if not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    return asset.groups.filter(id__in=user.asset_admin_groups.values("id")).exists()
