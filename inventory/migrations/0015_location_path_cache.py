from django.db import migrations, models


def populate_location_path_cache(apps, schema_editor):
    Location = apps.get_model("inventory", "Location")
    rows = list(Location.objects.order_by("parent_id", "id").values("id", "parent_id", "slug"))
    paths = {}
    pending = rows

    while pending:
        progressed = False
        next_pending = []
        for row in pending:
            parent_id = row["parent_id"]
            if parent_id is None:
                paths[row["id"]] = row["slug"]
                progressed = True
                continue
            parent_path = paths.get(parent_id)
            if parent_path is None:
                next_pending.append(row)
                continue
            paths[row["id"]] = f"{parent_path}/{row['slug']}"
            progressed = True

        if not progressed:
            for row in next_pending:
                paths[row["id"]] = row["slug"]
            break
        pending = next_pending

    for location_id, path in paths.items():
        Location.objects.filter(pk=location_id).update(path_cache=path)


class Migration(migrations.Migration):
    dependencies = [
        ("inventory", "0014_location_slug"),
        ("inventory", "0014_merge_20260208_0935"),
    ]

    operations = [
        migrations.AddField(
            model_name="location",
            name="path_cache",
            field=models.CharField(blank=True, db_index=True, default="", max_length=2000),
        ),
        migrations.RunPython(populate_location_path_cache, migrations.RunPython.noop),
    ]
