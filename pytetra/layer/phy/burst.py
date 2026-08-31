#!/usr/bin/env python

# 9.4.4.3.1 Frequency correction bits
f = [1] * 8 + [0] * 64 + [1] * 8
# 9.4.4.3.2 Normal training sequence
n = [1, 1, 0, 1, 0, 0, 0, 0, 1, 1, 1, 0, 1, 0, 0, 1, 1, 1, 0, 1, 0, 0]
p = [0, 1, 1, 1, 1, 0, 1, 0, 0, 1, 0, 0, 0, 0, 1, 1, 0, 1, 1, 1, 1, 0]
q = [1, 0, 1, 1, 0, 1, 1, 1, 0, 0, 0, 0, 0, 1, 1, 0, 1, 0, 1, 1, 0, 1]
# 9.4.4.3.4 Synchronization training sequence
y = [1, 1, 0, 0, 0, 0, 0, 1, 1, 0, 0, 1, 1, 1, 0, 0, 1, 1, 1, 0, 1, 0, 0, 1, 1, 1, 0, 0, 0, 0, 0, 1, 1, 0, 0, 1, 1, 1]

def bit_errors(a, b):
    return abs(len(a) - len(b)) + sum(x != y for x, y in zip(a, b))


class TrainingSequenceError(Exception):
    pass


class Burst(object):
    def __init__(self, bits):
        expected_length = sum(size for _, size in self.fields_desc)
        if len(bits) != expected_length:
            raise TrainingSequenceError(
                "Expected %d bits, received %d"
                % (expected_length, len(bits))
            )
        if any(bit not in (0, 1) for bit in bits):
            raise TrainingSequenceError("Burst contains non-binary values")

        self.fields = {}
        i = 0
        for name, size in self.fields_desc:
            self.fields[name] = bits[i:i + size]
            i += size
        if not self.check():
            raise TrainingSequenceError("Training sequence check failed")

    def __getattr__(self, attr):
        if attr in self.fields:
            return self.fields[attr]
        else:
            raise AttributeError

    @staticmethod
    def bits_to_string(bits):
        return ''.join(str(bit) for bit in bits)

    def layer1_fields(self):
        """Return interpreted PHY fields without coded Layer-2 blocks."""
        raise NotImplementedError

    @classmethod
    def parse(cls, bits):
        for burst_cls in [
            SynchronizationContinuousDownlinkBurst,
            NormalContinuousDownlinkBurst,
            SynchronizationDiscontinuousDownlinkBurst,
            NormalDiscontinuousDownlinkBurst,
        ]:
            try:
                burst = burst_cls(bits)
                return burst
            except TrainingSequenceError:
                pass

        return None


# 9.4.4.2.5 Normal continuous downlink self
class NormalContinuousDownlinkBurst(Burst):
    fields_desc = [
        ('q1', 12),
        ('ha', 2),
        ('bkn1', 216),
        ('bb1', 14),
        ('n_p', 22),
        ('bb2', 16),
        ('bkn2', 216),
        ('hb', 2),
        ('q2', 10),
    ]

    def __init__(self, bits):
        super(NormalContinuousDownlinkBurst, self).__init__(bits)

        self.bb = self.bb1 + self.bb2

        q_errors = bit_errors(self.q2 + self.q1, q)
        n_errors = bit_errors(self.n_p, n)
        p_errors = bit_errors(self.n_p, p)

        self.training_errors = {
            'q': q_errors,
            'n': n_errors,
            'p': p_errors,
        }
        self.training_sequence = 'P' if p_errors < n_errors else 'N'
        self.sf = self.training_sequence == 'P'

    def layer1_fields(self):
        return {
            'transmission': 'continuous',
            'edge_training_sequence': 'Q',
            'q_errors': self.training_errors['q'],
            'training_sequence': self.training_sequence,
            'training_errors': min(
                self.training_errors['n'],
                self.training_errors['p'],
            ),
            'stealing_flag': int(self.sf),
            'phase_start': self.bits_to_string(self.ha),
            'phase_end': self.bits_to_string(self.hb),
        }

    def check(self):
        q_errors = bit_errors(self.q2 + self.q1, q)
        n_errors = bit_errors(self.n_p, n)
        p_errors = bit_errors(self.n_p, p)

        return q_errors <= 2 and min(n_errors, p_errors) <= 2


# 9.4.4.2.6 Synchronization continuous downlink self
class SynchronizationContinuousDownlinkBurst(Burst):
    fields_desc = [
        ('q1', 12),
        ('hc', 2),
        ('f', 80),
        ('sb', 120),
        ('y', 38),
        ('bb', 30),
        ('bkn2', 216),
        ('hd', 2),
        ('q2', 10),
    ]

    def check(self):
        self.training_errors = {
            'q': bit_errors(self.q2 + self.q1, q),
            'frequency': bit_errors(self.f, f),
            'synchronization': bit_errors(self.y, y),
        }
        return (
            self.training_errors['q'] <= 2
            and self.training_errors['frequency'] <= 4
            and self.training_errors['synchronization'] <= 2
        )

    def layer1_fields(self):
        return {
            'transmission': 'continuous',
            'edge_training_sequence': 'Q',
            'q_errors': self.training_errors['q'],
            'frequency_correction_sequence': 'F',
            'frequency_correction_errors': self.training_errors['frequency'],
            'synchronization_sequence': 'Y',
            'synchronization_errors': self.training_errors['synchronization'],
            'phase_start': self.bits_to_string(self.hc),
            'phase_end': self.bits_to_string(self.hd),
        }


# 9.4.4.2.7 Normal discontinuous downlink self
class NormalDiscontinuousDownlinkBurst(Burst):
    fields_desc = [
        ('q1', 2),
        ('hg', 2),
        ('bkn1', 216),
        ('bb1', 14),
        ('n_p', 22),
        ('bb2', 16),
        ('bkn2', 216),
        ('hh', 2),
        ('q2', 2),
    ]

    def __init__(self, bits):
        super(NormalDiscontinuousDownlinkBurst, self).__init__(bits)
        self.bb = self.bb1 + self.bb2
        n_errors = bit_errors(self.n_p, n)
        p_errors = bit_errors(self.n_p, p)
        self.training_sequence = 'P' if p_errors < n_errors else 'N'
        self.sf = self.training_sequence == 'P'

    def layer1_fields(self):
        return {
            'transmission': 'discontinuous',
            'edge_training_sequence': 'Q',
            'q_start_errors': self.training_errors['q_start'],
            'q_end_errors': self.training_errors['q_end'],
            'training_sequence': self.training_sequence,
            'training_errors': min(
                self.training_errors['n'],
                self.training_errors['p'],
            ),
            'stealing_flag': int(self.sf),
            'phase_start': self.bits_to_string(self.hg),
            'phase_end': self.bits_to_string(self.hh),
        }

    def check(self):
        q1_errors = bit_errors(self.q1, q[-2:])
        q2_errors = bit_errors(self.q2, q[:2])
        n_errors = bit_errors(self.n_p, n)
        p_errors = bit_errors(self.n_p, p)

        self.training_errors = {
            'q_start': q1_errors,
            'q_end': q2_errors,
            'n': n_errors,
            'p': p_errors,
        }
        return (
            q1_errors <= 1
            and q2_errors <= 1
            and min(n_errors, p_errors) <= 2
        )


# 9.4.4.2.8 Synchronization discontinuous downlink self
class SynchronizationDiscontinuousDownlinkBurst(Burst):
    fields_desc = [
        ('q1', 2),
        ('hi', 2),
        ('f', 80),
        ('sb', 120),
        ('y', 38),
        ('bb', 30),
        ('bkn2', 216),
        ('hj', 2),
        ('q2', 2),
    ]

    def check(self):
        self.training_errors = {
            'q_start': bit_errors(self.q1, q[-2:]),
            'q_end': bit_errors(self.q2, q[:2]),
            'frequency': bit_errors(self.f, f),
            'synchronization': bit_errors(self.y, y),
        }
        return (
            self.training_errors['q_start'] <= 1
            and self.training_errors['q_end'] <= 1
            and self.training_errors['frequency'] <= 4
            and self.training_errors['synchronization'] <= 2
        )

    def layer1_fields(self):
        return {
            'transmission': 'discontinuous',
            'edge_training_sequence': 'Q',
            'q_start_errors': self.training_errors['q_start'],
            'q_end_errors': self.training_errors['q_end'],
            'frequency_correction_sequence': 'F',
            'frequency_correction_errors': self.training_errors['frequency'],
            'synchronization_sequence': 'Y',
            'synchronization_errors': self.training_errors['synchronization'],
            'phase_start': self.bits_to_string(self.hi),
            'phase_end': self.bits_to_string(self.hj),
        }


# Compatibility aliases for the misspelling used by older PyTetra versions.
NormalDisontinuousDownlinkBurst = NormalDiscontinuousDownlinkBurst
SynchronizationDisontinuousDownlinkBurst = (
    SynchronizationDiscontinuousDownlinkBurst
)
