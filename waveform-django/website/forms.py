from django import forms
from django.contrib.auth.forms import UserCreationForm, UsernameField
from django.contrib.auth.models import User as d_User
from django.contrib.sites.shortcuts import get_current_site
from django.core.exceptions import ValidationError
from django.core.mail import EmailMultiAlternatives
from django.template import loader
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from django.utils.translation import gettext_lazy as _

from waveforms.models import User
from website.tokens import password_reset_token


class CreateUserForm(UserCreationForm):
    """
    For creating a new user.
    """
    class Meta:
        model = d_User
        fields = ['username', 'email', 'password1', 'password2']


class ResetPasswordForm(forms.Form):
    """
    For changing the user's password.
    """
    username = UsernameField(
        widget = forms.TextInput(attrs={'autofocus': True})
    )
    email = forms.EmailField(
        label=_('Email'),
        max_length=254,
        widget=forms.EmailInput(attrs={'autocomplete': 'email'})
    )
    class Meta:
        model = User
        fields = ['username', 'email']

    def clean(self):
        """
        Check for any invalid values that may break the code later.

        Parameters
        ----------
        N/A

        Returns
        -------
        N/A

        """
        if self.errors:
            return

        user = self.get_user(self.cleaned_data['username'])
        if self.cleaned_data['email'] != user.email:
            raise forms.ValidationError("""That email does not match the email
                for that username's account""")

    def send_mail(self, subject_template_name, email_template_name, context,
                  from_email, to_email, html_email_template_name=None):
        """
        Send a django.core.mail.EmailMultiAlternatives to `to_email`.

        Parameters
        ----------
        subject_template_name : str
            The template for the email subject.
        email_template_name : str
            The template for the email.
        context : str
            The extra information (headers) needed for the email.
        from_email : str
            The email of the sender.
        to_email : str
            The email of the receiver.
        html_email_template_name : str, optional
            The template for the HTML email.

        Returns
        -------
        N/A

        """
        subject = loader.render_to_string(subject_template_name, context)
        # Email subject *must not* contain newlines
        subject = ''.join(subject.splitlines())
        body = loader.render_to_string(email_template_name, context)

        email_message = EmailMultiAlternatives(subject, body, from_email,
                                               [to_email])
        if html_email_template_name is not None:
            html_email = loader.render_to_string(html_email_template_name,
                                                 context)
            email_message.attach_alternative(html_email, 'text/html')

        email_message.send()

    def get_user(self, username):
        """
        Given a username, return matching user who should receive a reset.

        Parameters
        ----------
        username : str
            The user's username.

        Returns
        -------
        user : User object
            The object from the User model that matches the requested
            username.

        """
        try:
            user = User.objects.get(username__exact=username)
            return user
        except User.DoesNotExist:
            self.add_error(
                'username',
                ValidationError(_('That username was not found'),
                                code='invalid')
            )
            return None

    def save(self, domain_override=None,
             subject_template_name='registration/password_reset_subject.txt',
             email_template_name='registration/password_reset_email.html',
             from_email=None, request=None, html_email_template_name=None,
             extra_email_context=None):
        """
        Generate a one-use only link for resetting password and send it to the
        user.

        Parameters
        ----------
        domain_override : str, optional
            The name of the site.
        subject_template_name : str, optional
            The template for the email subject.
        email_template_name : str, optional
            The template for the email.
        from_email : str, optional
            The email of the sender.
        request : Request object, optional
            The current HTTP request.
        html_email_template_name : str, optional
            The template for the HTML email.
        extra_email_context : str, optional
            The extra information (headers) needed for the email.

        Returns
        -------
        N/A

        """
        username = self.cleaned_data['username']
        email = self.cleaned_data['email']
        user = self.get_user(username)

        if not domain_override:
            current_site = get_current_site(request)
            site_name = current_site.name
            domain = current_site.domain
        else:
            site_name = domain = domain_override

        context = {
            'email': email,
            'domain': domain,
            'site_name': site_name,
            'uid': urlsafe_base64_encode(force_bytes(user.pk)),
            'user': user,
            'token': password_reset_token.make_token(user),
            'protocol': 'http' if domain.startswith('localhost') else 'https',
            **(extra_email_context or {}),
        }
        self.send_mail(
            subject_template_name, email_template_name, context, from_email,
            email, html_email_template_name=html_email_template_name
        )


class ChangePasswordForm(forms.Form):
    """
    The form to change the user's password.
    """
    username = UsernameField(
        widget = forms.TextInput(attrs={'autofocus': True})
    )
    password1 = forms.CharField(label=_('Password'),
        widget=forms.PasswordInput
    )
    password2 = forms.CharField(label=_('Password'),
        widget=forms.PasswordInput
    )
    class Meta:
        model = User
        fields = []

    def clean(self):
        """
        Check for any invalid values that may break the code later.

        Parameters
        ----------
        N/A

        Returns
        -------
        N/A

        """
        if self.errors:
            return

        if self.cleaned_data['password1'] != self.cleaned_data['password2']:
            raise forms.ValidationError("""Your two passwords do not
                match. Please try again.""")

    def save(self):
        """
        Save the new user's password.

        Parameters
        ----------
        N/A

        Returns
        -------
        N/A

        """
        user = d_User.objects.get(username__exact=self.cleaned_data['username'])
        user.set_password(self.cleaned_data['password1'])
        user.save()
