import unittest
from pytetra.pdu.pdu import Bits
from pytetra.layer.mm.pdu import (
    DCkChangeDemand,
    DDisable,
    DEnable,
    DLocationUpdateAccept,
    DMmFunctionNotSupported,
    MmPdu,
)
from pytetra.layer.mm.elements import *


class MmTestCase(unittest.TestCase):
    def test_security_management_pdus_decode_standard_fields(self):
        ck = MmPdu.parse(Bits(
            "0010" "1" "10" "001" "0001001000110100" "10"
        ))
        self.assertIsInstance(ck, DCkChangeDemand)
        self.assertIn("CckId(4660)", repr(ck))
        self.assertIn("TimeType('Immediate')", repr(ck))

        disable = MmPdu.parse(Bits("0011" "0" "0" "0" "0" "0" "0"))
        self.assertIsInstance(disable, DDisable)
        self.assertIn("DisablingType('Temporary')", repr(disable))

        enable = MmPdu.parse(Bits("0100" "1" "0" "0" "0" "0"))
        self.assertIsInstance(enable, DEnable)
        self.assertIn("IntentConfirm('Confirmation')", repr(enable))

    def test_function_not_supported_has_standardized_pdu_name(self):
        pdu = MmPdu.parse(Bits("1111" "1010"))
        self.assertIsInstance(pdu, DMmFunctionNotSupported)

    def test_dlocationupdateaccept(self):
        bits = '0101011100000101010000011101000110111000001001100000010111000000000111110111000100111100'
        #       ****                                                                                      PDU type = 5 (D-LOCATION UPDATE ACCEPT)
        #           ***                                                                                   Location update accept type = 3 (ITSI attach)
        #              O                                                                                  O-Bit = 1
        #               P                                                                                 P-Bit = 0
        #                P                                                                                P-Bit = 0
        #                 P                                                                               P-Bit = 0
        #                  P                                                                              P-Bit = 0
        #                   P                                                                             P-Bit = 0
        #                    M                                                                            M-Bit = 1
        #                     ****                                                                        Type 3/4 element identifier = 5 (Group identity location accept)
        #                         ***********                                                             Length indicator = 58
        #                                    ==========================================================   Group identity location accept
        #                                    .                                                              Group identity accept/reject = 0 (All attachment/detachments accepted)
        #                                     .                                                             Reserved = 0
        #                                      O                                                            O-Bit = 1
        #                                       M                                                           M-Bit = 1
        #                                        ****                                                       Type 3/4 element identifier = 7 (Group identity downlink)
        #                                            ***********                                            Length indicator = 38
        #                                                       ======================================        Group identity downlink
        #                                                       ******                                        Number of repeated elements = 1
        #                                                             ================================        Element 1
        #                                                             *                                         Group identity attach/detach type identifier = 0 (Attachment)
        #                                                              =====                                    Group identity attachment
        #                                                              **                                         Group identity attachment lifetime = 3 (Attachment for next location update required)
        #                                                                ***                                      Class of Usage = 4 (Class of usage 5)
        #                                                                   **                                  Group identity address type = 0 (GSSI)
        #                                                                     ************************          GSSI = 515151
        #                                                                                             *     M-Bit = 0
        #                                                                                              *  M-Bit = 0
        pdu = DLocationUpdateAccept(
            PduType(5),
            LocationUpdateAcceptType('ITSI attach'),
            GroupIdentityLocationAccept(
                GroupIdentityAcceptReject('All attachment/detachments accepted'),
                Reserved(0),
                [
                    GroupIdentityDownlink(
                        GroupIdentityAttachDetachTypeIdentifier('Attachment'),
                        GroupIdentityAttachment(
                            GroupIdentityAttachmentLifetime(
                                'Attachment for next location update required'
                            ),
                            ClassOfUsage('Class of usage 5')
                        ),
                        GroupIdentityAddressType('GSSI'),
                        Gssi(515151)
                    )
                ]
            )
        )
        assert MmPdu.parse(Bits(bits)) == pdu

if __name__ == '__main__':
    unittest.main()
