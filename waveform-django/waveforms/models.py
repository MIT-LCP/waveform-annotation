from django.db import models


class Annotation(models.Model):
    project = models.CharField(max_length=50, blank=True)
    record = models.CharField(max_length=50, blank=True)
    decision = models.CharField(max_length=9, blank=True)
    comments = models.CharField(max_length=250, blank=True)
    decision_date = models.DateTimeField(null=True, blank=True)
