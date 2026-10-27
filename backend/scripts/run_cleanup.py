#!/usr/bin/env python3
"""
Saathi AI Automated Retention & Cleanup Runner
Enforces retention policies:
- Abandoned temporary audio files > ABANDONED_AUDIO_CLEANUP_HOURS
- Expired voice records > TRANSCRIPT_RETENTION_HOURS
- Unconfirmed complaints > UNCONFIRMED_COMPLAINT_RETENTION_HOURS
- Cancelled complaints > CANCELLED_COMPLAINT_RETENTION_HOURS
- Confirmed complaints preserved up to CONFIRMED_COMPLAINT_RETENTION_DAYS
"""

import asyncio
import json
import logging
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from backend.app.database import AsyncSessionLocal
from backend.app.services.retention_service import RetentionService

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("SaathiCleanup")


async def main() -> int:
    logger.info("Starting Saathi AI retention & cleanup script...")
    db = None
    try:
        async with AsyncSessionLocal() as session:
            db = session
            summary = await RetentionService.run_full_retention_cycle(db=db)
    except Exception as e:
        logger.warning(f"Could not connect to database for cleanup ({e}); executing filesystem and in-memory cleanup...")
        summary = await RetentionService.run_full_retention_cycle(db=None)

    print("\n--- Saathi AI Cleanup Summary ---")
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    code = asyncio.run(main())
    sys.exit(code)
