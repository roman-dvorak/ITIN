from django.core.management.base import BaseCommand

from inventory.exporters import export_dhcp


class Command(BaseCommand):
    help = "Export DHCP data into JSON format."

    def add_arguments(self, parser):
        parser.add_argument("--out", default="/exports/dhcp.json", help="Output path for DHCP JSON export.")

    def handle(self, *args, **options):
        output_path = export_dhcp(options["out"])
        self.stdout.write(self.style.SUCCESS(f"DHCP export written to {output_path}"))
