from django.db import models
from django.utils import timezone
from django.contrib.auth.models import User
from .utils import invalid_pattern


class Invalidation(models.Model):
    user = models.ForeignKey(User)
    pattern = models.CharField(max_length=200)
    created = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return self.pattern

    def save(self, *args, **kwargs):
        if not self.pk:
            invalid_pattern(self.pattern)
        super().save(*args, **kwargs)
