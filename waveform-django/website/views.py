from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect

from .forms import CreateUserForm, ResetPasswordForm, ChangePasswordForm
from waveforms.models import InvitedEmails, User, UserSettings


def register_page(request):
    """
    Create a new account upon request.
    """
    if request.user.is_authenticated:
        return redirect('waveform_published_home')
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
                return redirect('login')
        return render(request, 'website/register.html', {'form': form})

def login_page(request):
    """
    Login the user upon request.
    """
    if request.user.is_authenticated:
        return redirect('waveform_published_home')
    else:
        if request.method == 'POST':
            username = request.POST.get('username')
            password =request.POST.get('password')
            user = authenticate(request, username=username, password=password)
            if user is not None:
                login(request, user)
                if 'annotations' in request.environ['QUERY_STRING']:
                    return redirect('render_annotations')
                else:
                    return redirect('waveform_published_home')
            else:
                messages.info(request, 'Username OR password is incorrect')
                return render(request, 'website/login.html', {})
        else:
            if (request.GET.dict() == {}) or not (request.user.is_authenticated):
                return render(request, 'website/login.html', {})
            elif 'annotations' in request.GET.dict()['next']:
                return redirect('render_annotations')
            else:
                return redirect('waveform_published_home')

def reset_password(request):
    form = ResetPasswordForm()
    if request.method == 'POST':
        form = ResetPasswordForm(request.POST)
        if form.is_valid():
            form.save(
                from_email = 'help@waveform-annotation.com',
                request = request
            )
            return redirect('password_reset_done')
    return render(request, 'registration/password_reset_form.html',
                  {'form': form})

def change_password(request, uidb64, token):
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
    """
    logout(request)
    messages.info(request, 'Logged out successfully!')
    return redirect('login')
