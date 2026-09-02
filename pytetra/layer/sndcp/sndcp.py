from pytetra.layer import Layer
from pytetra.layer.sndcp.pdu import (
    ReassembledNpdu,
    SnDataPdu,
    SnUnitdataPdu,
    SndcpPdu,
)
from pytetra.pdu import Bits


class Sndcp(Layer):
    layer_number = 3

    def __init__(self, stack):
        super(Sndcp, self).__init__(stack)
        self.segments = {}

    def mle_unitdata_indication(self, sdu):
        try:
            pdu = SndcpPdu.parse(sdu)
        except Exception as exc:
            self.warning(
                "SNDCP PDU rejected | Bits(%d) | ErrorType(%s) | Error(%s)"
                % (len(sdu), type(exc).__name__, exc)
            )
            return

        self.expose_pdu(pdu)
        if isinstance(pdu, SnDataPdu):
            return

        self._process_unitdata(pdu)

    def _process_unitdata(self, pdu):
        key = (pdu.nsapi, pdu.npdu_number)

        if pdu.f == 1:
            self.segments[key] = {
                "expected": (pdu.segment_number + 1) % 16,
                "dcomp": pdu.dcomp,
                "pcomp": pdu.pcomp,
                "parts": [pdu.data.bits],
            }
        else:
            state = self.segments.get(key)
            if state is None:
                self.warning(
                    "SNDCP continuation rejected | Nsapi(%d) | NpduNumber(%d) | Reason(missing_first_segment)"
                    % key
                )
                return
            if pdu.segment_number != state["expected"]:
                del self.segments[key]
                self.warning(
                    "SNDCP continuation rejected | Nsapi(%d) | NpduNumber(%d) | ExpectedSegment(%d) | ReceivedSegment(%d)"
                    % (key[0], key[1], state["expected"], pdu.segment_number)
                )
                return
            state["parts"].append(pdu.data.bits)
            state["expected"] = (pdu.segment_number + 1) % 16

        if pdu.m == 1:
            return

        state = self.segments.pop(key)
        self.expose_pdu(
            ReassembledNpdu(
                pdu.nsapi,
                pdu.npdu_number,
                state["dcomp"],
                state["pcomp"],
                Bits("".join(state["parts"])),
            )
        )
