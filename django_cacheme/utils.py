from django.conf import settings
from django_redis import get_redis_connection


CACHEME = {
    'REDIS_CACHE_PREFIX': 'CM',  # key prefix for cache
    'REDIS_CACHE_SCAN_COUNT': 10
}

CACHEME.update(getattr(settings, 'CACHEME', {}))
CACHEME = type('CACHEME', (), CACHEME)


def split_key(string):
    lg = b'>' if type(string) == bytes else '>'
    if lg in string:
        return string.split(lg)[:2]
    return [string, 'base']


def invalid_keys_in_set(key, conn=None):
    if not conn:
        conn = get_redis_connection(CACHEME.REDIS_CACHE_ALIAS)
    key = CACHEME.REDIS_CACHE_PREFIX + key + ':invalid'
    invalid_keys = conn.smembers(key)
    if invalid_keys:
        conn.sadd(CACHEME.REDIS_CACHE_PREFIX + ':delete', *invalid_keys)


def invalid_cache(sender, instance, created=False, **kwargs):
    # for manytomany pre signal, do nothing
    if not CACHEME.ENABLE_CACHE:
        return

    m2m = False
    if 'pre_' in kwargs.get('action', ''):
        return
    if kwargs.get('action', False):
        m2m = True

    conn = get_redis_connection(CACHEME.REDIS_CACHE_ALIAS)

    if not m2m and instance.cache_key:
        keys = instance.cache_key
        if type(instance.cache_key) == str:
            keys = [keys]
        for key in keys:
            invalid_keys_in_set(key, conn)

    if m2m:
        name = instance.__class__.__name__
        m2m_cache_keys = sender.m2m_cache_keys.copy()
        to_invalid_keys = m2m_cache_keys.pop(name)(kwargs.get('pk_set', []))
        from_invalid_key = list(m2m_cache_keys.values())[0]([instance.id])
        all = from_invalid_key + to_invalid_keys
        for key in all:
            invalid_keys_in_set(key, conn)


def flat_list(li):
    if type(li) not in (list, tuple, set):
        li = [li]

    result = []
    for e in li:
        if type(e) in (list, tuple, set):
            result += flat_list(e)
        else:
            result.append(e)
    return result


def chunk_iter(iterator, size, stop):
    while True:
        result = {next(iterator, stop) for i in range(size)}
        if stop in result:
            result.remove(stop)
            yield result
            break
        yield result


def invalid_pattern(pattern):
    conn = get_redis_connection(CACHEME.REDIS_CACHE_ALIAS)
    chunks = chunk_iter(conn.scan_iter(pattern, count=CACHEME.REDIS_CACHE_SCAN_COUNT), 500, None)
    for keys in chunks:
        if keys:
            conn.unlink(*list(keys))
