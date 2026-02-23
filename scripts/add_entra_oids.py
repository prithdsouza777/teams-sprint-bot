"""
Populate entra_oid field on all MongoDB users via Graph API lookup.

Usage:
    python scripts/add_entra_oids.py
"""

import asyncio
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from loguru import logger
from app.services.database import get_database
from app.services.graph import get_user_oid_by_name, get_user_oid_by_email


async def main():
    logger.info("=== Add Entra Object IDs to MongoDB Users ===")

    db = get_database()
    if db is None:
        logger.error("Could not connect to MongoDB")
        return

    cursor = db.users.find({})
    users = await cursor.to_list(length=100)

    if not users:
        logger.warning("No users found in MongoDB")
        return

    logger.info(f"Found {len(users)} users in MongoDB")

    updated = 0
    skipped = 0
    failed = 0

    for user in users:
        name = user.get("name", "unknown")
        existing_oid = user.get("entra_oid", "")

        if existing_oid:
            logger.info(f"  SKIP: {name} (already has OID: {existing_oid[:12]}...)")
            skipped += 1
            continue

        # Try by email first, then by display name
        result = None
        email = user.get("email", "")
        if email:
            result = await get_user_oid_by_email(email)

        if not result:
            result = await get_user_oid_by_name(name)

        if result:
            oid = result["entra_oid"]
            await db.users.update_one(
                {"_id": user["_id"]},
                {"$set": {
                    "entra_oid": oid,
                    "email": result.get("email", email),
                }},
            )
            logger.success(f"  UPDATED: {name} -> {oid[:12]}...")
            updated += 1
        else:
            logger.warning(f"  FAILED: {name} (not found in Azure AD)")
            failed += 1

    logger.info(f"\nResults: {updated} updated, {skipped} skipped, {failed} failed")


if __name__ == "__main__":
    asyncio.run(main())
