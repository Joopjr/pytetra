from pytetra.layer.mac.pdu import MacResourcePdu, MacFrag, MacEnd
from pytetra.pdu.pdu import Bits


class MacDefragmenter(object):
    def __init__(self):
        self.fragments = []

    @property
    def active(self):
        return bool(self.fragments)

    def reset(self):
        self.fragments = []

    def process_pdu(self, pdu):
        if isinstance(pdu, MacResourcePdu):
            if pdu.length_indication == 63:
                self.fragments = [pdu]
                return None
            else:
                # A complete resource PDU supersedes any incomplete chain.
                self.reset()
                return pdu
        elif isinstance(pdu, MacFrag):
            if not self.active:
                raise ValueError("MAC-FRAG received without MAC-RESOURCE start")
            self.fragments.append(pdu)
            return None
        elif isinstance(pdu, MacEnd):
            if not self.active:
                raise ValueError("MAC-END received without MAC-RESOURCE start")
            self.fragments.append(pdu)
            sdu = Bits(''.join(f.sdu.bits for f in self.fragments))
            pdu = self.fragments[0]
            pdu.sdu = sdu
            self.reset()
            return pdu

        raise TypeError("Unsupported fragmented MAC PDU: %s" % type(pdu).__name__)
