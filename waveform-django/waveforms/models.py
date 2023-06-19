import csv
import os

from django.core.validators import EmailValidator
from django.db import models
from django.db.models import UniqueConstraint
from django.utils import timezone

from website.settings import base


def update_decision(waveform):
    """
    Update the decision value of a waveform if it has been annotated max times, or has been adjudicated.
    """
    decision_set = set()
    adjudicated_decision = None
    annotations = waveform.annotation_set.all()
    
    for annotation in annotations:
        if annotation.is_adjudication:
            adjudicated_decision = annotation.decision
            break
        decision_set.add(annotation.decision)
    
    if adjudicated_decision:
        # Waveform has been adjudicated
        waveform.decision = adjudicated_decision
        waveform.save()
        return
    
    if len(annotations) < base.NUM_ANNOTATORS:
        # Waveform is not done being annotated
        waveform.decision = 'None'
    
    elif len(annotations) == base.NUM_ANNOTATORS:
        if len(decision_set) == 1:
            # Unanimous decision
            waveform.decision = decision_set.pop()
        else:
            # Conflicting decisions
            waveform.decision = 'Conflict'
    waveform.save()


class WaveformEvent(models.Model):
    """
    Defines the model for each waveform event. Contains info about each event that has been assigned.
    """
    project = models.CharField(max_length=50, unique=False, blank=False)
    record = models.CharField(max_length=50, unique=False, blank=False)
    event = models.CharField(max_length=50, unique=False, blank=False)
    is_practice = models.BooleanField(default=False)
    decision = models.CharField(max_length=10, unique=False, default='None')
    
    def __str__(self):
        return f'{self.project}/{self.record}/{self.event}'
    
    @property
    def path(self):
        return f'{self.project}/{self.record}/{self.event}'

    class Meta:
        constraints = [
            UniqueConstraint(fields=['project', 'record', 'event'], name='unique_fields')
        ]
        ordering = ['project', 'record', 'event']


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
    is_annotator = models.BooleanField(default=False)
    waveforms = models.ManyToManyField(WaveformEvent, related_name='annotators')
    entrance_score = models.CharField(
        max_length=8,
        default='N/A',
    )
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
        default=BEGAN,
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


    def num_events_remaining(self):
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
        all_projects = [p for p in base.ALL_PROJECTS if p not in base.BLACKLIST]
        all_waveforms = WaveformEvent.objects.filter(annotators=self, project__in=all_projects)
        remaining_waveforms = all_waveforms.exclude(annotation__user=self)
        return remaining_waveforms.count()
    

    def get_waveforms(self, annotation = ''):
        """
        Return the waveforms for the user based on the type of waveforms requested.

        Parameters
        ----------
        type : str
            The type of waveforms to return. Options are:
                - EMPTY STRING (default) - all waveforms
                - unannotated
                - saved
                - annotated
                - adjudicated
        """

        if self.practice_status == 'ED':
            all_projects = [p for p in base.ALL_PROJECTS if p not in base.BLACKLIST]
            all_waveforms = WaveformEvent.objects.filter(annotators=self, project__in=all_projects, is_practice=False)
        else:
            all_waveforms = WaveformEvent.objects.filter(is_practice=True)
        
        if annotation == 'unannotated':
            return all_waveforms.exclude(bookmark__user=self).exclude(annotation__user=self)
        elif annotation == 'saved':
            return all_waveforms.filter(bookmark__user=self)
        elif annotation == 'annotated':
            return all_waveforms.filter(annotation__user=self)
        else:
            return all_waveforms
        

    def get_annotations(self, saved=False, is_adjudicated=False):
        if self.practice_status == 'ED':
            if self.is_admin:
                all_projects = base.ALL_PROJECTS
                all_annotations = Annotation.objects.filter(user=self, is_adjudication=is_adjudicated, waveform__is_practice=False)
            else:
                all_projects = [p for p in base.ALL_PROJECTS if p not in base.BLACKLIST]
                all_annotations = Annotation.objects.filter(user=self, waveform__project__in=all_projects, is_adjudication=is_adjudicated, waveform__is_practice=False)
        else:
            all_projects = list(base.PRACTICE_SET.keys())
            all_annotations = Annotation.objects.filter(user=self, is_adjudication=is_adjudicated, waveform__is_practice=True)
        
        return all_annotations
    

    def get_bookmarks(self):
        if self.practice_status == 'ED':
            if self.is_admin:
                all_projects = base.ALL_PROJECTS
                all_bookmarks = Bookmark.objects.filter(user=self, waveform__is_practice=False)
            else:
                all_projects = [p for p in base.ALL_PROJECTS if p not in base.BLACKLIST]
                all_bookmarks = Bookmark.objects.filter(user=self, waveform__project__in=all_projects, waveform__is_practice=False)
        else:
            all_projects = list(base.PRACTICE_SET.keys())
            all_bookmarks = Bookmark.objects.filter(user=self, waveform__is_practice=True)

        return all_bookmarks 



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
    waveform = models.ForeignKey('WaveformEvent', on_delete=models.CASCADE, default=None)
    project = models.CharField(max_length=50, blank=False)
    record = models.CharField(max_length=50, blank=False)
    event = models.CharField(max_length=50, blank=False)
    decision = models.CharField(max_length=9, blank=False)
    comments = models.TextField(default='')
    decision_date = models.DateTimeField(null=True, blank=False)
    is_adjudication = models.BooleanField(default=False, null=True)
    
    class Meta:
        ordering = ['waveform__project', 'waveform__record', 'waveform__event']

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

        try:
            if self.is_adjudication:
                annotation = Annotation.objects.get(waveform=self.waveform, is_adjudication=self.is_adjudication)
                annotation.user = self.user
            else:
                annotation = Annotation.objects.get(user=self.user, waveform=self.waveform, is_adjudication=self.is_adjudication)
            annotation.decision = self.decision
            annotation.comments = self.comments
            annotation.decision_date = self.decision_date
            annotation.save(update_fields=['user', 'decision', 'comments', 'decision_date'])
        except Annotation.DoesNotExist:
            try:
                bookmark = Bookmark.objects.get(user=self.user, waveform=self.waveform, is_adjudication=self.is_adjudication)
                bookmark.delete()
            except Bookmark.DoesNotExist:
                pass
            self.save()        
        
        update_decision(self.waveform)

    
    def delete(self, *args, **kwargs):
        """
        Delete the user's annotation.

        Parameters
        ----------
        N/A

        Returns
        -------
        N/A

        """
        super(Annotation, self).delete(*args, **kwargs)
        update_decision(self.waveform)


class Bookmark(models.Model):
    """
    Defines the object for a bookmarked waveform.
    """
    user = models.ForeignKey('User', on_delete=models.CASCADE)
    waveform = models.ForeignKey('WaveformEvent', on_delete=models.CASCADE, default=None)
    comments = models.TextField(default='')
    bookmark_date = models.DateTimeField(null=True, blank=False)
    is_adjudication = models.BooleanField(default=False, null=True)
    class Meta:
        ordering = ['waveform__project', 'waveform__record', 'waveform__event']
        constraints = [
            UniqueConstraint(fields=['waveform', 'user'], name='unique_fields')
        ]
    
    def update(self):
        """
        Update the user's bookmark if it exists, else create a new one.

        Parameters
        ----------
        N/A

        Returns
        -------
        N/A

        """
        try:
            bookmark = Bookmark.objects.get(user=self.user, waveform=self.waveform, is_adjudication=self.is_adjudication)
            bookmark.comments = self.comments
            bookmark.bookmark_date = self.bookmark_date
            bookmark.save(update_fields=['comments', 'bookmark_date'])
        except Bookmark.DoesNotExist:
            try:
                annotation = Annotation.objects.get(user=self.user, waveform=self.waveform, is_adjudication=self.is_adjudication)
                annotation.delete()
            except Annotation.DoesNotExist:
                pass
            self.save()
        
        update_decision(self.waveform)
    

    def delete(self, *args, **kwargs):
        """
        Delete the bookmark and update the decision of the waveform.

        Parameters
        ----------
        N/A

        Returns
        -------
        N/A

        """
        super(Bookmark, self).delete(*args, **kwargs)
        update_decision(self.waveform)


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
