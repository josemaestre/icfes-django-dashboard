# ruff: noqa
from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include
from django.urls import path
from django.views import defaults as default_views
from django.views.generic.base import RedirectView
from icfes_dashboard import sitemap_views
from reback import seo_views

home_redirect_view = RedirectView.as_view(url='/', permanent=True)
legacy_icfes_dashboard_redirect = RedirectView.as_view(url='/icfes/', permanent=False)

urlpatterns = [
    # Django Admin, use {% url 'admin:index' %}
    path(settings.ADMIN_URL, admin.site.urls),
    # User management
    path("users/", include("reback.users.urls", namespace="users")),
    path("accounts/", include("allauth.urls")),
    path("landing/", home_redirect_view),  # Redirect /landing/ to /
    path("icfes-dashboard/", legacy_icfes_dashboard_redirect),

    # Favicon — must be before the catch-all pages include to avoid dynamic_pages_view
    path("favicon.ico", seo_views.favicon_view),

    path('icfes/', include('icfes_dashboard.urls')),
    path('payments/', include('reback.users.stripe_urls', namespace='payments')),
    path("", include("reback.pages.urls", namespace="pages")),

    # SEO
    path("robots.txt", seo_views.robots_txt),
    path("BingSiteAuth.xml", seo_views.bing_site_auth),
    path("bingsiteauth.xml", seo_views.bing_site_auth),
    path("sitemap.xml", sitemap_views.sitemap_index),
    path("sitemap-static.xml", sitemap_views.sitemap_static),
    path("sitemap-icfes-<int:page>.xml", sitemap_views.sitemap_icfes),
    path("sitemap-departamentos.xml", sitemap_views.sitemap_departamentos),
    path("sitemap-municipios.xml", sitemap_views.sitemap_municipios),
    path("sitemap-geo.xml", sitemap_views.sitemap_geo),
    path("sitemap-longtail.xml", sitemap_views.sitemap_longtail),
    
    # Your stuff: custom urls includes go here
    # ...
    # Media files
    *static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT),
]

if settings.DEBUG:
    # This allows the error pages to be debugged during development, just visit
    # these url in browser to see how these error pages look like.
    urlpatterns += [
        path(
            "400/",
            default_views.bad_request,
            kwargs={"exception": Exception("Bad Request!")},
        ),
        path(
            "403/",
            default_views.permission_denied,
            kwargs={"exception": Exception("Permission Denied")},
        ),
        path(
            "404/",
            default_views.page_not_found,
            kwargs={"exception": Exception("Page not Found")},
        ),
        path("500/", default_views.server_error),
    ]
    if "debug_toolbar" in settings.INSTALLED_APPS:
        import debug_toolbar

        urlpatterns = [path("__debug__/", include(debug_toolbar.urls))] + urlpatterns
