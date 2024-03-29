import csv
import os

from django.core.validators import EmailValidator
from django.db import models
from django.utils import timezone

from website.settings import base


class User(models.Model):
    """
    The model for each user on the platform.
    """
    username = models.CharField(max_length=150, unique=True, blank=False)
    email = models.EmailField(max_length=255, unique=True, null=True,
        blank=False, validators=[EmailValidator()])
    join_date = models.DateTimeField(auto_now_add=True)
    is_adjudicator = models.BooleanField(default=False)
    is_admin = models.BooleanField(default=False)
    last_login = models.DateTimeField(default=timezone.now)
    date_assigned = models.DateTimeField(default=timezone.now)
    # Completion status of the practice test
    BEGAN = 'BG'
    COMPLETED = 'CO'
    ENDED = 'ED'
    practice_modes = [
        (BEGAN, 'Began'),
        (COMPLETED, 'Completed'),
        (ENDED, 'Ended')
    ]
    practice_status = models.CharField(
        max_length=2,
        choices=practice_modes,
        default=ENDED,
    )

    def num_annotations(self, project=None):
        """
        Determine the number of annotations for the current user.

        Parameters
        ----------
        project : str, optional
            The desired project from which to query for user annotations.

        Returns
        -------
        N/A : int
            The number of annotations for the current user.

        """
        if project:
            return len(Annotation.objects.filter(user=self, project=project,
                                                 is_adjudication=False))
        else:
            return len(Annotation.objects.filter(user=self,
                                                 is_adjudication=False))

    def new_settings(self):
        """
        Returns the changes in the user settings from default values.

        Parameters
        ----------
        N/A

        Returns
        -------
        diff_settings : dict
            All of the user settings changes from default in the form of:
                {
                    'field1': [default1, user_change1],
                    'field2': [default2, user_change2],
                    ...
                }

        """
        diff_settings = {}
        all_fields = [f.name for f in UserSettings._meta.fields][2:]
        for field in all_fields:
            user_set = UserSettings.objects.get(user=self).__dict__[field]
            default = UserSettings._meta.get_field(field).get_default()
            if user_set != default:
                diff_settings[field] = [default, user_set]
        return diff_settings

    def events_remaining(self):
        """
        Return the total number of event remaining from the user's assignment.

        Parameters
        ----------
        N/A

        Returns
        -------
        count : int
            The total number of events remaining from the user's assignment.

        """
        BASE_DIR = base.BASE_DIR
        FILE_ROOT = os.path.abspath(os.path.join(BASE_DIR, os.pardir))
        FILE_LOCAL = os.path.join('record-files')
        PROJECT_PATH = os.path.join(FILE_ROOT, FILE_LOCAL)

        count = 0
        for project in base.ALL_PROJECTS:
            event_list = []
            csv_path = os.path.join(PROJECT_PATH, project, base.ASSIGNMENT_FILE)
            with open(csv_path, 'r') as csv_file:
                csvreader = csv.reader(csv_file, delimiter=',')
                next(csvreader)
                for row in csvreader:
                    if self.username in row[1:]:
                        event_list.append(row[0])
            complete_events = Annotation.objects.filter(
                user=self, project=project, is_adjudication=False).exclude(
                decision='Save for Later').values_list('event', flat=True)
            event_list = [e for e in event_list if e not in complete_events]
            count += len(event_list)
        return count


class InvitedEmails(models.Model):
    """
    The emails which have been invited and their associated account.
    """
    email = models.EmailField(max_length=255, unique=True, null=True,
        blank=False, validators=[EmailValidator()])
    last_invite_date = models.DateTimeField()
    joined = models.BooleanField(default=False)
    joined_username = models.CharField(max_length=150, unique=True,
                                       blank=False, null=True)


class Annotation(models.Model):
    """
    """
    user = models.ForeignKey('User', related_name='annotation',
        on_delete=models.CASCADE)
    project = models.CharField(max_length=50, blank=False)
    record = models.CharField(max_length=50, blank=False)
    event = models.CharField(max_length=50, blank=False)
    decision = models.CharField(max_length=9, blank=False)
    comments = models.TextField(default='')
    decision_date = models.DateTimeField(null=True, blank=False)
    is_adjudication = models.BooleanField(default=False, null=True)

    def update(self):
        """
        Update the user's annotation if it exists, else create a new one.

        Parameters
        ----------
        N/A

        Returns
        -------
        N/A

        """
        all_annotations = Annotation.objects.filter(
            user=self.user, project=self.project, record=self.record,
            event=self.event, is_adjudication=False
        )
        if all_annotations:
            for a in all_annotations:
                a.decision = self.decision
                a.comments = self.comments
                a.decision_date = self.decision_date
                a.save(update_fields=['decision', 'comments',
                                      'decision_date'])
        else:
            self.save()


class UserSettings(models.Model):
    """
    The settings for the user to adjust their graph display.
    """
    user = models.ForeignKey('User', related_name='settings',
        on_delete=models.CASCADE)
    fig_height = models.FloatField(blank=False, default=690.0)
    fig_width = models.FloatField(blank=False, default=875.0)
    margin_left = models.FloatField(blank=False, default=0.0)
    margin_top = models.FloatField(blank=False, default=25.0)
    margin_right = models.FloatField(blank=False, default=0.0)
    margin_bottom = models.FloatField(blank=False, default=35.0)
    grid_color = models.TextField(blank=False, default='#ff3c3c')
    background_color = models.TextField(blank=False, default='#ffffff')
    sig_color = models.TextField(blank=False, default='#000000')
    sig_thickness = models.FloatField(blank=False, default=1.5)
    ann_color = models.TextField(blank=False, default='#3c3cc8')
    grid_delta_major = models.FloatField(blank=False, default=0.2)
    max_y_labels = models.IntegerField(blank=False, default=8)
    n_ekg_sigs = models.IntegerField(blank=False, default=2)
    down_sample_ekg = models.IntegerField(blank=False, default=1)
    down_sample = models.IntegerField(blank=False, default=1)
    signal_std = models.FloatField(blank=False, default=6.0)
    time_range_min = models.FloatField(blank=False, default=40.0)
    time_range_max = models.FloatField(blank=False, default=10.0)
    window_size_min = models.FloatField(blank=False, default=10.0)
    window_size_max = models.FloatField(blank=False, default=1.0)
