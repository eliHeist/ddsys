from django.urls import path, include

# Every domain app is listed here only: this feeds INSTALLED_APPS (getAppNames) and the URLs (getAppUrls).
app_configs = [
	{ 'app_name': 'accounts', 'url': 'app/accounts/', 'namespace': 'accounts' },

	{ 'app_name': 'apps.core', 'url': 'app/settings/', 'namespace': 'core' },

	{ 'app_name': 'apps.reports', 'url': 'app/', 'namespace': 'reports' },

	{ 'app_name': 'apps.clients', 'url': 'app/clients/', 'namespace': 'clients' },

	{ 'app_name': 'apps.projects', 'url': 'app/projects/', 'namespace': 'projects' },

	{ 'app_name': 'apps.billing', 'url': 'app/billing/', 'namespace': 'billing' },

	{ 'app_name': 'apps.finance', 'url': 'app/finance/', 'namespace': 'finance' },

	{ 'app_name': 'apps.documents', 'url': 'app/documents/', 'namespace': 'documents' },
]


def getAppUrls():
    urlpatterns = []
    for config in app_configs:
        if config['url']:
            urlpatterns.append(
                path(f"{config['url']}", include(f"{config['app_name']}.urls", namespace=config['namespace']))
            )
    return urlpatterns


def getAppNames():
    return [config['app_name'] for config in app_configs]
