import unittest
from unittest.mock import patch

from pytetra.layer.phy.burst import (
    Burst,
    NormalContinuousDownlinkBurst,
    NormalDiscontinuousDownlinkBurst,
    SynchronizationContinuousDownlinkBurst,
    SynchronizationDiscontinuousDownlinkBurst,
    f,
    n,
    p,
    q,
    y,
)
from pytetra.layer.phy.phy import BURST_BITS, Phy
from pytetra.timebase import Timebase


def synchronization_burst():
    return (
        q[10:]
        + [0, 0]
        + f
        + [0] * 120
        + y
        + [0] * 30
        + [0] * 216
        + [0, 0]
        + q[:10]
    )


def normal_burst():
    return (
        q[10:]
        + [0, 0]
        + [0] * 216
        + [0] * 14
        + n
        + [0] * 16
        + [0] * 216
        + [0, 0]
        + q[:10]
    )


def synchronization_discontinuous_burst():
    return (
        q[-2:]
        + [0, 0]
        + f
        + [0] * 120
        + y
        + [0] * 30
        + [0] * 216
        + [0, 0]
        + q[:2]
    )


def normal_discontinuous_burst(training=n):
    return (
        q[-2:]
        + [0, 0]
        + [0] * 216
        + [0] * 14
        + training
        + [0] * 16
        + [0] * 216
        + [0, 0]
        + q[:2]
    )


class LowerMacRecorder:
    def __init__(self):
        self.calls = []

    def tp_sb_indication(self, sb, bb, bkn2):
        self.calls.append(("SB", sb, bb, bkn2))

    def tp_ndb_indication(self, bb, bkn1, bkn2, sf):
        self.calls.append(("NDB", bb, bkn1, bkn2, sf))


class StackStub:
    def __init__(self):
        self.lower_mac = LowerMacRecorder()


class PhyBurstTestCase(unittest.TestCase):
    def test_continuous_burst_lengths_and_types(self):
        sync = synchronization_burst()
        normal = normal_burst()

        self.assertEqual(len(sync), BURST_BITS)
        self.assertEqual(len(normal), BURST_BITS)
        self.assertIsInstance(Burst.parse(sync), SynchronizationContinuousDownlinkBurst)
        self.assertIsInstance(Burst.parse(normal), NormalContinuousDownlinkBurst)

    def test_discontinuous_burst_lengths_and_types(self):
        sync = synchronization_discontinuous_burst()
        normal = normal_discontinuous_burst()

        self.assertEqual(len(sync), 492)
        self.assertEqual(len(normal), 492)
        self.assertIsInstance(
            Burst.parse(sync),
            SynchronizationDiscontinuousDownlinkBurst,
        )
        self.assertIsInstance(Burst.parse(normal), NormalDiscontinuousDownlinkBurst)

    def test_burst_parser_rejects_wrong_length_and_non_binary_data(self):
        self.assertIsNone(Burst.parse(synchronization_burst()[:-1]))

        malformed = synchronization_burst()
        malformed[100] = 2
        self.assertIsNone(Burst.parse(malformed))

    def test_phy_delivers_sync_and_normal_bursts_to_lower_mac(self):
        stack = StackStub()
        phy = Phy(stack)
        phy.feed(synchronization_burst() + normal_burst())

        self.assertEqual([call[0] for call in stack.lower_mac.calls], ["SB", "NDB"])
        self.assertEqual(phy.sync_bursts, 1)
        self.assertEqual(phy.normal_bursts, 1)
        self.assertEqual(phy.bursts_decoded, 2)

    def test_aligned_rejection_preserves_next_burst_boundary(self):
        stack = StackStub()
        phy = Phy(stack, burst_aligned=True)
        phy.feed(
            synchronization_burst()
            + [0] * BURST_BITS
            + normal_burst()
        )

        self.assertEqual([call[0] for call in stack.lower_mac.calls], ["SB", "NDB"])
        self.assertEqual(phy.bursts_rejected, 1)
        self.assertEqual(phy.index, 3 * BURST_BITS)
        self.assertTrue(phy.locked)

    def test_initial_aligned_rejection_does_not_bit_slide(self):
        stack = StackStub()
        phy = Phy(stack, burst_aligned=True, log_layer1=False)
        phy.feed([0] * BURST_BITS + synchronization_burst())

        self.assertEqual([call[0] for call in stack.lower_mac.calls], ["SB"])
        self.assertEqual(phy.bursts_rejected, 1)
        self.assertEqual(phy.skipped_bits, 0)
        self.assertEqual(phy.index, 2 * BURST_BITS)

    def test_noisy_p_sequence_retains_stealing_flag(self):
        noisy_p = list(p)
        noisy_p[0] ^= 1
        burst = Burst.parse(normal_discontinuous_burst(noisy_p))

        self.assertEqual(burst.training_sequence, "P")
        self.assertTrue(burst.sf)
        self.assertEqual(burst.training_errors["p"], 1)

    @patch("pytetra.layer.layer.Logger.log")
    def test_layer1_log_is_readable_and_excludes_layer2_blocks(self, log):
        phy = Phy(StackStub(), log_layer1=True)
        phy.feed(synchronization_burst())

        message = log.call_args_list[0].args[0]
        self.assertTrue(message.startswith("SynchronizationContinuousDownlinkBurst"))
        self.assertIn("LengthBits(510)", message)
        self.assertIn("FrequencyCorrectionErrors(0)", message)
        self.assertNotIn("bkn", message.lower())
        self.assertNotIn("payload", message.lower())

    def test_phy_rejects_packed_or_corrupt_input_values(self):
        phy = Phy(StackStub())
        with self.assertRaises(ValueError):
            phy.feed([0, 1, 255])

    def test_timebase_update_validates_ranges_and_reports_distance(self):
        timebase = Timebase()
        self.assertEqual(timebase.update(1, 1, 1), 0)
        self.assertEqual(timebase.update(2, 1, 1), 1)
        self.assertEqual(timebase.dump_time(), "1/1/2")

        for values in ((0, 1, 1), (1, 19, 1), (1, 1, 61)):
            with self.assertRaises(ValueError):
                timebase.update(*values)


if __name__ == "__main__":
    unittest.main()
