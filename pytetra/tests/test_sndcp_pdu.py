import unittest
from unittest.mock import patch

from pytetra.layer.sndcp import (
    ReassembledNpdu,
    SnDataPdu,
    SnUnitdataPdu,
    Sndcp,
    SndcpPdu,
)
from pytetra.pdu import Bits, PduDecodingException


class UserRecorder:
    def __init__(self):
        self.pdus = []

    def pdu_indication(self, layer, pdu):
        self.pdus.append((layer, pdu))


class StackStub:
    def __init__(self):
        self.user = UserRecorder()


def unitdata(f, m, segment, npdu, data, nsapi=3, dcomp=1, pcomp=2):
    common = "0%d1%d%s" % (f, m, format(nsapi, "04b"))
    compression = format(dcomp, "04b") + format(pcomp, "04b") if f else ""
    sequence = format(segment, "04b") + format(npdu, "012b")
    return Bits(common + compression + sequence + data)


class SndcpPduTestCase(unittest.TestCase):
    def test_short_common_header_is_rejected(self):
        with self.assertRaises(PduDecodingException):
            SndcpPdu.parse(Bits("0101010"))

    def test_sn_data_is_preserved(self):
        pdu = SndcpPdu.parse(Bits("00000011" + "10101"))
        self.assertIsInstance(pdu, SnDataPdu)
        self.assertEqual(pdu.payload, Bits("10101"))

    def test_sn_unitdata_fields(self):
        pdu = SndcpPdu.parse(unitdata(1, 0, 0, 17, "10101010"))
        self.assertIsInstance(pdu, SnUnitdataPdu)
        self.assertEqual(pdu.nsapi, 3)
        self.assertEqual(pdu.dcomp, 1)
        self.assertEqual(pdu.pcomp, 2)
        self.assertEqual(pdu.segment_number, 0)
        self.assertEqual(pdu.npdu_number, 17)
        self.assertEqual(pdu.data, Bits("10101010"))

    @patch("pytetra.layer.layer.Logger.log")
    def test_unitdata_segments_reassemble_without_inventing_bits(self, _log):
        stack = StackStub()
        sndcp = Sndcp(stack)
        sndcp.mle_unitdata_indication(unitdata(1, 1, 0, 17, "1010"))
        sndcp.mle_unitdata_indication(unitdata(0, 0, 1, 17, "0110"))

        complete = [p for _, p in stack.user.pdus if isinstance(p, ReassembledNpdu)]
        self.assertEqual(len(complete), 1)
        self.assertEqual(complete[0].data, Bits("10100110"))

    @patch("pytetra.layer.layer.Logger.log")
    def test_orphan_continuation_is_not_reassembled(self, _log):
        stack = StackStub()
        sndcp = Sndcp(stack)
        sndcp.mle_unitdata_indication(unitdata(0, 0, 1, 17, "0110"))
        self.assertFalse(
            any(isinstance(p, ReassembledNpdu) for _, p in stack.user.pdus)
        )


if __name__ == "__main__":
    unittest.main()
