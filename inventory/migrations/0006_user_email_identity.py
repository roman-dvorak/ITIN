from django.db import migrations


def normalize_user_identity(apps, schema_editor):
    User = apps.get_model("auth", "User")
    alias = schema_editor.connection.alias
    used_emails = set()

    for user in User.objects.using(alias).order_by("id"):
        email = (user.email or "").strip().lower()
        if not email:
            base_local = (user.username or f"user{user.id}").strip().lower().replace(" ", "")
            if "@" in base_local:
                email = base_local
            else:
                email = f"{base_local}@example.local"

        local_part, separator, domain_part = email.partition("@")
        if not separator:
            local_part = email
            domain_part = "example.local"

        candidate = email
        suffix = 1
        while candidate in used_emails:
            candidate = f"{local_part}+{suffix}@{domain_part}"
            suffix += 1

        used_emails.add(candidate)
        User.objects.using(alias).filter(pk=user.pk).update(email=candidate, username=candidate)


class Migration(migrations.Migration):
    dependencies = [
        ("inventory", "0005_asset_metadata"),
    ]

    operations = [
        migrations.RunPython(normalize_user_identity, migrations.RunPython.noop),
        migrations.RunSQL(
            sql=(
                "ALTER TABLE auth_user "
                "ADD CONSTRAINT auth_user_email_not_blank CHECK (char_length(btrim(email)) > 0), "
                "ADD CONSTRAINT auth_user_email_unique UNIQUE (email)"
            ),
            reverse_sql=(
                "ALTER TABLE auth_user "
                "DROP CONSTRAINT IF EXISTS auth_user_email_unique, "
                "DROP CONSTRAINT IF EXISTS auth_user_email_not_blank"
            ),
        ),
    ]
