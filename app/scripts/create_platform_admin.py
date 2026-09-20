"""
Bootstrap the first platform super-admin (run once per environment).

Usage:
  PLATFORM_BOOTSTRAP_USERNAME=admin \\
  PLATFORM_BOOTSTRAP_PASSWORD='...' \\
  PLATFORM_BOOTSTRAP_MOBILE='+919876543210' \\
  python -m app.scripts.create_platform_admin
"""

from __future__ import annotations

import asyncio
import getpass
import os
import sys

from sqlalchemy import select

from app.core.config import get_settings
from app.core.logging import setup_logging
from app.core.security import hash_password
from app.db.session import close_db, get_session_factory, init_db
from app.models.platform_admin import PlatformAdmin


async def _run() -> None:
    settings = get_settings()
    setup_logging(settings)

    username = os.getenv("PLATFORM_BOOTSTRAP_USERNAME", "").strip().lower()
    password = os.getenv("PLATFORM_BOOTSTRAP_PASSWORD", "")
    mobile = os.getenv("PLATFORM_BOOTSTRAP_MOBILE", "").strip()

    if not username:
        username = input("Platform admin username: ").strip().lower()
    if not password:
        password = getpass.getpass("Platform admin password (min 12 chars): ")
    if not mobile:
        mobile = input("Platform admin mobile (+91...): ").strip()

    if len(username) < 3:
        print("Username too short", file=sys.stderr)
        sys.exit(1)
    if len(password) < 12:
        print("Password must be at least 12 characters", file=sys.stderr)
        sys.exit(1)
    if len(mobile) < 10:
        print("Invalid mobile", file=sys.stderr)
        sys.exit(1)

    await init_db(settings)
    factory = get_session_factory()
    if factory is None:
        print("Database not initialized", file=sys.stderr)
        sys.exit(1)

    async with factory() as session:
        existing = await session.execute(
            select(PlatformAdmin).where(PlatformAdmin.username == username),
        )
        if existing.scalar_one_or_none():
            print("Platform admin already exists", file=sys.stderr)
            sys.exit(1)

        admin = PlatformAdmin(
            username=username,
            password_hash=hash_password(password),
            mobile=mobile,
            is_active=True,
        )
        session.add(admin)
        await session.commit()
        print(f"Created platform admin '{username}' (id={admin.id})")

    await close_db()


def main() -> None:
    asyncio.run(_run())


if __name__ == "__main__":
    main()
