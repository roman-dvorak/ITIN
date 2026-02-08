from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("inventory", "0016_os_catalog_refactor"),
    ]

    operations = [
        migrations.AddField(
            model_name="osfamily",
            name="support_status",
            field=models.CharField(
                choices=[("SUPPORTED", "Supported"), ("UNSUPPORTED", "Unsupported")],
                default="SUPPORTED",
                max_length=20,
            ),
        ),
    ]
