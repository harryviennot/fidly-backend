import json
import hashlib
import zipfile
import os
import io
import subprocess
import tempfile
from pathlib import Path


class PassGenerator:
    def __init__(
        self,
        team_id: str,
        pass_type_id: str,
        cert_path: str,
        key_path: str,
        wwdr_path: str,
        base_url: str,
        business_name: str = "Coffee Shop",
        cert_password: str | None = None,
    ):
        self.team_id = team_id
        self.pass_type_id = pass_type_id
        self.base_url = base_url.rstrip("/")
        self.business_name = business_name
        self.cert_path = cert_path
        self.key_path = key_path
        self.wwdr_path = wwdr_path
        self.cert_password = cert_password

        # Pass assets directory
        self.assets_dir = Path(__file__).parent / "pass_assets"

    def _create_pass_json(self, customer_id: str, name: str, stamps: int, auth_token: str) -> dict:
        """Create the pass.json content."""
        return {
            "formatVersion": 1,
            "passTypeIdentifier": self.pass_type_id,
            "teamIdentifier": self.team_id,
            "serialNumber": customer_id,
            "authenticationToken": auth_token,
            "webServiceURL": f"{self.base_url}/wallet",
            "organizationName": self.business_name,
            "description": f"{self.business_name} Loyalty Card",
            "logoText": self.business_name,
            "foregroundColor": "rgb(255, 255, 255)",
            "backgroundColor": "rgb(139, 90, 43)",
            "labelColor": "rgb(255, 255, 255)",
            "storeCard": {
                "headerFields": [
                    {
                        "key": "stamps",
                        "label": "STAMPS",
                        "value": f"{stamps} / 10"
                    }
                ],
                "primaryFields": [
                    {
                        "key": "name",
                        "label": "MEMBER",
                        "value": name
                    }
                ],
                "secondaryFields": [
                    {
                        "key": "reward",
                        "label": "REWARD",
                        "value": "Free Coffee at 10 stamps!"
                    }
                ],
                "auxiliaryFields": [
                    {
                        "key": "level",
                        "label": "STATUS",
                        "value": "Bronze" if stamps < 5 else ("Silver" if stamps < 10 else "Gold")
                    }
                ],
                "backFields": [
                    {
                        "key": "terms",
                        "label": "Terms & Conditions",
                        "value": "Earn 1 stamp per purchase. Collect 10 stamps for a free coffee. Stamps expire after 1 year."
                    },
                    {
                        "key": "website",
                        "label": "Website",
                        "value": self.base_url
                    }
                ]
            },
            "barcode": {
                "message": customer_id,
                "format": "PKBarcodeFormatQR",
                "messageEncoding": "iso-8859-1"
            },
            "barcodes": [
                {
                    "message": customer_id,
                    "format": "PKBarcodeFormatQR",
                    "messageEncoding": "iso-8859-1"
                }
            ]
        }

    def _create_manifest(self, files: dict[str, bytes]) -> bytes:
        """Create manifest.json with SHA-1 hashes of all files."""
        manifest = {}
        for filename, content in files.items():
            manifest[filename] = hashlib.sha1(content).hexdigest()
        return json.dumps(manifest).encode("utf-8")

    def _sign_manifest_openssl(self, manifest_data: bytes) -> bytes:
        """Create PKCS#7 detached signature using OpenSSL CLI."""
        with tempfile.TemporaryDirectory() as tmpdir:
            manifest_path = os.path.join(tmpdir, "manifest.json")
            signature_path = os.path.join(tmpdir, "signature")

            # Write manifest to temp file
            with open(manifest_path, "wb") as f:
                f.write(manifest_data)

            # Build openssl command
            cmd = [
                "openssl", "smime", "-sign",
                "-signer", self.cert_path,
                "-inkey", self.key_path,
                "-certfile", self.wwdr_path,
                "-in", manifest_path,
                "-out", signature_path,
                "-outform", "DER",
                "-binary",
            ]

            # Add password if provided
            if self.cert_password:
                cmd.extend(["-passin", f"pass:{self.cert_password}"])

            # Run openssl
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode != 0:
                raise RuntimeError(f"OpenSSL signing failed: {result.stderr}")

            # Read signature
            with open(signature_path, "rb") as f:
                return f.read()

    def _get_asset_files(self) -> dict[str, bytes]:
        """Load all pass asset images."""
        files = {}
        asset_files = [
            "icon.png",
            "icon@2x.png",
            "icon@3x.png",
            "logo.png",
            "logo@2x.png",
        ]

        for filename in asset_files:
            filepath = self.assets_dir / filename
            if filepath.exists():
                with open(filepath, "rb") as f:
                    files[filename] = f.read()

        return files

    def generate_pass(self, customer_id: str, name: str, stamps: int, auth_token: str) -> bytes:
        """Generate a complete .pkpass file."""
        # Start with asset files
        files = self._get_asset_files()

        # Add pass.json
        pass_json = self._create_pass_json(customer_id, name, stamps, auth_token)
        files["pass.json"] = json.dumps(pass_json).encode("utf-8")

        # Create manifest
        manifest_data = self._create_manifest(files)
        files["manifest.json"] = manifest_data

        # Sign manifest using OpenSSL
        signature = self._sign_manifest_openssl(manifest_data)
        files["signature"] = signature

        # Create ZIP file
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
            for filename, content in files.items():
                zf.writestr(filename, content)

        return buffer.getvalue()


def create_pass_generator() -> PassGenerator:
    """Factory function to create PassGenerator from environment variables."""
    from dotenv import load_dotenv
    load_dotenv()

    return PassGenerator(
        team_id=os.getenv("APPLE_TEAM_ID", ""),
        pass_type_id=os.getenv("APPLE_PASS_TYPE_ID", ""),
        cert_path=os.getenv("CERT_PATH", "certs/signerCert.pem"),
        key_path=os.getenv("KEY_PATH", "certs/signerKey.pem"),
        wwdr_path=os.getenv("WWDR_PATH", "certs/wwdr.pem"),
        base_url=os.getenv("BASE_URL", "https://762bfadc669f.ngrok-free.app"),
        business_name=os.getenv("BUSINESS_NAME", "Coffee Shop"),
        cert_password=os.getenv("CERT_PASSWORD") or None,
    )
