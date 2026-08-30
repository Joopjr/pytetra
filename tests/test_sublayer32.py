import unittest

from pytetra.pdu.pdu import Bits
from pytetra.pdu.sublayer32pdu import (
    BitsElement,
    CompoundElement,
    Type3,
    UnknownType34Element,
)


class KnownExtension(BitsElement):
    identifier = 2


class ExtensionContainer(CompoundElement):
    type1 = []
    type2 = []
    type34 = [Type3(KnownExtension)]
    has_o_bit = True


class Sublayer32TestCase(unittest.TestCase):
    def test_multiple_known_and_unknown_type3_elements(self):
        encoded = (
            "1"                       # O-bit
            "1" "0010" "00000000011" "101"  # known, 3 bits
            "1" "1111" "00000000010" "01"   # unknown, 2 bits
            "0"                       # final M-bit
        )

        pdu = ExtensionContainer.parse(Bits(encoded))

        self.assertEqual(pdu[KnownExtension].value.bits, "101")
        unknown = pdu[UnknownType34Element]
        self.assertEqual(unknown.identifier, 15)
        self.assertEqual(unknown.length, 2)
        self.assertEqual(unknown.value.bits, "01")

    def test_no_optional_elements(self):
        pdu = ExtensionContainer.parse(Bits("0"))
        self.assertEqual(pdu.fields, {})


if __name__ == "__main__":
    unittest.main()
