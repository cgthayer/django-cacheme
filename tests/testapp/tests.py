import pickle

import redis
from django.conf import settings
from django.test import TestCase
from django_redis import get_redis_connection

from .models import TestUser
from django_cacheme import cacheme

r = redis.Redis()


class CacheTestCase(TestCase):

    def tearDown(self):
        connection = get_redis_connection(settings.CACHEME['REDIS_CACHE_ALIAS'])
        connection.flushdb(settings.CACHEME['REDIS_CACHE_TEST_DB'])

    @cacheme(
        key=lambda c: "Test:123",
        invalid_keys=lambda c: ["User:%s" % c.user1.id],
        invalid_models=[TestUser]
    )
    def cache_test_func1(self, user1, user2):
        return {'results': [{'id': user1.id}, {'id': user2.id}], 'check': self.check}

    @cacheme(
        key=lambda c: "Test:456",
        invalid_keys=lambda c: ["User:%s" % c.user1.id],
        invalid_models=[TestUser],
        override=lambda c: "User:%s" % c.user2.id
    )
    def cache_test_func2(self, user1, user2):
        return {'results': [{'id': user1.id}, {'id': user2.id}], 'check': self.check}

    @cacheme(
        key=lambda c: str(c.self.pp + c.a + c.args[0] + c.kwargs['ff']),
    )
    def cache_bind_func(self, a, *args, **kwargs):
        return self.pp + a + args[0] + kwargs['ff']

    def test_cache_simple(self):
        user1 = TestUser.objects.create(name='test1')
        user2 = TestUser.objects.create(name='test2')
        self.check = 1

        expect = {'results': [{'id': user1.id}, {'id': user2.id}], 'check': 1}

        result = self.cache_test_func1(user1, user2)
        self.assertEqual(result, expect)

        conn = get_redis_connection(settings.CACHEME['REDIS_CACHE_ALIAS'])
        result = conn.hget(settings.CACHEME['REDIS_CACHE_PREFIX'] + 'Test:123', 'base')
        self.assertEqual(pickle.loads(result), expect)

        self.check = 2

        # still using cache, so old value
        result = self.cache_test_func1(user1, user2)
        self.assertEqual(result, expect)

        # user1 signal triggered, so cache invalid now
        user1.name += 'cc'
        user1.save()
        expect['check'] = 2
        result = self.cache_test_func1(user1, user2)
        self.assertEqual(result, expect)

        # no signal for user2, still using cache
        self.check = 3
        user2.name += 'cc'
        user2.save()
        result = self.cache_test_func1(user1, user2)
        self.assertEqual(result, expect)

    def test_cache_override(self):
        user1 = TestUser.objects.create(name='test1')
        user2 = TestUser.objects.create(name='test2')

        self.check = 1

        expect = {'results': [{'id': user1.id}, {'id': user2.id}], 'check': 1}

        result = self.cache_test_func2(user1, user2)
        self.assertEqual(result, expect)

        conn = get_redis_connection(settings.CACHEME['REDIS_CACHE_ALIAS'])
        result = conn.hget(settings.CACHEME['REDIS_CACHE_PREFIX'] + 'Test:456', 'base')
        self.assertEqual(pickle.loads(result), {'redis_key': 'TEST:User:%s' % user2.id})

        result = conn.hget('TEST:User:%s' % user2.id, 'base')
        self.assertEqual(pickle.loads(result), expect)

        self.check = 2

        user1.name += 'cc'
        user1.save()
        expect['check'] = 2
        conn = get_redis_connection(settings.CACHEME['REDIS_CACHE_ALIAS'])
        result = conn.hget(settings.CACHEME['REDIS_CACHE_PREFIX'] + 'Test:456', 'base')
        self.assertEqual(result, None)

        result = self.cache_test_func2(user1, user2)
        self.assertEqual(result, expect)

    def test_cache_arguments_bind(self):
        self.pp = 3
        result = self.cache_bind_func(1, 2, ff=14, qq=5)
        self.assertEqual(result, 20)
        conn = get_redis_connection(settings.CACHEME['REDIS_CACHE_ALIAS'])
        result = conn.hget(settings.CACHEME['REDIS_CACHE_PREFIX'] + '20', 'base')
        self.assertEqual(pickle.loads(result), 20)
