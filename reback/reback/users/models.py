
from typing import ClassVar

from django.contrib.auth.models import AbstractUser
from django.db.models import CharField
from django.db.models import EmailField
from django.urls import reverse
from django.utils.translation import gettext_lazy as _

from .managers import UserManager


class User(AbstractUser):
    """
    Default custom user model for reback.
    If adding fields that need to be filled at user signup,
    check forms.SignupForm and forms.SocialSignupForms accordingly.
    """

    # First and last name do not cover name patterns around the globe
    name = CharField(_("Name of User"), blank=True, max_length=255)
    first_name = None  # type: ignore[assignment]
    last_name = None  # type: ignore[assignment]
    email = EmailField(_("email address"), unique=True)
    username = None  # type: ignore[assignment]
    
    # Stripe integration
    stripe_customer_id = CharField(max_length=255, blank=True, default="")
    
    # User segmentation
    USER_TYPE_CHOICES = [
        ('parent', 'Padre/Tutor de Estudiante'),
        ('principal', 'Rector/Director de Colegio'),
        ('teacher', 'Docente/Coordinador Académico'),
        ('government', 'Entidad Pública Educativa'),
        ('researcher', 'Investigador/Académico'),
        ('preicfes', 'Empresa de Preparación Pre-ICFES'),
        ('language_academy', 'Academia de Idiomas'),
        ('consultant', 'Consultoría Educativa'),
        ('student', 'Estudiante'),
    ]
    
    user_type = CharField(
        max_length=50,
        choices=USER_TYPE_CHOICES,
        blank=True,
        verbose_name="Tipo de Usuario",
        help_text="¿Cómo planeas usar esta plataforma?"
    )
    
    organization_name = CharField(
        max_length=255,
        blank=True,
        verbose_name="Nombre de Institución/Empresa",
        help_text="Opcional, para usuarios institucionales"
    )

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []

    objects: ClassVar[UserManager] = UserManager()

    def get_absolute_url(self) -> str:
        """Get URL for user's detail view.

        Returns:
            str: URL for user detail.

        """
        return reverse("users:detail", kwargs={"pk": self.id})
