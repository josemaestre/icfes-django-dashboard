from django.urls import path
from .views import (
    dynamic_pages_view,
    home_redirect_view,
    landing_page_view,
    pricing_view,
    root_page_view,
)


app_name = 'pages'

urlpatterns = [
    path('landing/', home_redirect_view, name="landing_redirect"),
    path('pricing/', pricing_view, name="pricing"),
    path('', landing_page_view, name="home"),
    path('dashboard/', root_page_view, name="dashboard"),
    path('app/', root_page_view, name="app"),
    path('<str:template_name>/', dynamic_pages_view, name='dynamic_pages')
]
