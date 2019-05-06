from django.db import models


class TestUser(models.Model):
    name = models.CharField(max_length=30)

    @property
    def cache_key(self):
        return "User:%s" % self.id
