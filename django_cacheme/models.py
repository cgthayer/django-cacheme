from django.db import models
from django.utils import timezone
from django.contrib.auth.models import User
from .utils import invalid_pattern, CACHEME
from .cache_model import cacheme_tags


def default_pattern():
    return CACHEME.REDIS_CACHE_PREFIX + '*'


class Invalidation(models.Model):
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    pattern = models.CharField(max_length=200, default=default_pattern)
    created = models.DateTimeField(default=timezone.now)
    tags = models.CharField(max_length=5000, default='')

    def __str__(self):
        return self.pattern

    def save(self, *args, **kwargs):
        if not self.pk:
            invalid_pattern(self.pattern)
            tags = self.tags.split(',')
            for tag in tags:
                if tag:
                    cacheme_tags[tag].invalid_all()
        super().save(*args, **kwargs)
