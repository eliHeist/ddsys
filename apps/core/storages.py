from azure.core.exceptions import ResourceNotFoundError
from django.contrib.staticfiles.storage import ManifestFilesMixin
from storages.backends.azure_storage import AzureStorage


class AzureStaticStorage(ManifestFilesMixin, AzureStorage):
    """Static files in a public Azure Blob container, with hashed names (index.3f2a9c.css) so browsers can cache
    them for good and still get a new file after each deploy. `collectstatic` uploads them (entrypoint.sh)."""

    def read_manifest(self):
        # On the first deploy there is no manifest yet; Azure says so with its own error, not FileNotFoundError.
        try:
            return super().read_manifest()
        except ResourceNotFoundError:
            return None
