"""Django Q tasks for synchronizing data from Microsoft 365."""

import asyncio
import io
import logging
import os
import sys
from typing import Any

from asgiref.sync import sync_to_async
from azure.identity import ClientSecretCredential
from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone
from msgraph import GraphServiceClient

from inventory.models import TaskRun, UserProfile

logger = logging.getLogger(__name__)
User = get_user_model()


# ---------------------------------------------------------------------------
# Task registry
# ---------------------------------------------------------------------------

TASK_REGISTRY: dict[str, dict] = {}


def register_task(name: str, description: str, params: dict | None = None):
    """Decorator to register a callable in the task registry."""
    def decorator(func):
        TASK_REGISTRY[name] = {
            "func": func,
            "description": description,
            "params": params or {},
        }
        return func
    return decorator


def run_task_with_capture(task_name: str, triggered_by_id: int | None = None, **kwargs):
    """Run a registered task, capturing stdout into a TaskRun record."""
    entry = TASK_REGISTRY.get(task_name)
    if not entry:
        raise ValueError(f"Unknown task: {task_name}")

    task_run = TaskRun.objects.create(
        task_name=task_name,
        status=TaskRun.Status.RUNNING,
        triggered_by_id=triggered_by_id,
    )

    buf = io.StringIO()
    old_stdout = sys.stdout
    sys.stdout = buf
    try:
        result = entry["func"](**kwargs)
        task_run.status = TaskRun.Status.SUCCESS
        task_run.result_data = result if isinstance(result, dict) else {}
    except Exception as exc:
        task_run.status = TaskRun.Status.FAILED
        task_run.result_data = {"error": str(exc)}
        buf.write(f"\nERROR: {exc}\n")
    finally:
        sys.stdout = old_stdout
        task_run.stdout = buf.getvalue()
        task_run.finished_at = timezone.now()
        task_run.save(update_fields=["status", "stdout", "result_data", "finished_at"])

    return task_run


def execute_task_in_background(task_run_id: int, task_name: str, **kwargs) -> None:
    """Worker function called by Django-Q. Updates an existing TaskRun record."""
    entry = TASK_REGISTRY.get(task_name)
    if not entry:
        TaskRun.objects.filter(pk=task_run_id).update(
            status=TaskRun.Status.FAILED,
            result_data={"error": f"Unknown task: {task_name}"},
            finished_at=timezone.now(),
        )
        return

    task_run = TaskRun.objects.get(pk=task_run_id)
    task_run.status = TaskRun.Status.RUNNING
    task_run.save(update_fields=["status"])

    buf = io.StringIO()
    old_stdout = sys.stdout
    sys.stdout = buf
    try:
        result = entry["func"](**kwargs)
        task_run.status = TaskRun.Status.SUCCESS
        task_run.result_data = result if isinstance(result, dict) else {}
    except Exception as exc:
        task_run.status = TaskRun.Status.FAILED
        task_run.result_data = {"error": str(exc)}
        buf.write(f"\nERROR: {exc}\n")
    finally:
        sys.stdout = old_stdout
        task_run.stdout = buf.getvalue()
        task_run.finished_at = timezone.now()
        task_run.save(update_fields=["status", "stdout", "result_data", "finished_at"])


def enqueue_task(task_name: str, triggered_by_id: int | None = None, **kwargs) -> TaskRun:
    """Create a PENDING TaskRun and enqueue the work as a Django-Q background task."""
    from django_q.tasks import async_task

    if task_name not in TASK_REGISTRY:
        raise ValueError(f"Unknown task: {task_name}")

    task_run = TaskRun.objects.create(
        task_name=task_name,
        status=TaskRun.Status.PENDING,
        triggered_by_id=triggered_by_id,
    )

    async_task(
        "inventory.tasks.execute_task_in_background",
        task_run.pk,
        task_name,
        **kwargs,
    )

    return task_run


def get_graph_client() -> GraphServiceClient:
    """
    Get authenticated Microsoft Graph client.
    
    Returns:
        GraphServiceClient: Authenticated Graph API client
    
    Raises:
        ValueError: If required environment variables are not set
    """
    tenant_id = os.environ.get("ENTRA_TENANT_ID")
    client_id = os.environ.get("ENTRA_OIDC_CLIENT_ID")
    client_secret = os.environ.get("ENTRA_OIDC_CLIENT_SECRET")
    
    if not all([tenant_id, client_id, client_secret]):
        raise ValueError(
            "Missing required environment variables: "
            "ENTRA_TENANT_ID, ENTRA_OIDC_CLIENT_ID, ENTRA_OIDC_CLIENT_SECRET"
        )
    
    credential = ClientSecretCredential(
        tenant_id=tenant_id,
        client_id=client_id,
        client_secret=client_secret,
    )
    
    return GraphServiceClient(credentials=credential)


def _parse_name(display_name: str) -> tuple[str, str] | None:
    """Parse first and last name from display name."""
    if not display_name or not display_name.strip():
        return None
    
    parts = display_name.strip().split()
    if len(parts) < 2:
        return None
    
    # Assume format: "LastName FirstName" or "FirstName LastName"
    # Try to detect by checking if there are commas or other patterns
    if len(parts) == 2:
        return parts[1], parts[0]  # Assume "LastName FirstName"
    else:
        # For multiple parts, take first as first name, rest as last name
        return parts[0], " ".join(parts[1:])


def _create_or_update_user(email: str, first_name: str, last_name: str, entra_data: dict) -> dict:
    """Create or update user and profile (synchronous)."""
    # Normalize email to lowercase for case-insensitive username
    email_lower = email.lower()
    
    with transaction.atomic():
        user, created = User.objects.get_or_create(
            username__iexact=email_lower,
            defaults={
                "username": email_lower,
                "email": email,
                "first_name": first_name[:150],
                "last_name": last_name[:150],
            },
        )
        
        if not created:
            # Update name if changed
            if user.first_name != first_name[:150] or user.last_name != last_name[:150]:
                user.first_name = first_name[:150]
                user.last_name = last_name[:150]
                user.save(update_fields=["first_name", "last_name"])
        
        # Create or update profile with Entra data
        profile, _ = UserProfile.objects.get_or_create(user=user)
        profile.metadata["entra"] = entra_data
        profile.save()
        
        return {"created": created}


def _fetch_windows_build_labels() -> dict[int, str]:
    """Fetch Windows build number → releaseLabel mapping from endoflife.date.

    Returns an empty dict if the API is unavailable, so callers can safely
    skip setting AssetOS.version without failing the whole sync.
    Prefers the workstation (-w) variant when multiple editions share a build.
    """
    import urllib.request
    import json as _json

    url = "https://endoflife.date/api/windows.json"
    try:
        with urllib.request.urlopen(url, timeout=10) as resp:
            data = _json.loads(resp.read())
    except Exception as exc:
        logger.warning("Could not fetch Windows release data from %s: %s", url, exc)
        return {}

    result: dict[int, str] = {}
    for entry in data:
        latest = entry.get("latest", "")
        label = entry.get("releaseLabel", "")
        parts = latest.split(".")
        if len(parts) < 3:
            continue
        try:
            build_num = int(parts[2])
        except ValueError:
            continue
        # Prefer workstation (-w) variant; only overwrite if slot is still empty
        cycle = entry.get("cycle", "")
        if build_num not in result or cycle.endswith("-w"):
            result[build_num] = label

    return result


def _sync_windows_os_entry(asset, os_version: str, build_label_map: dict[int, str]) -> None:
    """Sync Windows OS entry for an asset based on Entra OS version string.

    Sets patch_level to the raw Entra version (e.g. "10.0.26200.7840") and
    version to the human-readable releaseLabel (e.g. "11 25H2 (W)") when
    the build number is found in build_label_map.
    """
    from inventory.models import AssetOS, OSFamily

    # Parse build number (third segment): "10.0.26200.7840" -> 26200
    parts = os_version.split(".")
    build_num = None
    if len(parts) >= 3:
        try:
            build_num = int(parts[2])
        except ValueError:
            pass

    os_family = OSFamily.objects.filter(family="windows").first()
    if os_family is None:
        logger.warning("No Windows OSFamily found; skipping OS entry for %s", asset.name)
        return

    release_label = build_label_map.get(build_num, "") if build_num is not None else ""

    existing = asset.os_entries.filter(family__family="windows").order_by("id").first()
    if existing:
        update_fields = []
        if existing.patch_level != os_version:
            existing.patch_level = os_version
            update_fields.append("patch_level")
        if existing.family_id != os_family.pk:
            existing.family = os_family
            update_fields.append("family")
        if release_label and existing.version != release_label:
            existing.version = release_label
            update_fields.append("version")
        if update_fields:
            existing.save(update_fields=update_fields)
    else:
        AssetOS.objects.create(
            asset=asset,
            family=os_family,
            patch_level=os_version,
            version=release_label,
        )


def _update_asset_entra_metadata(asset, entra_data: dict, deep_update: bool = False, build_label_map: dict | None = None) -> None:
    """Update asset metadata with Entra device data (synchronous).
    
    Args:
        asset: Asset instance to update
        entra_data: Entra device data dictionary
        deep_update: If True, also update core asset fields from Entra data
    """
    from datetime import datetime
    from inventory.models import Asset, AssetTag, UserProfile
    import re
    
    with transaction.atomic():
        # Refresh from DB to avoid race conditions
        asset = Asset.objects.get(pk=asset.pk)
        asset.metadata["entra"] = entra_data
        
        # Store entra device ID as separate field for easier querying
        if "id" in entra_data:
            asset.metadata["entra_id"] = entra_data["id"]
        
        update_fields = ["metadata"]
        
        # Try to assign owner based on physical_ids USER-GID if not already assigned
        if not asset.owner and "physical_ids" in entra_data:
            physical_ids_str = entra_data["physical_ids"]
            # Parse physical_ids to find USER-GID
            # Format: ['[USER-GID]:8ce5d528-68c5-473d-8376-6137c8535e46:6825809167846042', ...]
            user_gid_pattern = r'\[USER-GID\]:([a-f0-9-]+):'
            match = re.search(user_gid_pattern, physical_ids_str)
            if match:
                entra_user_id = match.group(1)
                # Find user with this entra ID in their metadata
                try:
                    profile = UserProfile.objects.filter(
                        metadata__entra__id=entra_user_id
                    ).select_related('user').first()
                    if profile:
                        asset.owner = profile.user
                        update_fields.append("owner")
                        logger.info(f"Assigned owner {profile.user.email} to asset {asset.name} based on USER-GID")
                except Exception as e:
                    logger.warning(f"Failed to assign owner for {asset.name}: {e}")
        
        # Add 'entra' tag to asset
        entra_tag, _ = AssetTag.objects.get_or_create(
            name="entra",
            defaults={"description": "Device synchronized from Microsoft Entra ID"}
        )
        asset.tags.add(entra_tag)
        
        if deep_update:
            # Update last_seen from approximate_last_sign_in_date_time
            if "approximate_last_sign_in_date_time" in entra_data:
                last_sign_in_str = entra_data["approximate_last_sign_in_date_time"]
                if last_sign_in_str:
                    try:
                        # Parse datetime string (format: "2024-09-28 13:30:45+00:00")
                        asset.last_seen = datetime.fromisoformat(last_sign_in_str)
                        update_fields.append("last_seen")
                    except (ValueError, TypeError) as e:
                        logger.warning(f"Failed to parse last_sign_in for {asset.name}: {e}")
            
            # Update commissioning_date from registration_date_time
            if not asset.commissioning_date and "registration_date_time" in entra_data:
                reg_date_str = entra_data["registration_date_time"]
                if reg_date_str:
                    try:
                        # Parse datetime and extract date
                        reg_datetime = datetime.fromisoformat(reg_date_str)
                        asset.commissioning_date = reg_datetime.date()
                        update_fields.append("commissioning_date")
                    except (ValueError, TypeError) as e:
                        logger.warning(f"Failed to parse registration_date for {asset.name}: {e}")
            
            # Update hostname from display_name
            if "display_name" in entra_data and entra_data["display_name"]:
                new_name = entra_data["display_name"]
                if asset.name != new_name:
                    asset.name = new_name
                    update_fields.append("name")

            # Sync Windows OS entry
            os_name = entra_data.get("operating_system", "")
            os_version = entra_data.get("operating_system_version", "")
            if os_name and "windows" in os_name.lower() and os_version:
                _sync_windows_os_entry(asset, os_version, build_label_map or {})

        asset.save(update_fields=update_fields)


async def _sync_users_from_o365_async() -> dict[str, Any]:
    """
    Synchronize users from Microsoft 365 tenant.
    
    Creates Django user accounts based on Entra ID data.
    Stores all Entra data in UserProfile.metadata['entra'].
    Skips users without first and last names.
    
    Returns:
        dict: Summary of the sync operation
    """
    logger.info("Starting user synchronization from O365")
    
    try:
        client = get_graph_client()
        
        # Get all users with pagination
        all_users = []
        users_response = await client.users.get()
        
        if not users_response:
            logger.warning("No users found in O365 tenant")
            print("No users found in O365 tenant")
            return {"status": "success", "users_found": 0}
        
        # Collect users from first page
        if users_response.value:
            all_users.extend(users_response.value)
            print(f"Fetched page 1: {len(users_response.value)} users")
        
        # Handle pagination
        page_num = 1
        while users_response.odata_next_link:
            page_num += 1
            users_response = await client.users.with_url(users_response.odata_next_link).get()
            if users_response and users_response.value:
                all_users.extend(users_response.value)
                print(f"Fetched page {page_num}: {len(users_response.value)} users")
        
        user_count = len(all_users)
        logger.info(f"Found {user_count} users in O365 tenant (across {page_num} pages)")
        print(f"\n{'='*80}")
        print(f"Processing {user_count} users from Microsoft 365 (across {page_num} pages)")
        print(f"{'='*80}\n")
        
        created_count = 0
        updated_count = 0
        skipped_emails = []
        
        for entra_user in all_users:
            email = entra_user.mail or entra_user.user_principal_name
            if not email:
                logger.warning(f"Skipping user without email: {entra_user.display_name}")
                skipped_emails.append(f"{entra_user.display_name} (no email)")
                continue
            
            # Parse name
            name_parts = _parse_name(entra_user.display_name)
            if not name_parts:
                logger.info(f"Skipping user without proper name: {email}")
                skipped_emails.append(email)
                continue
            
            first_name, last_name = name_parts
            
            # Collect all Entra user data
            entra_data = {}
            for attr in dir(entra_user):
                if not attr.startswith('_'):
                    try:
                        value = getattr(entra_user, attr)
                        if value is not None and not callable(value):
                            # Convert to JSON-serializable format
                            if isinstance(value, (str, int, float, bool, type(None))):
                                entra_data[attr] = value
                            else:
                                entra_data[attr] = str(value)
                    except Exception:
                        pass
            
            # Create or update user (wrap sync DB operation for async context)
            result = await sync_to_async(_create_or_update_user)(email, first_name, last_name, entra_data)
            
            if result["created"]:
                created_count += 1
                print(f"✓ Created: {first_name} {last_name} ({email})")
            else:
                updated_count += 1
                print(f"↻ Updated: {first_name} {last_name} ({email})")
        
        print(f"\n{'='*80}")
        print(f"Synchronization completed:")
        print(f"  Created: {created_count} users")
        print(f"  Updated: {updated_count} users")
        print(f"  Skipped: {len(skipped_emails)} users")
        print(f"{'='*80}")
        
        if skipped_emails:
            print(f"\nSkipped emails (no first/last name):")
            for email in skipped_emails:
                print(f"  - {email}")
        
        logger.info(
            f"User synchronization completed: "
            f"created={created_count}, updated={updated_count}, skipped={len(skipped_emails)}"
        )
        return {
            "status": "success",
            "users_found": user_count,
            "created": created_count,
            "updated": updated_count,
            "skipped": len(skipped_emails),
            "skipped_emails": skipped_emails,
            "pages_fetched": page_num,
            "message": f"Created {created_count}, updated {updated_count}, skipped {len(skipped_emails)} users",
        }
    
    except Exception as e:
        logger.error(f"Error during user synchronization: {e}", exc_info=True)
        print(f"ERROR: Failed to sync users: {e}")
        return {
            "status": "error",
            "message": str(e),
        }


@register_task("sync_users_from_o365", "Sync users from Microsoft Entra ID")
def sync_users_from_o365() -> dict[str, Any]:
    """Synchronous wrapper for Django Q."""
    return asyncio.run(_sync_users_from_o365_async())


async def _sync_devices_from_o365_async(dry_run: bool = False, deep_update: bool = False) -> dict[str, Any]:
    """
    Get list of devices from Microsoft 365 tenant and match with local assets.
    
    Matches devices by hostname (case insensitive) and stores Entra data in asset metadata.
    
    Args:
        dry_run: If True, don't update database, only show what would be matched
        deep_update: If True, update core asset fields from Entra data (hostname, dates, etc.)
    
    Returns:
        dict: Summary of the sync operation
    """
    logger.info(f"Starting device synchronization from O365 (dry_run={dry_run}, deep_update={deep_update})")

    build_label_map = _fetch_windows_build_labels()
    if build_label_map:
        print(f"Loaded Windows release labels for {len(build_label_map)} build numbers.")
    else:
        print("Windows release label data unavailable; AssetOS.version will not be set.")

    try:
        client = get_graph_client()
        
        # Get all devices with pagination
        all_devices = []
        devices_response = await client.devices.get()
        
        if not devices_response:
            logger.warning("No devices found in O365 tenant")
            print("No devices found in O365 tenant")
            return {"status": "success", "devices_found": 0}
        
        # Collect devices from first page
        if devices_response.value:
            all_devices.extend(devices_response.value)
            print(f"Fetched page 1: {len(devices_response.value)} devices")
        
        # Handle pagination
        page_num = 1
        while devices_response.odata_next_link:
            page_num += 1
            devices_response = await client.devices.with_url(devices_response.odata_next_link).get()
            if devices_response and devices_response.value:
                all_devices.extend(devices_response.value)
                print(f"Fetched page {page_num}: {len(devices_response.value)} devices")
        
        device_count = len(all_devices)
        logger.info(f"Found {device_count} devices in O365 tenant (across {page_num} pages)")
        print(f"\n{'='*80}")
        if dry_run:
            mode_str = "DEEP UPDATE" if deep_update else "standard"
            print(f"DRY RUN ({mode_str}): Matching {device_count} devices (no database changes)")
        else:
            mode_str = "with deep update" if deep_update else "standard mode"
            print(f"Matching {device_count} devices from Microsoft 365 ({mode_str})")
        print(f"{'='*80}\n")
        
        # Get all assets from database (sync operation)
        from inventory.models import Asset
        assets = await sync_to_async(list)(Asset.objects.all())
        
        # Create two mappings for asset matching:
        # 1. entra_id -> asset (for assets already synced)
        # 2. hostname -> asset (case insensitive, for new matches)
        entra_id_map = {}
        hostname_map = {}
        for asset in assets:
            if asset.metadata.get("entra_id"):
                entra_id_map[asset.metadata["entra_id"]] = asset
            if asset.name:
                hostname_map[asset.name.lower().strip()] = asset
        
        matched_count = 0
        not_matched = []
        
        for entra_device in all_devices:
            display_name = entra_device.display_name
            device_id = entra_device.id if hasattr(entra_device, 'id') else None
            
            if not display_name:
                not_matched.append(("(no display name)", device_id))
                continue
            
            hostname_lower = display_name.lower().strip()
            
            # Try to find matching asset:
            # 1. First by entra_id (stable identifier)
            # 2. Then by hostname (for new devices)
            asset = None
            match_method = None
            
            if device_id and device_id in entra_id_map:
                asset = entra_id_map[device_id]
                match_method = "entra_id"
            elif hostname_lower in hostname_map:
                asset = hostname_map[hostname_lower]
                match_method = "hostname"
            
            if asset:
                # Collect all Entra device data
                entra_data = {}
                for attr in dir(entra_device):
                    if not attr.startswith('_'):
                        try:
                            value = getattr(entra_device, attr)
                            if value is not None and not callable(value):
                                # Convert to JSON-serializable format
                                if isinstance(value, (str, int, float, bool, type(None))):
                                    entra_data[attr] = value
                                else:
                                    entra_data[attr] = str(value)
                        except Exception:
                            pass
                
                # Update asset metadata with Entra data (unless dry run)
                if not dry_run:
                    await sync_to_async(_update_asset_entra_metadata)(asset, entra_data, deep_update, build_label_map)
                
                matched_count += 1
                if dry_run:
                    mode_str = " (deep)" if deep_update else ""
                    method_str = f" [by {match_method}]" if match_method else ""
                    print(f"✓ Would match{mode_str}{method_str}: {display_name} -> Asset ID {asset.id} ({asset.name})")
                else:
                    mode_str = " (deep)" if deep_update else ""
                    method_str = f" [by {match_method}]" if match_method else ""
                    print(f"✓ Matched{mode_str}{method_str}: {display_name} -> Asset ID {asset.id} ({asset.name})")
            else:
                not_matched.append((display_name, device_id))

        print(f"\n{'='*80}")
        print(f"Matching completed:")
        print(f"  Matched: {matched_count} devices")
        print(f"  Not matched: {len(not_matched)} devices")
        print(f"{'='*80}")

        if not_matched:
            print(f"\nDevices not found in local database:")
            for name, eid in not_matched[:50]:  # Limit to first 50
                print(f"  - {name}  \"entra_id\": \"{eid}\"")
            if len(not_matched) > 50:
                print(f"  ... and {len(not_matched) - 50} more")
        
        logger.info(
            f"Device synchronization completed: "
            f"matched={matched_count}, not_matched={len(not_matched)}"
        )
        return {
            "status": "success",
            "devices_found": device_count,
            "matched": matched_count,
            "not_matched": len(not_matched),
            "not_matched_names": {eid: {"hostname": name, "entra_id": eid} for name, eid in not_matched},
            "pages_fetched": page_num,
            "message": f"Matched {matched_count} devices, {len(not_matched)} not found",
        }
    
    except Exception as e:
        logger.error(f"Error during device synchronization: {e}", exc_info=True)
        print(f"ERROR: Failed to sync devices: {e}")
        return {
            "status": "error",
            "message": str(e),
        }


@register_task(
    "sync_devices_from_o365",
    "Sync devices from Microsoft Entra ID",
    params={"dry_run": "bool", "deep_update": "bool"},
)
def sync_devices_from_o365(dry_run: bool = False, deep_update: bool = False) -> dict[str, Any]:
    """Synchronous wrapper for Django Q.

    Args:
        dry_run: If True, don't update database, only show what would be matched
        deep_update: If True, update core asset fields from Entra data
    """
    return asyncio.run(_sync_devices_from_o365_async(dry_run=dry_run, deep_update=deep_update))
