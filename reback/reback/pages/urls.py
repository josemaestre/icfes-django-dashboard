from django.urls import path
from pages.views import (root_page_view, dynamic_pages_view, landing_page_view)

app_name = 'pages'

urlpatterns = [
    path('landing/', landing_page_view, name="landing"),
    path('', root_page_view, name="dashboard"),
    path('<str:template_name>/', dynamic_pages_view, name='dynamic_pages')
]
