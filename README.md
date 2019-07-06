[![Build Status](https://travis-ci.com/Yiling-J/django-cacheme.svg?branch=master)](https://travis-ci.com/Yiling-J/django-cacheme)
[![Build Status](https://codecov.io/gh/Yiling-J/django-cacheme/branch/master/graph/badge.svg)](https://codecov.io/gh/Yiling-J/django-cacheme)
# Django-Cacheme

Django-Cacheme is a package to cache functions in Django(memoize) using redis. You can use your function params to define cache keys, also support model signals for invalidation.

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

#### - Cacheme Decorator

Cacheme need following params when init the decorator.

* `key`: Callable, required. The func to generate the cache key, will call this func when the key is needed.

* `invalid_keys`: Callable or None, default None. an invalid key that will store this key, use redis set,
and the key func before will be stored in this invalid key. If using Django , this invalid
key should be a models cache key, so when model invalid signal is called, all
keys in that invalid key will be invalid.

* `invalid_models`/`invalid_m2m_models`: List, default []. Models and m2m models that will trigger the invalid
signal, every model must has an invalid_key property(can be a list), and m2m model need m2m keys(see Model part).
And when signal is called, all members in the model instance invalid key will be removed.

* `hit`: callback when cache hit, need 3 arguments `(key, result, container)`

* `miss`: callback when cache miss, need 2 arguments `(key, container)`

* `tag`: string, default func name. using tag to get cache instance, then get all keys under that tag.

  ```
  from cacheme import cacheme_tags
  
  instance = cacheme_tags[tag]
  
  # get all keys
  keys = instance.keys
  
  # invalid all keys
  instance.invalid_all()
  ```

* `skip`: boolean or callable, default False. If value or callable value return true, will skip cache. For example,
you can cache result if request param has user, but return None directly, if no user.
* `timeout`: set ttl for this key, default `None`, if key contains '>', for example `Users:123>friends`, ttl will be set on main key `Users:123`



#### - Model property/attribute

To make invalid signal work, you need to define property for models that connect to signals in models.py.
As you can see in the example, a `cache_key` property is needed. And when invalid signal is triggered,
signal func will get this property value, add ':invalid' to it, and then invalid all keys store in this key.

```
class Book(models.Model):
    ...
	
    @property
    def cache_key(self):
        return "Book:%s" % self.id
```

This is enough for simple models, but for models include m2m field, we need some special rules. For example,
`Book` model has a m2m field to `User`, and if we do: `book.add(users)`, We have two update, first, book.users changed,
because a new user is add to this. Second, user.books also change, because this user has a new book. And on the other side,
if we do `user.add(books)`, also get two updates.
So if you take a look on [models.py](../master/tests/testapp/models.py), you will notice I add a `m2m_cache_keys` dict to through model,
that's because both `book.add()` and `user.add()` will trigger the [m2m invalid signal](https://docs.djangoproject.com/en/2.2/ref/signals/#m2m-changed), but the first one, signal `instance` will be book, and
`pk_set` will be users ids, and the second one, signal `instance` will be user, `pk_set` will be books ids. So the invalid keys is different
depend the `instance` in signal function.

```
Book.users.through.m2m_cache_keys = {

    # book is instance, so pk_set are user ids, used in signal book.add(users)
    'Book': lambda ids: ['User:%s:books' % id for id in ids],
	
    # user is instance, so pk_set are book ids, used in signal user.add(books)
    'TestUser': lambda ids: ['Book:%s:users' % id for id in ids],
    
}
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
