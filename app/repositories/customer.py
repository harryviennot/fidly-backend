from database.connection import get_db, with_retry


class CustomerRepository:

    @staticmethod
    @with_retry()
    def create(business_id: str, name: str, email: str, auth_token: str) -> dict | None:
        """Create a new customer for a business."""
        db = get_db()
        result = db.table("customers").insert({
            "business_id": business_id,
            "name": name,
            "email": email,
            "auth_token": auth_token,
            "stamps": 0,
        }).execute()
        return result.data[0] if result and result.data else None

    @staticmethod
    @with_retry()
    def get_by_id(customer_id: str) -> dict | None:
        """Get a customer by ID. Joins enrollment data from v2 tables."""
        db = get_db()
        result = db.table("customers").select(
            "*, enrollments(progress, total_redemptions, last_activity_at, status)"
        ).eq("id", customer_id).limit(1).execute()
        if not result or not result.data:
            return None
        row = result.data[0]
        enrollments = row.pop("enrollments", []) or []
        enrollment = enrollments[0] if enrollments else None
        if enrollment:
            progress = enrollment.get("progress") or {}
            row["stamps"] = progress.get("stamps", row.get("stamps", 0))
            row["total_redemptions"] = enrollment.get("total_redemptions", row.get("total_redemptions", 0))
            row["last_activity_at"] = enrollment.get("last_activity_at")
        return row

    @staticmethod
    @with_retry()
    def get_by_email(business_id: str, email: str) -> dict | None:
        """Get a customer by email within a business."""
        db = get_db()
        result = db.table("customers").select("*").eq(
            "business_id", business_id
        ).eq("email", email).limit(1).execute()
        return result.data[0] if result and result.data else None

    @staticmethod
    @with_retry()
    def get_by_auth_token(serial_number: str, auth_token: str) -> dict | None:
        """Verify auth token matches customer."""
        db = get_db()
        result = db.table("customers").select("*").eq(
            "id", serial_number
        ).eq("auth_token", auth_token).limit(1).execute()
        return result.data[0] if result and result.data else None

    @staticmethod
    @with_retry()
    def get_all(business_id: str) -> list[dict]:
        """Get all customers for a business ordered by creation date."""
        db = get_db()
        result = db.table("customers").select("*").eq(
            "business_id", business_id
        ).order("created_at", desc=True).execute()
        return result.data if result and result.data else []

    @staticmethod
    @with_retry()
    def add_stamp(customer_id: str, max_stamps: int = 10) -> int:
        """Add a stamp to a customer atomically. Returns the new stamp count."""
        db = get_db()
        result = db.rpc("increment_stamps", {
            "p_customer_id": customer_id,
            "p_max_stamps": max_stamps,
        }).execute()
        if not result or result.data is None:
            raise ValueError("Customer not found")
        return result.data

    @staticmethod
    @with_retry()
    def reset_stamps(customer_id: str) -> int:
        """Reset a customer's stamps to 0. Returns 0."""
        db = get_db()
        db.table("customers").update({
            "stamps": 0,
            "updated_at": "now()"
        }).eq("id", customer_id).execute()
        return 0

    @staticmethod
    @with_retry()
    def void_stamp(customer_id: str) -> int:
        """Decrement stamps by 1 atomically (min 0). Returns the new stamp count."""
        db = get_db()
        result = db.rpc("decrement_stamps", {
            "p_customer_id": customer_id,
        }).execute()
        if not result or result.data is None:
            raise ValueError("Customer not found")
        return result.data

    @staticmethod
    @with_retry()
    def increment_redemptions(customer_id: str) -> None:
        """Increment total_redemptions by 1 atomically."""
        db = get_db()
        db.rpc("increment_redemptions", {
            "p_customer_id": customer_id,
        }).execute()

    @staticmethod
    @with_retry()
    def get_paginated(business_id: str, limit: int = 50, offset: int = 0) -> dict:
        """Get paginated customers for a business. Returns {data, total}.
        Joins enrollment data to source stamps/redemptions from v2 tables."""
        db = get_db()
        query = db.table("customers").select(
            "*, enrollments(progress, total_redemptions, last_activity_at, status)",
            count="exact",
        ).eq(
            "business_id", business_id
        ).order("created_at", desc=True).range(offset, offset + limit - 1)
        result = query.execute()

        data = []
        for row in (result.data if result and result.data else []):
            enrollments = row.pop("enrollments", []) or []
            enrollment = enrollments[0] if enrollments else None
            if enrollment:
                progress = enrollment.get("progress") or {}
                row["stamps"] = progress.get("stamps", row.get("stamps", 0))
                row["total_redemptions"] = enrollment.get("total_redemptions", row.get("total_redemptions", 0))
                row["last_activity_at"] = enrollment.get("last_activity_at")
            data.append(row)

        return {
            "data": data,
            "total": result.count if result else 0,
        }

    @staticmethod
    @with_retry()
    def update(customer_id: str, **kwargs) -> dict | None:
        """Update a customer."""
        db = get_db()
        result = db.table("customers").update(kwargs).eq("id", customer_id).execute()
        return result.data[0] if result and result.data else None

    @staticmethod
    @with_retry()
    def delete(customer_id: str) -> bool:
        """Delete a customer."""
        db = get_db()
        result = db.table("customers").delete().eq("id", customer_id).execute()
        return bool(result and result.data and len(result.data) > 0)
