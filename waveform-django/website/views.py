from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.sites.shortcuts import get_current_site
from django.shortcuts import render, redirect
from django.utils import timezone

from .forms import CreateUserForm, ResetPasswordForm, ChangePasswordForm
from waveforms.models import InvitedEmails, User, UserSettings
from website.settings import base


def redirect_home(request):
    """
    Redirects users to home page
    """
    return redirect(login_page)


def register_page(request):
    """
    Create a new account upon request.

    Parameters
    ----------
    request : Request object
        The current HTTP request.

    Returns
    -------
    N/A

    """
    if request.user.is_authenticated:
        return redirect('viewer_overview')
    else:
        form = CreateUserForm()
        if request.method == 'POST':
            form = CreateUserForm(request.POST)
            if form.is_valid():
                form.save()
                username = form.cleaned_data.get('username')
                email = form.cleaned_data.get('email')
                try:
                    invited_user = InvitedEmails.objects.get(email=email)
                    invited_user.joined = True
                    invited_user.joined_username = username
                    invited_user.save()
                except InvitedEmails.DoesNotExist:
                    pass
                messages.success(request,
                                 f'Account was created for {username}')
                # Create the default profile and settings for that user
                new_user = User(username=username, email=email,
                                is_admin=False)
                new_user.save()
                UserSettings(user=new_user).save()
                # Send email to all admins notifying about new user
                admin_users = User.objects.filter(is_admin=True)
                current_site = get_current_site(request)
                domain = current_site.domain
                context = {
                    'protocol': 'http' if domain.startswith('localhost') else 'https',
                    'domain': domain,
                    'site_name': current_site.name,
                    'email': email
                }
                email_form = ResetPasswordForm()
                for admin_user in admin_users:
                    email_form.send_mail(
                        'registration/new_user_subject.txt',
                        'registration/new_user_email.html', context,
                        base.EMAIL_FROM, admin_user.email
                    )
                return redirect('login')
        return render(request, 'website/register.html', {'form': form})


def login_page(request):
    """
    Login the user upon request.

    Parameters
    ----------
    request : Request object
        The current HTTP request.

    Returns
    -------
    N/A

    """
    if request.user.is_authenticated:
        return redirect('viewer_overview')
    else:
        if request.method == 'POST':
            username = request.POST.get('username')
            password =request.POST.get('password')
            user = authenticate(request, username=username, password=password)
            if user is not None:
                login(request, user)
                user = User.objects.get(username=username)
                user.last_login = timezone.now()
                user.save()
                if 'annotations' in request.environ['QUERY_STRING']:
                    return redirect('current_assignment')
                else:
                    return redirect('viewer_overview')
            else:
                messages.info(request, 'Username OR password is incorrect')
                return render(request, 'website/login.html', {})
        else:
            if (request.GET.dict() == {}) or not (request.user.is_authenticated):
                return render(request, 'website/login.html', {})
            elif 'annotations' in request.GET.dict()['next']:
                return redirect('current_assignment')
            else:
                return redirect('viewer_overview')


def reset_password(request):
    """
    Reset the user's password.

    Parameters
    ----------
    request : Request object
        The current HTTP request.

    Returns
    -------
    N/A

    """
    form = ResetPasswordForm()
    if request.method == 'POST':
        form = ResetPasswordForm(request.POST)
        if form.is_valid():
            form.save(
                from_email = base.EMAIL_FROM,
                request = request
            )
            return redirect('password_reset_done')
    return render(request, 'registration/password_reset_form.html',
                  {'form': form})


def change_password(request):
    """
    Change the user's password.

    Parameters
    ----------
    request : Request object
        The current HTTP request.

    Returns
    -------
    N/A

    """
    form = ChangePasswordForm()
    if request.method == 'POST':
        form = ChangePasswordForm(request.POST)
        if form.is_valid():
            form.save()
            messages.info(request, 'Changed password successfully!')
            return redirect('login')
    return render(request, 'registration/password_reset_confirm.html',
                  {'form': form})


@login_required
def logout_user(request):
    """
    Logout the user upon request.

    Parameters
    ----------
    request : Request object
        The current HTTP request.

    Returns
    -------
    N/A

    """
    logout(request)
    messages.info(request, 'Logged out successfully!')
    return redirect('login')
