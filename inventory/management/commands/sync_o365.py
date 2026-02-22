"""Management command to synchronize data from Microsoft 365."""

from django.core.management.base import BaseCommand
from django_q.tasks import async_task

from inventory.tasks import sync_devices_from_o365, sync_users_from_o365


class Command(BaseCommand):
    """Synchronize data from Microsoft 365."""

    help = "Synchronize users and devices from Microsoft 365"

    def add_arguments(self, parser):
        """Add command arguments."""
        parser.add_argument(
            "--users",
            action="store_true",
            help="Sync users from O365",
        )
        parser.add_argument(
            "--devices",
            action="store_true",
            help="Sync devices from O365",
        )
        parser.add_argument(
            "--schedule",
            action="store_true",
            help="Schedule tasks instead of running directly",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Don't update database, only show what would be changed",
        )
        parser.add_argument(
            "--deep",
            action="store_true",
            help="Deep update: also update hostname, dates, and other core fields from Entra",
        )

    def handle(self, *args, **options):
        """Execute the command."""
        sync_users = options["users"]
        sync_devices = options["devices"]
        schedule = options["schedule"]
        dry_run = options["dry_run"]
        deep_update = options["deep"]

        # If no specific sync is requested, sync both
        if not sync_users and not sync_devices:
            sync_users = True
            sync_devices = True

        if schedule:
            # Schedule tasks with Django Q
            if sync_users:
                task_id = async_task("inventory.tasks.sync_users_from_o365")
                self.stdout.write(
                    self.style.SUCCESS(
                        f"Scheduled user sync task (ID: {task_id})"
                    )
                )

            if sync_devices:
                task_id = async_task(
                    "inventory.tasks.sync_devices_from_o365",
                    dry_run=dry_run,
                    deep_update=deep_update,
                )
                self.stdout.write(
                    self.style.SUCCESS(
                        f"Scheduled device sync task (ID: {task_id}, dry_run={dry_run}, deep={deep_update})"
                    )
                )
        else:
            # Run tasks directly
            if sync_users:
                self.stdout.write("Running user synchronization...")
                result = sync_users_from_o365()
                self.stdout.write(
                    self.style.SUCCESS(
                        f"User sync completed: {result.get('message', result)}"
                    )
                )

            if sync_devices:
                mode_parts = []
                if dry_run:
                    mode_parts.append("DRY RUN")
                if deep_update:
                    mode_parts.append("DEEP UPDATE")
                
                if mode_parts:
                    self.stdout.write(f"Running device synchronization ({', '.join(mode_parts)})...")
                else:
                    self.stdout.write("Running device synchronization...")
                result = sync_devices_from_o365(dry_run=dry_run, deep_update=deep_update)
                self.stdout.write(
                    self.style.SUCCESS(
                        f"Device sync completed: {result.get('message', result)}"
                    )
                )
