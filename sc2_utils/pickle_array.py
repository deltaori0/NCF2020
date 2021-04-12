import pickle
import pickletools
import os

import joblib
import numpy as np


class BasePickler:
    def encode(self, obj):
        raise NotImplementedError

    def decode(self, dumped):
        raise NotImplementedError


class BasicPickler(BasePickler):
    def encode(self, obj):
        return pickle.dumps(obj, protocol=2)

    def decode(self, dumped):
        return pickle.loads(dumped)


class OptimizedPickler(BasePickler):
    def encode(self, obj):
        # 불필요한 put op 제거하여 용량 축소 및 로드 속도 향상
        # 자기참조를 가진 객체를 처리 못함
        # loads 할 때는 BASIC과 동일
        pickled = pickle.dumps(obj, protocol=pickle.HIGHEST_PROTOCOL)
        identical = pickletools.optimize(pickled)
        return identical

    def decode(self, dumped):
        return pickle.loads(dumped)


class PickleArray:
    def __init__(self, directory, size, len=1000, pickler_cls=OptimizedPickler):
        self.directory = Path(directory)
        self.size = size
        self.len = len
        self.pickler = pickler_cls()
        self.max_dump_size = 0

        self.path = self.directory / f'{self.len}.mem'
        mode = 'r+' if self.path.exists() else 'w+'
        self.mem = np.memmap(self.path, dtype=f'S{self.len}', mode=mode, shape=self.size)
        
    def __repr__(self):
        buff = f'path: {self.directory}\n'
        buff += f'shape: ({self.size}, {self.len})\n'
        buff += f'pickler: {self.pickler.__class__.__name__}\n'
        return buff

    def __setitem__(self, idx, obj):
        encoded_obj = self.pickler.encode(obj)
        self.max_dump_size = max(self.max_dump_size, len(encoded_obj))
        if len(encoded_obj) > self.len:
            self.expand(len(encoded_obj))
        self.mem[idx] = encoded_obj

    def __getitem__(self, idx):
        return self.pickler.decode(self.mem[idx])

    def expand(self, new_len):
        new_path = self.directory / f'{new_len}.mem'
        new_mem = np.memmap(new_path, dtype=f'S{new_len}', mode='w+', shape=self.size)
        new_mem[:] = self.mem

        self.mem._mmap.close()
        self.path.unlink()

        self.len = new_len
        self.path = new_path
        self.mem = new_mem




if __name__ == '__main__':

    import tempfile
    from IPython import embed
    from pathlib import Path

    size = 640000
    length = 900000

    root = Path('D:/pickle_array_test/')
    array1_path = root / 'array1'
    array1_path.mkdir(exist_ok=True)
    array1 = PickleArray(array1_path, size=size, len=length)
    
    for i in range(640000):
        xs = np.random.random((100, 1000))
        array1[i] = xs
        print(i, (array1[i] == xs).all())

    print(array1)
    embed()
