from django.db import migrations, models


def _infer_os_family(name: str, platform_type: str) -> str:
    normalized = (name or "").strip().lower()
    if "windows" in normalized:
        return "windows"
    if "mac" in normalized or normalized.startswith("ios") or " os x" in normalized:
        return "macos"
    if any(token in normalized for token in ["routeros", "ios xe", "ios xr", "cisco ios", "openwrt", "opnsense", "qts", "dsm"]):
        return "network-os"
    if platform_type in {"DESKTOP", "SERVER"}:
        return "linux"
    return "other"


def _split_name_flavor(name: str):
    flavor_candidates = ("pro", "home", "enterprise", "server", "desktop")
    source = (name or "").strip()
    lowered = source.lower()
    for flavor in flavor_candidates:
        suffix = f" {flavor}"
        if lowered.endswith(suffix):
            base = source[: -len(suffix)].strip()
            if base:
                return base, flavor.capitalize()
    return source, None


def migrate_os_catalog_data(apps, schema_editor):
    OSFamily = apps.get_model("inventory", "OSFamily")
    AssetOS = apps.get_model("inventory", "AssetOS")

    for os_item in OSFamily.objects.all():
        family_value = _infer_os_family(os_item.name, getattr(os_item, "platform_type", "OTHER"))
        name_value, flavor_value = _split_name_flavor(os_item.name)
        os_item.family = family_value
        os_item.name = name_value or os_item.name
        os_item.flavor = flavor_value
        os_item.save(update_fields=["family", "name", "flavor"])

    for assignment in AssetOS.objects.select_related("version").all():
        assignment.version_text = assignment.version.version if assignment.version_id else ""
        assignment.save(update_fields=["version_text"])


class Migration(migrations.Migration):
    dependencies = [
        ("inventory", "0015_location_path_cache"),
    ]

    operations = [
        migrations.AddField(
            model_name="osfamily",
            name="family",
            field=models.CharField(
                choices=[
                    ("linux", "Linux"),
                    ("windows", "Windows"),
                    ("network-os", "Network OS"),
                    ("macos", "macOS"),
                    ("other", "Other"),
                ],
                default="other",
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name="osfamily",
            name="flavor",
            field=models.CharField(blank=True, max_length=120, null=True),
        ),
        migrations.AlterField(
            model_name="osfamily",
            name="name",
            field=models.CharField(max_length=120),
        ),
        migrations.AddField(
            model_name="assetos",
            name="version_text",
            field=models.CharField(blank=True, default="", max_length=120),
        ),
        migrations.RunPython(migrate_os_catalog_data, migrations.RunPython.noop),
        migrations.RemoveField(
            model_name="assetos",
            name="version",
        ),
        migrations.RenameField(
            model_name="assetos",
            old_name="version_text",
            new_name="version",
        ),
        migrations.RemoveField(
            model_name="osfamily",
            name="vendor",
        ),
        migrations.RemoveField(
            model_name="osfamily",
            name="platform_type",
        ),
        migrations.RemoveField(
            model_name="osfamily",
            name="supports_domain_join",
        ),
        migrations.DeleteModel(
            name="OSVersion",
        ),
        migrations.AddConstraint(
            model_name="osfamily",
            constraint=models.UniqueConstraint(fields=("family", "name", "flavor"), name="uniq_os_catalog_item"),
        ),
        migrations.AlterModelOptions(
            name="osfamily",
            options={"ordering": ("family", "name", "flavor", "id")},
        ),
    ]
