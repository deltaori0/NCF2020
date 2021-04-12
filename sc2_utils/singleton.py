

__author__ = 'Hyunsoo Park, hspark8312@ncsoft.com, Game AI Lab, NCOSFT'


class Singleton(type):
    _instances = {}
 
    def __call__(cls, *args, **kwargs):
        if cls not in cls._instances:
            cls._instances[cls] = super(Singleton, cls).__call__(*args, **kwargs)
        return cls._instances[cls]


if __name__ == '__main__':

    # 싱글톤 사용예

    class BlackBoard(metaclass=Singleton):
        pass

    BlackBoard().test = 1
    assert BlackBoard().test == 1
    print(BlackBoard().test == 1)
    