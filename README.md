[![Build Status](https://travis-ci.com/Yiling-J/django-cacheme.svg?branch=master)](https://travis-ci.com/Yiling-J/django-cacheme)
[![Build Status](https://codecov.io/gh/Yiling-J/django-cacheme/branch/master/graph/badge.svg)](https://codecov.io/gh/Yiling-J/django-cacheme)
# Django-Cacheme

Django-Cacheme is a package to cache data in Django, especially api results.
All you need is a cache key, invalid rules, and models to connect signal.
Support redis only.

## Getting started

`pip install django-cacheme`

Add 'django_cacheme' to your INSTALLED_APPS

Update your Django settings:
```
CACHEME = {
    'ENABLE_CACHE': True,
    'REDIS_CACHE_ALIAS': 'cacheme',  # your CACHES alias name in settings, optional, 'default' as default
    'REDIS_CACHE_PREFIX': 'MYCACHE:' # cacheme key prefix, optional, 'CM:' as default 
}
```

Finally run migration before use

## Example

models.py

```

class User(Model):
    name = Charfield(...)

    @property
    def cache_key(self):
        return 'User:%s' % self.id

class Book(Model):
    name = CharField(...)
    owner = ForeignKey(...)

    @property
    def cache_key(self):
        return 'Book:%s' % self.id

```

serializers.py

```
from django_cacheme import cacheme


class BookSerializer(object):

    @cacheme(
        key=lambda c: c.obj.cache_key + ">" + "owner",
        invalid_keys=lambda c: [c.obj.owner.cache_key],
        invalid_models=(api.models.User,)
    )
    def get_owner(self, obj):
        return BookOwnerSerializer(obj.owner).data
	
```

So for example we have a book, id is 100, and a user, id is 200. And we want to cache
book owner data in serializer. So the cache key will be `Book:100>owner`, "Book:100" as key, and
"owner" as field in redis.

Invalid key will be `User:200:invalid`, the ":invalid" suffix is auto added. And the redis data type
of this key is set. The `Book:100>owner` key will be stored under this invalid key.

Finally, if we change book 100 in django, the post save signal is triggered, and we get the invalid
key from cache_key property: `Book:100:invalid` (":invalid" is added automatically), and remove all
members from this key.

## Introduction

Some packages automatically cache Django queries, they are simple to use, but given
the fact that cache is very complicated, the automatic way may cause problems. Also, query in Django
is just one line code, we can't do a lot on that, so sometimes need to find another way.

One solution is not cache the original query, but cache the final results we want, for example
the api results. This can give us more flexibility.

Now considering you have a serializer to serializer models to json results. This serialzer may have
many fields, for example:

```
Class BookSerializer(object):

    def get_author(self, book):
        ...

    def get_chapters(self, book):
        ...

    def get_tables(self, book):
        ...
    ...
```

Each `get` method, has a relation, for example foreignkey or manytomany. Then we can cache
each `get` separately, when author is changed, only author part is invalid, other cache is still
working. 


## How to use

Cacheme need following params when init the decorator.

* key: Callable, required. The func to generate the cache key, will call this func when the key is needed.

* invalid_keys: Callable or None, default None. an invalid key that will store this key, use redis set,
and the key func before will be stored in this invalid key. If using Django , this invalid
key should be a models cache key, so when model invalid signal is called, all
keys in that invalid key will be invalid.

* invalid_models/invalid_m2m_models: List, default []. Models and m2m models that will trigger the invalid
signal, every model must has an invalid_key property(can be a list), and m2m model need to have a suffix.
And when signal is called, all members in the model instance invalid key will be removed.

* hit: callback when cache hit, need 3 arguments `(key, result, container)`

* miss: callback when cache miss, need 2 arguments `(key, container)`

* name: string, default func name. using name to get cache instance, then get all keys generated.

```
from cacheme import cacheme_instances

instance = cacheme_instances[name]

# get all keys
keys = instance.keys
```

## Tips:

* key and invalid_keys callable: the first argument in the callable is the container, this container
contains the args and kwargs for you function. For example, if your function is `def func(a, b, **kwargs)`,
then you can access `a` and `b` in your callable by `container.a`, `container.b`, also `container.kwargs`.

* For invalid_keys callable, you can aslo get your function result through `container.cacheme_result`, so you can invalid based on this result.

* if code is changed, developer should check if cache should invalid or not, for example you add some
fields to json, then cache for that json should be invalid, there is no signal for this, so do it manually
* also provide a simple admin page for invalidation pattern, just add this to your Django apps, and migrate,
then create validations in admin. Syntax is same as redis scan patterns, for example, "*" means remove all.
