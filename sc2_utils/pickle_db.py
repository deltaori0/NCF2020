#!/usr/bin/env python
""" 
PickleShare 를 기반으로 용도에 맞게 수정한 모듈

- PickleShare: a small 'shelve' like datastore with concurrency support
- https://github.com/pickleshare/pickleshare 

기존 PickleShare는 python 2와 호환성을 유지하기 위해 속도를 약간 희생하고 있었기 때문에,
호환성을 희생하는 대신 속도를 향상시키는 튜닝을 하였다.
"""

import collections.abc as collections_abc
import errno
import os
import pickle
import pickletools
import stat
import sys
import time
import heapq
from collections import OrderedDict
from enum import Enum
from pathlib import Path
from typing import Deque

import joblib

from .singleton import Singleton


class PickleMode(Enum):
    BASIC = 0
    OPTIMIZE = 1  # pickletools.optimize
    MEMMAP = 2  # joblib.dump
    COMPRESS = 3  # joblib.compress


class Pickler:
    def __init__(self, mode):
        self.mode = mode

    def dump(self, obj, f):
        if self.mode is PickleMode.BASIC:
            pickle.dump(obj, f, protocol=2)

        elif self.mode is PickleMode.OPTIMIZE:
            # 불필요한 put op 제거하여 용량 축소 및 로드 속도 향상
            # 자기참조를 가진 객체를 처리 못함
            # loads 할 때는 BASIC과 동일
            pickled = pickle.dumps(obj, protocol=pickle.HIGHEST_PROTOCOL)
            identical = pickletools.optimize(pickled)
            f.write(identical)

        elif self.mode is PickleMode.MEMMAP:
            # 가능하면 memory mapped file를 사용해서 속도 향상
            joblib.dump(obj, f, compress=False, protocol=pickle.HIGHEST_PROTOCOL)

        elif self.mode is PickleMode.COMPRESS:
            # 압축해서 용량감소, memory mapped file 사용 불가
            # joblib.dump(obj, f, compress='lz4', protocol=pickle.HIGHEST_PROTOCOL)
            joblib.dump(obj, f, compress=True, protocol=pickle.HIGHEST_PROTOCOL)

        else:
            raise NotImplementedError

    def loads(self, f):
        if self.mode in (PickleMode.BASIC, PickleMode.OPTIMIZE):
            return pickle.loads(f.read())

        elif self.mode in (PickleMode.MEMMAP, PickleMode.COMPRESS):
            return joblib.load(f)

        else:
            raise NotImplementedError


class Cache:

    def __init__(self, max_size):
        raise NotImplementedError

    def size(self):
        raise NotImplementedError

    def put(self, key, value):
        raise NotImplementedError

    def get(self, key, default=None):
        raise NotImplementedError

    def has(self, key):
        raise NotImplementedError

    def remove(self, key):
        raise NotImplementedError

    def clear(self):
        raise NotImplementedError

    def compact(self):
        raise NotImplementedError


class DictCache(Cache):
    def __init__(self, max_size):
        self.max_size = max_size
        self.dict = OrderedDict()

    def size(self):
        return len(self.dict)

    def put(self, key, value):
        self.dict[key] = value

    def get(self, key, default=None):
        return self.dict.get(key, default)

    def has(self, key):
        return key in self.dict

    def remove(self, key):
        self.dict.pop(key, None)

    def clear(self):
        self.dict = OrderedDict()

    def compact(self):
        # 캐시 크기 초과하면 가장 가장 오래된 아이템 삭제
        if self.size() > self.max_size:
            for key in self.dict.keys():
                self.dict.pop(key)
                break


def gethashfile(key):
    return ("%02x" % abs(hash(key) % 256))[-2:]


_sentinel = object()


class PickleDB(collections_abc.MutableMapping):
    """ The main 'connection' object for PickleShare database """

    def __init__(self, root, pickler=None, cache=None):
        """ Return a db object that will manage the specied directory"""
        if not isinstance(root, str):
            root = str(root)
        root = os.path.abspath(os.path.expanduser(root))
        self.root = Path(root)
        if not self.root.is_dir():
            # catching the exception is necessary
            # if multiple processes are concurrently trying to create a folder
            # exists_ok keyword argument of mkdir does the same but only from Python 3.5
            try:
                self.root.mkdir(parents=True)
            except OSError as e:
                if e.errno != errno.EEXIST:
                    raise

        # cache has { 'key' : (obj, orig_mod_time) }
        self.pickler = pickler if pickler else Pickler(PickleMode.MEMMAP)
        self.cache = cache if cache else DictCache(1000)

    def __getitem__(self, key):
        """ db['key'] reading """
        fil = self.root / key
        try:
            mtime = (fil.stat()[stat.ST_MTIME])
        except OSError:
            raise KeyError(key)

        # if fil in self.cache and mtime == self.cache[fil][1]:
        #     return self.cache[fil][0]
        if self.cache.has(fil) and mtime == self.cache.get(fil)[1]:
            return self.cache.get(fil)[0]

        try:
            # The cached item has expired, need to read
            with fil.open("rb") as f:
                # obj = pickle.loads(f.read())
                obj = self.pickler.loads(f)
        except:
            raise KeyError(key)

        # self.cache[fil] = (obj, mtime)
        # self.ensure_cache_size()
        self.cache.put(fil, (obj, mtime))
        self.cache.compact()
        return obj

    def __setitem__(self, key, value):
        """ db['key'] = value """
        fil = self.root / key
        parent = fil.parent
        if parent and not parent.is_dir():
            parent.mkdir(parents=True)

        with fil.open('wb') as f:
            self.pickler.dump(value, f)

        try:
            # self.cache[fil] = (value, fil.stat().st_mtime)
            # self.ensure_cache_size()
            self.cache.put(fil, (value, fil.stat().st_mtime))
            self.cache.compact()

        except OSError as e:
            if e.errno != errno.ENOENT:
                raise

    def uncache(self, *items):
        """ Removes all, or specified items from cache

        Use this after reading a large amount of large objects
        to free up memory, when you won't be needing the objects
        for a while.

        """
        if not items:
            # self.cache = OrderedDict()
            self.cache.clear()

        for it in items:
            # self.cache.pop(it, None)
            self.cache.remove(it)

    def hset(self, hashroot, key, value):
        """ hashed set """
        hroot = self.root / hashroot
        if not hroot.is_dir():
            hroot.mkdir()
        hfile = hroot / gethashfile(key)
        d = self.get(hfile, {})
        d.update({key: value})
        self[hfile] = d

    def hget(self, hashroot, key, default=_sentinel, fast_only=True):
        """ hashed get """
        hroot = self.root / hashroot
        hfile = hroot / gethashfile(key)

        d = self.get(hfile, _sentinel)
        #print "got dict",d,"from",hfile
        if d is _sentinel:
            if fast_only:
                if default is _sentinel:
                    raise KeyError(key)

                return default

            # slow mode ok, works even after hcompress()
            d = self.hdict(hashroot)

        return d.get(key, default)

    def hdict(self, hashroot):
        """ Get all data contained in hashed category 'hashroot' as dict """
        hfiles = self.keys(hashroot + "/*")
        hfiles.sort()
        last = len(hfiles) and hfiles[-1] or ''
        if last.endswith('xx'):
            # print "using xx"
            hfiles = [last] + hfiles[:-1]

        all = {}

        for f in hfiles:
            # print "using",f
            try:
                all.update(self[f])
            except KeyError:
                print("Corrupt", f, "deleted - hset is not threadsafe!")
                del self[f]

            self.uncache(f)

        return all

    def hcompress(self, hashroot):
        """ Compress category 'hashroot', so hset is fast again

        hget will fail if fast_only is True for compressed items (that were
        hset before hcompress).

        """
        hfiles = self.keys(hashroot + "/*")
        all = {}
        for f in hfiles:
            # print "using",f
            all.update(self[f])
            self.uncache(f)

        self[hashroot + '/xx'] = all
        for f in hfiles:
            p = self.root / f
            if p.name == 'xx':
                continue
            p.unlink()

    def __delitem__(self, key):
        """ del db["key"] """
        fil = self.root / key
        # self.cache.pop(fil, None)
        self.cache.remove(fil)
        try:
            fil.unlink()
        except OSError:
            # notfound and permission denied are ok - we
            # lost, the other process wins the conflict
            pass

    def _normalized(self, p):
        """ Make a key suitable for user's eyes """
        return str(p.relative_to(self.root)).replace('\\', '/')

    def keys(self, globpat=None):
        """ All keys in DB, or all keys matching a glob"""

        if globpat is None:
            files = self.root.rglob('*')
        else:
            files = self.root.glob(globpat)
        return [self._normalized(p) for p in files if p.is_file()]

    def __iter__(self):
        return iter(self.keys())

    def __len__(self):
        return len(self.keys())

    def waitget(self, key, maxwaittime=60):
        """ Wait (poll) for a key to get a value

        Will wait for `maxwaittime` seconds before raising a KeyError.
        The call exits normally if the `key` field in db gets a value
        within the timeout period.

        Use this for synchronizing different processes or for ensuring
        that an unfortunately timed "db['key'] = newvalue" operation
        in another process (which causes all 'get' operation to cause a
        KeyError for the duration of pickling) won't screw up your program
        logic.
        """

        wtimes = [0.2] * 3 + [0.5] * 2 + [1]
        tries = 0
        waited = 0
        while 1:
            try:
                val = self[key]
                return val
            except KeyError:
                pass

            if waited > maxwaittime:
                raise KeyError(key)

            time.sleep(wtimes[tries])
            waited += wtimes[tries]
            if tries < len(wtimes) - 1:
                tries += 1

    def getlink(self, folder):
        """ Get a convenient link for accessing items  """
        return PickleDBLink(self, folder)

    def __repr__(self):
        fmt = "PickleDB('%s') pickler: %s cache: %s"
        return fmt % (
            self.root, 
            self.pickler.mode, 
            self.cache.__class__.__name__)


class PickleDBLink:
    """ A shortdand for accessing nested PickleShare data conveniently.

    Created through PickleDB.getlink(), example::

        lnk = db.getlink('myobjects/test')
        lnk.foo = 2
        lnk.bar = lnk.foo + 5

    """

    def __init__(self, db, keydir):
        self.__dict__.update(locals())

    def __getattr__(self, key):
        return self.__dict__['db'][self.__dict__['keydir'] + '/' + key]

    def __setattr__(self, key, val):
        self.db[self.keydir + '/' + key] = val

    def __repr__(self):
        db = self.__dict__['db']
        keys = db.keys(self.__dict__['keydir'] + "/*")
        return "<PickleDBLink '%s': %s>" % (self.__dict__['keydir'], ";".join(
            [Path(k).name for k in keys]))


if __name__ == "__main__":

    import numpy as np
    from IPython import embed

    size = 640000
    length = 900000

    root = Path('D:/pickle_db_test/')
    db1_path = root / 'db1'
    db1_path.mkdir(parents=True, exist_ok=True)
    db1 = PickleDB(db1_path, Pickler(PickleMode.OPTIMIZE), DictCache(max_size=100))

    for i in range(640000):
        xs = np.random.random((100, 1000))
        db1[str(i)] = xs
        print(i, (db1[str(i)] == xs).all())

    print(db1)
    embed()
    exit()

    import numpy as np
    import tempfile
    from IPython import embed

    xs1 = np.random.random((1000, 1000))
    xs2 = np.zeros((1000, 1000))
    xs3 = [np.random.random((1000, 1000)) for i in range(10)]
    tmepdir = tempfile.mkdtemp()
    print('temp dir: %s' % tmepdir)

    dbs = list()

    for mode in (PickleMode.BASIC, PickleMode.OPTIMIZE,
                 PickleMode.MEMMAP, PickleMode.COMPRESS):
        db = PickleDB(tmepdir + f'/{mode.name}', Pickler(mode), DictCache(max_size=100))
        db['xs1'] = xs1
        db['xs2'] = xs2
        db['xs3'] = xs3
        db.uncache()
        dbs.append(db)

    for db in dbs:
        print(db)
        print((db['xs1'] == xs1).all())
        print((db['xs2'] == xs2).all())
        print((db['xs3'][0] == xs3[0]).all(), (db['xs3'][1] == xs3[1]).all())

    db = dbs[2]
    for i in range(1000):
        db[str(i)] = np.random.random(100)
        print(i, db.cache.size(), list(db.cache.dict.keys())[0])

    print('!!!!')

    import tempfile
    tmpdir = tempfile.mkdtemp()
    print('temp dir: %s' % tmpdir)
    db = PickleDB(tmepdir + f'/{mode.name}')
    db.clear()
    print("Should be empty:", db.items())
    assert len(db) == 0
    db['hello'] = 15
    assert db['hello'] == 15
    db['aku ankka'] = [1, 2, 313]
    assert db['aku ankka'] == [1, 2, 313]
    db['paths/nest/ok/keyname'] = [1, (5, 46)]
    assert db['paths/nest/ok/keyname'] == [1, (5, 46)]

    db.hset('hash', 'aku', 12)
    db.hset('hash', 'ankka', 313)
    assert db.hget('hash', 'aku') == 12
    assert db.hget('hash', 'ankka') == 313

    print("all hashed", db.hdict('hash'))
    print(db.keys())
    print(db.keys('paths/nest/ok/k*'))
    print(dict(db))  # snapsot of whole db
    db.uncache()  # frees memory, causes re-reads later

    # shorthand for accessing deeply nested files
    lnk = db.getlink('myobjects/test')
    lnk.foo = 2
    lnk.bar = lnk.foo + 5
    assert lnk.bar == 7

    db = PickleDB(tmpdir)
    import time, sys
    for i in range(100):
        for j in range(500):
            if i % 15 == 0 and i < 70:
                if str(j) in db:
                    del db[str(j)]
                continue

            if j % 33 == 0:
                time.sleep(0.02)

            db[str(j)] = db.get(str(j), []) + [(i, j, "proc %d" % os.getpid())]
            db.hset('hash', j, db.hget('hash', j, 15) + 1)

        print(i, end=' ')
        sys.stdout.flush()
        if i % 10 == 0:
            db.uncache()
