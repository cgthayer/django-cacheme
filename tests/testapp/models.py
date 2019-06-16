from django.db import models


class TestUser(models.Model):
    name = models.CharField(max_length=30)

    @property
    def cache_key(self):
        return "User:%s" % self.id


class Book(models.Model):
    name = models.CharField(max_length=30)
    users = models.ManyToManyField(TestUser)

    @property
    def cache_key(self):
        return "Book:%s" % self.id


Book.users.through.suffix = 'users'
