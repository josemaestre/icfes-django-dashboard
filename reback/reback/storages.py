"""Custom static file storage backends."""
from whitenoise.storage import CompressedManifestStaticFilesStorage


class LenientManifestStorage(CompressedManifestStaticFilesStorage):
    """
    CompressedManifestStaticFilesStorage that never raises ValueError for files
    missing from the manifest.  Returns the original (unhashed) path instead,
    so a missing entry causes a cache-miss rather than a 500 error.
    """
    manifest_strict = False
