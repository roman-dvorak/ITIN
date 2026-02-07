from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("inventory", "0010_asset_owner_nullable"),
    ]

    operations = [
        migrations.AlterField(
            model_name="assetos",
            name="asset",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="os_entries",
                to="inventory.asset",
            ),
        ),
    ]
