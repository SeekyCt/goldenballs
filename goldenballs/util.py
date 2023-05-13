from random import randint
from typing import List, TypeVar


T = TypeVar('T')


def pop_random(list: List[T]) -> T:
    idx = randint(0, len(list) - 1)
    return list.pop(idx)
