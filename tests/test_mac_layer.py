import unittest
from collections import OrderedDict
from unittest.mock import patch

from pytetra.layer.mac.pdu import MacPdu, MacResourcePdu
from pytetra.logger import Logger
from pytetra.pdu import Bits
from pytetra.stack import TetraStack
from pytetra.layer.user import UserLayer
from pytetra.summary import format_chain


class RecordingUser(UserLayer):
    def __init__(self, stack):
        super(RecordingUser, self).__init__(stack)
        self.records = []
        self.summaries = []

    def pdu_indication(self, layer, pdu):
        self.records.append((layer, pdu))

    def burst_summary_indication(self, chains):
        self.summaries.extend(chains)


class Layer3Probe(object):
    def __init__(self, stack):
        self.stack = stack

    def tma_unitdata_indication(self, sdu):
        self.stack.mle.expose_pdu("DownstreamProbe")

    def tmb_sysinfo_indication(self, sdu):
        self.stack.mle.expose_pdu("SysinfoDownstreamProbe")


class MacLayerTestCase(unittest.TestCase):
    @staticmethod
    def _resource_with_ssi(ssi):
        pdu = object.__new__(MacResourcePdu)
        pdu.fields = OrderedDict((
            ("length_indication", 4),
            ("address_type", 1),
            ("ssi", ssi),
            ("encryption_mode", 0),
            ("sdu", Bits("0000")),
        ))
        return pdu

    def test_zero_ssi_hides_layer2_and_downstream_layer3(self):
        stack = TetraStack(RecordingUser, debug=False)
        stack.llc = Layer3Probe(stack)

        stack.upper_mac._handle_data_pdu(self._resource_with_ssi(0))

        self.assertEqual(stack.user.records, [])

    def test_missing_ssi_hides_layer2_and_downstream_layer3(self):
        stack = TetraStack(RecordingUser, debug=False)
        stack.llc = Layer3Probe(stack)

        stack.upper_mac._handle_data_pdu(self._resource_with_ssi(None))

        self.assertEqual(stack.user.records, [])

    def test_broadcast_ssi_hides_layer2_and_downstream_layer3(self):
        stack = TetraStack(RecordingUser, debug=False)
        stack.llc = Layer3Probe(stack)

        stack.upper_mac._handle_data_pdu(self._resource_with_ssi(0xFFFFFF))

        self.assertEqual(stack.user.records, [])

    def test_debug_shows_zero_ssi_and_downstream_layer3(self):
        stack = TetraStack(RecordingUser, debug=True)
        stack.llc = Layer3Probe(stack)

        stack.upper_mac._handle_data_pdu(self._resource_with_ssi(0))

        self.assertEqual(
            [layer for layer, unused in stack.user.records],
            ["UpperMac", "Mle"],
        )

    def test_debug_shows_missing_ssi_and_downstream_layer3(self):
        stack = TetraStack(RecordingUser, debug=True)
        stack.llc = Layer3Probe(stack)

        stack.upper_mac._handle_data_pdu(self._resource_with_ssi(None))

        self.assertEqual(
            [layer for layer, unused in stack.user.records],
            ["UpperMac", "Mle"],
        )

    def test_debug_shows_broadcast_ssi_and_downstream_layer3(self):
        stack = TetraStack(RecordingUser, debug=True)
        stack.llc = Layer3Probe(stack)

        stack.upper_mac._handle_data_pdu(self._resource_with_ssi(0xFFFFFF))

        self.assertEqual(
            [layer for layer, unused in stack.user.records],
            ["UpperMac", "Mle"],
        )

    def test_nonzero_ssi_remains_visible_without_debug(self):
        stack = TetraStack(RecordingUser, debug=False)
        stack.llc = Layer3Probe(stack)

        stack.upper_mac._handle_data_pdu(self._resource_with_ssi(1))

        self.assertEqual(
            [layer for layer, unused in stack.user.records],
            ["UpperMac", "Mle"],
        )

    def test_hidden_sysinfo_also_hides_downstream_mle(self):
        stack = TetraStack(RecordingUser, debug=False)
        stack.llc = Layer3Probe(stack)
        pdu = type("SysinfoProbe", (), {"sdu": Bits("1")})()

        stack.upper_mac._handle_sysinfo_pdu(pdu)

        self.assertEqual(stack.user.records, [])

    def test_debug_shows_sysinfo_and_downstream_mle(self):
        stack = TetraStack(RecordingUser, debug=True)
        stack.llc = Layer3Probe(stack)
        pdu = type("SysinfoProbe", (), {"sdu": Bits("1")})()

        stack.upper_mac._handle_sysinfo_pdu(pdu)

        self.assertEqual(
            [layer for layer, unused in stack.user.records],
            ["UpperMac", "Mle"],
        )

    def test_summary_uses_layer2_when_no_layer3_exists(self):
        stack = TetraStack(RecordingUser, debug=False)
        stack.lower_mac.set_mobile_codes(204, 1000)
        stack.lower_mac.set_location_area(2333)
        stack.begin_burst()
        stack.upper_mac._handle_data_pdu(self._resource_with_ssi(3436244))
        stack.finish_burst()

        self.assertEqual(len(stack.user.summaries), 1)
        line = format_chain(stack.user.summaries[0])
        self.assertTrue(line.startswith(
            "DL; MCC(204), MNC(1000), LA(2333); "
            "Layer 2 - MAC(MacResourcePdu);"
        ))
        self.assertIn("SSI(3436244)", line)
        self.assertNotIn("Sdu(", line)

    def test_authentication_result_is_selected_as_highest_layer(self):
        stack = TetraStack(RecordingUser, debug=False)
        pdu = self._resource_with_ssi(3436244)
        pdu.fields["length_indication"] = 13
        pdu.fields["sdu"] = Bits(
            "00001100100011011000101111110000101011110011011010"
        )

        stack.begin_burst()
        stack.upper_mac._handle_data_pdu(pdu)
        stack.finish_burst()

        self.assertEqual(len(stack.user.summaries), 1)
        line = format_chain(stack.user.summaries[0])
        self.assertTrue(line.startswith(
            "DL; MCC(0), MNC(0), LA(0); "
            "Layer 3 - MM(DAuthentication);"
        ))
        self.assertIn("SSI(3436244)", line)
        self.assertIn("AuthenticationResult('Authentication successful')", line)
        self.assertIn("ResponseValue(400645741)", line)

    def test_minimal_mac_resource_does_not_require_stack_reference(self):
        bits = Bits(
            "00"       # MAC-RESOURCE
            "0"        # fill bits indication
            "0"        # position of grant
            "00"       # encryption mode
            "0"        # random access flag
            "000010"   # length indication
            "000"      # address type
            "0"        # power control flag
            "0"        # slot granting flag
            "0"        # channel allocation flag
        )

        pdu = MacPdu(bits)

        self.assertIsInstance(pdu, MacResourcePdu)
        self.assertEqual(pdu.length_indication, 2)
        self.assertEqual(len(pdu.sdu), 0)

    def test_mac_resource_length_includes_two_bit_discriminator(self):
        bits = Bits(
            "00"       # MAC-RESOURCE
            "1"        # fill bits indication
            "0"        # position of grant
            "00"       # encryption mode
            "0"        # random access flag
            "000011"   # total length: three octets
            "000"      # address type
            "0"        # power control flag
            "0"        # slot granting flag
            "0"        # channel allocation flag
            "10110"    # SDU 101 + fill marker 1 + one fill zero
        )

        pdu = MacPdu(bits)

        self.assertEqual(len(bits), 0)
        self.assertEqual(pdu.sdu, "101")

    def test_mac_resource_can_contain_only_fill_bits(self):
        bits = Bits(
            "00"       # MAC-RESOURCE
            "1"        # fill bits indication
            "0"        # position of grant
            "00"       # encryption mode
            "1"        # random access flag
            "000110"   # total length: six octets
            "001"      # SSI address
            + format(3436244, "024b")
            + "0"      # power control flag
            + "0"      # slot granting flag
            + "0"      # channel allocation flag
            + "10000"  # fill marker and four fill zeroes
        )

        pdu = MacPdu(bits)

        self.assertEqual(len(bits), 0)
        self.assertEqual(pdu.sdu, "")

    @patch("builtins.print")
    def test_logger_prints_a_section_only_when_layer_changes(self, output):
        Logger.reset()
        Logger.log("first", 1)
        Logger.log("second", 1)
        Logger.log("third", 2)

        lines = [call.args[0] for call in output.call_args_list]
        self.assertIn("Layer 1 - physical layer", lines[0])
        self.assertTrue(lines[0].startswith("╔"))
        self.assertEqual(lines[1:3], ["first", "second"])
        self.assertIn("Layer 2 - MAC / LLC", lines[3])
        self.assertTrue(lines[3].startswith("▓"))
        self.assertEqual(lines[4], "third")
