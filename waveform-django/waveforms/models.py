from django.db import models


class Annotation(models.Model):
    user = models.CharField(max_length=150, unique=False, blank=False, default='')
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
                a.save(update_fields=['decision', 'comments', 'decision_date'])
        if not exists_already:
            self.save()


class UserSettings(models.Model):
    user = models.CharField(max_length=150, unique=True, blank=False, default='')
    fig_height = models.FloatField(blank=False, default=725.0)
    fig_width = models.FloatField(blank=False, default=875.0)
    margin_left = models.FloatField(blank=False, default=0.0)
    margin_top = models.FloatField(blank=False, default=25.0)
    margin_right = models.FloatField(blank=False, default=0.0)
    margin_bottom = models.FloatField(blank=False, default=0.0)
    grid_color = models.TextField(blank=False, default='#ff3c3c')
    sig_color = models.TextField(blank=False, default='#000000')
    sig_thickness = models.FloatField(blank=False, default=1.5)
    ann_color = models.TextField(blank=False, default='#3c3cc8')
    grid_delta_major = models.FloatField(blank=False, default=0.2)
    max_y_labels = models.IntegerField(blank=False, default=8)
    down_sample_ekg = models.IntegerField(blank=False, default=8)
    down_sample = models.IntegerField(blank=False, default=16)
    time_range_min = models.FloatField(blank=False, default=40.0)
    time_range_max = models.FloatField(blank=False, default=10.0)
    window_size_min = models.FloatField(blank=False, default=10.0)
    window_size_max = models.FloatField(blank=False, default=1.0)
