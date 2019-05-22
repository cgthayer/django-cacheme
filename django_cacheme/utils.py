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


def invalid_cache(sender, instance, created=False, **kwargs):
    # for manytomany pre signal, do nothing
    m2m = False
    if 'pre_' in kwargs.get('action', ''):
        return
    if kwargs.get('action', False):
        m2m = True

    if CACHEME.ENABLE_CACHE and instance.cache_key:
        conn = get_redis_connection(CACHEME.REDIS_CACHE_ALIAS)
        keys = instance.cache_key
        if type(instance.cache_key) == str:
            keys = [keys]
        for key in keys:
            if m2m and sender.suffix:
                key = key + ':' + sender.suffix
            key = CACHEME.REDIS_CACHE_PREFIX + key + ':invalid'
            invalid_keys = conn.smembers(key)
            if invalid_keys:
                conn.sadd(CACHEME.REDIS_CACHE_PREFIX + ':delete', *invalid_keys)


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
