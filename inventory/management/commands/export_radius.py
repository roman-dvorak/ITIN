from django.core.management.base import BaseCommand

from inventory.exporters import export_radius


class Command(BaseCommand):
    help = "Export RADIUS authorize entries."

    def add_arguments(self, parser):
        parser.add_argument(
            "--out",
            default="/exports/radius-authorize",
            help="Output path for RADIUS authorize export.",
        )

    def handle(self, *args, **options):
        output_path = export_radius(options["out"])
        self.stdout.write(self.style.SUCCESS(f"RADIUS export written to {output_path}"))
