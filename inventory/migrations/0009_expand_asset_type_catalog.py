from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("inventory", "0008_asset_type_catalog_update"),
    ]

    operations = [
        migrations.AlterField(
            model_name="asset",
            name="asset_type",
            field=models.CharField(
                choices=[
                    ("COMPUTER", "Computer"),
                    ("NOTEBOOK", "Notebook"),
                    ("SERVER", "Server"),
                    ("MONITOR", "Monitor"),
                    ("KEYBOARD", "Keyboard"),
                    ("DEVICE", "Device"),
                    ("NETWORK", "Network"),
                    ("PRINTER", "Printer"),
                    ("MOBILE", "Mobile"),
                    ("TABLET", "Tablet"),
                    ("BYOD", "BYOD"),
                    ("OTHER", "Other"),
                ],
                default="COMPUTER",
                max_length=20,
            ),
        ),
    ]
