"""
Invoice Generator Sync Service
Handles offline-first data synchronization with cloud-ready architecture.
"""

from datetime import datetime
from loguru import logger
from database.connection import db_manager
from backend.config import settings


class SyncService:
    """
    Manages offline-first synchronization:
    - Tracks all local changes via sync_logs
    - When online, pushes pending changes to cloud
    - Supports conflict resolution
    """

    async def get_pending_changes(self) -> list[dict]:
        """Get all pending sync log entries."""
        return await db_manager.fetch_all(
            "SELECT * FROM sync_logs WHERE status = 'pending' ORDER BY created_at"
        )

    async def get_sync_status(self) -> dict:
        """Get overall sync status."""
        pending = await db_manager.fetch_one(
            "SELECT COUNT(*) as count FROM sync_logs WHERE status = 'pending'"
        )
        synced = await db_manager.fetch_one(
            "SELECT COUNT(*) as count FROM sync_logs WHERE status = 'synced'"
        )
        failed = await db_manager.fetch_one(
            "SELECT COUNT(*) as count FROM sync_logs WHERE status = 'failed'"
        )
        last_sync = await db_manager.fetch_one(
            "SELECT MAX(synced_at) as last_sync FROM sync_logs WHERE status = 'synced'"
        )

        return {
            "is_online": settings.SYNC_ENABLED,
            "pending_changes": pending["count"] if pending else 0,
            "synced_changes": synced["count"] if synced else 0,
            "failed_changes": failed["count"] if failed else 0,
            "last_sync_at": last_sync["last_sync"] if last_sync else None,
        }

    async def sync_to_cloud(self) -> dict:
        """
        Attempt to sync all pending changes to cloud.

        In the current prototype, this marks changes as synced.
        In production, this would push data to PostgreSQL/Firebase/Supabase.
        """
        if not settings.SYNC_ENABLED:
            logger.info("Cloud sync is disabled. All data stored locally.")
            return {
                "success": True,
                "message": "Sync disabled. Data stored locally (offline mode).",
                "synced_count": 0,
            }

        pending = await self.get_pending_changes()
        synced_count = 0

        for change in pending:
            try:
                # In production: push to cloud database here
                # For prototype: mark as synced
                await db_manager.execute(
                    """UPDATE sync_logs
                       SET status = 'synced', synced_at = ?
                       WHERE id = ?""",
                    (datetime.now().isoformat(), change["id"]),
                )
                synced_count += 1

                # Mark the source record as synced
                await db_manager.execute(
                    f"UPDATE {change['table_name']} SET synced = 1 WHERE id = ?",
                    (change["record_id"],),
                )

            except Exception as e:
                logger.error(f"Sync error for {change['table_name']}#{change['record_id']}: {e}")
                await db_manager.execute(
                    """UPDATE sync_logs
                       SET status = 'failed', error_message = ?
                       WHERE id = ?""",
                    (str(e), change["id"]),
                )

        logger.info(f"Cloud sync complete: {synced_count}/{len(pending)} changes synced")
        return {
            "success": True,
            "message": f"Synced {synced_count} of {len(pending)} pending changes",
            "synced_count": synced_count,
            "total_pending": len(pending),
        }

    async def mark_synced(self, sync_log_id: int):
        """Mark a specific sync log entry as synced."""
        await db_manager.execute(
            """UPDATE sync_logs
               SET status = 'synced', synced_at = ?
               WHERE id = ?""",
            (datetime.now().isoformat(), sync_log_id),
        )

    async def clear_synced_logs(self):
        """Clear all synced log entries (maintenance)."""
        result = await db_manager.execute(
            "DELETE FROM sync_logs WHERE status = 'synced'"
        )
        logger.info("Cleared synced log entries")


# Global instance
sync_service = SyncService()
