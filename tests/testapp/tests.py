import pickle

import redis
from unittest.mock import MagicMock
from django.conf import settings
from django.test import TestCase
from django_redis import get_redis_connection

from .models import TestUser, Book
from django_cacheme import cacheme, cacheme_tags
from django_cacheme.models import Invalidation

r = redis.Redis()


hit = MagicMock()
miss = MagicMock()


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

        # lazy invalid, so if we get value directly, still old value
        result = conn.hget(settings.CACHEME['REDIS_CACHE_PREFIX'] + 'Test:123', 'base')
        self.assertEqual(pickle.loads(result), expect)
        deletes = conn.smembers(settings.CACHEME['REDIS_CACHE_PREFIX'] + ':delete')
        self.assertTrue(b'TEST:Test:123' in deletes)

        expect['check'] = 2
        result = self.cache_test_func1(user1, user2)
        self.assertEqual(result, expect)

        # no signal for user2, still using cache
        self.check = 3
        user2.name += 'cc'
        user2.save()
        result = self.cache_test_func1(user1, user2)
        self.assertEqual(result, expect)

    def test_cache_arguments_bind(self):
        self.pp = 3
        result = self.cache_bind_func(1, 2, ff=14, qq=5)
        self.assertEqual(result, 20)
        conn = get_redis_connection(settings.CACHEME['REDIS_CACHE_ALIAS'])
        result = conn.hget(settings.CACHEME['REDIS_CACHE_PREFIX'] + '20', 'base')
        self.assertEqual(pickle.loads(result), 20)

    @cacheme(
        key=lambda c: "Test:123",
        hit=hit,
        miss=miss
    )
    def cache_test_func_hit_miss(self):
        return 'test'

    def test_cache_hit_miss(self):
        self.cache_test_func_hit_miss()
        self.assertEqual(miss.call_count, 1)
        hit.assert_not_called()
        self.cache_test_func_hit_miss()
        self.assertEqual(miss.call_count, 1)
        self.assertEqual(hit.call_count, 1)

    @cacheme(
        key=lambda c: "Test:m2m",
        invalid_keys=lambda c: ["Book:%s:users" % c.book.id],
        invalid_m2m_models=[Book.users.through]
    )
    def cache_m2m_func(self, book):
        return {'users': [u.id for u in book.users.all()]}

    def test_m2m_cache(self):
        user1 = TestUser.objects.create(name='test1')
        user2 = TestUser.objects.create(name='test2')

        book = Book.objects.create(name='book')
        book.users.add(user1, user2)
        result = self.cache_m2m_func(book)
        self.assertEqual(result, {'users': [user1.id, user2.id]})
        book.users.remove(user1)
        result = self.cache_m2m_func(book)
        self.assertEqual(result, {'users': [user2.id]})

    @cacheme(
        key=lambda c: "INST:1"
    )
    def cache_inst_1(self):
        return 'test'

    @cacheme(
        key=lambda c: "INST:2",
        tag='test_instance_sec'
    )
    def cache_inst_2(self):
        return 'test'

    @cacheme(
        key=lambda c: "INST:3",
        tag='three'
    )
    def cache_inst_3(self):
        return 'test'

    def test_instances(self):
        self.cache_inst_1()
        self.cache_inst_2()
        self.cache_inst_3()
        self.assertEqual(cacheme_tags['cache_inst_1'].keys, {b'TEST:INST:1'})
        self.assertEqual(cacheme_tags['test_instance_sec'].keys, {b'TEST:INST:2'})
        self.assertEqual(cacheme_tags['three'].keys, {b'TEST:INST:3'})

    def test_invalidation_model(self):
        conn = get_redis_connection(settings.CACHEME['REDIS_CACHE_ALIAS'])
        conn.set('TEST:PATTERN:1', 1)
        conn.set('TEST:PATTERN:2', 2)
        conn.set('TEST:ANOTHER:3', 3)

        self.assertEqual(conn.get('TEST:PATTERN:1'), b'1')
        self.assertEqual(conn.get('TEST:PATTERN:2'), b'2')
        self.assertEqual(conn.get('TEST:ANOTHER:3'), b'3')

        Invalidation.objects.create(pattern='TEST:PATTERN*')

        self.assertEqual(conn.get('TEST:PATTERN:1'), None)
        self.assertEqual(conn.get('TEST:PATTERN:2'), None)
        self.assertEqual(conn.get('TEST:ANOTHER:3'), b'3')
