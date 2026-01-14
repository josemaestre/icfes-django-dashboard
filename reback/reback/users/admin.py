from allauth.account.decorators import secure_admin_login
from django.conf import settings
from django.contrib import admin
from django.contrib.auth import admin as auth_admin
from django.utils.translation import gettext_lazy as _

from .forms import UserAdminChangeForm
from .forms import UserAdminCreationForm
from .models import User
from .subscription_models import SubscriptionPlan, UserSubscription, QueryLog

if settings.DJANGO_ADMIN_FORCE_ALLAUTH:
    # Force the `admin` sign in process to go through the `django-allauth` workflow:
    # https://docs.allauth.org/en/latest/common/admin.html#admin
    admin.autodiscover()
    admin.site.login = secure_admin_login(admin.site.login)  # type: ignore[method-assign]


@admin.register(User)
class UserAdmin(auth_admin.UserAdmin):
    form = UserAdminChangeForm
    add_form = UserAdminCreationForm
    fieldsets = (
        (None, {"fields": ("email", "password")}),
        (_("Personal info"), {"fields": ("name",)}),
        (
            _("Permissions"),
            {
                "fields": (
                    "is_active",
                    "is_staff",
                    "is_superuser",
                    "groups",
                    "user_permissions",
                ),
            },
        ),
        (_("Important dates"), {"fields": ("last_login", "date_joined")}),
    )
    list_display = ["email", "name", "is_superuser"]
    search_fields = ["name"]
    ordering = ["id"]
    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": ("email", "password1", "password2"),
            },
        ),
    )


@admin.register(SubscriptionPlan)
class SubscriptionPlanAdmin(admin.ModelAdmin):
    list_display = [
        "name", "tier", "price_monthly", "max_queries_per_day",
        "access_schools", "is_active"
    ]
    list_filter = ["tier", "is_active", "api_access"]
    search_fields = ["name", "description"]
    ordering = ["price_monthly"]
    
    fieldsets = (
        ("Basic Information", {
            "fields": ("tier", "name", "description", "price_monthly", "is_active")
        }),
        ("Usage Limits", {
            "fields": ("max_queries_per_day", "max_export_rows", "years_of_data")
        }),
        ("API Access", {
            "fields": ("api_access", "api_rate_limit")
        }),
        ("Geographic Access", {
            "fields": (
                "access_regions", "access_departments",
                "access_municipalities", "access_schools"
            )
        }),
        ("Export Permissions", {
            "fields": ("export_csv", "export_excel", "export_pdf")
        }),
    )


@admin.register(UserSubscription)
class UserSubscriptionAdmin(admin.ModelAdmin):
    list_display = [
        "user", "plan", "is_active", "queries_today",
        "get_remaining_queries", "start_date"
    ]
    list_filter = ["plan", "is_active", "start_date"]
    search_fields = ["user__email", "user__name"]
    readonly_fields = ["created_at", "updated_at", "queries_today", "last_query_date"]
    
    fieldsets = (
        ("Subscription", {
            "fields": ("user", "plan", "is_active")
        }),
        ("Dates", {
            "fields": ("start_date", "end_date", "created_at", "updated_at")
        }),
        ("Usage Tracking", {
            "fields": ("queries_today", "last_query_date")
        }),
        ("Payment Info", {
            "fields": ("stripe_customer_id", "stripe_subscription_id"),
            "classes": ("collapse",)
        }),
    )
    
    def get_remaining_queries(self, obj):
        return obj.get_remaining_queries()
    get_remaining_queries.short_description = "Remaining Queries Today"


@admin.register(QueryLog)
class QueryLogAdmin(admin.ModelAdmin):
    list_display = [
        "user", "endpoint", "timestamp", "response_time_ms", "status_code"
    ]
    list_filter = ["endpoint", "status_code", "timestamp"]
    search_fields = ["user__email", "endpoint"]
    readonly_fields = ["user", "endpoint", "timestamp", "query_params", "response_time_ms", "status_code"]
    date_hierarchy = "timestamp"
    
    def has_add_permission(self, request):
        # Query logs are created automatically, not manually
        return False
