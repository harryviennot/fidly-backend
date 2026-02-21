from database.connection import get_db, with_retry


class EnrollmentRepository:

    @staticmethod
    @with_retry()
    def create(
        customer_id: str,
        program_id: str,
        progress: dict | None = None,
        status: str = "active",
    ) -> dict | None:
        db = get_db()
        data = {
            "customer_id": customer_id,
            "program_id": program_id,
            "progress": progress or {"stamps": 0},
            "status": status,
        }
        result = db.table("enrollments").insert(data).execute()
        return result.data[0] if result and result.data else None

    @staticmethod
    @with_retry()
    def get_by_id(enrollment_id: str) -> dict | None:
        db = get_db()
        result = db.table("enrollments").select("*").eq("id", enrollment_id).limit(1).execute()
        return result.data[0] if result and result.data else None

    @staticmethod
    @with_retry()
    def get_by_customer_and_program(customer_id: str, program_id: str) -> dict | None:
        db = get_db()
        result = (
            db.table("enrollments")
            .select("*")
            .eq("customer_id", customer_id)
            .eq("program_id", program_id)
            .limit(1)
            .execute()
        )
        return result.data[0] if result and result.data else None

    @staticmethod
    @with_retry()
    def get_or_create(customer_id: str, program_id: str, program_type: str = "stamp") -> dict:
        """Get existing enrollment or create a new one."""
        existing = EnrollmentRepository.get_by_customer_and_program(customer_id, program_id)
        if existing:
            return existing

        initial_progress = {"stamps": 0}
        if program_type == "points":
            initial_progress = {"points": 0, "lifetime_points": 0}
        elif program_type == "tiered":
            initial_progress = {"points": 0, "lifetime_points": 0, "current_tier": "Bronze"}

        result = EnrollmentRepository.create(
            customer_id=customer_id,
            program_id=program_id,
            progress=initial_progress,
        )
        if not result:
            # Race condition - another request created it
            return EnrollmentRepository.get_by_customer_and_program(customer_id, program_id)
        return result

    @staticmethod
    @with_retry()
    def get_customer_enrollments(customer_id: str) -> list[dict]:
        db = get_db()
        result = (
            db.table("enrollments")
            .select("*")
            .eq("customer_id", customer_id)
            .order("enrolled_at")
            .execute()
        )
        return result.data if result and result.data else []

    @staticmethod
    @with_retry()
    def get_program_enrollments(program_id: str, status: str | None = None) -> list[dict]:
        db = get_db()
        query = db.table("enrollments").select("*").eq("program_id", program_id)
        if status:
            query = query.eq("status", status)
        result = query.order("enrolled_at").execute()
        return result.data if result and result.data else []

    @staticmethod
    @with_retry()
    def update_progress(
        enrollment_id: str,
        progress: dict,
        last_activity_at: str = "now()",
    ) -> dict | None:
        db = get_db()
        result = (
            db.table("enrollments")
            .update({
                "progress": progress,
                "last_activity_at": last_activity_at,
            })
            .eq("id", enrollment_id)
            .execute()
        )
        return result.data[0] if result and result.data else None

    @staticmethod
    @with_retry()
    def increment_redemptions(enrollment_id: str) -> dict | None:
        """Increment total_redemptions and update last_activity_at."""
        db = get_db()
        # Fetch current value first
        enrollment = EnrollmentRepository.get_by_id(enrollment_id)
        if not enrollment:
            return None
        new_count = enrollment.get("total_redemptions", 0) + 1
        result = (
            db.table("enrollments")
            .update({
                "total_redemptions": new_count,
                "last_activity_at": "now()",
            })
            .eq("id", enrollment_id)
            .execute()
        )
        return result.data[0] if result and result.data else None

    @staticmethod
    @with_retry()
    def void_stamp(enrollment_id: str) -> int:
        """Decrement stamps by 1 atomically (min 0). Returns new stamp count."""
        db = get_db()
        result = db.rpc("decrement_enrollment_stamps", {
            "p_enrollment_id": enrollment_id,
        }).execute()
        if not result or result.data is None:
            raise ValueError("Enrollment not found")
        return result.data

    @staticmethod
    @with_retry()
    def update_status(enrollment_id: str, status: str) -> dict | None:
        db = get_db()
        result = (
            db.table("enrollments")
            .update({"status": status})
            .eq("id", enrollment_id)
            .execute()
        )
        return result.data[0] if result and result.data else None
