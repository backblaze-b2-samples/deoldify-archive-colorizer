from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # --- Backblaze B2 (S3-compatible API) ---
    # Standard #3 env-var names. The S3 endpoint is constructed from the
    # region rather than stored directly, so a single B2_REGION drives the
    # boto3 client. Required at startup (see main.py REQUIRED_B2_SETTINGS);
    # left empty here so no region is hardcoded in source — set it via the
    # B2_REGION env var (e.g. us-west-004). See .env.example.
    b2_region: str = ""
    b2_application_key_id: str = ""
    b2_application_key: str = ""
    b2_bucket_name: str = ""
    # Optional public base URL for object links (e.g. a CDN or the bucket's
    # friendly URL). When empty the UI falls back to presigned URLs.
    b2_public_url_base: str = ""

    api_port: int = 8000
    # Explicit allowlist by default — covers Next on :3000 and the
    # fallback :3001 it picks if 3000 is busy. Production deploys should
    # override with the exact frontend origin.
    api_cors_origins: str = "http://localhost:3000,http://localhost:3001"
    # Optional dev-only escape hatch: a regex that matches additional
    # allowed origins. Empty by default — set this to e.g.
    # `^http://localhost:\d+$` to accept any localhost port without
    # listing each one. NEVER ship this to production.
    api_cors_origin_regex: str = ""

    # Upload limits (archival masters can be large scans / clips)
    max_file_size: int = 500 * 1024 * 1024  # 500MB

    # Archive prefixes — the documented happy-path layout. Ingested B&W
    # masters land under originals; colorized renditions + provenance JSON
    # land under restored/<asset_id>/.
    originals_prefix: str = "archive/originals/"
    restored_prefix: str = "archive/restored/"

    # DeOldify colorization microservice (Docker, native linux/arm64). The
    # legacy fastai-v1/torch-1.11 stack runs there, not in this process. The
    # repo adapter POSTs image bytes to {deoldify_service_url}/colorize.
    deoldify_service_url: str = "http://localhost:8137"

    # Small durable counters (downloads, etc). Point at a persistent
    # volume in production if you care about surviving restarts.
    download_count_file: str = "data/download_count.json"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}

    @property
    def b2_endpoint(self) -> str:
        """S3-compatible endpoint constructed from the configured region.

        Standard #4: no hardcoded region in source — it flows from B2_REGION.
        """
        return f"https://s3.{self.b2_region}.backblazeb2.com"

    @property
    def cors_origins(self) -> list[str]:
        return [o.strip() for o in self.api_cors_origins.split(",")]


settings = Settings()
