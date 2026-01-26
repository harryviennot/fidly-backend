import json
from database.connection import get_db


class CardDesignRepository:

    @staticmethod
    async def create(
        design_id: str,
        name: str,
        organization_name: str,
        description: str,
        logo_text: str | None = None,
        foreground_color: str = "rgb(255, 255, 255)",
        background_color: str = "rgb(139, 90, 43)",
        label_color: str = "rgb(255, 255, 255)",
        total_stamps: int = 10,
        stamp_filled_color: str = "rgb(255, 215, 0)",
        stamp_empty_color: str = "rgb(80, 50, 20)",
        stamp_border_color: str = "rgb(255, 255, 255)",
        secondary_fields: list | None = None,
        auxiliary_fields: list | None = None,
        back_fields: list | None = None,
    ) -> dict:
        """Create a new card design."""
        async with get_db() as db:
            await db.execute(
                """INSERT INTO card_designs (
                    id, name, organization_name, description, logo_text,
                    foreground_color, background_color, label_color,
                    total_stamps, stamp_filled_color, stamp_empty_color, stamp_border_color,
                    secondary_fields, auxiliary_fields, back_fields
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    design_id,
                    name,
                    organization_name,
                    description,
                    logo_text,
                    foreground_color,
                    background_color,
                    label_color,
                    total_stamps,
                    stamp_filled_color,
                    stamp_empty_color,
                    stamp_border_color,
                    json.dumps(secondary_fields or []),
                    json.dumps(auxiliary_fields or []),
                    json.dumps(back_fields or []),
                )
            )
            await db.commit()
            return await CardDesignRepository.get_by_id(design_id)

    @staticmethod
    async def get_by_id(design_id: str) -> dict | None:
        """Get a card design by ID."""
        async with get_db() as db:
            cursor = await db.execute(
                """SELECT id, name, is_active, organization_name, description, logo_text,
                    foreground_color, background_color, label_color,
                    total_stamps, stamp_filled_color, stamp_empty_color, stamp_border_color,
                    logo_path, custom_filled_stamp_path, custom_empty_stamp_path,
                    secondary_fields, auxiliary_fields, back_fields,
                    created_at, updated_at
                FROM card_designs WHERE id = ?""",
                (design_id,)
            )
            row = await cursor.fetchone()
            if row:
                return CardDesignRepository._row_to_dict(row)
            return None

    @staticmethod
    async def get_active() -> dict | None:
        """Get the currently active card design."""
        async with get_db() as db:
            cursor = await db.execute(
                """SELECT id, name, is_active, organization_name, description, logo_text,
                    foreground_color, background_color, label_color,
                    total_stamps, stamp_filled_color, stamp_empty_color, stamp_border_color,
                    logo_path, custom_filled_stamp_path, custom_empty_stamp_path,
                    secondary_fields, auxiliary_fields, back_fields,
                    created_at, updated_at
                FROM card_designs WHERE is_active = 1"""
            )
            row = await cursor.fetchone()
            if row:
                return CardDesignRepository._row_to_dict(row)
            return None

    @staticmethod
    async def get_all() -> list[dict]:
        """Get all card designs ordered by creation date."""
        async with get_db() as db:
            cursor = await db.execute(
                """SELECT id, name, is_active, organization_name, description, logo_text,
                    foreground_color, background_color, label_color,
                    total_stamps, stamp_filled_color, stamp_empty_color, stamp_border_color,
                    logo_path, custom_filled_stamp_path, custom_empty_stamp_path,
                    secondary_fields, auxiliary_fields, back_fields,
                    created_at, updated_at
                FROM card_designs ORDER BY created_at DESC"""
            )
            rows = await cursor.fetchall()
            return [CardDesignRepository._row_to_dict(row) for row in rows]

    @staticmethod
    async def update(design_id: str, **kwargs) -> dict | None:
        """Update a card design. Only updates provided fields."""
        if not kwargs:
            return await CardDesignRepository.get_by_id(design_id)

        # Handle JSON fields
        json_fields = ['secondary_fields', 'auxiliary_fields', 'back_fields']
        for field in json_fields:
            if field in kwargs and isinstance(kwargs[field], list):
                kwargs[field] = json.dumps(kwargs[field])

        # Build update query
        set_clauses = [f"{key} = ?" for key in kwargs.keys()]
        set_clauses.append("updated_at = CURRENT_TIMESTAMP")
        values = list(kwargs.values()) + [design_id]

        async with get_db() as db:
            await db.execute(
                f"UPDATE card_designs SET {', '.join(set_clauses)} WHERE id = ?",
                values
            )
            await db.commit()
            return await CardDesignRepository.get_by_id(design_id)

    @staticmethod
    async def delete(design_id: str) -> bool:
        """Delete a card design. Returns True if deleted."""
        async with get_db() as db:
            cursor = await db.execute(
                "DELETE FROM card_designs WHERE id = ?",
                (design_id,)
            )
            await db.commit()
            return cursor.rowcount > 0

    @staticmethod
    async def set_active(design_id: str) -> dict | None:
        """Set a design as active, deactivating all others."""
        async with get_db() as db:
            # Deactivate all designs
            await db.execute("UPDATE card_designs SET is_active = 0")
            # Activate the specified design
            await db.execute(
                "UPDATE card_designs SET is_active = 1, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                (design_id,)
            )
            await db.commit()
            return await CardDesignRepository.get_by_id(design_id)

    @staticmethod
    def _row_to_dict(row) -> dict:
        """Convert a database row to a dictionary with parsed JSON fields."""
        data = dict(row)
        # Parse JSON fields
        for field in ['secondary_fields', 'auxiliary_fields', 'back_fields']:
            if data.get(field):
                try:
                    data[field] = json.loads(data[field])
                except (json.JSONDecodeError, TypeError):
                    data[field] = []
            else:
                data[field] = []
        # Convert is_active to boolean
        data['is_active'] = bool(data.get('is_active'))
        return data
