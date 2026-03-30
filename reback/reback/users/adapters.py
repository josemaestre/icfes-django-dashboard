from __future__ import annotations

import logging
import typing

from allauth.account.adapter import DefaultAccountAdapter
from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from django.conf import settings

if typing.TYPE_CHECKING:
    from allauth.socialaccount.models import SocialLogin
    from django.http import HttpRequest

    from reback.users.models import User

logger = logging.getLogger("auth")


class AccountAdapter(DefaultAccountAdapter):
    def is_open_for_signup(self, request: HttpRequest) -> bool:
        return getattr(settings, "ACCOUNT_ALLOW_REGISTRATION", True)


class SocialAccountAdapter(DefaultSocialAccountAdapter):
    def pre_social_login(self, request: HttpRequest, sociallogin: SocialLogin) -> None:
        """Log Google OAuth attempts — nuevo registro vs login existente."""
        email = ""
        try:
            email = sociallogin.account.extra_data.get("email", "")
        except Exception:
            pass
        action = "LOGIN" if sociallogin.is_existing else "SIGNUP"
        logger.info("Google OAuth %s | email=%s | ip=%s",
                    action, email, request.META.get("REMOTE_ADDR", "-"))

    def is_open_for_signup(
        self,
        request: HttpRequest,
        sociallogin: SocialLogin,
    ) -> bool:
        return getattr(settings, "ACCOUNT_ALLOW_REGISTRATION", True)

    def populate_user(
        self,
        request: HttpRequest,
        sociallogin: SocialLogin,
        data: dict[str, typing.Any],
    ) -> User:
        """
        Populates user information from social provider info.

        Captura nombre completo, first_name y last_name desde Google OAuth.
        See: https://docs.allauth.org/en/latest/socialaccount/advanced.html#creating-and-populating-user-instances
        """
        user = super().populate_user(request, sociallogin, data)

        # Guardar nombre completo en el campo `name`
        if not user.name:
            if name := data.get("name"):
                user.name = name
            elif first_name := data.get("first_name"):
                user.name = first_name
                if last_name := data.get("last_name"):
                    user.name += f" {last_name}"

        # Guardar first_name y last_name desde los campos de Google
        # (given_name / family_name vienen en extra_data de Google)
        extra_data = getattr(sociallogin.account, "extra_data", {}) or {}
        if not user.first_name:
            user.first_name = (
                data.get("first_name")
                or extra_data.get("given_name")
                or ""
            )
        if not user.last_name:
            user.last_name = (
                data.get("last_name")
                or extra_data.get("family_name")
                or ""
            )

        return user
