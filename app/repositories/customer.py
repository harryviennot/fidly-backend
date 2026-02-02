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
        """Get a customer by ID."""
        db = get_db()
        result = db.table("customers").select("*").eq("id", customer_id).limit(1).execute()
        return result.data[0] if result and result.data else None

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
        """Add a stamp to a customer. Returns the new stamp count."""
        db = get_db()
        # Get current stamps
        customer = db.table("customers").select("stamps").eq("id", customer_id).limit(1).execute()
        if not customer or not customer.data:
            raise ValueError("Customer not found")

        current_stamps = customer.data[0]["stamps"]
        new_stamps = min(current_stamps + 1, max_stamps)

        # Update stamps and updated_at to trigger pass refresh
        db.table("customers").update({
            "stamps": new_stamps,
            "updated_at": "now()"
        }).eq("id", customer_id).execute()

        return new_stamps

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
