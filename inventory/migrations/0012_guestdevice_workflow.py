from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


def initialize_guest_statuses(apps, schema_editor):
    GuestDevice = apps.get_model("inventory", "GuestDevice")
    GuestDevice.objects.filter(enabled=True).update(approval_status="APPROVED")
    GuestDevice.objects.filter(enabled=False).update(approval_status="DISABLED")


class Migration(migrations.Migration):

    dependencies = [
        ("inventory", "0011_assetos_multi_per_asset"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name="guestdevice",
            name="approval_status",
            field=models.CharField(
                choices=[
                    ("PENDING", "Pending"),
                    ("APPROVED", "Approved"),
                    ("REJECTED", "Rejected"),
                    ("DISABLED", "Disabled"),
                ],
                default="APPROVED",
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name="guestdevice",
            name="approved_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="guestdevice",
            name="approved_by",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="approved_guest_devices",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AddField(
            model_name="guestdevice",
            name="device_name",
            field=models.CharField(blank=True, max_length=200),
        ),
        migrations.AddField(
            model_name="guestdevice",
            name="network",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="guest_access_devices",
                to="inventory.network",
            ),
        ),
        migrations.AddField(
            model_name="guestdevice",
            name="owner_email",
            field=models.EmailField(blank=True, max_length=254),
        ),
        migrations.AddField(
            model_name="guestdevice",
            name="owner_name",
            field=models.CharField(blank=True, max_length=200),
        ),
        migrations.AddField(
            model_name="guestdevice",
            name="rejected_reason",
            field=models.TextField(blank=True),
        ),
        migrations.RunPython(initialize_guest_statuses, migrations.RunPython.noop),
    ]
