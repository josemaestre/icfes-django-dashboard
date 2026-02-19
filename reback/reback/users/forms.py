from allauth.account.forms import SignupForm
from allauth.socialaccount.forms import SignupForm as SocialSignupForm
from django.contrib.auth import forms as admin_forms
from django.forms import (EmailField, CharField, ChoiceField, IntegerField,
                          Select, TextInput, NumberInput, HiddenInput)
from django.utils.translation import gettext_lazy as _

from .models import User
from .subscription_models import SubscriptionPlan, UserSubscription
from django.utils import timezone
from datetime import timedelta
from django import forms


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
        required=False,
        label=_("Departamento"),
        widget=Select(choices=[('', 'Selecciona un departamento...')], attrs={'class': 'form-select', 'id': 'id_department'})
    )
    
    municipality = CharField(
        required=False,
        label=_("Municipio"),
        widget=Select(choices=[('', 'Primero selecciona un departamento')], attrs={'class': 'form-select', 'id': 'id_municipality'})
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
        required=False,
        label=_("Departamento"),
        widget=Select(choices=[('', 'Selecciona un departamento...')], attrs={'class': 'form-select', 'id': 'id_department'})
    )
    
    municipality = CharField(
        required=False,
        label=_("Municipio"),
        widget=Select(choices=[('', 'Primero selecciona un departamento')], attrs={'class': 'form-select', 'id': 'id_municipality'})
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


class UserManagementForm(forms.ModelForm):
    """
    Form to manage user permissions and subscription plans.
    """
    is_staff = forms.BooleanField(required=False, label=_("Es Administrador (Staff)"), widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}))
    is_superuser = forms.BooleanField(required=False, label=_("Es Superusuario"), widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}))
    
    plan = forms.ModelChoiceField(
        queryset=SubscriptionPlan.objects.all(),
        required=False,
        label=_("Plan de Suscripción"),
        empty_label=None,
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    
    TRIAL_CHOICES = [
        (0, 'Sin cambios / Actual'),
        (10, '10 Días'),
        (15, '15 Días'),
        (30, '30 Días'),
    ]
    
    trial_duration = forms.ChoiceField(
        choices=TRIAL_CHOICES,
        required=False,
        label=_("Días de Prueba (desde hoy)"),
        initial=0,
        widget=forms.Select(attrs={'class': 'form-select'})
    )

    class Meta:
        model = User
        fields = ['name', 'email', 'is_staff', 'is_superuser']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.pk:
            self.fields['is_staff'].initial = self.instance.is_staff
            self.fields['is_superuser'].initial = self.instance.is_superuser
            
            # Populate initial plan from subscription
            try:
                if hasattr(self.instance, 'subscription'):
                    self.fields['plan'].initial = self.instance.subscription.plan
            except UserSubscription.DoesNotExist:
                pass

    def save(self, commit=True):
        user = super().save(commit=False)
        
        user.is_staff = self.cleaned_data.get('is_staff')
        user.is_superuser = self.cleaned_data.get('is_superuser')
        
        if commit:
            user.save()
            
            # Handle Subscription
            plan = self.cleaned_data.get('plan')
            trial_days = int(self.cleaned_data.get('trial_duration', 0))
            
            if plan:
                subscription, created = UserSubscription.objects.get_or_create(
                    user=user,
                    defaults={'plan': plan}
                )
                
                if subscription.plan != plan:
                    subscription.plan = plan
                    subscription.save()
                
                if trial_days > 0:
                    subscription.start_date = timezone.now()
                    subscription.end_date = timezone.now() + timedelta(days=trial_days)
                    subscription.save()
            
        return user
