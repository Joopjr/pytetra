import unittest
from unittest.mock import patch

from pytetra.layer.llc.fcs import compute_fcs
from pytetra.layer.llc.llc import Llc
from pytetra.layer.llc.pdu import (
    LlcPdu,
    BlADataPdu,
    BlDataPdu,
    BlUDataPdu,
    BlAckPdu,
    BlADataFcsPdu,
    BlDataFcsPdu,
    BlUDataFcsPdu,
    BlAckFcsPdu,
    AlSetupPdu,
    AlDataPdu,
    AlUDataPdu,
    AlAckPdu,
    AlReconnectPdu,
    LlcReservedPdu13,
    LlcReservedPdu14,
    AlDiscPdu,
)
from pytetra.pdu import Bits, PduDecodingException


class MleRecorder:
    def __init__(self):
        self.sdus = []

    def tl_unitdata_indication(self, sdu):
        self.sdus.append(sdu.bits)

    def tl_sync_indication(self, sdu):
        pass

    def tl_sysinfo_indication(self, sdu):
        pass


class UserRecorder:
    def __init__(self):
        self.pdus = []

    def pdu_indication(self, layer, pdu):
        self.pdus.append((layer, pdu))


class StackStub:
    def __init__(self):
        self.debug_llc = False
        self.mle = MleRecorder()
        self.user = UserRecorder()


def with_fcs(type_bits, payload):
    protected = type_bits + payload
    return protected + compute_fcs(protected)


class LlcPduTestCase(unittest.TestCase):
    def test_crc32_reference_vector(self):
        data = "".join(format(byte, "08b") for byte in b"123456789")
        self.assertEqual(compute_fcs(data), format(0xFC891918, "032b"))

    def test_all_downlink_discriminators_dispatch(self):
        vectors = {
            0: ("00", BlADataPdu),
            1: ("0", BlDataPdu),
            2: ("", BlUDataPdu),
            3: ("0", BlAckPdu),
            4: (with_fcs("0100", "00")[4:], BlADataFcsPdu),
            5: (with_fcs("0101", "0")[4:], BlDataFcsPdu),
            6: (with_fcs("0110", "")[4:], BlUDataFcsPdu),
            7: (with_fcs("0111", "0")[4:], BlAckFcsPdu),
            8: ("10000000000010000000000", AlSetupPdu),
            9: ("0000000000000", AlDataPdu),
            10: ("00000000000000000", AlUDataPdu),
            11: ("0", AlAckPdu),
            12: ("00000", AlReconnectPdu),
            13: ("", LlcReservedPdu13),
            14: ("", LlcReservedPdu14),
            15: ("000000", AlDiscPdu),
        }

        for pdu_type, (payload, expected_class) in vectors.items():
            with self.subTest(pdu_type=pdu_type):
                bits = format(pdu_type, "04b") + payload
                self.assertIsInstance(LlcPdu(Bits(bits)), expected_class)

    def test_truncated_fcs_pdu_is_rejected(self):
        with self.assertRaises(PduDecodingException):
            LlcPdu(Bits("0110" + "0" * 31))

    @patch("pytetra.layer.layer.Logger.log")
    def test_basic_link_udata_is_delivered(self, _log):
        stack = StackStub()
        llc = Llc(stack)
        llc.tma_unitdata_indication(Bits("0010" + "101011"))

        self.assertEqual(stack.mle.sdus, ["101011"])
        self.assertEqual(llc.delivered_sdus, 1)

    @patch("pytetra.layer.layer.Logger.log")
    def test_valid_fcs_is_delivered_and_invalid_fcs_is_dropped(self, _log):
        stack = StackStub()
        llc = Llc(stack)
        valid = with_fcs("0110", "101011")
        invalid = valid[:-1] + ("1" if valid[-1] == "0" else "0")

        llc.tma_unitdata_indication(Bits(valid))
        llc.tma_unitdata_indication(Bits(invalid))

        self.assertEqual(stack.mle.sdus, ["101011"])
        self.assertEqual(llc.fcs_passes, 1)
        self.assertEqual(llc.fcs_failures, 1)

    @patch("pytetra.layer.layer.Logger.log")
    def test_advanced_link_segments_are_reassembled_on_final(self, _log):
        stack = StackStub()
        llc = Llc(stack)
        first = "1001" + "00" + "000" + "00000000" + "101"
        final = "1001" + "10" + "000" + "00000001" + "011"

        llc.tma_unitdata_indication(Bits(first))
        self.assertEqual(stack.mle.sdus, [])

        llc.tma_unitdata_indication(Bits(final))
        self.assertEqual(stack.mle.sdus, ["101011"])


if __name__ == "__main__":
    unittest.main()
