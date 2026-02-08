from django import forms
from django.contrib.auth import get_user_model
from django.utils import timezone

from .access import assignable_locations_for_user
from .models import (
    Asset,
    AssetOS,
    GuestDevice,
    Location,
    Network,
    NetworkInterface,
    OrganizationalGroup,
    Port,
    normalize_mac,
    validate_mac,
)

User = get_user_model()


def apply_base_field_styles(fields):
    for field in fields.values():
        existing_class = field.widget.attrs.get("class", "")
        if isinstance(field.widget, forms.CheckboxInput):
            field.widget.attrs["class"] = f"{existing_class} h-4 w-4 rounded border-slate-300".strip()
            continue
        base_class = "w-full rounded border border-slate-300 px-3 text-sm"
        if isinstance(field.widget, forms.Textarea):
            sizing_class = "py-2"
        else:
            sizing_class = "h-9 py-1.5"
        field.widget.attrs["class"] = f"{existing_class} {base_class} {sizing_class}".strip()


def apply_select2(fields, names):
    for name in names:
        field = fields.get(name)
        if field is None:
            continue
        existing_class = field.widget.attrs.get("class", "")
        field.widget.attrs["class"] = f"{existing_class} select2".strip()


class LocationChoiceField(forms.ModelChoiceField):
    def label_from_instance(self, obj):
        return obj.path_label


class OSChoiceField(forms.ModelChoiceField):
    def label_from_instance(self, obj):
        if obj.support_status == obj.SupportStatus.UNSUPPORTED:
            return f"{obj.name_flavor} [Unsupported]"
        return obj.name_flavor


class AssetEditForm(forms.ModelForm):
    class Meta:
        model = Asset
        fields = (
            "name",
            "asset_type",
            "owner",
            "status",
            "location",
            "groups",
            "asset_tag",
            "serial_number",
            "manufacturer",
            "model",
            "notes",
            "metadata",
        )
        widgets = {
            "groups": forms.SelectMultiple(),
            "notes": forms.Textarea(attrs={"rows": 3}),
            "metadata": forms.Textarea(attrs={"rows": 4}),
        }

    def __init__(self, *args, user, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user
        self.fields["location"] = LocationChoiceField(
            queryset=Location.objects.none(),
            required=False,
            label="Location",
        )
        self.fields["owner"].queryset = User.objects.filter(is_active=True).order_by("email")
        if user.is_superuser:
            self.fields["groups"].queryset = OrganizationalGroup.objects.all().order_by("name")
            self.fields["location"].queryset = Location.objects.select_related("parent").order_by("name")
        else:
            self.fields["groups"].queryset = user.asset_admin_groups.order_by("name")
            allowed_ids = set(assignable_locations_for_user(user).values_list("id", flat=True))
            if self.instance and self.instance.pk and self.instance.location_id:
                allowed_ids.add(self.instance.location_id)
            self.fields["location"].queryset = Location.objects.filter(id__in=allowed_ids).select_related("parent").order_by("name")
        apply_base_field_styles(self.fields)
        apply_select2(self.fields, ["owner", "groups", "asset_type", "status", "location"])


class AssetOSFeaturesForm(forms.ModelForm):
    class Meta:
        model = AssetOS
        fields = (
            "family",
            "version",
            "patch_level",
            "installed_on",
            "support_state",
            "auto_updates_enabled",
        )
        widgets = {
            "installed_on": forms.DateInput(attrs={"type": "date"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["family"] = OSChoiceField(
            queryset=self.fields["family"].queryset.order_by("family", "name", "flavor", "id"),
            required=False,
            label="OS",
        )
        self.fields["family"].required = False
        self.fields["version"].required = False
        self.fields["patch_level"].required = False
        self.fields["installed_on"].required = False
        self.fields["support_state"].initial = AssetOS.SupportState.UNKNOWN
        self.fields["family"].widget.attrs["data-placeholder"] = "Name - Flavor"
        self.fields["version"].widget.attrs["placeholder"] = "23H2 / 22.04 / 15.2 ..."
        apply_base_field_styles(self.fields)
        apply_select2(self.fields, ["family", "support_state"])

    def clean(self):
        cleaned = super().clean()
        family = cleaned.get("family")
        version = cleaned.get("version")
        if version and not family:
            self.add_error("family", "OS is required when version is set.")
        if isinstance(version, str):
            cleaned["version"] = version.strip()
        return cleaned


class PortCreateForm(forms.ModelForm):
    class Meta:
        model = Port
        fields = ("name", "port_kind", "notes")
        widgets = {
            "notes": forms.TextInput(),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        apply_base_field_styles(self.fields)
        apply_select2(self.fields, ["port_kind"])
        self.fields["name"].widget.attrs["placeholder"] = "LAN1"
        self.fields["notes"].widget.attrs["placeholder"] = "optional"


class PortEditForm(PortCreateForm):
    pass


class PortInterfaceCreateForm(forms.ModelForm):
    class Meta:
        model = NetworkInterface
        fields = ("identifier", "mac_address", "notes")
        widgets = {
            "notes": forms.TextInput(),
        }

    def __init__(self, *args, asset=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.asset = asset
        apply_base_field_styles(self.fields)
        self.fields["identifier"].widget.attrs["placeholder"] = "eth0"
        self.fields["mac_address"].widget.attrs["placeholder"] = "aa:bb:cc:dd:ee:ff"
        self.fields["notes"].widget.attrs["placeholder"] = "optional"

    def clean_identifier(self):
        identifier = self.cleaned_data["identifier"]
        if not self.asset:
            return identifier
        exists = NetworkInterface.objects.filter(asset=self.asset, identifier=identifier)
        if self.instance.pk:
            exists = exists.exclude(pk=self.instance.pk)
        if exists.exists():
            raise forms.ValidationError("Interface identifier must be unique per asset.")
        return identifier

    def save(self, *, asset, port):
        interface = super().save(commit=False)
        interface.asset = asset
        interface.port = port
        interface.active = True
        interface.full_clean()
        interface.save()
        return interface


class AssetFilterForm(forms.Form):
    q = forms.CharField(required=False, label="Search")


class PortInterfaceEditForm(PortInterfaceCreateForm):
    def save(self):
        interface = forms.ModelForm.save(self, commit=False)
        interface.full_clean()
        interface.save()
        return interface


class GuestSelfRegistrationForm(forms.Form):
    device_name = forms.CharField(required=False, max_length=200)
    owner_name = forms.CharField(required=True, max_length=200)
    owner_email = forms.EmailField(required=True)
    mac_address = forms.CharField(required=True, max_length=17)
    responsible_email = forms.EmailField(required=False)
    network = forms.ModelChoiceField(queryset=Network.objects.none(), required=True)
    valid_until = forms.DateTimeField(
        required=True,
        widget=forms.DateTimeInput(attrs={"type": "datetime-local"}),
        input_formats=["%Y-%m-%dT%H:%M"],
    )
    description = forms.CharField(required=False, widget=forms.Textarea(attrs={"rows": 2}))

    def __init__(self, *args, **kwargs):
        self.request_user = kwargs.pop("user", None)
        super().__init__(*args, **kwargs)
        self.fields["network"].queryset = Network.objects.order_by("name")
        if self.request_user and self.request_user.is_authenticated:
            self.fields.pop("responsible_email", None)
        else:
            self.fields["responsible_email"].help_text = "Email must match an existing active system user."
        apply_base_field_styles(self.fields)

    def clean_mac_address(self):
        mac_address = normalize_mac(self.cleaned_data["mac_address"])
        validate_mac(mac_address)
        active_duplicate = GuestDevice.objects.filter(
            mac_address=mac_address,
            enabled=True,
            approval_status=GuestDevice.ApprovalStatus.APPROVED,
            valid_until__gte=timezone.now(),
        )
        if active_duplicate.exists():
            raise forms.ValidationError("This MAC address is already registered as an active guest device.")
        return mac_address

    def clean_responsible_email(self):
        responsible_email = self.cleaned_data["responsible_email"].strip().lower()
        responsible_user = User.objects.filter(email__iexact=responsible_email, is_active=True).first()
        if not responsible_user:
            raise forms.ValidationError("Responsible person email must belong to an active system user.")
        self.cleaned_data["responsible_user"] = responsible_user
        return responsible_email

    def clean(self):
        cleaned_data = super().clean()
        if self.request_user and self.request_user.is_authenticated:
            cleaned_data["responsible_user"] = self.request_user
            return cleaned_data

        responsible_email = cleaned_data.get("responsible_email", "").strip().lower()
        if not responsible_email:
            self.add_error("responsible_email", "Responsible person email is required.")
        return cleaned_data

    def clean_valid_until(self):
        valid_until = self.cleaned_data["valid_until"]
        if timezone.is_naive(valid_until):
            valid_until = timezone.make_aware(valid_until, timezone.get_current_timezone())
        if valid_until <= timezone.now():
            raise forms.ValidationError("Expiration must be in the future.")
        return valid_until

    def save(self):
        responsible_user = self.cleaned_data["responsible_user"]
        guest = GuestDevice(
            device_name=self.cleaned_data.get("device_name", "").strip(),
            owner_name=self.cleaned_data["owner_name"].strip(),
            owner_email=self.cleaned_data["owner_email"].strip().lower(),
            mac_address=self.cleaned_data["mac_address"],
            sponsor=responsible_user,
            network=self.cleaned_data["network"],
            valid_from=timezone.now(),
            valid_until=self.cleaned_data["valid_until"],
            description=self.cleaned_data.get("description", "").strip(),
            approval_status=GuestDevice.ApprovalStatus.PENDING,
            enabled=False,
        )
        guest.full_clean()
        guest.save()
        return guest
