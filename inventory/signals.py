from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db.models.signals import pre_save
from django.dispatch import receiver

User = get_user_model()


@receiver(pre_save, sender=User)
def sync_user_identity_with_email(sender, instance, raw=False, **_kwargs):
    if raw:
        return
    email = (instance.email or "").strip().lower()
    if not email:
        raise ValidationError({"email": "Email is required."})
    instance.email = email
    instance.username = email
