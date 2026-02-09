"""Repository for pass_type_ids table — per-business Apple certificate pool."""

import base64

from database.connection import get_db, with_retry


class PassTypeIdRepository:
    """CRUD and pool operations for pass_type_ids."""

    @staticmethod
    @with_retry()
    def create(
        identifier: str,
        team_id: str,
        signer_cert_encrypted: bytes,
        signer_key_encrypted: bytes,
        apns_combined_encrypted: bytes,
    ) -> dict | None:
        """Insert a new pool entry (available, unassigned)."""
        db = get_db()
        result = (
            db.table("pass_type_ids")
            .insert(
                {
                    "identifier": identifier,
                    "team_id": team_id,
                    "signer_cert_encrypted": base64.b64encode(signer_cert_encrypted).decode(),
                    "signer_key_encrypted": base64.b64encode(signer_key_encrypted).decode(),
                    "apns_combined_encrypted": base64.b64encode(apns_combined_encrypted).decode(),
                    "status": "available",
                }
            )
            .execute()
        )
        return result.data[0] if result and result.data else None

    @staticmethod
    @with_retry()
    def get_for_business(business_id: str) -> dict | None:
        """Get the pass_type_id record assigned to a business."""
        db = get_db()
        result = (
            db.table("pass_type_ids")
            .select("*")
            .eq("business_id", business_id)
            .eq("status", "assigned")
            .execute()
        )
        return result.data[0] if result and result.data else None

    @staticmethod
    @with_retry()
    def assign_next_available(business_id: str) -> dict | None:
        """Atomically assign the next available pass_type_id to a business.

        Uses select-then-update. The UNIQUE constraint on business_id
        prevents double-assignment.

        Returns the assigned record, or None if pool is empty.
        """
        db = get_db()

        # Find the next available entry
        available = (
            db.table("pass_type_ids")
            .select("id")
            .eq("status", "available")
            .is_("business_id", "null")
            .order("created_at")
            .limit(1)
            .execute()
        )
        if not available or not available.data:
            return None

        entry_id = available.data[0]["id"]

        # Assign it to the business
        result = (
            db.table("pass_type_ids")
            .update(
                {
                    "business_id": business_id,
                    "status": "assigned",
                    "assigned_at": "now()",
                    "updated_at": "now()",
                }
            )
            .eq("id", entry_id)
            .eq("status", "available")  # Guard against race condition
            .execute()
        )
        return result.data[0] if result and result.data else None

    @staticmethod
    @with_retry()
    def get_pool_stats() -> dict:
        """Get counts by status."""
        db = get_db()
        result = db.table("pass_type_ids").select("status").execute()
        rows = result.data if result and result.data else []

        stats = {"available": 0, "assigned": 0, "revoked": 0, "total": len(rows)}
        for row in rows:
            s = row.get("status", "")
            if s in stats:
                stats[s] += 1
        return stats

    @staticmethod
    @with_retry()
    def list_all() -> list[dict]:
        """List all pass_type_id records with business name via join."""
        db = get_db()
        result = (
            db.table("pass_type_ids")
            .select("id, identifier, team_id, status, business_id, assigned_at, created_at, businesses(name)")
            .order("created_at")
            .execute()
        )
        rows = result.data if result and result.data else []
        # Flatten the joined business name
        for row in rows:
            biz = row.pop("businesses", None)
            row["business_name"] = biz["name"] if biz else None
        return rows

    @staticmethod
    @with_retry()
    def revoke(pass_type_id_id: str) -> dict | None:
        """Mark a pass_type_id as revoked."""
        db = get_db()
        result = (
            db.table("pass_type_ids")
            .update({"status": "revoked", "updated_at": "now()"})
            .eq("id", pass_type_id_id)
            .execute()
        )
        return result.data[0] if result and result.data else None

    @staticmethod
    @with_retry()
    def get_by_id(pass_type_id_id: str) -> dict | None:
        """Get a single record by ID."""
        db = get_db()
        result = (
            db.table("pass_type_ids")
            .select("*")
            .eq("id", pass_type_id_id)
            .execute()
        )
        return result.data[0] if result and result.data else None
