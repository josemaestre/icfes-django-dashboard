
from typing import ClassVar

from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.core.validators import MinValueValidator, MaxValueValidator
from django.db import models
from django.db.models import CharField, EmailField, IntegerField
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
    # first_name and last_name are redefined below as CharField
    # first_name = None  # type: ignore[assignment]
    # last_name = None  # type: ignore[assignment]
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
    
    GENDER_CHOICES = [
        ('M', 'Masculino'),
        ('F', 'Femenino'),
        ('O', 'Otro'),
        ('N', 'Prefiero no decir'),
    ]
    
    # User Type & Organization
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
        verbose_name="Nombre de Organización",
        help_text="Nombre de tu institución o empresa (opcional)"
    )
    
    # Personal Information
    first_name = CharField(
        max_length=100,
        blank=True,
        verbose_name="Nombre(s)"
    )
    
    last_name = CharField(
        max_length=100,
        blank=True,
        verbose_name="Apellido(s)"
    )
    
    gender = CharField(
        max_length=1,
        choices=GENDER_CHOICES,
        blank=True,
        verbose_name="Sexo"
    )
    
    birth_year = IntegerField(
        null=True,
        blank=True,
        validators=[
            MinValueValidator(1940),
            MaxValueValidator(2015)
        ],
        verbose_name="Año de Nacimiento"
    )
    
    phone = CharField(
        max_length=20,
        blank=True,
        verbose_name="Teléfono/Celular"
    )
    
    # Geographic Location
    department = CharField(
        max_length=100,
        blank=True,
        verbose_name="Departamento"
    )
    
    municipality = CharField(
        max_length=100,
        blank=True,
        verbose_name="Municipio"
    )
    
    # School Affiliation (for principals/teachers)
    school_code = CharField(
        max_length=20,
        blank=True,
        verbose_name="Código DANE",
        help_text="Código DANE del colegio"
    )
    
    school_name = CharField(
        max_length=255,
        blank=True,
        verbose_name="Nombre del Colegio"
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


class InvitacionEmail(models.Model):
    TIPO_CHOICES = [
        ('rector',        'Rector / Director de colegio'),
        ('supervisor',    'Supervisor / Secretaría de Educación'),
        ('institucional', 'Institucional / Ministerio / Entidad gubernamental'),
        ('padre',         'Padre de Familia'),
        ('conocido',      'Conocido Personal'),
    ]

    email               = models.EmailField()
    nombre_destinatario = models.CharField(max_length=200, blank=True)
    tipo                = models.CharField(max_length=20, choices=TIPO_CHOICES)
    colegio_nombre      = models.CharField(
        max_length=300, blank=True,
        help_text="Para rector/padre: personaliza el email con el nombre del colegio",
    )
    enviado_por         = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='invitaciones',
    )
    fecha_envio         = models.DateTimeField(auto_now_add=True)
    estado              = models.CharField(max_length=20, default='enviado')
    error_msg           = models.TextField(blank=True)

    class Meta:
        ordering = ['-fecha_envio']
        verbose_name = 'Invitación Email'
        verbose_name_plural = 'Invitaciones Email'

    def __str__(self):
        return f"{self.get_tipo_display()} → {self.email} ({self.fecha_envio:%d/%m/%Y})"
