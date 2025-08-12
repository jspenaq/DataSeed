import asyncio
import argparse
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

from alembic.config import Config
from alembic import command
from scripts.database import create_database, drop_database
from dotenv import load_dotenv

load_dotenv()

def run_migrations(revision: str):
    """Run alembic migrations."""
    alembic_cfg = Config("alembic.ini")
    command.upgrade(alembic_cfg, revision)

def rollback_migrations(revision: str):
    """Rollback alembic migrations."""
    alembic_cfg = Config("alembic.ini")
    command.downgrade(alembic_cfg, revision)

async def main():
    parser = argparse.ArgumentParser(description="Manage database migrations.")
    parser.add_argument("action", choices=["upgrade", "downgrade", "recreate"], help="Action to perform.")
    parser.add_argument("--revision", default="head", help="Revision to migrate to.")
    args = parser.parse_args()

    if args.action == "recreate":
        await drop_database()
        await create_database()
        run_migrations("head")
    elif args.action == "upgrade":
        run_migrations(args.revision)
    elif args.action == "downgrade":
        rollback_migrations(args.revision)

if __name__ == "__main__":
    asyncio.run(main())