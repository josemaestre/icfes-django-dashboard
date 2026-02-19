from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.messages.views import SuccessMessageMixin
from django.urls import reverse
from django.utils.translation import gettext_lazy as _
from django.views.generic import DetailView, ListView
from django.views.generic import RedirectView
from django.views.generic import UpdateView
from django.contrib.auth.mixins import UserPassesTestMixin
from .forms import UserManagementForm

from reback.users.models import User


class UserDetailView(LoginRequiredMixin, DetailView):
    model = User
    slug_field = "id"
    slug_url_kwarg = "id"


user_detail_view = UserDetailView.as_view()


class UserUpdateView(LoginRequiredMixin, SuccessMessageMixin, UpdateView):
    model = User
    fields = ["name"]
    success_message = _("Information successfully updated")

    def get_success_url(self):
        # for mypy to know that the user is authenticated
        assert self.request.user.is_authenticated
        return self.request.user.get_absolute_url()

    def get_object(self):
        return self.request.user


user_update_view = UserUpdateView.as_view()


class UserRedirectView(LoginRequiredMixin, RedirectView):
    permanent = False

    def get_redirect_url(self):
        return "/dashboard-icfes/"


user_redirect_view = UserRedirectView.as_view()


class SuperUserRequiredMixin(UserPassesTestMixin):
    def test_func(self):
        return self.request.user.is_superuser


class UserManagementListView(SuperUserRequiredMixin, ListView):
    model = User
    template_name = "users/management_list.html"
    context_object_name = "users_list"
    ordering = ['-date_joined']
    paginate_by = 20


class UserManagementUpdateView(SuperUserRequiredMixin, SuccessMessageMixin, UpdateView):
    model = User
    form_class = UserManagementForm
    template_name = "users/management_form.html"
    success_message = _("User details successfully updated")

    def get_success_url(self):
        return reverse("users:management_list")

user_management_list_view = UserManagementListView.as_view()
user_management_update_view = UserManagementUpdateView.as_view()
