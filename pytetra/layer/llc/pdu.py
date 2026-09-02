#!/usr/bin/env python

from pytetra.pdu import (
    Pdu,
    UIntField,
    BitsField,
    ConditionalField,
    Bits,
    PduDecodingException,
)
from pytetra.layer.llc.fcs import check_fcs


# ============================================================================
# TETRA LLC PDU TYPES
# ============================================================================
#
# EN 300 392-2, table 304:
#
#   0  0000  BL-ADATA       without FCS
#   1  0001  BL-DATA        without FCS
#   2  0010  BL-UDATA       without FCS
#   3  0011  BL-ACK         without FCS
#   4  0100  BL-ADATA       with FCS
#   5  0101  BL-DATA        with FCS
#   6  0110  BL-UDATA       with FCS
#   7  0111  BL-ACK         with FCS
#   8  1000  AL-SETUP
#   9  1001  AL-DATA /
#                         AL-DATA-AR /
#                         AL-FINAL /
#                         AL-FINAL-AR
#   10 1010  AL-UDATA /
#                         AL-UFINAL
#   11 1011  AL-ACK /
#                         AL-RNR
#   12 1100  AL-RECONNECT
#   13 1101  RESERVED
#   14 1110  RESERVED
#   15 1111  AL-DISC
#
# The 4-bit LLC PDU type is consumed here.
# Concrete PDU classes therefore receive the remaining bits.
# ============================================================================


# ============================================================================
# LLC DISPATCH
# ============================================================================

class LlcPdu(Pdu):
    def __new__(cls, bits):

        # ------------------------------------------------------------
        # LLC PDU type = first 4 bits
        # ------------------------------------------------------------

        if len(bits) < 4:
            raise PduDecodingException(
                "LLC PDU too short for PDU type: %d bits" % len(bits)
            )

        pdu_type = bits.peek_int(0, 4)

        type_bits = bits.bits[:4]
        payload_bits = bits.bits[4:]

        payload = Bits(payload_bits)

        # ------------------------------------------------------------
        # Minimum length checks
        #
        # Do not try to decode a known LLC PDU when the captured
        # payload is shorter than its mandatory header.
        # Preserve the complete payload instead.
        # ------------------------------------------------------------

        minimum_payload_bits = {
            0: 2,    # BL-ADATA: N(R) + N(S)
            1: 1,    # BL-DATA: N(S)
            2: 0,    # BL-UDATA
            3: 1,    # BL-ACK: N(R)
            4: 34,   # BL-ADATA header + 32-bit FCS
            5: 33,   # BL-DATA header + 32-bit FCS
            6: 32,   # BL-UDATA + 32-bit FCS
            7: 33,   # BL-ACK header + 32-bit FCS
            8: 23,   # AL-SETUP mandatory fields
            9: 13,   # AL-DATA mandatory fields
            10: 17,  # AL-UDATA mandatory fields
            11: 1,   # AL-ACK / AL-RNR selector
            12: 5,   # AL-RECONNECT
            13: 0,   # RESERVED
            14: 0,   # RESERVED
            15: 6,   # AL-DISC
        }

        required = minimum_payload_bits.get(pdu_type, 0)

        if len(payload) < required:
            raise PduDecodingException(
                "LLC PDU type %d is truncated: need at least %d payload "
                "bits, have %d"
                % (pdu_type, required, len(payload))
            )

        # ------------------------------------------------------------
        # Basic Link
        # ------------------------------------------------------------

        pdu_class = {
            0: BlADataPdu,
            1: BlDataPdu,
            2: BlUDataPdu,
            3: BlAckPdu,
            4: BlADataFcsPdu,
            5: BlDataFcsPdu,
            6: BlUDataFcsPdu,
            7: BlAckFcsPdu,
            8: AlSetupPdu,
            9: AlDataPdu,
            10: AlUDataPdu,
            11: AlAckPdu,
            12: AlReconnectPdu,
            13: LlcReservedPdu13,
            14: LlcReservedPdu14,
            15: AlDiscPdu,
        }[pdu_type]

        pdu = pdu_class(payload)
        pdu.pdu_type = pdu_type
        pdu.pdu_type_bits = type_bits

        if pdu_type in (4, 5, 6, 7):
            protected_payload = payload_bits[:-32]
            pdu.fcs_valid = check_fcs(
                type_bits + protected_payload,
                payload_bits[-32:],
            )
        else:
            pdu.fcs_valid = None

        return pdu

# ============================================================================
# RAW / UNKNOWN LLC PDU
# ============================================================================

class LlcRawPdu(Pdu):
    """
    Raw/reserved/unknown LLC PDU.

    The four-bit LLC PDU type has already been consumed by LlcPdu.
    The remaining payload is preserved without interpretation.
    """

    fields_desc = [
        BitsField("sdu"),
    ]

    def __init__(self, pdu_type=None, payload=None, *args, **kwargs):

        self.pdu_type = pdu_type

        if payload is not None:
            super(LlcRawPdu, self).__init__(payload, *args, **kwargs)
        else:
            super(LlcRawPdu, self).__init__(*args, **kwargs)


# ============================================================================
# HELPER
# ============================================================================

def _split_fcs(bits):
    """
    Split the final 32 bits as FCS.

    Returns:
        (payload, fcs)

    If fewer than 32 bits are available, no FCS is extracted.
    """

    if len(bits) >= 32:
        return (
            Bits(bits.bits[:-32]),
            Bits(bits.bits[-32:]),
        )

    return bits, Bits("")


# ============================================================================
# BASIC LINK
# ============================================================================


# ---------------------------------------------------------------------------
# LLC type 3
# BL-ACK
# ---------------------------------------------------------------------------

class BlAckPdu(Pdu):

    fields_desc = [
        UIntField("n_r", 1),
    ]


# ---------------------------------------------------------------------------
# LLC type 0
# BL-ADATA
# ---------------------------------------------------------------------------

class BlADataPdu(Pdu):

    fields_desc = [
        UIntField("n_r", 1),
        UIntField("n_s", 1),
        BitsField("sdu"),
    ]


# ---------------------------------------------------------------------------
# LLC type 1
# BL-DATA
# ---------------------------------------------------------------------------

class BlDataPdu(Pdu):

    fields_desc = [
        UIntField("n_s", 1),
        BitsField("sdu"),
    ]


# ---------------------------------------------------------------------------
# LLC type 2
# BL-UDATA
# ---------------------------------------------------------------------------

class BlUDataPdu(Pdu):

    fields_desc = [
        BitsField("sdu"),
    ]


# ============================================================================
# BASIC LINK + FCS
# ============================================================================


# ---------------------------------------------------------------------------
# LLC type 4
# BL-ADATA + FCS
# ---------------------------------------------------------------------------

class BlADataFcsPdu(Pdu):

    fields_desc = [
        UIntField("n_r", 1),
        UIntField("n_s", 1),
        BitsField("sdu"),
    ]

    def __init__(self, bits):

        payload, fcs = _split_fcs(bits)

        super(BlADataFcsPdu, self).__init__(payload)

        self.fields["fcs"] = fcs


# ---------------------------------------------------------------------------
# LLC type 5
# BL-DATA + FCS
# ---------------------------------------------------------------------------

class BlDataFcsPdu(Pdu):

    fields_desc = [
        UIntField("n_s", 1),
        BitsField("sdu"),
    ]

    def __init__(self, bits):

        payload, fcs = _split_fcs(bits)

        super(BlDataFcsPdu, self).__init__(payload)

        self.fields["fcs"] = fcs


# ---------------------------------------------------------------------------
# LLC type 6
# BL-UDATA + FCS
# ---------------------------------------------------------------------------

class BlUDataFcsPdu(Pdu):

    fields_desc = [
        BitsField("sdu"),
    ]

    def __init__(self, bits):

        payload, fcs = _split_fcs(bits)

        super(BlUDataFcsPdu, self).__init__(payload)

        self.fields["fcs"] = fcs


# ---------------------------------------------------------------------------
# LLC type 7
# BL-ACK + FCS
# ---------------------------------------------------------------------------

class BlAckFcsPdu(Pdu):

    fields_desc = [
        UIntField("n_r", 1),
    ]

    def __init__(self, bits):

        payload, fcs = _split_fcs(bits)

        super(BlAckFcsPdu, self).__init__(payload)

        self.fields["fcs"] = fcs


# ============================================================================
# ADVANCED LINK
# ============================================================================


# ---------------------------------------------------------------------------
# LLC type 8
# AL-SETUP
# ---------------------------------------------------------------------------

class AlSetupPdu(Pdu):

    fields_desc = [

        UIntField("advanced_link_service", 1),

        UIntField("advanced_link_number", 2),

        UIntField("maximum_length_of_tl_sdu", 3),

        UIntField("connection_width", 1),

        UIntField("advanced_link_symmetry", 1),

        ConditionalField(
            UIntField("num_timeslots_ul", 2),
            lambda pkt: pkt.connection_width == 1
        ),

        ConditionalField(
            UIntField("num_timeslots_dl", 2),
            lambda pkt: pkt.connection_width == 1
        ),

        UIntField("data_transfer_throughput", 3),

        UIntField("tl_sdu_window_size", 2),

        UIntField("max_tl_sdu_retransmissions", 3),

        UIntField("max_segment_retransmissions", 4),

        UIntField("setup_report", 3),

        ConditionalField(
            UIntField("n_s", 8),
            lambda pkt: pkt.advanced_link_service == 0
        ),

        # Augmented AL-SETUP

        ConditionalField(
            UIntField("advanced_link_type", 1),
            lambda pkt: pkt.tl_sdu_window_size == 0
        ),

        ConditionalField(
            UIntField("tl_sdu_window_original", 2),
            lambda pkt: (
                pkt.tl_sdu_window_size == 0
                and pkt.advanced_link_type == 0
            )
        ),

        ConditionalField(
            UIntField("tl_sdu_window_extended", 4),
            lambda pkt: (
                pkt.tl_sdu_window_size == 0
                and pkt.advanced_link_type == 1
            )
        ),

        ConditionalField(
            UIntField("reserved", 3),
            lambda pkt: pkt.tl_sdu_window_size == 0
        ),

        BitsField("payload"),
    ]


# ---------------------------------------------------------------------------
# LLC type 9
# AL-DATA
# AL-DATA-AR
# AL-FINAL
# AL-FINAL-AR
# ---------------------------------------------------------------------------

class AlDataPdu(Pdu):

    fields_desc = [

        UIntField("final", 1),

        UIntField("ar", 1),

        UIntField("n_s", 3),

        UIntField("s_s", 8),

        BitsField("sdu"),
    ]

    def __init__(self, bits):

        super(AlDataPdu, self).__init__(bits)

        if self.final:

            if self.ar:
                self.fields["pdu_variant"] = "AL-FINAL-AR"
            else:
                self.fields["pdu_variant"] = "AL-FINAL"

        else:

            if self.ar:
                self.fields["pdu_variant"] = "AL-DATA-AR"
            else:
                self.fields["pdu_variant"] = "AL-DATA"


# ---------------------------------------------------------------------------
# LLC type 10
# AL-UDATA / AL-UFINAL
# ---------------------------------------------------------------------------

class AlUDataPdu(Pdu):

    fields_desc = [

        UIntField("final", 1),

        UIntField("n_s", 8),

        UIntField("s_s", 8),

        BitsField("sdu"),
    ]

    def __init__(self, bits):

        super(AlUDataPdu, self).__init__(bits)

        if self.final:
            self.fields["pdu_variant"] = "AL-UFINAL"
        else:
            self.fields["pdu_variant"] = "AL-UDATA"


# ---------------------------------------------------------------------------
# LLC type 11
# AL-ACK / AL-RNR
# ---------------------------------------------------------------------------

class AlAckPdu(Pdu):

    fields_desc = [

        UIntField("flow_control", 1),

        BitsField("acknowledgement_blocks"),
    ]

    def __init__(self, bits):

        super(AlAckPdu, self).__init__(bits)

        if self.flow_control:
            self.fields["pdu_variant"] = "AL-ACK"
        else:
            self.fields["pdu_variant"] = "AL-RNR"


# ---------------------------------------------------------------------------
# LLC type 12
# AL-RECONNECT
# ---------------------------------------------------------------------------

class AlReconnectPdu(Pdu):

    fields_desc = [

        UIntField("advanced_link_service", 1),

        UIntField("advanced_link_number", 2),

        UIntField("reconnect_report", 2),
    ]


# ============================================================================
# RESERVED LLC TYPES
# ============================================================================


# ---------------------------------------------------------------------------
# LLC type 13
# RESERVED
# ---------------------------------------------------------------------------

class LlcReservedPdu13(Pdu):

    fields_desc = [
        BitsField("payload"),
    ]


# ---------------------------------------------------------------------------
# LLC type 14
# RESERVED
# ---------------------------------------------------------------------------

class LlcReservedPdu14(Pdu):

    fields_desc = [
        BitsField("payload"),
    ]


# ============================================================================
# AL-DISC
# ============================================================================


# ---------------------------------------------------------------------------
# LLC type 15
# AL-DISC
# ---------------------------------------------------------------------------

class AlDiscPdu(Pdu):

    fields_desc = [

        UIntField("advanced_link_service", 1),

        UIntField("advanced_link_number", 2),

        UIntField("report", 3),
    ]
