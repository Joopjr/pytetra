#!/usr/bin/env python

from pytetra.pdu.pdu import (
    Pdu,
    PduDecodingException,
    UIntField,
    BitsField,
    ConditionalField,
    Bits,
)
from pytetra.logger import format_record


def _remove_fill_bits(sdu):
    """Remove the MAC fill marker (one) and all zero bits after it."""
    marker = sdu.bits.rstrip("0")
    # Some networks emit a fill-indicated MAC-END whose remaining SDU area
    # contains only zero padding, without the normally required one marker.
    # Treat that observed wire representation as an empty SDU instead of
    # rejecting the complete MAC PDU.
    if not marker:
        return Bits("")
    return Bits(marker[:-1])


# 21.4.1 MAC PDU types
class MacPdu(Pdu):
    fields_desc = [
        UIntField("pdu_type", 2),
    ]

    def __new__(cls, bits):
        pdu = Pdu.__new__(cls)
        Pdu.__init__(pdu, bits)

        if pdu.pdu_type == 0:
            return MacResourcePdu(bits)

        elif pdu.pdu_type == 1:
            return MacFragEnd(bits)

        elif pdu.pdu_type == 2:
            return BroadcastPdu(bits)

        raise PduDecodingException(
            "Unknown MAC PDU type %d" % pdu.pdu_type
        )


class MacFragEnd(Pdu):
    fields_desc = [
        UIntField("pdu_subtype", 1),
    ]

    def __new__(cls, bits):
        pdu = Pdu.__new__(cls)
        Pdu.__init__(pdu, bits)

        if pdu.pdu_subtype == 0:
            return MacFrag(bits)
        elif pdu.pdu_subtype == 1:
            return MacEnd(bits)


# 21.4.3.2 MAC-FRAG (downlink)
class MacFrag(Pdu):
    fields_desc = [
        UIntField("fill_bits_indication", 1),
    ]

    def __init__(self, bits):
        super(MacFrag, self).__init__(bits)
        sdu = BitsField('sdu', len(bits)).dissect(self, bits)
        if self.fill_bits_indication:
            sdu = _remove_fill_bits(sdu)
        self.fields['sdu'] = sdu


# 21.4.3.3 MAC-END (downlink)
class MacEnd(Pdu):
    fields_desc = [
        UIntField("fill_bits_indication", 1),
        UIntField("position_of_grant", 1),
        UIntField("length_indication", 6),
        UIntField("slot_granting_flag", 1),
        ConditionalField(UIntField("slot_granting_element", 8), lambda pkt: pkt.slot_granting_flag),
        UIntField("channel_allocation_flag", 1),
        ConditionalField(UIntField("allocation_type", 2), lambda pkt: pkt.channel_allocation_flag),
        ConditionalField(UIntField("timeslot_assigned", 4), lambda pkt: pkt.channel_allocation_flag),
        ConditionalField(UIntField("up_down_assigned", 2), lambda pkt: pkt.channel_allocation_flag),
        ConditionalField(UIntField("clch_permission", 1), lambda pkt: pkt.channel_allocation_flag),
        ConditionalField(UIntField("cell_change", 1), lambda pkt: pkt.channel_allocation_flag),
        ConditionalField(UIntField("carrier_number", 12), lambda pkt: pkt.channel_allocation_flag),
        ConditionalField(UIntField("ext_carrier_number", 1), lambda pkt: pkt.channel_allocation_flag),
        ConditionalField(UIntField("freq_band", 4), lambda pkt: pkt.channel_allocation_flag and pkt.ext_carrier_number),
        ConditionalField(UIntField("offset", 2), lambda pkt: pkt.channel_allocation_flag and pkt.ext_carrier_number),
        ConditionalField(UIntField("duplex_spacing", 3), lambda pkt: pkt.channel_allocation_flag and pkt.ext_carrier_number),
        ConditionalField(UIntField("reverse_operation", 1), lambda pkt: pkt.channel_allocation_flag and pkt.ext_carrier_number),
        ConditionalField(UIntField("monitoring_pattern", 2), lambda pkt: pkt.channel_allocation_flag),
        ConditionalField(UIntField("frame_18_monitoring_pattern", 2), lambda pkt: pkt.channel_allocation_flag and pkt.monitoring_pattern == 0),
    ]

    def __init__(self, bits):
        initial_size = len(bits) + 3
        super(MacEnd, self).__init__(bits)
        sdu_size = self.length_indication * 8 - (initial_size - len(bits))
        sdu = BitsField('sdu', sdu_size).dissect(self, bits)
        if self.fill_bits_indication:
            sdu = _remove_fill_bits(sdu)
        self.fields['sdu'] = sdu


class NullPdu(Pdu):
    fields_desc = [
        UIntField("fill_bits_indication", 1),
        UIntField("position_of_grant", 1),
        UIntField("encryption_mode", 2),
        UIntField("random_access_flag", 1),
        UIntField("length_indication", 6),
        UIntField("address_type", 3),
    ]


# EN 300 392-2, MAC-RESOURCE address-type table. Keep field presence in one
# authoritative mapping so parsing and presentation cannot diverge.
MAC_RESOURCE_ADDRESS_FIELDS = {
    0: (),
    1: ("ssi",),
    2: ("event_label",),
    3: ("ssi",),
    4: ("ssi",),
    5: ("ssi", "event_label"),
    6: ("ssi", "usage_marker"),
    7: ("ssi", "event_label"),
}


def mac_resource_address_has(address_type, field_name):
    return field_name in MAC_RESOURCE_ADDRESS_FIELDS.get(address_type, ())


def mac_resource_identity_field_name(address_type, encryption_mode):
    """Return the ETSI identity label used to present a MAC address."""
    if address_type in (4, 7):
        return "smi"
    if encryption_mode in (2, 3):
        return "esi"
    return "ssi"


# 21.4.3.1 MAC-RESOURCE
class MacResourcePdu(Pdu):
    fields_desc = [
        UIntField("fill_bits_indication", 1),
        UIntField("position_of_grant", 1),
        UIntField("encryption_mode", 2),
        UIntField("random_access_flag", 1),
        UIntField("length_indication", 6),
        UIntField("address_type", 3),
        ConditionalField(UIntField("ssi", 24), lambda pkt: mac_resource_address_has(pkt.address_type, "ssi")),
        ConditionalField(UIntField("event_label", 10), lambda pkt: mac_resource_address_has(pkt.address_type, "event_label")),
        ConditionalField(UIntField("usage_marker", 6), lambda pkt: mac_resource_address_has(pkt.address_type, "usage_marker")),
        UIntField("power_control_flag", 1),
        ConditionalField(UIntField("power_control_element", 4), lambda pkt: pkt.power_control_flag),
        UIntField("slot_granting_flag", 1),
        ConditionalField(UIntField("slot_granting_element", 8), lambda pkt: pkt.slot_granting_flag),
        UIntField("channel_allocation_flag", 1),
        ConditionalField(UIntField("allocation_type", 2), lambda pkt: pkt.channel_allocation_flag and pkt.encryption_mode == 0),
        ConditionalField(UIntField("timeslot_assigned", 4), lambda pkt: pkt.channel_allocation_flag and pkt.encryption_mode == 0),
        ConditionalField(UIntField("up_down_assigned", 2), lambda pkt: pkt.channel_allocation_flag and pkt.encryption_mode == 0),
        ConditionalField(UIntField("clch_permission", 1), lambda pkt: pkt.channel_allocation_flag and pkt.encryption_mode == 0),
        ConditionalField(UIntField("cell_change", 1), lambda pkt: pkt.channel_allocation_flag and pkt.encryption_mode == 0),
        ConditionalField(UIntField("carrier_number", 12), lambda pkt: pkt.channel_allocation_flag and pkt.encryption_mode == 0),
        ConditionalField(UIntField("ext_carrier_number", 1), lambda pkt: pkt.channel_allocation_flag and pkt.encryption_mode == 0),
        ConditionalField(UIntField("freq_band", 4), lambda pkt: pkt.channel_allocation_flag and pkt.encryption_mode == 0 and pkt.ext_carrier_number),
        ConditionalField(UIntField("offset", 2), lambda pkt: pkt.channel_allocation_flag and pkt.encryption_mode == 0 and pkt.ext_carrier_number),
        ConditionalField(UIntField("duplex_spacing", 3), lambda pkt: pkt.channel_allocation_flag and pkt.encryption_mode == 0 and pkt.ext_carrier_number),
        ConditionalField(UIntField("reverse_operation", 1), lambda pkt: pkt.channel_allocation_flag and pkt.encryption_mode == 0 and pkt.ext_carrier_number),
        ConditionalField(UIntField("monitoring_pattern", 2), lambda pkt: pkt.channel_allocation_flag and pkt.encryption_mode == 0),
        ConditionalField(UIntField("frame_18_monitoring_pattern", 2), lambda pkt: pkt.channel_allocation_flag and pkt.encryption_mode == 0 and pkt.monitoring_pattern == 0),
    ]

    def __repr__(self):
        identity_field_name = mac_resource_identity_field_name(
            self.address_type, self.encryption_mode
        )
        fields = []
        for key, value in self.fields.items():
            fields.append((
                identity_field_name if key == "ssi" else key,
                value,
            ))
            if (
                key == "channel_allocation_flag"
                and value
                and self.encryption_mode != 0
            ):
                # EN 300 392-2 clause 21.4.3.1: the channel-allocation
                # element is cipher text whenever encryption mode is non-zero.
                fields.append(("channel_allocation", "encrypted"))

        return format_record(self.__class__.__name__, fields)

    def __init__(self, bits):
        # Preserve the number of bits initially available to this MAC PDU.
        # Pdu.__init__() consumes the header from bits in place.
        # MacPdu has already consumed the two-bit PDU discriminator.
        initial_size = len(bits) + 2

        super(MacResourcePdu, self).__init__(bits)

        # ConditionalField historically retained non-selected keys with a
        # None value. Remove those presentation artefacts: the ETSI address
        # type selects the fields that are actually present on air.
        selected_address_fields = MAC_RESOURCE_ADDRESS_FIELDS.get(
            self.address_type, ()
        )
        for address_field in ("ssi", "event_label", "usage_marker"):
            if address_field not in selected_address_fields:
                self.fields.pop(address_field, None)

        # A length indication of 2 with address type 0 carries no LLC SDU.
        if self.length_indication == 2 and self.address_type == 0:
                self.fields['sdu'] = Bits('')
                return

        # A length indication of 0 with address type 0 is padding.
        if self.length_indication == 0 and self.address_type == 0:
                self.fields['sdu'] = Bits('')
                return

        # The length indication is the total MAC-RESOURCE length in octets,
        # including the MAC header and SDU.
        total_resource_bits = self.length_indication * 8

        # After header parsing, bits contains only unconsumed data.
        remaining_bits = len(bits)

        # Never consume beyond the PDU length or the available block.
        sdu_bits = total_resource_bits - (initial_size - remaining_bits)

        if sdu_bits < 0:
                sdu_bits = 0

        sdu_bits = min(sdu_bits, remaining_bits)

        sdu = BitsField('sdu', sdu_bits).dissect(self, bits)

        if self.fill_bits_indication and self.encryption_mode == 0:
                sdu = _remove_fill_bits(sdu)

        self.fields['sdu'] = sdu



# 21.4.4 TMB-SAP: MAC PDU structure for broadcast
class BroadcastPdu(Pdu):
    fields_desc = [
        UIntField("broadcast_type", 2),
    ]

    def __new__(cls, bits):
        pdu = Pdu.__new__(cls)
        Pdu.__init__(pdu, bits)

        if pdu.broadcast_type == 0:
            return SysinfoPdu(bits)
        elif pdu.broadcast_type == 1:
            return AccessDefinePdu(bits)

        raise PduDecodingException(
            "Reserved MAC-BROADCAST subtype %d" % pdu.broadcast_type
        )


# 21.4.4.3 ACCESS-DEFINE
class AccessDefinePdu(Pdu):
    fields_desc = [
        UIntField("common_assigned_control_channel_flag", 1),
        UIntField("access_code", 2),
        UIntField("imm", 4),
        UIntField("wt", 4),
        UIntField("nu", 4),
        UIntField("frame_length_factor", 1),
        UIntField("timeslot_pointer", 4),
        UIntField("minimum_priority", 3),
        UIntField("optional_field", 2),
        ConditionalField(
            UIntField("subscriber_class_bitmap", 16),
            lambda pkt: pkt.optional_field == 1
        ),
        ConditionalField(
            UIntField("gssi", 24),
            lambda pkt: pkt.optional_field == 2
        ),
        UIntField("filler_bits", 3),
    ]


# 21.4.4.1 SYSINFO
class SysinfoPdu(Pdu):
    fields_desc = [
        UIntField("main_carrier", 12),
        UIntField("frequency_band", 4),
        UIntField("offset", 2),
        UIntField("duplex_spacing", 3),
        UIntField("reverse_operation", 1),
        UIntField("number_of_scch", 2),
        UIntField("max_ms_tx_power", 3),
        UIntField("min_rxlevel", 4),
        UIntField("access_parameter", 4),
        UIntField("radio_downlink_timeout", 4),
        UIntField("hyperframe_or_cck", 1),
        ConditionalField(UIntField("hyperframe_number", 16), lambda pkt: pkt.hyperframe_or_cck == 0),
        ConditionalField(UIntField("cck", 16), lambda pkt: pkt.hyperframe_or_cck == 1),
        UIntField("optional_field", 2),
        ConditionalField(UIntField("ts_common_frames", 20), lambda pkt: pkt.optional_field in [0, 1]),
        ConditionalField(UIntField("default_def_access_code_a", 20), lambda pkt: pkt.optional_field == 2),
        ConditionalField(UIntField("extended_services", 20), lambda pkt: pkt.optional_field == 3),
        BitsField("sdu", 42),
    ]


# 21.4.4.2 SYNC
class SyncPdu(Pdu):
    fields_desc = [
        UIntField("system_code", 4),
        UIntField("colour_code", 6),
        UIntField("timeslot_number", 2),
        UIntField("frame_number", 5),
        UIntField("multiframe_number", 6),
        UIntField("sharing_mode", 2),
        UIntField("ts_rsvd_frames", 3),
        UIntField("uplane_dtx", 1),
        UIntField("frame18_ext", 1),
        UIntField("reserved", 1),
        BitsField("tm_sdu", 29),
    ]


# 21.4.7 MAC PDU structure for access assignment broadcast
class AccessAssignPdu(Pdu):
    fields_desc = [
        UIntField("header", 2),
        UIntField("field1", 6),
        UIntField("field2", 6),
    ]

    ACCESS_CODES = ("A", "B", "C", "D")
    BASE_FRAME_LENGTHS = {
        0: "Reserved subslot",
        1: "CLCH subslot",
        2: "Ongoing frame",
        3: "1 subslot",
        4: "2 subslots",
        5: "3 subslots",
        6: "4 subslots",
        7: "5 subslots",
        8: "6 subslots",
        9: "8 subslots",
        10: "10 subslots",
        11: "12 subslots",
        12: "16 subslots",
        13: "20 subslots",
        14: "24 subslots",
        15: "Reserved",
    }

    @classmethod
    def format_access_field(cls, value, suffix=""):
        access_code = cls.ACCESS_CODES[(value >> 4) & 0x03]
        frame_length = cls.BASE_FRAME_LENGTHS[value & 0x0F]
        return (
            "UplinkAccessField%s(AccessCode(%s), BaseFrameLength(%r))"
            % (suffix, access_code, frame_length)
        )

    def __repr__(self):
        if self.header == 0:
            rendered_fields = (
                self.format_access_field(self.field1, "1"),
                self.format_access_field(self.field2, "2"),
            )
        elif self.header in (1, 2):
            rendered_fields = (
                "DownlinkUsageMarker(%d)" % self.field1,
                self.format_access_field(self.field2),
            )
        elif self.header == 3:
            rendered_fields = (
                "DownlinkUsageMarker(%d)" % self.field1,
                "UplinkUsageMarker(%d)" % self.field2,
            )
        else:
            rendered_fields = (
                "Field1(%d)" % self.field1,
                "Field2(%d)" % self.field2,
            )

        return "%s(Header(%d), %s)" % (
            self.__class__.__name__,
            self.header,
            ", ".join(rendered_fields),
        )
