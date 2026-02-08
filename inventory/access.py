from django.db.models import Q

from .models import Asset, Location, OrganizationalGroup


def _group_ids_for_user(user):
    if not user.is_authenticated:
        return set()
    return set(
        OrganizationalGroup.objects.filter(Q(members=user) | Q(admins=user)).values_list("id", flat=True)
    )


def _expand_descendant_location_ids(seed_ids):
    all_ids = set(seed_ids)
    frontier = set(seed_ids)
    while frontier:
        child_ids = set(Location.objects.filter(parent_id__in=frontier).values_list("id", flat=True))
        new_ids = child_ids - all_ids
        if not new_ids:
            break
        all_ids.update(new_ids)
        frontier = new_ids
    return all_ids


def _expand_ancestor_location_ids(seed_ids):
    all_ids = set()
    frontier = set(
        Location.objects.filter(id__in=seed_ids)
        .exclude(parent_id__isnull=True)
        .values_list("parent_id", flat=True)
    )
    while frontier:
        new_ids = frontier - all_ids
        if not new_ids:
            break
        all_ids.update(new_ids)
        frontier = set(
            Location.objects.filter(id__in=new_ids)
            .exclude(parent_id__isnull=True)
            .values_list("parent_id", flat=True)
        )
    return all_ids


def assignable_location_ids_for_user(user):
    if not user.is_authenticated:
        return set()
    if user.is_superuser:
        return set(Location.objects.values_list("id", flat=True))

    group_ids = _group_ids_for_user(user)
    if not group_ids:
        return set()
    direct_ids = set(Location.objects.filter(groups__id__in=group_ids).values_list("id", flat=True))
    if not direct_ids:
        return set()
    return _expand_descendant_location_ids(direct_ids)


def visible_location_ids_for_user(user):
    if not user.is_authenticated:
        return set()
    if user.is_superuser:
        return set(Location.objects.values_list("id", flat=True))

    assignable_ids = assignable_location_ids_for_user(user)
    if not assignable_ids:
        return set()
    ancestor_ids = _expand_ancestor_location_ids(assignable_ids)
    return assignable_ids | ancestor_ids


def assignable_locations_for_user(user):
    ids = assignable_location_ids_for_user(user)
    if not ids:
        return Location.objects.none()
    return Location.objects.filter(id__in=ids).select_related("parent").order_by("name")


def visible_locations_for_user(user):
    ids = visible_location_ids_for_user(user)
    if not ids:
        return Location.objects.none()
    return Location.objects.filter(id__in=ids).select_related("parent").order_by("name")


def visible_assets_for_user(user):
    queryset = Asset.objects.all()
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
