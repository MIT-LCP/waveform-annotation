from django.db import models
from django.contrib.auth.models import User
class User(models.Model):
    username = models.CharField(max_length=150, unique=True, blank=False,
        default='')
    join_date = models.DateTimeField(auto_now_add=True)
    last_logged_in = models.DateTimeField(auto_now_add=True)
    is_admin = models.BooleanField(default=False)

    def num_annotations(self):
        return len(Annotation.objects.filter(user=self))

    def new_settings(self):
        diff_settings = {}
        all_fields = [f.name for f in UserSettings._meta.fields][2:]
        for field in all_fields:
            user_set = UserSettings.objects.get(user=self).__dict__[field]
            default = UserSettings._meta.get_field(field).get_default()
            if user_set != default:
                diff_settings[field] = [default, user_set]
        return diff_settings


class Annotation(models.Model):
    user = models.ForeignKey('User', related_name='annotation',
        on_delete=models.CASCADE)
    record = models.CharField(max_length=50, blank=False)
    event = models.CharField(max_length=50, blank=False)
    decision = models.CharField(max_length=9, blank=False)
    comments = models.TextField(default='')
    decision_date = models.DateTimeField(null=True, blank=False)

    def update(self):
        all_annotations = Annotation.objects.all()
        exists_already = False
        for a in all_annotations:
            if (a.user == self.user) and (a.record == self.record) and (a.event == self.event):
                exists_already = True
                a.decision = self.decision
                a.comments = self.comments
                a.decision_date = self.decision_date
                a.save(update_fields=['decision', 'comments',
                                      'decision_date'])
        if not exists_already:
            self.save()


class UserSettings(models.Model):
    user = models.ForeignKey('User', related_name='settings',
        on_delete=models.CASCADE)
    fig_height = models.FloatField(blank=False, default=725.0)
    fig_width = models.FloatField(blank=False, default=875.0)
    margin_left = models.FloatField(blank=False, default=0.0)
    margin_top = models.FloatField(blank=False, default=25.0)
    margin_right = models.FloatField(blank=False, default=0.0)
    margin_bottom = models.FloatField(blank=False, default=0.0)
    grid_color = models.TextField(blank=False, default='#ff3c3c')
    background_color = models.TextField(blank=False, default='#ffffff')
    sig_color = models.TextField(blank=False, default='#000000')
    sig_thickness = models.FloatField(blank=False, default=1.5)
    ann_color = models.TextField(blank=False, default='#3c3cc8')
    grid_delta_major = models.FloatField(blank=False, default=0.2)
    max_y_labels = models.IntegerField(blank=False, default=8)
    down_sample_ekg = models.IntegerField(blank=False, default=8)
    down_sample = models.IntegerField(blank=False, default=16)
    signal_std = models.FloatField(blank=False, default=2.0)
    time_range_min = models.FloatField(blank=False, default=40.0)
    time_range_max = models.FloatField(blank=False, default=10.0)
    window_size_min = models.FloatField(blank=False, default=10.0)
    window_size_max = models.FloatField(blank=False, default=1.0)
