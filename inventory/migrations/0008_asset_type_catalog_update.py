from django.db import migrations, models


def remap_legacy_asset_types(apps, schema_editor):
    Asset = apps.get_model("inventory", "Asset")
    alias = schema_editor.connection.alias
    Asset.objects.using(alias).filter(asset_type="MONITOR").update(asset_type="DEVICE")
    Asset.objects.using(alias).filter(asset_type="KEYBOARD").update(asset_type="DEVICE")


class Migration(migrations.Migration):
    dependencies = [
        ("inventory", "0007_merge_0002_alter_asset_name_0006_user_email_identity"),
    ]

    operations = [
        migrations.RunPython(remap_legacy_asset_types, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="asset",
            name="asset_type",
            field=models.CharField(
                choices=[
                    ("COMPUTER", "Computer"),
                    ("NOTEBOOK", "Notebook"),
                    ("SERVER", "Server"),
                    ("DEVICE", "Device"),
                    ("NETWORK", "Network"),
                    ("PRINTER", "Printer"),
                    ("MOBILE", "Mobile"),
                    ("BYOD", "BYOD"),
                    ("OTHER", "Other"),
                ],
                default="COMPUTER",
                max_length=20,
            ),
        ),
    ]
