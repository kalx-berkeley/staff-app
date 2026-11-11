#!/usr/bin/env python3
"""
Email that a deploy failed.

``staff-app-deploy-failed@<environment>.service`` runs this when
``staff-app-deploy@<environment>.service`` fails (its ``OnFailure=``). The
email quotes the reason the deploy saved, and the end of its log. The same
failure isn't emailed again within 12 hours, so a problem that repeats on
every staging run doesn't flood the inbox.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from collections.abc import Sequence

from deploy_common import get_environment, read_state, send_failure_email, setup_logging


def main(argv: Sequence[str] | None = None) -> int:
    """
    Send the failure email for an environment's last deploy.

    :param argv: The arguments, or None for ``sys.argv``
    :type argv: Sequence[str] | None
    :returns: The exit status
    :rtype: int
    """
    parser = argparse.ArgumentParser(description="Email that a deploy failed.")
    parser.add_argument("event", choices=["failure"])
    parser.add_argument("environment", choices=["staging", "production"])
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args(argv)
    setup_logging(args.verbose)
    environment = get_environment(args.environment)
    reason = read_state(environment, "last-failure") or (
        f"The {environment.name} deploy stopped with an unexpected error. "
        "The log below says where."
    )
    # The email still goes when the log can't be read
    try:
        journal = subprocess.run(
            [
                "journalctl",
                "--user",
                "--unit",
                f"staff-app-deploy@{environment.name}.service",
                "--lines",
                "100",
                "--no-pager",
            ],
            capture_output=True,
            text=True,
            timeout=60,
        )
        log = journal.stdout.strip() or f"(The log was empty. {journal.stderr.strip()})"
    except (OSError, subprocess.TimeoutExpired) as error:
        log = f"(The log couldn't be read: {error})"
    send_failure_email(environment, reason, log)
    return 0


if __name__ == "__main__":
    sys.exit(main())
