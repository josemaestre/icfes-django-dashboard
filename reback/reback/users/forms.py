from allauth.account.forms import SignupForm
from allauth.socialaccount.forms import SignupForm as SocialSignupForm
from django.contrib.auth import forms as admin_forms
from django.forms import (EmailField, CharField, ChoiceField, IntegerField,
                          Select, TextInput, NumberInput, HiddenInput)
from django.utils.translation import gettext_lazy as _

from .models import User


class UserAdminChangeForm(admin_forms.UserChangeForm):
    class Meta(admin_forms.UserChangeForm.Meta):  # type: ignore[name-defined]
        model = User
        field_classes = {"email": EmailField}


class UserAdminCreationForm(admin_forms.UserCreationForm):
    """
    Form for User Creation in the Admin Area.
    To change user signup, see UserSignupForm and UserSocialSignupForm.
    """

    class Meta(admin_forms.UserCreationForm.Meta):  # type: ignore[name-defined]
        model = User
        fields = ("email",)
        field_classes = {"email": EmailField}
        error_messages = {
            "email": {"unique": _("This email has already been taken.")},
        }


class UserSignupForm(SignupForm):
    """
    Form that will be rendered on a user sign up section/screen.
    Default fields will be added automatically.
    Check UserSocialSignupForm for accounts created from social.
    """
    
    # Personal Information
    first_name = CharField(
        max_length=100,
        required=True,
        label=_("Nombre(s)"),
        widget=TextInput(attrs={'class': 'form-control', 'placeholder': 'Juan'})
    )
    
    last_name = CharField(
        max_length=100,
        required=True,
        label=_("Apellido(s)"),
        widget=TextInput(attrs={'class': 'form-control', 'placeholder': 'Pérez'})
    )
    
    gender = ChoiceField(
        choices=[('', 'Selecciona...')] + User.GENDER_CHOICES,
        required=False,
        label=_("Sexo"),
        widget=Select(attrs={'class': 'form-select'})
    )
    
    birth_year = IntegerField(
        required=False,
        label=_("Año de Nacimiento"),
        widget=NumberInput(attrs={
            'class': 'form-control',
            'min': 1940,
            'max': 2015,
            'placeholder': '1990'
        })
    )
    
    phone = CharField(
        max_length=20,
        required=False,
        label=_("Teléfono/Celular"),
        widget=TextInput(attrs={
            'class': 'form-control',
            'placeholder': '+57 300 123 4567'
        })
    )
    
    # Geographic Location
    department = CharField(
        max_length=100,
        required=False,
        label=_("Departamento"),
        widget=Select(attrs={'class': 'form-select', 'id': 'id_department'})
    )
    
    municipality = CharField(
        max_length=100,
        required=False,
        label=_("Municipio"),
        widget=Select(attrs={'class': 'form-select', 'id': 'id_municipality'})
    )
    
    # User Type & Organization
    user_type = ChoiceField(
        choices=[('', 'Selecciona...')] + User.USER_TYPE_CHOICES,
        required=False,
        label=_("¿Cómo planeas usar esta plataforma?"),
        widget=Select(attrs={'class': 'form-select', 'id': 'id_user_type'})
    )
    
    organization_name = CharField(
        max_length=255,
        required=False,
        label=_("Nombre de tu Institución/Empresa (opcional)"),
        widget=TextInput(attrs={
            'class': 'form-control',
            'id': 'id_organization_name',
            'placeholder': 'Ej: Colegio San José'
        })
    )
    
    # School Affiliation (hidden, populated by JavaScript)
    school_code = CharField(
        max_length=20,
        required=False,
        widget=HiddenInput(attrs={'id': 'id_school_code'})
    )
    
    school_name = CharField(
        max_length=255,
        required=False,
        widget=HiddenInput(attrs={'id': 'id_school_name'})
    )
    
    def save(self, request):
        user = super().save(request)
        
        # Personal info
        user.first_name = self.cleaned_data.get('first_name', '')
        user.last_name = self.cleaned_data.get('last_name', '')
        user.gender = self.cleaned_data.get('gender', '')
        user.birth_year = self.cleaned_data.get('birth_year')
        user.phone = self.cleaned_data.get('phone', '')
        
        # Geographic
        user.department = self.cleaned_data.get('department', '')
        user.municipality = self.cleaned_data.get('municipality', '')
        
        # User type & organization
        user.user_type = self.cleaned_data.get('user_type', '')
        user.organization_name = self.cleaned_data.get('organization_name', '')
        
        # School affiliation
        user.school_code = self.cleaned_data.get('school_code', '')
        user.school_name = self.cleaned_data.get('school_name', '')
        
        user.save()
        return user


class UserSocialSignupForm(SocialSignupForm):
    """
    Renders the form when user has signed up using social accounts.
    Default fields will be added automatically.
    See UserSignupForm otherwise.
    """
    
    # Personal Information
    first_name = CharField(
        max_length=100,
        required=True,
        label=_("Nombre(s)"),
        widget=TextInput(attrs={'class': 'form-control', 'placeholder': 'Juan'})
    )
    
    last_name = CharField(
        max_length=100,
        required=True,
        label=_("Apellido(s)"),
        widget=TextInput(attrs={'class': 'form-control', 'placeholder': 'Pérez'})
    )
    
    gender = ChoiceField(
        choices=[('', 'Selecciona...')] + User.GENDER_CHOICES,
        required=False,
        label=_("Sexo"),
        widget=Select(attrs={'class': 'form-select'})
    )
    
    birth_year = IntegerField(
        required=False,
        label=_("Año de Nacimiento"),
        widget=NumberInput(attrs={
            'class': 'form-control',
            'min': 1940,
            'max': 2015,
            'placeholder': '1990'
        })
    )
    
    phone = CharField(
        max_length=20,
        required=False,
        label=_("Teléfono/Celular"),
        widget=TextInput(attrs={
            'class': 'form-control',
            'placeholder': '+57 300 123 4567'
        })
    )
    
    # Geographic Location
    department = CharField(
        max_length=100,
        required=False,
        label=_("Departamento"),
        widget=Select(attrs={'class': 'form-select', 'id': 'id_department'})
    )
    
    municipality = CharField(
        max_length=100,
        required=False,
        label=_("Municipio"),
        widget=Select(attrs={'class': 'form-select', 'id': 'id_municipality'})
    )
    
    # User Type & Organization
    user_type = ChoiceField(
        choices=[('', 'Selecciona...')] + User.USER_TYPE_CHOICES,
        required=False,
        label=_("¿Cómo planeas usar esta plataforma?"),
        widget=Select(attrs={'class': 'form-select', 'id': 'id_user_type'})
    )
    
    organization_name = CharField(
        max_length=255,
        required=False,
        label=_("Nombre de tu Institución/Empresa (opcional)"),
        widget=TextInput(attrs={
            'class': 'form-control',
            'id': 'id_organization_name',
            'placeholder': 'Ej: Colegio San José'
        })
    )
    
    # School Affiliation (hidden, populated by JavaScript)
    school_code = CharField(
        max_length=20,
        required=False,
        widget=HiddenInput(attrs={'id': 'id_school_code'})
    )
    
    school_name = CharField(
        max_length=255,
        required=False,
        widget=HiddenInput(attrs={'id': 'id_school_name'})
    )
    
    def save(self, request):
        user = super().save(request)
        
        # Personal info
        user.first_name = self.cleaned_data.get('first_name', '')
        user.last_name = self.cleaned_data.get('last_name', '')
        user.gender = self.cleaned_data.get('gender', '')
        user.birth_year = self.cleaned_data.get('birth_year')
        user.phone = self.cleaned_data.get('phone', '')
        
        # Geographic
        user.department = self.cleaned_data.get('department', '')
        user.municipality = self.cleaned_data.get('municipality', '')
        
        # User type & organization
        user.user_type = self.cleaned_data.get('user_type', '')
        user.organization_name = self.cleaned_data.get('organization_name', '')
        
        # School affiliation
        user.school_code = self.cleaned_data.get('school_code', '')
        user.school_name = self.cleaned_data.get('school_name', '')
        
        user.save()
        return user
