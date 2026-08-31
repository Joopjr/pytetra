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
    def __init__(self, user_class=UserLayer, debug=False,
                 debug_layer2=None, debug_llc=None):
        Logger.reset()
        self.debug = bool(debug)
        self._output_suppression_depth = 0
        self._burst_chains = None
        self._active_mac_chain = None
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
        if not self.debug:
            self._burst_chains = []

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
