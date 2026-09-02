

# ETSI EN 300 392-2, clause 7.3: timebase counters.
class Timebase(object):
    def __init__(self):
        self.tn = 1  # Timeslot Number
        self.fn = 1  # TDMA Frame Number
        self.mn = 1  # TDMA Multiframe Number

    def increment(self):
        self.tn += 1
        if self.tn > 4:
            self.tn = 1
            self.fn += 1
            if self.fn > 18:
                self.fn = 1
                self.mn += 1
                if self.mn > 60:
                    self.mn = 1

    def update(self, tn, fn, mn):
        if not 1 <= tn <= 4:
            raise ValueError("Timeslot number must be in the range 1..4")
        if not 1 <= fn <= 18:
            raise ValueError("TDMA frame number must be in the range 1..18")
        if not 1 <= mn <= 60:
            raise ValueError("TDMA multiframe number must be in the range 1..60")

        missed = 0
        while not (tn == self.tn and fn == self.fn and mn == self.mn):
            self.increment()
            missed += 1

        return missed

    def dump_time(self):
        return '%s/%s/%s' % (self.mn, self.fn, self.tn)

    def dumpTime(self):
        """Compatibility alias for older callers."""
        return self.dump_time()

g_timebase = Timebase()
