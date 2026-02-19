from django.urls import path

from .views import user_detail_view
from .views import user_redirect_view
from .views import user_update_view
from .views import user_management_list_view
from .views import user_management_update_view

app_name = "users"
urlpatterns = [
    path("~redirect/", view=user_redirect_view, name="redirect"),
    path("~update/", view=user_update_view, name="update"),
    path("management/", view=user_management_list_view, name="management_list"),
    path("management/<int:pk>/", view=user_management_update_view, name="management_update"),
    path("<int:pk>/", view=user_detail_view, name="detail"),
]
