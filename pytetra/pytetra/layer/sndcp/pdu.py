from collections import OrderedDict

from pytetra.logger import format_record
from pytetra.pdu import Bits, PduDecodingException


class SndcpPdu(object):
    """Base parser for the common downlink SNDCP header."""

    def __init__(self):
        self.fields = OrderedDict()

    def __getattr__(self, name):
        try:
            return self.fields[name]
        except KeyError:
            raise AttributeError(name)

    def __repr__(self):
        return format_record(type(self).__name__, self.fields.items())

    @classmethod
    def parse(cls, source):
        bits = source.bits if isinstance(source, Bits) else str(source)
        if len(bits) < 8:
            raise PduDecodingException(
                "SNDCP PDU too short for common header: %d bits" % len(bits)
            )

        header = {
            "x": int(bits[0], 2),
            "f": int(bits[1], 2),
            "t": int(bits[2], 2),
            "m": int(bits[3], 2),
            "nsapi": int(bits[4:8], 2),
        }
        remainder = bits[8:]

        if header["t"] == 1:
            return SnUnitdataPdu.from_parts(header, remainder)
        return SnDataPdu.from_parts(header, remainder)

    @classmethod
    def from_parts(cls, header, remainder):
        pdu = cls()
        pdu.fields.update(header)
        pdu.fields["payload"] = Bits(remainder)
        return pdu


class SnDataPdu(SndcpPdu):
    """Acknowledged SN-DATA form; retain unimplemented body without loss."""


class SnUnitdataPdu(SndcpPdu):
    """Downlink SN-UNITDATA segment."""

    @classmethod
    def from_parts(cls, header, remainder):
        pdu = cls()
        pdu.fields.update(header)
        pos = 0

        if header["f"] == 1:
            if len(remainder) < 8:
                raise PduDecodingException(
                    "First SN-UNITDATA segment lacks DCOMP/PCOMP"
                )
            pdu.fields["dcomp"] = int(remainder[0:4], 2)
            pdu.fields["pcomp"] = int(remainder[4:8], 2)
            pos = 8
        else:
            pdu.fields["dcomp"] = None
            pdu.fields["pcomp"] = None

        if len(remainder) < pos + 16:
            raise PduDecodingException(
                "SN-UNITDATA segment lacks segment/N-PDU numbers"
            )

        pdu.fields["segment_number"] = int(remainder[pos:pos + 4], 2)
        pdu.fields["npdu_number"] = int(remainder[pos + 4:pos + 16], 2)
        pdu.fields["data"] = Bits(remainder[pos + 16:])
        return pdu


class ReassembledNpdu(SndcpPdu):
    def __init__(self, nsapi, npdu_number, dcomp, pcomp, data):
        super(ReassembledNpdu, self).__init__()
        self.fields.update((
            ("nsapi", nsapi),
            ("npdu_number", npdu_number),
            ("dcomp", dcomp),
            ("pcomp", pcomp),
            ("data", data),
        ))
