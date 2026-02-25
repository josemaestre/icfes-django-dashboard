"""Custom static file storage backends."""
from django.core.exceptions import SuspiciousFileOperation
from whitenoise.storage import CompressedManifestStaticFilesStorage


class LenientManifestStorage(CompressedManifestStaticFilesStorage):
    """
    CompressedManifestStaticFilesStorage that never raises for files missing
    from the manifest, missing from disk, or referenced with an absolute path.

    Django 5 behaviour when manifest_strict=False:
      stored_name() → not in manifest → calls hashed_name(name)
      hashed_name(name) → tries to open file from STATIC_ROOT → raises ValueError
                          if file doesn't exist on disk.

    Additionally, theme templates sometimes use {% static '/images/...' %} with
    a leading slash. Django's safe_join() raises SuspiciousFileOperation for
    those absolute-looking paths. We strip the leading slash before lookup so
    those paths resolve normally instead of causing a 400 response.
    """
    manifest_strict = False

    def stored_name(self, name):
        # Strip leading slash to avoid SuspiciousFileOperation from safe_join.
        name = name.lstrip("/")
        try:
            return super().stored_name(name)
        except (ValueError, SuspiciousFileOperation):
            # File not in manifest, not found on disk, or unsafe path —
            # return unhashed path so the page renders (possibly with a 404
            # for the asset, but not a 400 for the whole page).
            return name
