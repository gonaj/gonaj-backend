"""
Management command for explicit recompute orchestration.

Sprint-12: Performance & Recompute Control

Usage:
    python manage.py recompute stops
    python manage.py recompute routes
    python manage.py recompute all

RULES:
- No default target is allowed — target must be explicit
- 'all' enforces Stops → Routes dependency ordering
- Admin-only (management command, not a public API)
"""

from django.core.management.base import BaseCommand, CommandError

from transit.evaluation.executor import InlineExecutor
from transit.evaluation.orchestration import (
    DEFAULT_RULESET_VERSION,
    recompute_all,
    recompute_routes,
    recompute_stops,
)

VALID_TARGETS = ("stops", "routes", "all")


class Command(BaseCommand):
    help = "Recompute canonical evaluation for stops, routes, or all entities."

    def add_arguments(self, parser):
        parser.add_argument(
            "target",
            type=str,
            choices=VALID_TARGETS,
            help="Target scope for recompute: stops, routes, or all.",
        )
        parser.add_argument(
            "--ruleset-version",
            type=str,
            default=DEFAULT_RULESET_VERSION,
            help=f"Evaluation ruleset version to apply (default: {DEFAULT_RULESET_VERSION}).",
        )

    def handle(self, *args, **options):
        target = options["target"]
        ruleset_version = options["ruleset_version"]
        executor = InlineExecutor()

        self.stdout.write(
            f"Starting recompute: target={target}, ruleset_version={ruleset_version}"
        )

        if target == "stops":
            result = recompute_stops(executor, ruleset_version)
        elif target == "routes":
            result = recompute_routes(executor, ruleset_version)
        elif target == "all":
            result = recompute_all(executor, ruleset_version)
        else:
            raise CommandError(f"Invalid target: {target}")

        # Report results
        self.stdout.write(
            f"Recompute complete: "
            f"jobs={result.total_jobs}, "
            f"successful={result.successful_jobs}, "
            f"failed={result.failed_jobs}"
        )

        for exec_result in result.execution_results:
            status = "OK" if exec_result.success else "FAILED"
            self.stdout.write(
                f"  [{status}] {exec_result.job.target_type.value}: "
                f"evaluated={exec_result.entities_evaluated}, "
                f"writes={exec_result.canonical_writes}, "
                f"skipped_locked={exec_result.skipped_locked}"
            )
            if exec_result.errors:
                for err in exec_result.errors:
                    self.stderr.write(f"    ERROR: {err}")

        if result.has_failures:
            raise CommandError("Recompute completed with failures.")

        self.stdout.write(self.style.SUCCESS("Recompute completed successfully."))
