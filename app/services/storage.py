"""
Supabase Storage service for file uploads.
"""

from typing import Optional
import uuid

from database.supabase_client import get_supabase_client


class StorageService:
    """Service for managing file uploads to Supabase Storage."""

    ONBOARDING_BUCKET = "onboarding"
    BUSINESSES_BUCKET = "businesses"
    PROFILES_BUCKET = "profiles"

    def __init__(self):
        self.supabase = get_supabase_client()

    def upload_file(
        self,
        bucket: str,
        path: str,
        file_data: bytes,
        content_type: str = "image/png",
    ) -> str:
        """
        Upload a file to Supabase Storage.

        Args:
            bucket: The storage bucket name
            path: The file path within the bucket (e.g., "{user_id}/logo.png")
            file_data: The file content as bytes
            content_type: The MIME type of the file

        Returns:
            The public URL of the uploaded file
        """
        # Upload file to Supabase Storage
        response = self.supabase.storage.from_(bucket).upload(
            path=path,
            file=file_data,
            file_options={"content-type": content_type, "upsert": "true"},
        )

        # Get public URL
        return self.get_public_url(bucket, path)

    def delete_file(self, bucket: str, path: str) -> bool:
        """
        Delete a file from Supabase Storage.

        Args:
            bucket: The storage bucket name
            path: The file path within the bucket

        Returns:
            True if deletion was successful
        """
        try:
            self.supabase.storage.from_(bucket).remove([path])
            return True
        except Exception:
            return False

    def get_public_url(self, bucket: str, path: str) -> str:
        """
        Get the public URL for a file in Supabase Storage.

        Args:
            bucket: The storage bucket name
            path: The file path within the bucket

        Returns:
            The public URL of the file
        """
        response = self.supabase.storage.from_(bucket).get_public_url(path)
        return response

    def upload_onboarding_logo(self, user_id: str, file_data: bytes) -> str:
        """
        Upload a logo image for onboarding.

        Args:
            user_id: The user's ID
            file_data: The PNG image data

        Returns:
            The public URL of the uploaded logo
        """
        path = f"{user_id}/logo.png"
        return self.upload_file(
            bucket=self.ONBOARDING_BUCKET,
            path=path,
            file_data=file_data,
            content_type="image/png",
        )

    def delete_onboarding_logo(self, user_id: str) -> bool:
        """
        Delete a user's onboarding logo.

        Args:
            user_id: The user's ID

        Returns:
            True if deletion was successful
        """
        path = f"{user_id}/logo.png"
        return self.delete_file(bucket=self.ONBOARDING_BUCKET, path=path)

    def download_file(self, bucket: str, path: str) -> bytes | None:
        """
        Download a file from Supabase Storage.

        Args:
            bucket: The storage bucket name
            path: The file path within the bucket

        Returns:
            The file content as bytes, or None if download failed
        """
        try:
            response = self.supabase.storage.from_(bucket).download(path)
            return response
        except Exception:
            return None

    def upload_business_logo(self, business_id: str, file_data: bytes) -> str:
        """
        Upload a logo image for a business.

        Args:
            business_id: The business's ID
            file_data: The PNG image data

        Returns:
            The public URL of the uploaded logo
        """
        path = f"{business_id}/logo.png"
        return self.upload_file(
            bucket=self.BUSINESSES_BUCKET,
            path=path,
            file_data=file_data,
            content_type="image/png",
        )

    def copy_onboarding_logo_to_business(
        self, user_id: str, business_id: str
    ) -> str | None:
        """
        Copy a logo from the onboarding bucket to the businesses bucket.

        Args:
            user_id: The user's auth ID (used in onboarding path)
            business_id: The business's ID

        Returns:
            The public URL of the new logo, or None if copy failed
        """
        # Download from onboarding bucket
        onboarding_path = f"{user_id}/logo.png"
        file_data = self.download_file(self.ONBOARDING_BUCKET, onboarding_path)

        if not file_data:
            return None

        # Upload to businesses bucket
        return self.upload_business_logo(business_id, file_data)

    def upload_base64_logo_to_business(
        self, base64_data: str, business_id: str
    ) -> str | None:
        """
        Upload a base64 encoded logo directly to the businesses bucket.

        Args:
            base64_data: The base64 data URL (e.g., "data:image/png;base64,...")
            business_id: The business's ID

        Returns:
            The public URL of the uploaded logo, or None if upload failed
        """
        import base64

        try:
            # Parse base64 data URL
            # Format: data:image/png;base64,<data>
            if "," not in base64_data:
                return None

            _, encoded = base64_data.split(",", 1)
            file_data = base64.b64decode(encoded)

            # Upload to businesses bucket
            return self.upload_business_logo(business_id, file_data)
        except Exception:
            return None


    def upload_profile_picture(
        self, user_id: str, file_data: bytes, content_type: str = "image/png"
    ) -> str:
        """
        Upload a profile picture for a user.

        Args:
            user_id: The user's ID
            file_data: The image data
            content_type: The MIME type of the file

        Returns:
            The public URL of the uploaded profile picture
        """
        ext = "png" if content_type == "image/png" else "jpg"
        path = f"{user_id}/avatar.{ext}"
        return self.upload_file(
            bucket=self.PROFILES_BUCKET,
            path=path,
            file_data=file_data,
            content_type=content_type,
        )

    def delete_profile_picture(self, user_id: str) -> bool:
        """
        Delete a user's profile picture (tries both extensions).

        Args:
            user_id: The user's ID

        Returns:
            True if deletion was successful
        """
        deleted_png = self.delete_file(
            bucket=self.PROFILES_BUCKET, path=f"{user_id}/avatar.png"
        )
        deleted_jpg = self.delete_file(
            bucket=self.PROFILES_BUCKET, path=f"{user_id}/avatar.jpg"
        )
        return deleted_png or deleted_jpg

    # ============================================
    # Card Design Assets
    # ============================================
    # Path structure: {business_id}/cards/{card_id}/{filename}

    def upload_card_logo(
        self, business_id: str, card_id: str, file_data: bytes
    ) -> str:
        """
        Upload a logo image for a card design.

        Args:
            business_id: The business's ID
            card_id: The card design's ID
            file_data: The PNG image data

        Returns:
            The public URL of the uploaded logo
        """
        path = f"{business_id}/cards/{card_id}/logo.png"
        return self.upload_file(
            bucket=self.BUSINESSES_BUCKET,
            path=path,
            file_data=file_data,
            content_type="image/png",
        )

    def upload_card_strip_background(
        self, business_id: str, card_id: str, file_data: bytes
    ) -> str:
        """
        Upload a strip background image for a card design.

        Args:
            business_id: The business's ID
            card_id: The card design's ID
            file_data: The PNG image data

        Returns:
            The public URL of the uploaded strip background
        """
        path = f"{business_id}/cards/{card_id}/strip_bg.png"
        return self.upload_file(
            bucket=self.BUSINESSES_BUCKET,
            path=path,
            file_data=file_data,
            content_type="image/png",
        )

    def delete_card_assets(self, business_id: str, card_id: str) -> bool:
        """
        Delete all assets for a card design.

        Args:
            business_id: The business's ID
            card_id: The card design's ID

        Returns:
            True if any deletion was successful
        """
        deleted_logo = self.delete_file(
            bucket=self.BUSINESSES_BUCKET,
            path=f"{business_id}/cards/{card_id}/logo.png",
        )
        deleted_strip = self.delete_file(
            bucket=self.BUSINESSES_BUCKET,
            path=f"{business_id}/cards/{card_id}/strip_bg.png",
        )
        return deleted_logo or deleted_strip

    def download_card_strip_background(
        self, business_id: str, card_id: str
    ) -> bytes | None:
        """
        Download a card's strip background image.

        Args:
            business_id: The business's ID
            card_id: The card design's ID

        Returns:
            The file content as bytes, or None if download failed
        """
        path = f"{business_id}/cards/{card_id}/strip_bg.png"
        return self.download_file(self.BUSINESSES_BUCKET, path)


# Singleton instance
_storage_service: Optional[StorageService] = None


def get_storage_service() -> StorageService:
    """Get or create the storage service singleton."""
    global _storage_service
    if _storage_service is None:
        _storage_service = StorageService()
    return _storage_service
