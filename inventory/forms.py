from django import forms
from django.contrib.auth import get_user_model

from .models import Asset, AssetOS, NetworkInterface, OrganizationalGroup, Port

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


class AssetEditForm(forms.ModelForm):
    class Meta:
        model = Asset
        fields = (
            "name",
            "asset_type",
            "owner",
            "status",
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
        self.fields["owner"].queryset = User.objects.filter(is_active=True).order_by("email")
        if user.is_superuser:
            self.fields["groups"].queryset = OrganizationalGroup.objects.all().order_by("name")
        else:
            self.fields["groups"].queryset = user.asset_admin_groups.order_by("name")
        apply_base_field_styles(self.fields)
        apply_select2(self.fields, ["owner", "groups", "asset_type", "status"])


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
        self.fields["family"].required = False
        self.fields["version"].required = False
        self.fields["patch_level"].required = False
        self.fields["installed_on"].required = False
        self.fields["support_state"].initial = AssetOS.SupportState.UNKNOWN
        apply_base_field_styles(self.fields)
        apply_select2(self.fields, ["family", "version", "support_state"])

    def clean(self):
        cleaned = super().clean()
        family = cleaned.get("family")
        version = cleaned.get("version")
        if version and not family:
            self.add_error("family", "OS family is required when version is set.")
        if family and version and version.family_id != family.id:
            self.add_error("version", "Selected OS version must belong to selected family.")
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
