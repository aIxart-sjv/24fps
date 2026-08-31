#!/usr/bin/env python3
"""
Operational bootstrap script for creating the first user account(s).

`app.core.auth_manager.AuthManager.create_user` is deliberately
manager-level-only, not a public self-service HTTP registration route
(see that module's docstring). Someone still has to create the very
first account before anyone can log in at all -- this script is that
"deployment-time/operational concern" the module docstring already
anticipates, reusing `AuthManager.create_user` unchanged rather than
reimplementing user provisioning. Once at least one `admin` account
exists, further accounts can be created through the authenticated
`POST /api/v1/users` route instead.

Usage:
    python scripts/create_user.py --username officer1 --display-name "Officer One" \\
        --password "change-me" --role officer

Never prints or logs the password.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.bootstrap import run_database_migrations  # noqa: E402
from app.core.auth_manager import AuthManager  # noqa: E402
from app.models import UserRole  # noqa: E402
from app.storage.db import SessionLocal  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Create a 24FPS user account.")
    parser.add_argument("--username", required=True)
    parser.add_argument("--display-name", required=True)
    parser.add_argument("--password", required=True)
    parser.add_argument(
        "--role", choices=[r.value for r in UserRole], default=UserRole.OFFICER.value
    )
    args = parser.parse_args()

    run_database_migrations()

    db = SessionLocal()
    try:
        user = AuthManager.create_user(
            db,
            username=args.username,
            display_name=args.display_name,
            password=args.password,
            role=UserRole(args.role),
        )
        print(f"Created user id={user.id} username={user.username!r} role={user.role.value!r}")
        return 0
    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
