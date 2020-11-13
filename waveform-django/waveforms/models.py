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
