from collections import Counter

from pytetra.sap.tmasap import UpperTmaSap
from pytetra.sap.tmbsap import UpperTmbSap
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
from pytetra.layer import Layer
from pytetra.pdu import Bits


class Llc(Layer, UpperTmaSap, UpperTmbSap):
    """Downlink Logical Link Control entity."""

    layer_number = 2

    BASIC_DATA_PDUS = (
        BlADataPdu,
        BlDataPdu,
        BlUDataPdu,
        BlADataFcsPdu,
        BlDataFcsPdu,
        BlUDataFcsPdu,
    )
    BASIC_ACK_PDUS = (BlAckPdu, BlAckFcsPdu)
    RESERVED_PDUS = (LlcReservedPdu13, LlcReservedPdu14)

    def __init__(self, stack):
        super(Llc, self).__init__(stack)
        self.debug_enabled = bool(getattr(stack, "debug_llc", True))
        self.received_pdus = 0
        self.parsed_pdus = Counter()
        self.parse_failures = 0
        self.fcs_passes = 0
        self.fcs_failures = 0
        self.delivered_sdus = 0
        self.basic_sequence_mismatches = 0
        self.segment_resets = 0
        self.expected_basic_ns = None
        self.advanced_link = None
        self.al_data_segments = []
        self.al_udata_segments = []
        self.expected_al_data_ss = None
        self.expected_al_udata_ss = None

    @staticmethod
    def _join_segments(segments):
        return Bits("".join(segment.bits for segment in segments))

    def _debug(self, message):
        if self.debug_enabled:
            self.info("DEBUG " + message)

    def _deliver(self, sdu, source):
        if sdu is None or len(sdu) == 0:
            self._debug("drop | source=%s | reason=empty_sdu" % source)
            return

        self.delivered_sdus += 1
        self._debug(
            "deliver | source=%s | sdu_bits=%d | destination=MLE"
            % (source, len(sdu))
        )
        self.stack.mle.tl_unitdata_indication(sdu)

    def _check_fcs(self, pdu):
        if pdu.fcs_valid is None:
            return True
        if pdu.fcs_valid:
            self.fcs_passes += 1
            return True

        self.fcs_failures += 1
        if self.debug_enabled:
            self.warning(
                "LLC FCS failed | type=%s | pdu_type=%d"
                % (type(pdu).__name__, pdu.pdu_type)
            )
        return False

    def _track_basic_sequence(self, pdu):
        n_s = getattr(pdu, "n_s", None)
        if n_s is None:
            return

        if self.expected_basic_ns is not None and n_s != self.expected_basic_ns:
            self.basic_sequence_mismatches += 1
            if self.debug_enabled:
                self.warning(
                "LLC basic-link sequence mismatch | expected_n_s=%d | "
                "received_n_s=%d"
                % (self.expected_basic_ns, n_s)
                )

        self.expected_basic_ns = (n_s + 1) % 2

    def _append_advanced_segment(self, pdu, segments, expected_attr, source):
        sequence = pdu.s_s
        expected = getattr(self, expected_attr)

        if expected is not None and sequence != expected:
            segments[:] = []
            self.segment_resets += 1
            if self.debug_enabled:
                self.warning(
                "LLC advanced-link segment discontinuity | source=%s | "
                "expected_s_s=%d | received_s_s=%d"
                % (source, expected, sequence)
                )

        segments.append(pdu.sdu)
        setattr(self, expected_attr, (sequence + 1) % 256)

        if not pdu.final:
            self._debug(
                "segment buffered | source=%s | s_s=%d | segment_bits=%d | "
                "segments=%d"
                % (source, sequence, len(pdu.sdu), len(segments))
            )
            return

        complete_sdu = self._join_segments(segments)
        segments[:] = []
        setattr(self, expected_attr, None)
        self._deliver(complete_sdu, pdu.pdu_variant)

    def tma_unitdata_indication(self, sdu):
        """Receive one clear MAC-SDU and process its LLC PDU."""
        self.received_pdus += 1
        input_length = len(sdu) if sdu is not None else 0

        if sdu is None or input_length < 4:
            self.parse_failures += 1
            if self.debug_enabled:
                self.warning(
                "LLC input rejected | bits=%d | reason=missing_pdu_type"
                % input_length
                )
            return

        try:
            pdu = LlcPdu(Bits(sdu.bits))
        except Exception as exc:
            self.parse_failures += 1
            if self.debug_enabled:
                self.warning(
                "LLC parse failed | bits=%d | first_bits=%s | "
                "error_type=%s | error=%s"
                % (
                    input_length,
                    sdu.bits[:64],
                    type(exc).__name__,
                    exc,
                )
                )
            return

        pdu_name = type(pdu).__name__
        self.parsed_pdus[pdu_name] += 1
        fcs_status = (
            "not_present"
            if pdu.fcs_valid is None
            else "pass" if pdu.fcs_valid else "fail"
        )
        self._debug(
            "PDU | type=%s | pdu_type=%d | bits=%d | fcs=%s"
            % (pdu_name, pdu.pdu_type, input_length, fcs_status)
        )
        self.expose_pdu(pdu)

        if not self._check_fcs(pdu):
            return

        if isinstance(pdu, self.BASIC_DATA_PDUS):
            self._track_basic_sequence(pdu)
            self._deliver(pdu.sdu, pdu_name)
            return

        if isinstance(pdu, self.BASIC_ACK_PDUS):
            self._debug("control | type=%s | n_r=%s" % (pdu_name, pdu.n_r))
            return

        if isinstance(pdu, AlSetupPdu):
            self.advanced_link = pdu.advanced_link_number
            self._reset_advanced_segments()
            self._debug(
                "advanced-link setup | link=%d | service=%d"
                % (pdu.advanced_link_number, pdu.advanced_link_service)
            )
            return

        if isinstance(pdu, AlDataPdu):
            self._append_advanced_segment(
                pdu,
                self.al_data_segments,
                "expected_al_data_ss",
                "AL-DATA",
            )
            return

        if isinstance(pdu, AlUDataPdu):
            self._append_advanced_segment(
                pdu,
                self.al_udata_segments,
                "expected_al_udata_ss",
                "AL-UDATA",
            )
            return

        if isinstance(pdu, AlAckPdu):
            self._debug(
                "advanced-link control | variant=%s | acknowledgement_bits=%d"
                % (pdu.pdu_variant, len(pdu.acknowledgement_blocks))
            )
            return

        if isinstance(pdu, AlReconnectPdu):
            self.advanced_link = pdu.advanced_link_number
            self._reset_advanced_segments()
            self._debug(
                "advanced-link reconnect | link=%d | report=%d"
                % (pdu.advanced_link_number, pdu.reconnect_report)
            )
            return

        if isinstance(pdu, AlDiscPdu):
            self._debug(
                "advanced-link disconnect | link=%d | report=%d"
                % (pdu.advanced_link_number, pdu.report)
            )
            self.advanced_link = None
            self._reset_advanced_segments()
            return

        if isinstance(pdu, self.RESERVED_PDUS):
            if self.debug_enabled:
                self.warning(
                "Reserved LLC PDU received | pdu_type=%d | bits=%d"
                % (pdu.pdu_type, input_length)
                )

    def _reset_advanced_segments(self):
        self.al_data_segments = []
        self.al_udata_segments = []
        self.expected_al_data_ss = None
        self.expected_al_udata_ss = None

    def tmb_sync_indication(self, sdu):
        self.stack.mle.tl_sync_indication(sdu)

    def tmb_sysinfo_indication(self, sdu):
        self.stack.mle.tl_sysinfo_indication(sdu)

    def log_summary(self):
        if not self.debug_enabled:
            return
        self.info(
            "LLC summary | received=%d | parsed=%s | parse_failures=%d | "
            "fcs_pass=%d | fcs_fail=%d | delivered_sdus=%d | "
            "basic_sequence_mismatches=%d | segment_resets=%d"
            % (
                self.received_pdus,
                dict(self.parsed_pdus),
                self.parse_failures,
                self.fcs_passes,
                self.fcs_failures,
                self.delivered_sdus,
                self.basic_sequence_mismatches,
                self.segment_resets,
            )
        )
