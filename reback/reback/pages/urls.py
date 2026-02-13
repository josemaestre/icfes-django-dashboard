from django.urls import path
from django.shortcuts import render
from .views import (
    dynamic_pages_view,
    home_redirect_view,
    landing_page_view,
    root_page_view,
)


app_name = 'pages'

urlpatterns = [
    path('landing/', landing_page_view, name="landing"),
    path('pricing/', lambda request: render(request, 'pages/pricing.html'), name="pricing"),
    path('', home_redirect_view, name="home"),
    path('dashboard/', root_page_view, name="dashboard"),
    path('app/', root_page_view, name="app"),
    path('<str:template_name>/', dynamic_pages_view, name='dynamic_pages')
]
