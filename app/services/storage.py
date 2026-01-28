"""
Supabase Storage service for file uploads.
"""

from typing import Optional
import uuid

from database.supabase_client import get_supabase_client


class StorageService:
    """Service for managing file uploads to Supabase Storage."""

    ONBOARDING_BUCKET = "onboarding"

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


# Singleton instance
_storage_service: Optional[StorageService] = None


def get_storage_service() -> StorageService:
    """Get or create the storage service singleton."""
    global _storage_service
    if _storage_service is None:
        _storage_service = StorageService()
    return _storage_service
