from django.shortcuts import render

from django.contrib.auth.decorators import login_required
from django.template import TemplateDoesNotExist


def landing_page_view(request):
    """
    Landing page - public, no login required.
    """
    return render(request, 'pages/landing.html')


@login_required
def root_page_view(request):
    try:
        return render(request, 'pages/index.html')
    except TemplateDoesNotExist:
        return render(request, 'pages/pages-404.html')


def dynamic_pages_view(request, template_name):
    """
    Render dynamic pages. 
    Pricing page is public, all other pages require login.
    """
    # Public pages that don't require authentication
    public_pages = ['pages-pricing']
    
    # Require login for non-public pages
    if template_name not in public_pages and not request.user.is_authenticated:
        from django.contrib.auth.views import redirect_to_login
        return redirect_to_login(request.get_full_path())
    
    try:
        return render(request, f'pages/{template_name}.html')
    except TemplateDoesNotExist:
        return render(request, f'pages/pages-404.html')


