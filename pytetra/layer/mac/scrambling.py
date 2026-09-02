from operator import xor, mul
from itertools import starmap
from functools import reduce


class Unscrambler(object):
    def __init__(self, extended_colour_code):
        c = [1, 1, 0, 1, 1, 0, 1, 1, 0, 1, 1, 1, 0, 0, 0, 1, 0, 0, 0, 0, 0, 1, 1, 0, 0, 1, 0, 0, 0, 0, 0, 1]
        p = [1, 1] + list(reversed(extended_colour_code))
        for i in range(432):
            p.append(reduce(xor, starmap(mul, zip(reversed(p[-32:]), c))))
        self.p = p[32:]

    def __call__(self, b5):
        return list(starmap(xor, zip(b5, self.p)))

    def confidence(self, values):
        """Apply scrambling to signed reliability by flipping its polarity."""
        return [(-float(value) if bit else float(value))
                for value, bit in zip(values, self.p)]
