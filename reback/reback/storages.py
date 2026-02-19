"""Custom static file storage backends."""
from whitenoise.storage import CompressedManifestStaticFilesStorage


class LenientManifestStorage(CompressedManifestStaticFilesStorage):
    """
    CompressedManifestStaticFilesStorage that never raises ValueError for files
    missing from the manifest or missing from disk.

    Django 5 behaviour when manifest_strict=False:
      stored_name() → not in manifest → calls hashed_name(name)
      hashed_name(name) → tries to open file from STATIC_ROOT → raises ValueError
                          if file doesn't exist on disk.

    We override stored_name() to catch that second ValueError and return
    the original unhashed path instead, so a missing entry causes a plain
    cache-miss (no fingerprinting) rather than a 500 error.
    """
    manifest_strict = False

    def stored_name(self, name):
        try:
            return super().stored_name(name)
        except ValueError:
            # File not in manifest or not found on disk — return unhashed path.
            return name
