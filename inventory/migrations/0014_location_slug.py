from django.db import migrations, models
from django.utils.text import slugify


def populate_location_slugs(apps, schema_editor):
    Location = apps.get_model("inventory", "Location")
    by_parent = {}
    for location in Location.objects.order_by("parent_id", "id"):
        parent_id = location.parent_id or 0
        used = by_parent.setdefault(parent_id, set())
        base_slug = slugify(location.name) or "location"
        slug = base_slug
        index = 2
        while slug in used:
            slug = f"{base_slug}-{index}"
            index += 1
        used.add(slug)
        location.slug = slug
        location.save(update_fields=["slug"])


class Migration(migrations.Migration):

    dependencies = [
        ("inventory", "0013_location_tree_asset_location"),
    ]

    operations = [
        migrations.AddField(
            model_name="location",
            name="slug",
            field=models.SlugField(blank=True, max_length=220),
        ),
        migrations.RunPython(populate_location_slugs, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="location",
            name="slug",
            field=models.SlugField(max_length=220),
        ),
        migrations.AddConstraint(
            model_name="location",
            constraint=models.UniqueConstraint(fields=("parent", "slug"), name="uniq_location_slug_per_parent"),
        ),
    ]
