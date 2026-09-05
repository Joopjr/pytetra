from pytetra.layer.sndcp import Sndcp
from pytetra.layer.phy import Phy
from pytetra.layer.mac import LowerMac, UpperMac
from pytetra.layer.llc import Llc
from pytetra.layer.mle import Mle
from pytetra.layer.cmce import Cmce
from pytetra.layer.mm import Mm
from pytetra.layer.user import UserLayer
from pytetra.logger import Logger
from contextlib import contextmanager


class TetraStack(object):
    # One continuous downlink burst occupies one 14.167 ms TDMA timeslot.
    # 353 observed bursts are therefore just over five seconds.
    USAGE_MARKER_TIMEOUT_BURSTS = 353

    def __init__(self, user_class=UserLayer, debug=False,
                 debug_layer2=None, debug_llc=None, show_esi=False):
        Logger.reset()
        self.debug = bool(debug)
        self.show_esi = bool(show_esi)
        self.cck_id = None
        self._security_context_reported = False
        self._output_suppression_depth = 0
        self._burst_chains = None
        self._active_mac_chain = None
        self._burst_sequence = 0
        self._usage_marker_last_seen = {}
        self._esi_usage_assignments = set()
        self.debug_layer2 = self.debug if debug_layer2 is None else bool(debug_layer2)
        self.debug_llc = self.debug if debug_llc is None else bool(debug_llc)
        self.sndcp = Sndcp(self)
        self.phy = Phy(self, log_layer1=self.debug)
        self.lower_mac = LowerMac(self)
        self.upper_mac = UpperMac(self)
        self.llc = Llc(self)
        self.mle = Mle(self)
        self.cmce = Cmce(self)
        self.mm = Mm(self)
        self.user = user_class(self)

    def set_cck_id(self, cck_id):
        """Store a validated CCK identifier and report the complete context."""
        try:
            cck_id = int(cck_id)
        except (TypeError, ValueError):
            return
        if not 0 <= cck_id <= 0xFFFF:
            raise ValueError("CCK identifier must fit in 16 bits")
        self.cck_id = cck_id
        self.report_security_context()

    def report_security_context(self):
        """Emit the first complete MCC/MNC/LA/CCK context once per run."""
        if self._security_context_reported or self.cck_id is None:
            return
        context = (
            self.lower_mac.mcc,
            self.lower_mac.mnc,
            self.lower_mac.la,
            self.cck_id,
        )
        if (
            not self.lower_mac.mobile_codes_known
            or not self.lower_mac.location_area_known
        ):
            return
        self._security_context_reported = True
        parity = "odd" if self.cck_id & 1 else "even"
        Logger.log(
            "SecurityContext(MCC(%d), MNC(%d), LA(%d), CCKId(%d), "
            "EncryptionModeParity(%s))" % (context + (parity,))
        )

    @property
    def output_suppressed(self):
        return not self.debug and self._output_suppression_depth > 0

    @contextmanager
    def output_context(self, suppress=False):
        """Temporarily hide protocol output while decoding continues."""
        if suppress and not self.debug:
            self._output_suppression_depth += 1
        try:
            yield
        finally:
            if suppress and not self.debug:
                self._output_suppression_depth -= 1

    def begin_burst(self):
        self._burst_sequence += 1
        if not self.debug:
            self._burst_chains = []

    def _observe_usage_marker(self, usage_marker):
        """Record marker activity and return True for a new local epoch."""
        try:
            usage_marker = int(usage_marker)
        except (TypeError, ValueError):
            return False

        # Values 0..3 describe idle/control/reserved slot use, not traffic.
        if not 4 <= usage_marker <= 63:
            return False

        previous = self._usage_marker_last_seen.get(usage_marker)
        is_new = (
            previous is None
            or self._burst_sequence - previous
            > self.USAGE_MARKER_TIMEOUT_BURSTS
        )
        if is_new:
            self._esi_usage_assignments = {
                item for item in self._esi_usage_assignments
                if item[0] != usage_marker
            }

        self._usage_marker_last_seen[usage_marker] = self._burst_sequence
        return is_new

    def record_usage_marker(self, pdu, usage_marker):
        """Queue the first observed AACH traffic marker for compact output."""
        is_new = self._observe_usage_marker(usage_marker)
        if (
            self.debug
            or not self.show_esi
            or not is_new
            or self._burst_chains is None
        ):
            return

        self._burst_chains.append({
            "ssi": None,
            "mcc": self.lower_mac.mcc,
            "mnc": self.lower_mac.mnc,
            "la": self.lower_mac.la,
            "layer2": pdu,
            "layer3": None,
            "layer3_priority": -1,
            "usage_marker": int(usage_marker),
        })

    def should_emit_esi_usage_assignment(self, pdu):
        """Return True only for a first ESI/traffic-marker observation."""
        if (
            self.debug
            or not self.show_esi
            or getattr(pdu, "address_type", None) != 6
            or getattr(pdu, "encryption_mode", None) not in (2, 3)
        ):
            return False

        usage_marker = getattr(pdu, "usage_marker", None)
        esi = getattr(pdu, "ssi", None)
        if esi is None:
            return False

        self._observe_usage_marker(usage_marker)
        key = (usage_marker, esi)
        if key in self._esi_usage_assignments:
            return False

        self._esi_usage_assignments.add(key)
        return True

    def reset_after_gap(self):
        """Discard only state that cannot safely cross a missing burst."""
        self._burst_chains = None
        self._active_mac_chain = None
        self.upper_mac.downlink_usage_marker = None
        self.lower_mac.bkn2_stolen = False
        self.upper_mac.defragmenter.reset()
        self.llc._reset_advanced_segments()
        self.llc.expected_basic_ns = None
        self.sndcp.segments.clear()

    def finish_burst(self):
        if self.debug or self._burst_chains is None:
            return
        chains = self._burst_chains
        self._burst_chains = None
        if not self.show_esi:
            chains = [
                chain for chain in chains
                if getattr(chain.get("layer2"), "encryption_mode", None)
                not in (2, 3)
            ]
        if chains:
            self.user.burst_summary_indication(chains)

    @contextmanager
    def mac_pdu_context(self, pdu, suppress=False):
        previous = self._active_mac_chain
        chain = {
            "ssi": getattr(pdu, "ssi", None),
            "mcc": self.lower_mac.mcc,
            "mnc": self.lower_mac.mnc,
            "la": self.lower_mac.la,
            "layer2": None,
            "layer3": None,
            "layer3_priority": -1,
        }
        self._active_mac_chain = chain
        try:
            with self.output_context(suppress):
                yield
        finally:
            self._active_mac_chain = previous
            if (
                not self.debug
                and self._burst_chains is not None
                and chain["layer2"] is not None
            ):
                self._burst_chains.append(chain)

    def record_pdu(self, layer, pdu):
        if self.debug or self._active_mac_chain is None:
            return
        chain = self._active_mac_chain
        if layer == "UpperMac":
            chain["layer2"] = pdu
            return
        priority = {
            "Mle": 1,
            "Cmce": 2,
            "Mm": 2,
            "Sndcp": 2,
        }.get(layer)
        if priority is not None and priority >= chain["layer3_priority"]:
            la = self._find_named_field_value(pdu, "La")
            if la is not None:
                self.lower_mac.set_location_area(la)
                chain["la"] = self.lower_mac.la
            chain["layer3"] = (layer, pdu)
            chain["layer3_priority"] = priority

    @classmethod
    def _find_named_field_value(cls, value, field_name):
        """Find an integer protocol field in a nested parsed PDU."""
        fields = getattr(value, "fields", None)
        if fields is None:
            return None

        for key, item in fields.items():
            if getattr(key, "__name__", None) == field_name:
                return getattr(item, "value", None)

            if isinstance(item, list):
                for nested in item:
                    result = cls._find_named_field_value(nested, field_name)
                    if result is not None:
                        return result
            else:
                result = cls._find_named_field_value(item, field_name)
                if result is not None:
                    return result

        return None
