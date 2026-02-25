"""
Módulo de invitaciones por email — solo superadmin.
Permite enviar emails personalizados a 5 tipos de audiencia.
"""
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.core.mail import send_mail
from django.shortcuts import redirect, render
from django.template.loader import render_to_string

from reback.users.models import InvitacionEmail

_superuser_required = user_passes_test(lambda u: u.is_active and u.is_superuser)

SUBJECTS = {
    'rector':        '¿Cómo está {colegio} frente a su contexto educativo? — ICFES Analytics',
    'supervisor':    'Inteligencia educativa para su jurisdicción — ICFES Analytics',
    'institucional': '30 años de datos ICFES revelan lo que los informes oficiales no muestran',
    'padre':         '¿Conoces el historial ICFES real del colegio de tu hijo?',
    'conocido':      'Construí algo que creo que te va a interesar — ICFES Analytics',
}


@login_required
@_superuser_required
def invitar(request):
    historial = InvitacionEmail.objects.select_related('enviado_por').all()[:50]

    if request.method == 'POST':
        tipo            = request.POST.get('tipo', '').strip()
        email           = request.POST.get('email', '').strip()
        nombre          = request.POST.get('nombre_destinatario', '').strip()
        colegio         = request.POST.get('colegio_nombre', '').strip()

        if not tipo or not email:
            messages.error(request, 'Tipo de destinatario y email son obligatorios.')
            return redirect('icfes_dashboard:invitar')

        if tipo not in SUBJECTS:
            messages.error(request, 'Tipo de destinatario inválido.')
            return redirect('icfes_dashboard:invitar')

        context = {
            'nombre':        nombre or 'Estimado/a',
            'colegio':       colegio or 'su institución',
            'site_url':      getattr(settings, 'PUBLIC_SITE_URL', 'https://www.icfes-analytics.com'),
        }

        subject = SUBJECTS[tipo].format(colegio=colegio or 'su institución')
        template_name = f'email/invitacion_{tipo}.html'

        try:
            html_message = render_to_string(template_name, context)
            send_mail(
                subject=subject,
                message='',
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[email],
                html_message=html_message,
                fail_silently=False,
            )
            InvitacionEmail.objects.create(
                email=email,
                nombre_destinatario=nombre,
                tipo=tipo,
                colegio_nombre=colegio,
                enviado_por=request.user,
                estado='enviado',
            )
            messages.success(request, f'Invitación enviada correctamente a {email}.')
        except Exception as exc:
            InvitacionEmail.objects.create(
                email=email,
                nombre_destinatario=nombre,
                tipo=tipo,
                colegio_nombre=colegio,
                enviado_por=request.user,
                estado='error',
                error_msg=str(exc),
            )
            messages.error(request, f'Error al enviar: {exc}')

        return redirect('icfes_dashboard:invitar')

    return render(request, 'icfes_dashboard/pages/invitar.html', {
        'historial': historial,
    })
