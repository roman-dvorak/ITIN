from django.db import migrations, models


def remap_os_family_values(apps, schema_editor):
    OSFamily = apps.get_model("inventory", "OSFamily")
    valid_values = {"linux", "windows", "nas-os", "network-os", "android", "macos", "other"}

    for row in OSFamily.objects.all():
        name = (row.name or "").lower()
        flavor = (row.flavor or "").lower()
        text = f"{name} {flavor}".strip()
        target = None

        if "android" in text:
            target = "android"
        elif any(
            token in text
            for token in ("synology", "qnap", "truenas", "freenas", "asustor", "unraid", "dsm", "qts", "nas")
        ):
            target = "nas-os"
        elif any(
            token in text
            for token in ("routeros", "openwrt", "opnsense", "pfsense", "cisco ios", "ios xr", "ios xe", "junos")
        ):
            target = "network-os"
        elif row.family not in valid_values:
            target = "other"

        if target and row.family != target:
            row.family = target
            row.save(update_fields=["family"])


class Migration(migrations.Migration):
    dependencies = [
        ("inventory", "0017_osfamily_support_status"),
    ]

    operations = [
        migrations.AlterField(
            model_name="osfamily",
            name="family",
            field=models.CharField(
                choices=[
                    ("linux", "Linux"),
                    ("windows", "Windows"),
                    ("nas-os", "NAS OS"),
                    ("network-os", "Network OS"),
                    ("android", "Android"),
                    ("macos", "macOS"),
                    ("other", "Other"),
                ],
                default="other",
                max_length=20,
            ),
        ),
        migrations.RunPython(remap_os_family_values, migrations.RunPython.noop),
    ]
