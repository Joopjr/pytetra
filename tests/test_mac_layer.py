import unittest
from collections import OrderedDict
from unittest.mock import patch

from pytetra.layer.mac.pdu import (
    MAC_RESOURCE_ADDRESS_FIELDS,
    AccessAssignPdu,
    MacEnd,
    MacPdu,
    MacResourcePdu,
)
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
    def _resource_with_ssi(ssi, address_type=1, encryption_mode=0):
        pdu = object.__new__(MacResourcePdu)
        pdu.fields = OrderedDict((
            ("length_indication", 4),
            ("address_type", address_type),
            ("ssi", ssi),
            ("encryption_mode", encryption_mode),
            ("sdu", Bits("0000")),
        ))
        return pdu

    def test_compact_identity_label_follows_encryption_mode(self):
        for encryption_mode, expected_label in (
            (0, "SSI"),
            (1, "SSI"),
            (2, "ESI"),
            (3, "ESI"),
        ):
            with self.subTest(encryption_mode=encryption_mode):
                pdu = self._resource_with_ssi(
                    424242, encryption_mode=encryption_mode
                )
                rendered = format_chain({
                    "ssi": 424242,
                    "mcc": 204,
                    "mnc": 1000,
                    "la": 42,
                    "layer2": pdu,
                    "layer3": None,
                })
                self.assertIn("%s(424242)" % expected_label, rendered)
                other_label = "ESI" if expected_label == "SSI" else "SSI"
                self.assertNotIn("%s(424242)" % other_label, rendered)

    def test_debug_identity_label_follows_encryption_mode(self):
        for encryption_mode, expected_label in (
            (0, "SSI"),
            (1, "SSI"),
            (2, "ESI"),
            (3, "ESI"),
        ):
            with self.subTest(encryption_mode=encryption_mode):
                pdu = self._resource_with_ssi(
                    424242, encryption_mode=encryption_mode
                )
                rendered = repr(pdu)
                self.assertIn("%s(424242)" % expected_label, rendered)
                other_label = "ESI" if expected_label == "SSI" else "SSI"
                self.assertNotIn("%s(424242)" % other_label, rendered)

    def test_smi_identity_label_follows_address_type(self):
        for address_type in (4, 7):
            for encryption_mode in (0, 1, 2, 3):
                with self.subTest(
                    address_type=address_type,
                    encryption_mode=encryption_mode,
                ):
                    pdu = self._resource_with_ssi(
                        424242,
                        address_type=address_type,
                        encryption_mode=encryption_mode,
                    )
                    chain = {
                        "ssi": 424242,
                        "mcc": 204,
                        "mnc": 1000,
                        "la": 42,
                        "layer2": pdu,
                        "layer3": None,
                    }

                    self.assertIn("SMI(424242)", format_chain(chain))
                    self.assertIn("SMI(424242)", repr(pdu))
                    self.assertNotIn("SSI(424242)", format_chain(chain))
                    self.assertNotIn("ESI(424242)", format_chain(chain))
                    self.assertNotIn("SSI(424242)", repr(pdu))
                    self.assertNotIn("ESI(424242)", repr(pdu))

    def test_encrypted_identity_is_hidden_from_compact_output_by_default(self):
        stack = TetraStack(RecordingUser, debug=False)
        stack.begin_burst()
        stack.upper_mac._handle_data_pdu(
            self._resource_with_ssi(424242, encryption_mode=3)
        )
        stack.finish_burst()

        self.assertEqual(stack.user.summaries, [])

    def test_show_esi_retains_encrypted_identity_in_compact_output(self):
        stack = TetraStack(
            RecordingUser,
            debug=False,
            show_esi=True,
            carrier_frequency=410012500,
        )
        stack.begin_burst()
        stack.upper_mac._handle_data_pdu(
            self._resource_with_ssi(424242, encryption_mode=3)
        )
        stack.finish_burst()

        self.assertEqual(len(stack.user.summaries), 1)
        self.assertIn("ESI(424242)", format_chain(stack.user.summaries[0]))

    def test_security_context_reports_first_complete_context_once(self):
        messages = []
        Logger.set_writer(messages.append)
        try:
            stack = TetraStack(RecordingUser, debug=False)
            stack.lower_mac.set_mobile_codes(204, 9999)
            stack.lower_mac.set_location_area(42)
            self.assertEqual(messages, [])

            sysinfo = type("SysinfoProbe", (), {
                "hyperframe_or_cck": 1,
                "cck": 5,
                "sdu": None,
            })()
            stack.upper_mac._handle_sysinfo_pdu(sysinfo)
            stack.upper_mac._handle_sysinfo_pdu(sysinfo)
            stack.lower_mac.set_location_area(43)
        finally:
            Logger.set_writer(None)

        self.assertEqual(messages, [
            "SecurityContext(MCC(204), MNC(9999), LA(42), CCKId(5), "
            "EncryptionModeParity(odd))",
        ])

    def test_security_context_accepts_valid_zero_identifiers(self):
        messages = []
        Logger.set_writer(messages.append)
        try:
            stack = TetraStack(RecordingUser)
            stack.lower_mac.set_mobile_codes(0, 0)
            stack.lower_mac.set_location_area(0)
            stack.set_cck_id(2)
        finally:
            Logger.set_writer(None)

        self.assertEqual(messages, [
            "SecurityContext(MCC(0), MNC(0), LA(0), CCKId(2), "
            "EncryptionModeParity(even))",
        ])

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

    def test_compact_output_hides_selected_address_types_and_layer3(self):
        for address_type in (2, 3, 6):
            with self.subTest(address_type=address_type):
                stack = TetraStack(RecordingUser, debug=False)
                stack.llc = Layer3Probe(stack)

                stack.upper_mac._handle_data_pdu(
                    self._resource_with_ssi(424242, address_type)
                )

                self.assertEqual(stack.user.records, [])

    def test_debug_keeps_selected_address_types_visible(self):
        for address_type in (2, 3, 6):
            with self.subTest(address_type=address_type):
                stack = TetraStack(RecordingUser, debug=True)
                stack.llc = Layer3Probe(stack)

                stack.upper_mac._handle_data_pdu(
                    self._resource_with_ssi(424242, address_type)
                )

                self.assertEqual(
                    [layer for layer, unused in stack.user.records],
                    ["UpperMac", "Mle"],
                )

    def test_etsi_address_table_declares_the_parsed_keys(self):
        self.assertEqual(MAC_RESOURCE_ADDRESS_FIELDS[0], ())
        self.assertEqual(MAC_RESOURCE_ADDRESS_FIELDS[1], ("ssi",))
        self.assertEqual(MAC_RESOURCE_ADDRESS_FIELDS[2], ("event_label",))
        self.assertEqual(MAC_RESOURCE_ADDRESS_FIELDS[5], ("ssi", "event_label"))
        self.assertEqual(MAC_RESOURCE_ADDRESS_FIELDS[6], ("ssi", "usage_marker"))

    def test_mac_resource_keeps_only_etsi_selected_address_keys(self):
        bits = Bits(
            "00"       # MAC-RESOURCE
            "0"        # fill bits indication
            "0"        # position of grant
            "00"       # encryption mode
            "0"        # random access flag
            "000101"   # total length: five octets
            "010"      # event-label address type
            "1010101010"  # event label
            "0"        # power control flag
            "0"        # slot granting flag
            "0"        # channel allocation flag
            "0" * 11   # remaining SDU/padding within declared length
        )

        pdu = MacPdu(bits)

        self.assertEqual(pdu.event_label, int("1010101010", 2))
        self.assertNotIn("ssi", pdu.fields)
        self.assertNotIn("usage_marker", pdu.fields)
        self.assertIn("EventLabel(682)", repr(pdu))
        self.assertNotIn("SSI(None)", repr(pdu))

    def test_all_encryption_modes_are_kept_out_of_llc(self):
        for encryption_mode in (1, 2, 3):
            with self.subTest(encryption_mode=encryption_mode):
                stack = TetraStack(RecordingUser, debug=False)
                stack.llc = Layer3Probe(stack)
                pdu = self._resource_with_ssi(424242)
                pdu.fields["encryption_mode"] = encryption_mode

                stack.upper_mac._handle_data_pdu(pdu)

                self.assertEqual(
                    [layer for layer, unused in stack.user.records],
                    ["UpperMac"],
                )

    def test_encrypted_sdu_stops_further_mac_block_parsing(self):
        stack = TetraStack(RecordingUser, debug=False)
        encrypted_resource = (
            "00"       # MAC-RESOURCE
            "0"        # fill bits indication
            "0"        # position of grant
            "11"       # encrypted MAC-SDU
            "0"        # random access flag
            "000110"   # total length: six octets
            "001"      # SSI address
            + format(424242, "024b")
            + "0"      # power control flag
            + "0"      # slot granting flag
            + "0"      # channel allocation flag
            + "10101"  # opaque encrypted SDU
        )
        apparent_second_resource = (
            "00"       # MAC-RESOURCE
            "0"        # fill bits indication
            "0"        # position of grant
            "00"       # clear
            "0"        # random access flag
            "000010"   # minimal resource
            "000"      # no address
            "0"        # power control flag
            "0"        # slot granting flag
            "0"        # channel allocation flag
        )

        stack.upper_mac._handle_mac_block(
            Bits(encrypted_resource + apparent_second_resource),
            "SCH/F",
        )

        self.assertEqual(stack.upper_mac.parsed_pdus["MacResourcePdu"], 1)
        self.assertEqual(
            [layer for layer, unused in stack.user.records],
            ["UpperMac"],
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
        stack.lower_mac.set_mobile_codes(204, 9999)
        stack.lower_mac.set_location_area(42)
        stack.begin_burst()
        stack.upper_mac._handle_data_pdu(self._resource_with_ssi(424242))
        stack.finish_burst()

        self.assertEqual(len(stack.user.summaries), 1)
        line = format_chain(stack.user.summaries[0])
        self.assertTrue(line.startswith(
            "DL; MCC(204), MNC(9999), LA(42); "
            "Layer 2 - MAC(MacResourcePdu);"
        ))
        self.assertIn("SSI(424242)", line)
        self.assertNotIn("Sdu(", line)

    def test_compact_mac_resource_includes_all_present_header_fields(self):
        pdu = object.__new__(MacResourcePdu)
        pdu.fields = OrderedDict((
            ("fill_bits_indication", 1),
            ("position_of_grant", 0),
            ("encryption_mode", 0),
            ("random_access_flag", 1),
            ("length_indication", 20),
            ("address_type", 6),
            ("ssi", 424242),
            ("usage_marker", 17),
            ("power_control_flag", 1),
            ("power_control_element", 9),
            ("slot_granting_flag", 1),
            ("slot_granting_element", 85),
            ("channel_allocation_flag", 1),
            ("allocation_type", 2),
            ("timeslot_assigned", 4),
            ("up_down_assigned", 1),
            ("clch_permission", 1),
            ("cell_change", 0),
            ("carrier_number", 512),
            ("ext_carrier_number", 1),
            ("freq_band", 4),
            ("offset", 2),
            ("duplex_spacing", 3),
            ("reverse_operation", 0),
            ("monitoring_pattern", 0),
            ("frame_18_monitoring_pattern", 2),
            ("sdu", Bits("1010")),
        ))
        rendered = format_chain({
            "ssi": 424242,
            "mcc": 204,
            "mnc": 9999,
            "la": 42,
            "layer2": pdu,
            "layer3": None,
        })

        expected_fields = (
            "FillBitsIndication(1)",
            "PositionOfGrant(0)",
            "EncryptionMode(0)",
            "RandomAccessFlag(1)",
            "LengthIndication(20)",
            "AddressType(6)",
            "UsageMarker(17)",
            "PowerControlFlag(1)",
            "PowerControlElement(9)",
            "SlotGrantingFlag(1)",
            "SlotGrantingElement(85)",
            "ChannelAllocationFlag(1)",
            "AllocationType(2)",
            "TimeslotAssigned(4)",
            "UpDownAssigned(1)",
            "ClchPermission(1)",
            "CellChange(0)",
            "CarrierNumber(512)",
            "ExtCarrierNumber(1)",
            "FreqBand(4)",
            "Offset(2)",
            "DuplexSpacing(3)",
            "ReverseOperation(0)",
            "MonitoringPattern(0)",
            "Frame18MonitoringPattern(2)",
        )
        for expected in expected_fields:
            with self.subTest(field=expected):
                self.assertIn(expected, rendered)
        self.assertNotIn("Sdu(", rendered)

    def test_compact_mac_resource_omits_absent_optional_fields(self):
        pdu = self._resource_with_ssi(424242)
        pdu.fields.update((
            ("fill_bits_indication", 0),
            ("position_of_grant", 0),
            ("random_access_flag", 0),
            ("power_control_flag", 0),
            ("slot_granting_flag", 0),
            ("channel_allocation_flag", 0),
        ))
        rendered = format_chain({
            "ssi": 424242,
            "mcc": 204,
            "mnc": 9999,
            "la": 42,
            "layer2": pdu,
            "layer3": None,
        })

        self.assertIn("PowerControlFlag(0)", rendered)
        self.assertIn("SlotGrantingFlag(0)", rendered)
        self.assertIn("ChannelAllocationFlag(0)", rendered)
        self.assertNotIn("PowerControlElement(", rendered)
        self.assertNotIn("SlotGrantingElement(", rendered)
        self.assertNotIn("AllocationType(", rendered)

    def test_access_assign_debug_fields_follow_header(self):
        expected = {
            0: (
                "UplinkAccessField1(AccessCode(C), BaseFrameLength('Ongoing frame'))",
                "UplinkAccessField2(AccessCode(A), BaseFrameLength('4 subslots'))",
            ),
            1: (
                "DownlinkUsageMarker(34)",
                "UplinkAccessField(AccessCode(A), BaseFrameLength('4 subslots'))",
            ),
            2: (
                "DownlinkUsageMarker(34)",
                "UplinkAccessField(AccessCode(A), BaseFrameLength('4 subslots'))",
            ),
            3: ("DownlinkUsageMarker(34)", "UplinkUsageMarker(6)"),
        }
        for header, names in expected.items():
            with self.subTest(header=header):
                pdu = AccessAssignPdu(
                    Bits(format(header, "02b") + format(34, "06b") + format(6, "06b"))
                )
                rendered = repr(pdu)
                self.assertIn("Header(%d)" % header, rendered)
                self.assertIn(names[0], rendered)
                self.assertIn(names[1], rendered)
                self.assertNotIn(", Field1(", rendered)
                self.assertNotIn(", Field2(", rendered)

    def test_encrypted_channel_allocation_is_opaque(self):
        bits = Bits(
            "00"       # MAC-RESOURCE
            "0"        # fill bits indication
            "0"        # position of grant
            "11"       # encryption mode 3
            "0"        # random access flag
            "001000"   # total length: eight octets
            "110"      # SSI plus traffic usage marker
            + format(424242, "024b")
            + format(34, "06b")
            + "0"      # power control flag
            + "0"      # slot granting flag
            + "1"      # encrypted channel allocation is present
            + "101010101010101"  # opaque encrypted remainder
        )

        pdu = MacPdu(bits)
        rendered = repr(pdu)

        self.assertEqual(pdu.channel_allocation_flag, 1)
        self.assertNotIn("allocation_type", pdu.fields)
        self.assertNotIn("timeslot_assigned", pdu.fields)
        self.assertNotIn("carrier_number", pdu.fields)
        self.assertIn("ChannelAllocation(encrypted)", rendered)
        self.assertEqual(pdu.sdu, "101010101010101")

    def test_show_esi_emits_marker_and_assignment_once_per_epoch(self):
        stack = TetraStack(RecordingUser, debug=False, show_esi=True)
        aach = AccessAssignPdu(Bits("10" + format(34, "06b") + format(6, "06b")))
        pdu = self._resource_with_ssi(
            424242,
            address_type=6,
            encryption_mode=3,
        )
        pdu.fields["usage_marker"] = 34

        stack.begin_burst()
        stack.record_usage_marker(aach, 34)
        stack.finish_burst()
        stack.begin_burst()
        stack.upper_mac._handle_data_pdu(pdu)
        stack.finish_burst()
        stack.begin_burst()
        stack.upper_mac._handle_data_pdu(pdu)
        stack.finish_burst()

        rendered = [format_chain(chain) for chain in stack.user.summaries]
        self.assertEqual(len(rendered), 2)
        self.assertIn("MAC(AccessAssignPdu); CarrierFrequency(410012500)", rendered[0])
        self.assertIn("Timeslot(", rendered[0])
        self.assertIn("UsageMarker(34)", rendered[0])
        self.assertIn("ESI(424242)", rendered[1])
        self.assertIn("UsageMarker(34)", rendered[1])

        stack._burst_sequence += stack.USAGE_MARKER_TIMEOUT_BURSTS + 1
        stack.begin_burst()
        stack.record_usage_marker(aach, 34)
        stack.finish_burst()
        stack.begin_burst()
        stack.upper_mac._handle_data_pdu(pdu)
        stack.finish_burst()

        self.assertEqual(len(stack.user.summaries), 4)

    def test_show_esi_excludes_non_traffic_usage_markers(self):
        stack = TetraStack(RecordingUser, debug=False, show_esi=True)
        pdu = self._resource_with_ssi(
            424242,
            address_type=6,
            encryption_mode=3,
        )
        pdu.fields["usage_marker"] = 2

        stack.begin_burst()
        stack.upper_mac._handle_data_pdu(pdu)
        stack.finish_burst()

        self.assertEqual(stack.user.summaries, [])

    def test_aach_marker_change_reports_previous_value(self):
        stack = TetraStack(
            RecordingUser,
            debug=False,
            show_esi=True,
            carrier_frequency=410012500,
        )
        first = AccessAssignPdu(
            Bits("10" + format(34, "06b") + format(6, "06b"))
        )
        second = AccessAssignPdu(
            Bits("10" + format(35, "06b") + format(6, "06b"))
        )

        stack.begin_burst()
        stack.record_usage_marker(first, 34)
        stack.finish_burst()
        stack.begin_burst()
        stack.record_usage_marker(second, 35)
        stack.finish_burst()

        rendered = [format_chain(chain) for chain in stack.user.summaries]
        self.assertEqual(len(rendered), 2)
        self.assertNotIn("PreviousUsageMarker(", rendered[0])
        self.assertIn("PreviousUsageMarker(34)", rendered[1])
        self.assertIn("UsageMarker(35)", rendered[1])

    def test_authentication_result_is_selected_as_highest_layer(self):
        stack = TetraStack(RecordingUser, debug=False)
        pdu = self._resource_with_ssi(424242)
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
        self.assertIn("SSI(424242)", line)
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
            + format(424242, "024b")
            + "0"      # power control flag
            + "0"      # slot granting flag
            + "0"      # channel allocation flag
            + "10000"  # fill marker and four fill zeroes
        )

        pdu = MacPdu(bits)

        self.assertEqual(len(bits), 0)
        self.assertEqual(pdu.sdu, "")

    def test_mac_end_accepts_zero_only_fill_padding(self):
        # Prefix captured from a real SCH/HD block that previously raised
        # "Invalid MAC fill-bit pattern". Its seven-octet MAC-END contains a
        # six-bit, zero-only fill area after the channel-allocation fields.
        bits = Bits(
            "01110000111010010101101001001110100101100011110011"
            "000000"
            + "00001100"
            + "0" * 60
        )

        pdu = MacPdu(bits)

        self.assertIsInstance(pdu, MacEnd)
        self.assertEqual(pdu.fill_bits_indication, 1)
        self.assertEqual(pdu.length_indication, 7)
        self.assertEqual(pdu.sdu, "")

    def test_mac_parse_failure_is_silent_without_debug(self):
        stack = TetraStack(RecordingUser, debug=False)
        with patch("pytetra.layer.mac.mac.MacPdu", side_effect=ValueError("bad")):
            with patch.object(stack.upper_mac, "info") as info:
                stack.upper_mac._handle_mac_block(Bits("01" + "1" * 20), "SCH/F")
        info.assert_not_called()

    @patch("builtins.print")
    def test_logger_prints_a_section_only_when_layer_changes(self, output):
        Logger.set_writer(None)
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

    def test_logger_can_route_complete_lines_to_live_frontend(self):
        lines = []
        Logger.set_writer(lines.append)
        try:
            Logger.reset()
            Logger.log("DL; Layer 2", 2)
        finally:
            Logger.set_writer(None)

        self.assertEqual(len(lines), 2)
        self.assertIn("Layer 2 - MAC / LLC", lines[0])
        self.assertEqual(lines[1], "DL; Layer 2")
