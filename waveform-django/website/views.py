from django.contrib import messages
from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
# Outside packages
from waveforms import views
from waveforms.models import UserSettings
from .forms import CreateUserForm, ResetPasswordForm


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
                user = form.cleaned_data.get('username')
                messages.success(request, 'Account was created for ' + user)
                # Create the default settings file for that user
                UserSettings(user=user).save()
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
        # Check if form username is valid first
        form.get_user(form.data['username'])
        if form.is_valid():
            form.save(
                from_email = 'help@waveform-annotation.com',
                request = request
            )
            return redirect('password_reset_done')
    return render(request, 'registration/password_reset_form.html', {'form': form})


@login_required
def logout_user(request):
    """
    Logout the user upon request.
    """
    logout(request)
    messages.info(request, 'Logged out successfully!')
    return redirect('login')
