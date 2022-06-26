import datetime

from django import forms
from django.contrib.sites.shortcuts import get_current_site
from django.core.mail import EmailMultiAlternatives
from django.db import IntegrityError
from django.template import loader
from django.utils.translation import gettext_lazy as _
import pytz

from waveforms.models import InvitedEmails, User, UserSettings
from website.settings import base


class GraphSettings(forms.ModelForm):
    """
    Allow the user to change their default graph settings.
    """
    class Meta:
        # The name of the model to be modified.
        model = UserSettings
        # The attributes of the model to be modified.
        fields = (
            'fig_height', 'fig_width', 'margin_left', 'margin_top',
            'margin_right', 'margin_bottom', 'grid_color', 'background_color',
            'sig_color', 'sig_thickness', 'ann_color', 'grid_delta_major',
            'max_y_labels', 'n_ekg_sigs', 'down_sample_ekg', 'down_sample',
            'signal_std', 'time_range_min', 'time_range_max',
            'window_size_min', 'window_size_max'
        )
        # The help text that further informs the user.
        help_texts = {
            'fig_height': """The figure height""",
            'fig_width': """The figure width""",
            'margin_left': """The padding to the left of the figure""",
            'margin_top': """The padding to the top of the figure""",
            'margin_right': """The padding to the right of the figure""",
            'margin_bottom': """The padding to the bottom of the figure""",
            'grid_color': """The grid color""",
            'background_color': """The background color""",
            'sig_color': """The color of the signal""",
            'sig_thickness': """The thickness of the signal""",
            'ann_color': """The color of the event annotation (zero-line)""",
            'grid_delta_major': """EKG gridline spacing in seconds (standard
                EKG paper has large squares every 0.2 seconds)""",
            'max_y_labels': """Set the maximum number of y-axis labels per
                signal""",
            'n_ekg_sigs': """Set the maximum number of EKG signals to
                display.""",
            'down_sample_ekg': """Downsample EKG signal to increase
                performance (average starting frequency = 250 Hz)""",
            'down_sample': """Downsample non-EKG signals to increase
                performance (usually higher than EKG downsampling rate since
                it consists of lower frequency signals)""",
            'signal_std': """The number of standard deviations to be shown
                on each side from the signal mean""",
            'time_range_min': """How much total signal should be displayed
                before the event (seconds)""",
            'time_range_max': """How much total signal should be displayed
                after the event (seconds)""",
            'window_size_min': """How much initial signal should be displayed
                before the event (seconds)""",
            'window_size_max': """How much initial signal should be displayed
                after the event (seconds)"""
        }
        # What kind of input is accepted for each model attribute.
        widgets = {
            'fig_height': forms.NumberInput(attrs={'min': 0, 'type': 'number'}),
            'fig_width': forms.NumberInput(attrs={'min': 0, 'type': 'number'}),
            'margin_left': forms.NumberInput(attrs={'type': 'number'}),
            'margin_top': forms.NumberInput(attrs={'type': 'number'}),
            'margin_right': forms.NumberInput(attrs={'type': 'number'}),
            'margin_bottom': forms.NumberInput(attrs={'type': 'number'}),
            'grid_color': forms.TextInput(attrs={'type': 'color'}),
            'background_color': forms.TextInput(attrs={'type': 'color'}),
            'sig_color': forms.TextInput(attrs={'type': 'color'}),
            'sig_thickness': forms.NumberInput(attrs={'min': 0, 'type': 'number'}),
            'ann_color': forms.TextInput(attrs={'type': 'color'}),
            'grid_delta_major': forms.NumberInput(attrs={'min': 0, 'type': 'number'}),
            'max_y_labels': forms.NumberInput(attrs={'min': 1, 'type': 'number'}),
            'n_ekg_sigs': forms.NumberInput(attrs={'min': 1, 'max': 4, 'type': 'number'}),
            'down_sample_ekg': forms.NumberInput(attrs={'min': 1, 'type': 'number'}),
            'down_sample': forms.NumberInput(attrs={'min': 1, 'type': 'number'}),
            'signal_std': forms.NumberInput(attrs={'min': 0.1, 'type': 'number'}),
            'time_range_min': forms.NumberInput(attrs={'min': 0, 'max': 300, 'type': 'number'}),
            'time_range_max': forms.NumberInput(attrs={'min': 0, 'max': 300, 'type': 'number'}),
            'window_size_min': forms.NumberInput(attrs={'min': 0, 'max': 300, 'type': 'number'}),
            'window_size_max': forms.NumberInput(attrs={'min': 0, 'max': 300, 'type': 'number'}),
        }
        # The main label for each setting.
        labels = {
            'fig_height': 'Figure height',
            'fig_width': 'Figure width',
            'margin_left': 'Left margin',
            'margin_top': 'Top margin',
            'margin_right': 'Right margin',
            'margin_bottom': 'Bottom margin',
            'grid_color': 'Grid color',
            'background_color': 'Background color',
            'sig_color': 'Signal color',
            'sig_thickness': 'Signal thickness',
            'ann_color': 'Annotation color',
            'grid_delta_major': 'Grid delta',
            'max_y_labels': 'Maximum y-labels',
            'n_ekg_sigs': 'Maximum EKG signals',
            'down_sample_ekg': 'EKG downsample',
            'down_sample': 'Non-EKG downsample',
            'signal_std': 'Signal range',
            'time_range_min': 'Total time before event',
            'time_range_max': 'Total time after event',
            'window_size_min': 'Initial time before event',
            'window_size_max': 'Initial time after event'
        }

    def __init__(self, user, *args, **kwargs):
        """
        Initialize a settings model for the user.

        Parameters
        ----------
        TODO

        Returns
        -------
        N/A

        """
        super().__init__(*args, **kwargs)
        self.user = user.username

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

        if self.cleaned_data['window_size_min'] > self.cleaned_data['time_range_min']:
            raise forms.ValidationError('The initial minimum window must be less than the total minimum window')

        if self.cleaned_data['window_size_max'] > self.cleaned_data['time_range_max']:
            raise forms.ValidationError('The initial maximum window must be less than the total maximum window')

    def reset_default(self):
        """
        Reset all the values to their defaults.

        Parameters
        ----------
        N/A

        Returns
        -------
        N/A

        """
        for f in self.instance._meta.fields:
            if f.name in set(self.fields):
                setattr(self.instance, f.name, f.default)
        self.instance.save()

    def save(self):
        """
        Save the cleaned form data.

        Parameters
        ----------
        N/A

        Returns
        -------
        N/A

        """
        super().save()


class InviteUserForm(forms.Form):
    """
    The form used to invite new users to the platform.
    """
    email = forms.EmailField(
        label=_('Email'),
        max_length=254,
        widget=forms.EmailInput(attrs={'class': 'form-control',
                                       'autocomplete': 'email'})
    )

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

    def send_mail(self, subject_template_name, email_template_name, context,
                  from_email, to_email, html_email_template_name=None):
        """
        Send an invite email to `to_email`.

        Parameters
        ----------
        subject_template_name : str
            The template for the email subject.
        email_template_name : str
            The template for the email.
        context : str
            The information (headers) needed for the email.
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

    def save(self, domain_override=None,
             subject_template_name='registration/invite_user_subject.txt',
             email_template_name='registration/invite_user_email.html',
             from_email=None, request=None, html_email_template_name=None,
             extra_email_context=None):
        """
        Send the invited user an email so they can sign up for an account.

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
        email = self.cleaned_data['email']

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
            'protocol': 'http' if domain.startswith('localhost') else 'https',
            **(extra_email_context or {}),
        }
        self.send_mail(
            subject_template_name, email_template_name, context, from_email,
            email, html_email_template_name=html_email_template_name
        )

        # Send email to all admins notifying about new user
        admin_users = User.objects.filter(is_admin=True)
        context = {
            'protocol': 'http' if domain.startswith('localhost') else 'https',
            'domain': domain,
            'email': email,
            **(extra_email_context or {}),
        }
        for admin_user in admin_users:
            self.send_mail(
                'registration/new_invite_subject.txt',
                'registration/new_invite_email.html', context,
                base.EMAIL_FROM, admin_user.email,
                html_email_template_name=html_email_template_name
            )

        try:
            new_invited_email = InvitedEmails()
            new_invited_email.email = email
            new_invited_email.last_invite_date = datetime.datetime.now(tz=pytz.timezone(base.TIME_ZONE))
            new_invited_email.save()
        except IntegrityError:
            updated_email = InvitedEmails.objects.get(email__exact=email)
            updated_email.last_invite_date = datetime.datetime.now(tz=pytz.timezone(base.TIME_ZONE))
            updated_email.save()
