from django.contrib.auth import authenticate, login
from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.utils import timezone
from drf_spectacular.utils import extend_schema
from rest_framework.authtoken.models import Token
from rest_framework import mixins, serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .access import (
    can_edit_asset,
    visible_assets_for_user,
    visible_location_ids_for_user,
    visible_locations_for_user,
)
from .models import (
    Asset,
    GuestDevice,
    Location,
    Network,
    NetworkInterface,
    OrganizationalGroup,
    OSFamily,
    Port,
)
from .permissions import AssetObjectPermission
from .serializers import (
    ApiLoginSerializer,
    AssetPortInterfaceCreateSerializer,
    AssetCreateSerializer,
    AssetListSerializer,
    AssetUpdateSerializer,
    BulkAssetRowSerializer,
    BulkInterfaceRowSerializer,
    GuestApprovalDecisionSerializer,
    GuestDeviceSerializer,
    GuestSelfRegistrationSerializer,
    GroupCreateSerializer,
    GroupLookupSerializer,
    LocationDetailSerializer,
    LocationLookupSerializer,
    LocationWriteSerializer,
    NetworkInterfaceCreateSerializer,
    NetworkInterfaceListSerializer,
    NetworkInterfaceUpdateSerializer,
    NetworkLookupSerializer,
    OSFamilyCreateSerializer,
    OSFamilyLookupSerializer,
    PortCreateSerializer,
    PortLookupSerializer,
    PortUpdateSerializer,
    UserLookupSerializer,
)

User = get_user_model()


class ApiLoginView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = ApiLoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        username = serializer.validated_data.get("username")
        email = serializer.validated_data.get("email")
        password = serializer.validated_data["password"]

        auth_identifier = username or email
        user = authenticate(request=request, username=auth_identifier, password=password)
        if user is None and email:
            candidate = User.objects.filter(email__iexact=email, is_active=True).first()
            if candidate:
                user = authenticate(
                    request=request,
                    username=getattr(candidate, User.USERNAME_FIELD),
                    password=password,
                )

        if user is None:
            raise ValidationError({"detail": "Invalid credentials."})
        if not user.is_active:
            raise ValidationError({"detail": "User account is inactive."})

        login(request, user)
        token = Token.objects.filter(user=user).first()
        return Response(
            {
                "user": UserLookupSerializer(user).data,
                "token": token.key if token else None,
                "token_available": bool(token),
                "detail": (
                    "Login successful."
                    if token
                    else "Login successful. Token is not provisioned for this user; create it in Django admin."
                ),
            }
        )


class AssetViewSet(
    mixins.CreateModelMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    viewsets.GenericViewSet,
):
    permission_classes = [AssetObjectPermission]

    def get_queryset(self):
        user = self.request.user
        queryset = (
            visible_assets_for_user(user)
            .select_related("owner", "location", "location__parent")
            .prefetch_related(
                "groups",
                "os_entries__family",
                "ports__port_interfaces__ip_addresses__network",
                "interfaces__ip_addresses__network",
            )
            .order_by("name")
        )
        params = self.request.query_params
        if params.get("q"):
            queryset = queryset.filter(
                Q(name__icontains=params["q"])
                | Q(asset_tag__icontains=params["q"])
                | Q(serial_number__icontains=params["q"])
            )
        if params.get("group"):
            queryset = queryset.filter(groups__id=params["group"])
        if params.get("owner"):
            queryset = queryset.filter(owner_id=params["owner"])
        if params.get("location"):
            queryset = queryset.filter(location_id=params["location"])
        if params.get("status"):
            queryset = queryset.filter(status=params["status"])
        if params.get("type"):
            queryset = queryset.filter(asset_type=params["type"])
        return queryset.distinct()

    def get_serializer_class(self):
        if self.action == "create":
            return AssetCreateSerializer
        if self.action in ("partial_update", "update"):
            return AssetUpdateSerializer
        return AssetListSerializer

    def perform_create(self, serializer):
        serializer.save()

    def perform_update(self, serializer):
        asset = self.get_object()
        if not can_edit_asset(self.request.user, asset):
            raise PermissionDenied("You do not have permission to edit this asset.")
        serializer.save()


def _build_location_tree_payload(location_queryset):
    locations = list(location_queryset.select_related("parent").order_by("name", "id"))
    nodes = {
        location.id: {
            "id": location.id,
            "name": location.name,
            "slug": location.slug,
            "parent": location.parent_id,
            "path": location.path_label,
            "children": [],
        }
        for location in locations
    }
    roots = []
    for location in locations:
        node = nodes[location.id]
        if location.parent_id and location.parent_id in nodes:
            nodes[location.parent_id]["children"].append(node)
        else:
            roots.append(node)
    return roots


class LocationViewSet(
    mixins.CreateModelMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    viewsets.GenericViewSet,
):
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        queryset = visible_locations_for_user(self.request.user).prefetch_related("groups").order_by("name", "id")
        parent = self.request.query_params.get("parent")
        if parent == "null":
            queryset = queryset.filter(parent__isnull=True)
        elif parent and parent.isdigit():
            queryset = queryset.filter(parent_id=int(parent))
        return queryset

    def get_serializer_class(self):
        if self.action in ("create", "update", "partial_update"):
            return LocationWriteSerializer
        if self.action == "retrieve":
            return LocationDetailSerializer
        return LocationLookupSerializer

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["visible_location_ids"] = visible_location_ids_for_user(self.request.user)
        return context

    @action(detail=False, methods=["get"], url_path="tree")
    def tree(self, request):
        tree_payload = _build_location_tree_payload(self.get_queryset())
        return Response(tree_payload)

    def perform_create(self, serializer):
        user = self.request.user
        groups = serializer.validated_data.get("groups", [])
        parent = serializer.validated_data.get("parent")
        if user.is_superuser:
            serializer.save()
            return

        admin_group_ids = set(user.asset_admin_groups.values_list("id", flat=True))
        if not groups:
            raise PermissionDenied("At least one group is required.")
        if any(group.id not in admin_group_ids for group in groups):
            raise PermissionDenied("Location groups are outside your managed groups.")
        if parent and parent.id not in visible_location_ids_for_user(user):
            raise PermissionDenied("Parent location is outside your visible tree.")
        serializer.save()

    def perform_update(self, serializer):
        user = self.request.user
        location = self.get_object()
        if user.is_superuser:
            serializer.save()
            return

        admin_group_ids = set(user.asset_admin_groups.values_list("id", flat=True))
        existing_group_ids = set(location.groups.values_list("id", flat=True))
        groups = serializer.validated_data.get("groups", serializers.empty)
        effective_group_ids = set(group.id for group in groups) if groups is not serializers.empty else existing_group_ids
        if not effective_group_ids:
            raise PermissionDenied("At least one group is required.")
        if any(group_id not in admin_group_ids for group_id in effective_group_ids):
            raise PermissionDenied("Location groups are outside your managed groups.")

        parent = serializer.validated_data.get("parent", location.parent)
        if parent and parent.id not in visible_location_ids_for_user(user):
            raise PermissionDenied("Parent location is outside your visible tree.")
        serializer.save()


class NetworkInterfaceViewSet(
    mixins.CreateModelMixin,
    mixins.ListModelMixin,
    mixins.UpdateModelMixin,
    viewsets.GenericViewSet,
):
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        queryset = (
            NetworkInterface.objects.filter(asset__in=visible_assets_for_user(user))
            .select_related("asset", "port")
            .prefetch_related("ip_addresses__network")
            .order_by("asset__name", "identifier", "id")
        )
        params = self.request.query_params
        if params.get("asset"):
            queryset = queryset.filter(asset_id=params["asset"])
        if params.get("active") in {"true", "false"}:
            queryset = queryset.filter(active=(params["active"] == "true"))
        if params.get("q"):
            query = params["q"]
            queryset = queryset.filter(
                Q(asset__name__icontains=query)
                | Q(identifier__icontains=query)
                | Q(mac_address__icontains=query)
                | Q(port__name__icontains=query)
                | Q(ip_addresses__address__icontains=query)
            ).distinct()
        return queryset

    def get_serializer_class(self):
        if self.action == "create":
            return NetworkInterfaceCreateSerializer
        if self.action in ("update", "partial_update"):
            return NetworkInterfaceUpdateSerializer
        return NetworkInterfaceListSerializer

    def perform_create(self, serializer):
        serializer.save()

    def perform_update(self, serializer):
        interface = self.get_object()
        if not can_edit_asset(self.request.user, interface.asset):
            raise PermissionDenied("You do not have permission to edit this interface.")
        serializer.save()


class PortViewSet(
    mixins.CreateModelMixin,
    mixins.ListModelMixin,
    mixins.UpdateModelMixin,
    viewsets.GenericViewSet,
):
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        queryset = Port.objects.filter(asset__in=visible_assets_for_user(user)).select_related("asset")
        params = self.request.query_params
        if params.get("asset"):
            queryset = queryset.filter(asset_id=params["asset"])
        if params.get("active") in {"true", "false"}:
            queryset = queryset.filter(active=(params["active"] == "true"))
        if params.get("q"):
            query = params["q"]
            queryset = queryset.filter(Q(name__icontains=query) | Q(asset__name__icontains=query))
        return queryset.order_by("asset__name", "name", "id")

    def get_serializer_class(self):
        if self.action == "create":
            return PortCreateSerializer
        if self.action in ("update", "partial_update"):
            return PortUpdateSerializer
        return PortLookupSerializer

    def perform_create(self, serializer):
        serializer.save()

    def perform_update(self, serializer):
        port = self.get_object()
        if not can_edit_asset(self.request.user, port.asset):
            raise PermissionDenied("You do not have permission to edit this port.")
        serializer.save()


class BulkAssetUpdateAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        payload = request.data.get("rows", request.data)
        if not isinstance(payload, list):
            raise ValidationError({"rows": "Expected list of rows."})

        results = []
        for index, row in enumerate(payload):
            row_serializer = BulkAssetRowSerializer(data=row)
            if not row_serializer.is_valid():
                results.append(
                    {
                        "row": index,
                        "id": row.get("id"),
                        "success": False,
                        "errors": row_serializer.errors,
                    }
                )
                continue

            validated = row_serializer.validated_data
            asset_id = validated["id"]
            try:
                asset = visible_assets_for_user(request.user).get(pk=asset_id)
            except Asset.DoesNotExist:
                results.append(
                    {
                        "row": index,
                        "id": asset_id,
                        "success": False,
                        "errors": {"id": ["Asset not found or not visible."]},
                    }
                )
                continue

            if not can_edit_asset(request.user, asset):
                results.append(
                    {
                        "row": index,
                        "id": asset_id,
                        "success": False,
                        "errors": {"permission": ["Missing edit permission for this asset."]},
                    }
                )
                continue

            update_serializer = AssetUpdateSerializer(asset, data=validated, partial=True)
            if not update_serializer.is_valid():
                results.append(
                    {
                        "row": index,
                        "id": asset_id,
                        "success": False,
                        "errors": update_serializer.errors,
                    }
                )
                continue

            try:
                update_serializer.save()
            except ValidationError as error:
                results.append(
                    {
                        "row": index,
                        "id": asset_id,
                        "success": False,
                        "errors": error.detail,
                    }
                )
                continue

            results.append({"row": index, "id": asset_id, "success": True, "errors": {}})

        has_errors = any(not entry["success"] for entry in results)
        return Response({"results": results}, status=status.HTTP_207_MULTI_STATUS if has_errors else status.HTTP_200_OK)


class BulkInterfaceUpdateAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        payload = request.data.get("rows", request.data)
        if not isinstance(payload, list):
            raise ValidationError({"rows": "Expected list of rows."})

        results = []
        visible_assets = visible_assets_for_user(request.user)
        for index, row in enumerate(payload):
            row_serializer = BulkInterfaceRowSerializer(data=row)
            if not row_serializer.is_valid():
                results.append(
                    {
                        "row": index,
                        "id": row.get("id"),
                        "success": False,
                        "errors": row_serializer.errors,
                    }
                )
                continue

            validated = row_serializer.validated_data
            interface_id = validated.pop("id")
            try:
                interface = NetworkInterface.objects.select_related("asset").get(
                    pk=interface_id,
                    asset__in=visible_assets,
                )
            except NetworkInterface.DoesNotExist:
                results.append(
                    {
                        "row": index,
                        "id": interface_id,
                        "success": False,
                        "errors": {"id": ["Interface not found or not visible."]},
                    }
                )
                continue

            if not can_edit_asset(request.user, interface.asset):
                results.append(
                    {
                        "row": index,
                        "id": interface_id,
                        "success": False,
                        "errors": {"permission": ["Missing edit permission for this interface."]},
                    }
                )
                continue

            payload = dict(validated)
            for field in ("port", "network"):
                if field in payload and payload[field] is not None:
                    payload[field] = payload[field].pk

            update_serializer = NetworkInterfaceUpdateSerializer(interface, data=payload, partial=True)
            if not update_serializer.is_valid():
                results.append(
                    {
                        "row": index,
                        "id": interface_id,
                        "success": False,
                        "errors": update_serializer.errors,
                    }
                )
                continue

            try:
                update_serializer.save()
            except ValidationError as error:
                results.append(
                    {
                        "row": index,
                        "id": interface_id,
                        "success": False,
                        "errors": error.detail,
                    }
                )
                continue

            results.append({"row": index, "id": interface_id, "success": True, "errors": {}})

        has_errors = any(not entry["success"] for entry in results)
        return Response({"results": results}, status=status.HTTP_207_MULTI_STATUS if has_errors else status.HTTP_200_OK)


class AssetPortInterfaceCreateAPIView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        request=AssetPortInterfaceCreateSerializer,
        responses={201: dict},
        description="Create port and interface in one request and link both to the given asset.",
    )
    def post(self, request, asset_id):
        try:
            asset = visible_assets_for_user(request.user).get(pk=asset_id)
        except Asset.DoesNotExist:
            raise ValidationError({"asset_id": "Asset not found or not visible."})

        if not can_edit_asset(request.user, asset):
            raise PermissionDenied("Missing edit permission for this asset.")

        serializer = AssetPortInterfaceCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        validated = serializer.validated_data

        with transaction.atomic():
            port = Port(
                asset=asset,
                name=validated["port_name"],
                port_kind=validated["port_kind"],
                notes=validated["port_notes"],
                active=validated["port_active"],
            )
            port.full_clean()
            port.save()

            interface = NetworkInterface(
                asset=asset,
                port=port,
                identifier=validated["interface_identifier"],
                mac_address=validated["interface_mac_address"] or None,
                notes=validated["interface_notes"],
                active=validated["interface_active"],
            )
            interface.full_clean()
            interface.save()

        return Response(
            {
                "asset_id": asset.id,
                "port": PortLookupSerializer(port).data,
                "interface": NetworkInterfaceListSerializer(interface).data,
            },
            status=status.HTTP_201_CREATED,
        )


class UserLookupAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        queryset = User.objects.filter(is_active=True).order_by("email")
        q = request.query_params.get("q")
        if q:
            queryset = queryset.filter(
                Q(email__icontains=q) | Q(first_name__icontains=q) | Q(last_name__icontains=q)
            )
        serializer = UserLookupSerializer(queryset[:50], many=True)
        return Response(serializer.data)


class GroupLookupAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if request.user.is_superuser:
            queryset = OrganizationalGroup.objects.all()
        else:
            queryset = OrganizationalGroup.objects.filter(
                Q(members=request.user) | Q(admins=request.user)
            ).distinct()
        q = request.query_params.get("q")
        if q:
            queryset = queryset.filter(name__icontains=q)
        serializer = GroupLookupSerializer(queryset.order_by("name")[:50], many=True)
        return Response(serializer.data)

    def post(self, request):
        if not request.user.is_superuser:
            raise PermissionDenied("Only superusers can create groups via API.")
        serializer = GroupCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        group = serializer.save()
        return Response(GroupLookupSerializer(group).data, status=status.HTTP_201_CREATED)


class OSFamilyLookupAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        queryset = OSFamily.objects.all().order_by("family", "name", "flavor", "id")
        family = request.query_params.get("family")
        if family:
            queryset = queryset.filter(family=family)
        support_status = request.query_params.get("support_status")
        if support_status:
            queryset = queryset.filter(support_status=support_status)
        q = request.query_params.get("q")
        if q:
            queryset = queryset.filter(Q(name__icontains=q) | Q(flavor__icontains=q))
        serializer = OSFamilyLookupSerializer(queryset[:50], many=True)
        return Response(serializer.data)

    def post(self, request):
        if not request.user.is_superuser:
            raise PermissionDenied("Only superusers can create OS families via API.")
        serializer = OSFamilyCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        family = serializer.save()
        return Response(OSFamilyLookupSerializer(family).data, status=status.HTTP_201_CREATED)


class OSVersionLookupAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        # Legacy endpoint kept for backward compatibility after moving to free-text AssetOS.version.
        return Response([])


class NetworkLookupAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        queryset = Network.objects.order_by("name")
        q = request.query_params.get("q")
        if q:
            queryset = queryset.filter(Q(name__icontains=q) | Q(cidr__icontains=q))
        serializer = NetworkLookupSerializer(queryset[:50], many=True)
        return Response(serializer.data)


class GuestSelfRegistrationAPIView(APIView):
    permission_classes = [AllowAny]

    @extend_schema(
        request=GuestSelfRegistrationSerializer,
        responses={201: GuestDeviceSerializer},
        description=(
            "Create guest network-access request. "
            "Request is created in PENDING state and must be approved by responsible system user."
        ),
    )
    def post(self, request):
        serializer = GuestSelfRegistrationSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        guest = serializer.save()
        return Response(GuestDeviceSerializer(guest).data, status=status.HTTP_201_CREATED)


class GuestPendingApprovalAPIView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        responses={200: GuestDeviceSerializer(many=True)},
        description="List pending guest requests assigned to current user (or all pending for superuser).",
    )
    def get(self, request):
        queryset = GuestDevice.objects.select_related("sponsor", "approved_by", "network").filter(
            approval_status=GuestDevice.ApprovalStatus.PENDING
        )
        if not request.user.is_superuser:
            queryset = queryset.filter(sponsor=request.user)
        serializer = GuestDeviceSerializer(queryset.order_by("-created_at"), many=True)
        return Response(serializer.data)


class GuestApproveAPIView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        request=GuestApprovalDecisionSerializer,
        responses={200: GuestDeviceSerializer},
        description="Approve pending guest request. Only assigned responsible user (or superuser) can approve.",
    )
    def post(self, request, pk):
        guest = get_object_or_404(GuestDevice.objects.select_related("sponsor"), pk=pk)
        if not request.user.is_superuser and guest.sponsor_id != request.user.id:
            raise PermissionDenied("Missing permission to approve this guest request.")
        if guest.approval_status != GuestDevice.ApprovalStatus.PENDING:
            raise ValidationError({"status": "Only pending requests can be approved."})

        guest.approval_status = GuestDevice.ApprovalStatus.APPROVED
        guest.enabled = True
        guest.approved_by = request.user
        guest.approved_at = timezone.now()
        guest.rejected_reason = ""
        guest.save(
            update_fields=[
                "approval_status",
                "enabled",
                "approved_by",
                "approved_at",
                "rejected_reason",
                "updated_at",
            ]
        )
        return Response(GuestDeviceSerializer(guest).data, status=status.HTTP_200_OK)


class GuestRejectAPIView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        request=GuestApprovalDecisionSerializer,
        responses={200: GuestDeviceSerializer},
        description="Reject pending guest request. Only assigned responsible user (or superuser) can reject.",
    )
    def post(self, request, pk):
        serializer = GuestApprovalDecisionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        guest = get_object_or_404(GuestDevice.objects.select_related("sponsor"), pk=pk)
        if not request.user.is_superuser and guest.sponsor_id != request.user.id:
            raise PermissionDenied("Missing permission to reject this guest request.")
        if guest.approval_status != GuestDevice.ApprovalStatus.PENDING:
            raise ValidationError({"status": "Only pending requests can be rejected."})

        guest.approval_status = GuestDevice.ApprovalStatus.REJECTED
        guest.enabled = False
        guest.rejected_reason = serializer.validated_data.get("reason", "").strip()
        guest.save(update_fields=["approval_status", "enabled", "rejected_reason", "updated_at"])
        return Response(GuestDeviceSerializer(guest).data, status=status.HTTP_200_OK)
