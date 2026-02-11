from database.connection import get_db, with_retry


class TransactionRepository:

    @staticmethod
    @with_retry()
    def create(
        business_id: str,
        customer_id: str,
        type: str,
        stamp_delta: int,
        stamps_before: int,
        stamps_after: int,
        employee_id: str | None = None,
        metadata: dict | None = None,
        source: str = "scanner",
        voided_transaction_id: str | None = None,
    ) -> dict | None:
        """Create a transaction record."""
        db = get_db()
        data = {
            "business_id": business_id,
            "customer_id": customer_id,
            "type": type,
            "stamp_delta": stamp_delta,
            "stamps_before": stamps_before,
            "stamps_after": stamps_after,
            "source": source,
            "metadata": metadata or {},
        }
        if employee_id:
            data["employee_id"] = employee_id
        if voided_transaction_id:
            data["voided_transaction_id"] = voided_transaction_id
        result = db.table("transactions").insert(data).execute()
        return result.data[0] if result and result.data else None

    @staticmethod
    @with_retry()
    def get_by_id(transaction_id: str) -> dict | None:
        """Fetch a single transaction by ID."""
        db = get_db()
        result = db.table("transactions").select("*").eq("id", transaction_id).limit(1).execute()
        return result.data[0] if result and result.data else None

    @staticmethod
    @with_retry()
    def list_by_business(
        business_id: str,
        customer_id: str | None = None,
        type_filter: str | None = None,
        search: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[dict], int]:
        """List transactions for a business with optional filters. Returns (rows, total_count)."""
        db = get_db()
        query = db.table("transactions").select("*", count="exact").eq("business_id", business_id)
        if customer_id:
            query = query.eq("customer_id", customer_id)
        if type_filter:
            query = query.eq("type", type_filter)
        if search:
            query = query.ilike("metadata->>customer_name", f"%{search}%")
        result = query.order("created_at", desc=True).range(offset, offset + limit - 1).execute()
        rows = result.data if result and result.data else []
        total = result.count if result and result.count is not None else len(rows)
        return rows, total

    @staticmethod
    @with_retry()
    def get_activity_stats(business_id: str) -> dict:
        """Get aggregate activity stats for the business dashboard."""
        db = get_db()
        result = db.rpc("get_activity_stats", {"p_business_id": business_id}).execute()
        if result and result.data and len(result.data) > 0:
            return result.data[0]
        return {
            "stamps_today": 0,
            "rewards_today": 0,
            "total_this_week": 0,
            "active_customers_today": 0,
            "latest_transaction_at": None,
        }

    @staticmethod
    @with_retry()
    def is_already_voided(transaction_id: str) -> bool:
        """Check if a void transaction already references this transaction ID."""
        db = get_db()
        result = (
            db.table("transactions")
            .select("id")
            .eq("voided_transaction_id", transaction_id)
            .eq("type", "stamp_voided")
            .limit(1)
            .execute()
        )
        return bool(result and result.data and len(result.data) > 0)
