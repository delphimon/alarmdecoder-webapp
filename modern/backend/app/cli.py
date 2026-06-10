from __future__ import annotations

import argparse
import getpass
import shutil

from .auth import create_user
from .config import AppConfig
from .db import Database


def main() -> None:
    parser = argparse.ArgumentParser(prog="alarmdecoder-modern")
    subcommands = parser.add_subparsers(dest="command", required=True)

    create_admin = subcommands.add_parser("create-admin", help="Create a local admin user")
    create_admin.add_argument("--username", required=True)
    create_admin.add_argument("--password")
    backup = subcommands.add_parser("backup", help="Back up the SQLite database file")
    backup.add_argument("--output", required=True)
    subcommands.add_parser("prune-retention", help="Prune raw/event history using configured retention")

    args = parser.parse_args()
    config = AppConfig.from_env()
    database = Database(config)
    database.init()

    if args.command == "create-admin":
        password = args.password or getpass.getpass("Admin password: ")
        with database.session_factory() as session:
            create_user(session, args.username, password, "admin")
        database.audit(args.username, "admin_created_cli", {"role": "admin"})
        print(f"Created admin user {args.username}")
    elif args.command == "backup":
        if not config.database_url.startswith("sqlite:///"):
            raise SystemExit("backup currently supports sqlite:/// database URLs only")
        source = config.database_url.removeprefix("sqlite:///")
        shutil.copy2(source, args.output)
        print(f"Backed up database to {args.output}")
    elif args.command == "prune-retention":
        database.prune_retention()
        print("Pruned raw/event history")


if __name__ == "__main__":
    main()
