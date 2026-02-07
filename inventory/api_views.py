from django.contrib.auth import get_user_model
from django.db.models import Q
from rest_framework import mixins, status, viewsets
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .access import can_edit_asset, visible_assets_for_user
from .models import Asset, Network, NetworkInterface, OrganizationalGroup, OSFamily, OSVersion, Port
from .permissions import AssetObjectPermission
from .serializers import (
    AssetListSerializer,
    AssetUpdateSerializer,
    BulkAssetRowSerializer,
    BulkInterfaceRowSerializer,
    GroupLookupSerializer,
    NetworkInterfaceListSerializer,
    NetworkInterfaceUpdateSerializer,
    NetworkLookupSerializer,
    OSFamilyLookupSerializer,
    OSVersionLookupSerializer,
    PortLookupSerializer,
    PortUpdateSerializer,
    UserLookupSerializer,
)

User = get_user_model()


class AssetViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, mixins.UpdateModelMixin, viewsets.GenericViewSet):
    permission_classes = [AssetObjectPermission]

    def get_queryset(self):
        user = self.request.user
        queryset = (
            visible_assets_for_user(user)
            .select_related("owner")
            .prefetch_related(
                "groups",
                "asset_os__family",
                "asset_os__version",
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
        if params.get("status"):
            queryset = queryset.filter(status=params["status"])
        if params.get("type"):
            queryset = queryset.filter(asset_type=params["type"])
        return queryset.distinct()

    def get_serializer_class(self):
        if self.action in ("partial_update", "update"):
            return AssetUpdateSerializer
        return AssetListSerializer

    def perform_update(self, serializer):
        asset = self.get_object()
        if not can_edit_asset(self.request.user, asset):
            raise PermissionDenied("You do not have permission to edit this asset.")
        serializer.save()


class NetworkInterfaceViewSet(mixins.ListModelMixin, mixins.UpdateModelMixin, viewsets.GenericViewSet):
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
        if self.action in ("update", "partial_update"):
            return NetworkInterfaceUpdateSerializer
        return NetworkInterfaceListSerializer

    def perform_update(self, serializer):
        interface = self.get_object()
        if not can_edit_asset(self.request.user, interface.asset):
            raise PermissionDenied("You do not have permission to edit this interface.")
        serializer.save()


class PortViewSet(mixins.ListModelMixin, mixins.UpdateModelMixin, viewsets.GenericViewSet):
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
        if self.action in ("update", "partial_update"):
            return PortUpdateSerializer
        return PortLookupSerializer

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


class OSFamilyLookupAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        queryset = OSFamily.objects.all().order_by("name")
        q = request.query_params.get("q")
        if q:
            queryset = queryset.filter(name__icontains=q)
        serializer = OSFamilyLookupSerializer(queryset[:50], many=True)
        return Response(serializer.data)


class OSVersionLookupAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        queryset = OSVersion.objects.select_related("family").order_by("family__name", "version")
        family_id = request.query_params.get("family_id")
        if family_id:
            queryset = queryset.filter(family_id=family_id)
        q = request.query_params.get("q")
        if q:
            queryset = queryset.filter(version__icontains=q)
        serializer = OSVersionLookupSerializer(queryset[:50], many=True)
        return Response(serializer.data)


class NetworkLookupAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        queryset = Network.objects.order_by("name")
        q = request.query_params.get("q")
        if q:
            queryset = queryset.filter(Q(name__icontains=q) | Q(cidr__icontains=q))
        serializer = NetworkLookupSerializer(queryset[:50], many=True)
        return Response(serializer.data)
