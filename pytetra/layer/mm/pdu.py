#!/usr/bin/env python3

"""
TETRA Mobility Management (MM) downlink PDU decoder.

Basis:
    ETSI EN 300 392-2 V3.8.1
    clause 16.9 / 16.10

DOWNLINK ONLY.

Important:
    - 4-bit MM PDU discriminator.
    - Correcte DOWNLINK discriminator mapping.
    - Correcte O-bit / P-bit verwerking.
    - Correcte M-bit / Type 3 / Type 4 verwerking.
    - Type 3/4 identifiers are decoded by identifier, not fixed order.
    - Unknown and security-related elements are retained as raw bits.
"""

from pytetra.pdu.sublayer32pdu import (
    Pdu,
    Type1,
    Type2,
    Type3,
    Type4,
    BitsElement,
    CompoundElement,
    PduDecodingException,
)

from pytetra.layer.mm.elements import *


# ============================================================================
# Raw helpers
# ============================================================================

class MmRawBits(BitsElement):
    name = "MM raw bits"


class MmUnknownType34(BitsElement):
    name = "Unknown MM Type 3/4 element"

class MmTrailingBits(BitsElement):
    name = "MM trailing bits"


# ============================================================================
# MM base parser
# ============================================================================

class MmPduBase(Pdu):
    """
    MM PDU parser conforming to the TETRA Type 3/4 encoding rules.

    We deliberately do NOT use CompoundElement.parse() here because the
    generic implementation in sublayer32pdu.py assumes a fixed ordering of
    Type 3 elements. TETRA instead uses the Type 3/4 identifier in the
    encoded stream.
    """

    type1 = []
    type2 = []
    type34 = []

    @classmethod
    def _decode_type1(cls, pdu, bits):
        for field in cls.type1:
            field.decode(pdu, bits)

    @classmethod
    def _decode_type2(cls, pdu, bits):
        for field in cls.type2:
            if len(bits) < 1:
                raise PduDecodingException(
                    "Missing Type 2 presence bit"
                )

            field.decode(pdu, bits)

    @classmethod
    def _type34_map(cls):
        result = {}

        for field in cls.type34:
            element = field.element
            identifier = getattr(element, "identifier", None)

            if identifier is not None:
                result[identifier] = field

        return result

    @classmethod
    def _decode_one_type34(cls, pdu, bits):
        """
        Decode one MM Type 3 or Type 4 element.

        Encoding:

            M-bit
            4-bit identifier
            11-bit length
            [6-bit repeat count for Type 4]
            payload
        """

        start_length = len(bits)

        if len(bits) < 1:
            raise PduDecodingException(
                "Missing M-bit in MM Type 3/4 section"
            )

        m_bit = bits.read_int(1)


        if m_bit == 0:
            return False

        if len(bits) < 15:
            raise PduDecodingException(
                "Truncated MM Type 3/4 header"
            )

        identifier = bits.read_int(4)
        length = bits.read_int(11)

        header_consumed = start_length - len(bits)

        field_map = cls._type34_map()
        field = field_map.get(identifier)

        if field is None:
            if length > len(bits):
                raise PduDecodingException(
                    "MM Type 3/4 element length %d exceeds "
                    "remaining %d bits"
                    % (length, len(bits))
                )

            raw = MmUnknownType34.parse(bits, length)

            pdu.add_field(raw)

            return True

        element_cls = field.element

        # ------------------------------------------------------------
        # Type 4
        # ------------------------------------------------------------

        if isinstance(field, Type4):
            if length < 6:
                raise PduDecodingException(
                    "Invalid Type 4 length %d for identifier %d"
                    % (length, identifier)
                )

            if length > len(bits):
                raise PduDecodingException(
                    "MM Type 4 length %d exceeds remaining %d bits"
                    % (length, len(bits))
                )

            payload = bits.read(length)

            repeat = payload.read_int(6)

            if repeat == 0:
                raise PduDecodingException(
                    "Invalid Type 4 repeat count 0 "
                    "(identifier %d)" % identifier
                )



            values = []

            for index in range(repeat):
                value = element_cls.parse(payload)
                values.append(value)



            if len(payload):
                raise PduDecodingException(
                    "Trailing bits inside MM Type 4 element "
                    "identifier %d: %d bits"
                    % (identifier, len(payload))
                )

            pdu.add_field(values)

            return True

        # ------------------------------------------------------------
        # Type 3
        # ------------------------------------------------------------

        if length > len(bits):
            raise PduDecodingException(
                "MM Type 3 length %d exceeds remaining %d bits"
                % (length, len(bits))
            )

        payload = bits.read(length)

        if (
            getattr(element_cls, "length", None) is None
            and not issubclass(element_cls, CompoundElement)
        ):
            value = MmRawBits.parse(payload, len(payload))
            pdu.add_field(value)

            return True

        value = element_cls.parse(payload)

        if len(payload):
            raise PduDecodingException(
                "Trailing bits inside MM Type 3 element "
                "identifier %d: %d bits"
                % (identifier, len(payload))
            )

        pdu.add_field(value)


        return True


    @classmethod
    def _decode_type34(cls, pdu, bits):
        while True:
            present = cls._decode_one_type34(pdu, bits)

            if not present:
                break

    @classmethod
    def parse(cls, bits):
        pdu = cls()

        # ------------------------------------------------------------
        # Type 1 elements
        # ------------------------------------------------------------

        cls._decode_type1(pdu, bits)

        # ------------------------------------------------------------
        # O-bit
        #
        # 0 = no optional elements are present
        # 1 = optional elements are present
        # ------------------------------------------------------------

        if len(bits) < 1:
            raise PduDecodingException(
                "%s missing O-bit" % cls.name
            )


        o_bit = bits.read_int(1)


        # ------------------------------------------------------------
        # Type 2 / Type 3 / Type 4 optional elements
        # ------------------------------------------------------------

        if o_bit:
            cls._decode_type2(pdu, bits)

            if cls.type34:
                cls._decode_type34(pdu, bits)

        # ------------------------------------------------------------
        # Preserve trailing bits
        #
        # The MM PDU has been decoded through the M-bit indicating
        # that no further Type 3/4 element follows. If bits remain
        # in the supplied SDU, preserve them as raw data instead of
        # discarding them or hiding them as padding.
        #
        # This is intentionally not treated as padding yet. The
        # relationship between the MM PDU length and the enclosing
        # MLE SDU must be verified separately.
        # ------------------------------------------------------------


        if len(bits):
            trailing_length = len(bits)
            trailing = MmTrailingBits.parse(bits, trailing_length)

            pdu.add_field(trailing)


        return pdu


# ============================================================================
# Raw / reserved MM PDUs
# ============================================================================

class MmRawPdu(MmPduBase):
    name = "MM RAW PDU"

    type1 = [
        Type1(PduType),
    ]

    type2 = []
    type34 = []

    @classmethod
    def parse(cls, bits):
        pdu = cls()

        pdu.add_field(PduType.parse(bits))

        if len(bits):
            pdu.add_field(
                MmRawBits.parse(bits, len(bits))
            )

        return pdu


class MmReservedPdu(MmRawPdu):
    name = "MM RESERVED PDU"


class DMmFunctionNotSupported(MmRawPdu):
    name = "MM PDU/FUNCTION NOT SUPPORTED"


# ============================================================================
# 0x0 D-OTAR
# Security definition is in EN 300 392-7.
# ============================================================================

class DOtar(MmPduBase):
    name = "D-OTAR"

    type1 = [
        Type1(PduType),
        Type1(OtarSubtype),
    ]

    type2 = []
    type34 = []

    @classmethod
    def parse(cls, bits):
        pdu = cls()

        # ------------------------------------------------------------
        # PDU type
        # ------------------------------------------------------------

        if len(bits) < 4:
            raise PduDecodingException(
                "D-OTAR missing PDU type"
            )

        pdu.add_field(
            PduType.parse(bits)
        )

        # ------------------------------------------------------------
        # OTAR subtype
        #
        # A D-OTAR PDU may be incomplete/truncated at the MM input
        # boundary. Preserve that condition explicitly instead of
        # producing a generic "not enough bits" error.
        # ------------------------------------------------------------

        if len(bits) < 4:
            pdu.add_field(
                MmTrailingBits.parse(bits, len(bits))
            )

            return pdu

        subtype = OtarSubtype.parse(bits)

        pdu.add_field(subtype)


        # ------------------------------------------------------------
        # Remaining OTAR payload
        #
        # Detailed OTAR coding is defined in EN 300 392-7.
        # Preserve it raw until the individual subtype structures
        # have been verified.
        # ------------------------------------------------------------

        if len(bits):
            raw = MmRawBits.parse(bits, len(bits))
            pdu.add_field(raw)


        return pdu


# ============================================================================
# 0x1 D-AUTHENTICATION
# Security definition is in EN 300 392-7.
# ============================================================================

class DAuthentication(MmPduBase):
    name = "D-AUTHENTICATION"

    type1 = [
        Type1(PduType),
        Type1(AuthenticationSubtype),
    ]

    type2 = []
    type34 = []

    @classmethod
    def parse(cls, bits):
        pdu = cls()

        # ------------------------------------------------------------
        # PDU type
        # ------------------------------------------------------------

        pdu.add_field(PduType.parse(bits))

        # ------------------------------------------------------------
        # Authentication subtype
        # ------------------------------------------------------------

        subtype = AuthenticationSubtype.parse(bits)
        pdu.add_field(subtype)

        # ------------------------------------------------------------
        # D-AUTHENTICATION DEMAND
        #
        # RAND1: 80 bits
        # RS:    80 bits
        # M-bit: optional Type 3/4 section
        # ------------------------------------------------------------

        if subtype.value == "D-AUTHENTICATION DEMAND":

            if len(bits) < 160:
                raise PduDecodingException(
                    "D-AUTHENTICATION DEMAND too short: "
                    "%d bits remaining, need at least 160"
                    % len(bits)
                )

            pdu.add_field(
                RandomChallenge.parse(bits)
            )

            pdu.add_field(
                RandomSeed.parse(bits)
            )

            if len(bits) < 1:
                raise PduDecodingException(
                    "D-AUTHENTICATION DEMAND missing M-bit"
                )

            m_bit = bits.read_int(1)

            if m_bit:
                raise PduDecodingException(
                    "D-AUTHENTICATION DEMAND contains "
                    "an unsupported optional Type 3/4 element"
                )

        # ------------------------------------------------------------
        # D-AUTHENTICATION RESPONSE
        #
        # RS:                    80 bits
        # RES2:                  32 bits
        # Mutual authentication: 1 bit
        # RAND1:                 80 bits if mutual authentication = 1
        # M-bit:                 optional Type 3/4 section
        # ------------------------------------------------------------

        elif subtype.value == "D-AUTHENTICATION RESPONSE":

            if len(bits) < 113:
                raise PduDecodingException(
                    "D-AUTHENTICATION RESPONSE too short: "
                    "%d bits remaining, need at least 113"
                    % len(bits)
                )

            pdu.add_field(
                RandomSeed.parse(bits)
            )

            pdu.add_field(
                ResponseValue.parse(bits)
            )

            mutual_authentication = MutualAuthenticationFlag.parse(bits)
            pdu.add_field(
                mutual_authentication
            )

            if (
                mutual_authentication.value
                == "Mutual authentication requested"
            ):
                if len(bits) < 80:
                    raise PduDecodingException(
                        "D-AUTHENTICATION RESPONSE missing RAND1: "
                        "%d bits remaining" % len(bits)
                    )

                pdu.add_field(
                    RandomChallenge.parse(bits)
                )

            if len(bits) < 1:
                raise PduDecodingException(
                    "D-AUTHENTICATION RESPONSE missing M-bit"
                )

            m_bit = bits.read_int(1)

            if m_bit:
                raise PduDecodingException(
                    "D-AUTHENTICATION RESPONSE contains "
                    "an unsupported optional Type 3/4 element"
                )

        # ------------------------------------------------------------
        # D-AUTHENTICATION RESULT
        #
        # Authentication result: 1 bit
        # Mutual authentication: 1 bit
        # RES2:                   32 bits if mutual authentication = 1
        # M-bit:                  optional Type 3/4 section
        # ------------------------------------------------------------

        elif subtype.value == "D-AUTHENTICATION RESULT":

            if len(bits) < 2:
                raise PduDecodingException(
                    "D-AUTHENTICATION RESULT too short: "
                    "%d bits remaining, need at least 2"
                    % len(bits)
                )

            pdu.add_field(
                AuthenticationResult.parse(bits)
            )

            mutual_authentication = MutualAuthenticationFlag.parse(bits)
            pdu.add_field(
                mutual_authentication
            )

            if (
                mutual_authentication.value
                == "Mutual authentication requested"
            ):
                if len(bits) < 32:
                    raise PduDecodingException(
                        "D-AUTHENTICATION RESULT missing RES2: "
                        "%d bits remaining" % len(bits)
                    )

                pdu.add_field(
                    ResponseValue.parse(bits)
                )

            if len(bits) < 1:
                raise PduDecodingException(
                    "D-AUTHENTICATION RESULT missing M-bit"
                )

            m_bit = bits.read_int(1)

            if m_bit:
                raise PduDecodingException(
                    "D-AUTHENTICATION RESULT contains "
                    "an unsupported optional Type 3/4 element"
                )

        # ------------------------------------------------------------
        # D-AUTHENTICATION REJECT
        #
        # Authentication reject reason: 3 bits
        # M-bit:                       optional Type 3/4 section
        # ------------------------------------------------------------

        elif subtype.value == "D-AUTHENTICATION REJECT":

            if len(bits) < 3:
                raise PduDecodingException(
                    "D-AUTHENTICATION REJECT too short: "
                    "%d bits remaining, need at least 3"
                    % len(bits)
                )

            pdu.add_field(
                AuthenticationRejectReason.parse(bits)
            )

            if len(bits) < 1:
                raise PduDecodingException(
                    "D-AUTHENTICATION REJECT missing M-bit"
                )

            m_bit = bits.read_int(1)

            if m_bit:
                raise PduDecodingException(
                    "D-AUTHENTICATION REJECT contains "
                    "an unsupported optional Type 3/4 element"
                )

        else:
            raise PduDecodingException(
                "Unknown D-AUTHENTICATION subtype: %s"
                % subtype.value
            )

        return pdu


#=============================================================================
# 0x2 D-CK CHANGE DEMAND
# Security definition is in EN 300 392-7.
# ============================================================================

class DCkChangeDemand(MmPduBase):
    name = "D-CK CHANGE DEMAND"

    @classmethod
    def parse(cls, bits):
        pdu = cls()
        pdu.add_field(PduType.parse(bits))
        pdu.add_field(AcknowledgementFlag.parse(bits))
        pdu.add_field(ChangeOfSecurityClass.parse(bits))
        key_type = KeyChangeType.parse(bits)
        pdu.add_field(key_type)

        if key_type.value == "SCK":
            pdu.add_field(SckUse.parse(bits))
            count = NumberOfScksChanged.parse(bits)
            pdu.add_field(count)
            if count.value == 0:
                pdu.add_field(SckSubsetGroupingType.parse(bits))
                pdu.add_field(SckSubsetNumber.parse(bits))
                pdu.add_field(SckVersionNumber.parse(bits))
            else:
                for _ in range(count.value):
                    pdu.add_field(SckData.parse(bits))
        elif key_type.value == "CCK":
            pdu.add_field(CckId.parse(bits))
        elif key_type.value == "GCK":
            count = NumberOfGcksChanged.parse(bits)
            pdu.add_field(count)
            for _ in range(count.value):
                pdu.add_field(GckData.parse(bits))
        elif key_type.value == "Class 3 CCK/GCK activation":
            pdu.add_field(CckId.parse(bits))
            pdu.add_field(GckVersionNumber.parse(bits))
        elif key_type.value == "All GCKs":
            pdu.add_field(GckVersionNumber.parse(bits))

        time_type = TimeType.parse(bits)
        pdu.add_field(time_type)
        if time_type.value == "Absolute IV":
            pdu.add_field(SlotNumber.parse(bits))
            pdu.add_field(FrameNumber.parse(bits))
            pdu.add_field(MultiframeNumber.parse(bits))
            pdu.add_field(HyperframeNumber.parse(bits))
        elif time_type.value == "Network time":
            pdu.add_field(NetworkTime.parse(bits))
        if len(bits):
            pdu.add_field(MmTrailingBits.parse(bits, len(bits)))
        return pdu


# ============================================================================
# 0x3 D-DISABLE
# Security definition is in EN 300 392-7.
# ============================================================================

class _DEnableDisableBase(MmPduBase):
    equipment_flag = None
    subscription_flag = None
    has_disabling_type = False

    @classmethod
    def parse(cls, bits):
        pdu = cls()
        pdu.add_field(PduType.parse(bits))
        pdu.add_field(IntentConfirm.parse(bits))
        if cls.has_disabling_type:
            pdu.add_field(DisablingType.parse(bits))
        equipment = cls.equipment_flag.parse(bits)
        pdu.add_field(equipment)
        if equipment.value:
            pdu.add_field(TetraEquipmentIdentity.parse(bits))
        subscription = cls.subscription_flag.parse(bits)
        pdu.add_field(subscription)
        if subscription.value:
            pdu.add_field(AddressExtension.parse(bits))
            pdu.add_field(Ssi.parse(bits))

        if len(bits):
            authentication_present = bits.read_int(1)
            if authentication_present:
                pdu.add_field(RandomChallenge.parse(bits))
                pdu.add_field(RandomSeed.parse(bits))
        if len(bits):
            cls._decode_type34(pdu, bits)
        if len(bits):
            pdu.add_field(MmTrailingBits.parse(bits, len(bits)))
        return pdu


class DDisable(_DEnableDisableBase):
    name = "D-DISABLE"
    equipment_flag = EquipmentDisableFlag
    subscription_flag = SubscriptionDisableFlag
    has_disabling_type = True


# ============================================================================
# 0x4 D-ENABLE
# Security definition is in EN 300 392-7.
# ============================================================================

class DEnable(_DEnableDisableBase):
    name = "D-ENABLE"
    equipment_flag = EquipmentEnableFlag
    subscription_flag = SubscriptionEnableFlag


# ============================================================================
# 0x5 D-LOCATION UPDATE ACCEPT
# ============================================================================

class DLocationUpdateAccept(MmPduBase):
    name = "D-LOCATION UPDATE ACCEPT"

    type1 = [
        Type1(PduType),
        Type1(LocationUpdateAcceptType),
    ]

    type2 = [
        Type2(Ssi),
        Type2(AddressExtension),
        Type2(SubscriberClass),
        Type2(EnergySavingInformation),
        Type2(ScchInformationAndDistributionOn18thFrame),
    ]

    type34 = [
        Type3(DefaultGroupAttachmentLifetime),
        Type4(NewRegisteredArea),
        Type3(SecurityDownlink),
        Type3(GroupReportResponse),
        Type3(GroupIdentityLocationAccept),
        Type3(DmMsAddress),
        Type4(GroupIdentityDownlink),
        Type3(AuthenticationDownlink),
        Type3(GroupIdentitySecurityRelatedInformation),
        Type3(CellTypeControl),
        Type3(Proprietary),
    ]


# ============================================================================
# 0x6 D-LOCATION UPDATE COMMAND
# ============================================================================

class DLocationUpdateCommand(MmPduBase):
    name = "D-LOCATION UPDATE COMMAND"

    type1 = [
        Type1(PduType),
        Type1(GroupIdentityReport),
        Type1(CipherControl),
    ]

    type2 = [
        Type2(AddressExtension),
    ]

    type34 = [
        Type3(Proprietary),
    ]


# ============================================================================
# 0x7 D-LOCATION UPDATE REJECT
# ============================================================================

class DLocationUpdateReject(MmPduBase):
    name = "D-LOCATION UPDATE REJECT"

    type1 = [
        Type1(PduType),
        Type1(LocationUpdateType),
        Type1(RejectCause),
        Type1(CipherControl),
    ]

    type2 = [
        Type2(AddressExtension),
    ]

    type34 = [
        Type3(Proprietary),
    ]


# ============================================================================
# 0x9 D-LOCATION UPDATE PROCEEDING
# ============================================================================

class DLocationUpdateProceeding(MmPduBase):
    name = "D-LOCATION UPDATE PROCEEDING"

    type1 = [
        Type1(PduType),
        Type1(Ssi),
        Type1(AddressExtension),
    ]

    type2 = []

    type34 = [
        Type3(Proprietary),
    ]


# ============================================================================
# 0xA D-ATTACH/DETACH GROUP IDENTITY
# ============================================================================

class DAttachDetachGroupIdentity(MmPduBase):
    name = "D-ATTACH/DETACH GROUP IDENTITY"

    type1 = [
        Type1(PduType),
        Type1(GroupIdentityReport),
        Type1(GroupIdentityAcknowledgementRequest),
        Type1(GroupIdentityAttachDetachMode),
    ]

    type2 = []

    type34 = [
        Type3(Proprietary),
        Type3(GroupReportResponse),
        Type4(GroupIdentityDownlink),
    ]


# ============================================================================
# 0xB D-ATTACH/DETACH GROUP IDENTITY ACKNOWLEDGEMENT
# ============================================================================

class DAttachDetachGroupIdentityAcknowledgement(MmPduBase):
    name = "D-ATTACH/DETACH GROUP IDENTITY ACKNOWLEDGEMENT"

    type1 = [
        Type1(PduType),
        Type1(GroupIdentityAcceptReject),
        Type1(Reserved),
    ]

    type2 = []

    type34 = [
        Type3(Proprietary),
        Type4(GroupIdentityDownlink),
        Type4(GroupIdentitySecurityRelatedInformation),
    ]


# ============================================================================
# 0xC D-MM STATUS
# ============================================================================

class DMmStatus(MmPduBase):
    """
    D-MM STATUS.

    The first two fields are always:
        PDU type       4 bits
        Status downlink 6 bits

    The remainder depends on the status value.

    We decode the standardized sub-PDUs where their definition is
    available directly in EN 300 392-2. Unknown / DMO-specific
    extensions remain raw.
    """

    name = "D-MM STATUS"

    type1 = [
        Type1(PduType),
        Type1(StatusDownlink),
    ]

    type2 = []
    type34 = []

    @classmethod
    def parse(cls, bits):
        pdu = cls()

        pdu.add_field(PduType.parse(bits))

        status = StatusDownlink.parse(bits)
        pdu.add_field(status)

        status_value = status.value

        # ------------------------------------------------------------
        # Status dependant payloads.
        #
        # These are encoded directly after Status downlink and have
        # their own definitions.
        # ------------------------------------------------------------

        if status_value in (
            "Change of energy saving mode request",
            "Change of energy saving mode response",
        ):
            pdu.add_field(
                EnergySavingInformation.parse(bits)
            )

        elif status_value == "Dual watch mode response":
            pdu.add_field(
                EnergySavingInformation.parse(bits)
            )

            pdu.add_field(
                ResultOfDualWatchRequest.parse(bits)
            )

            pdu.add_field(
                Reserved8.parse(bits)
            )

            if len(bits):
                # The optional Type 2 SCCH information has a P-bit.
                present = bits.read_int(1)

                if present:
                    pdu.add_field(
                        ScchInformationAndDistributionOn18thFrame.parse(
                            bits
                        )
                    )

        elif status_value == "Terminating dual watch mode response":
            pdu.add_field(
                Reserved8.parse(bits)
            )

            if len(bits):
                present = bits.read_int(1)

                if present:
                    pdu.add_field(
                        EnergySavingInformation.parse(bits)
                    )

            if len(bits):
                present = bits.read_int(1)

                if present:
                    pdu.add_field(
                        ScchInformationAndDistributionOn18thFrame.parse(
                            bits
                        )
                    )

        elif status_value == "Change of dual watch mode request":
            pdu.add_field(
                EnergySavingInformation.parse(bits)
            )

            pdu.add_field(
                ReasonForDualWatchChangeBySwmi.parse(bits)
            )

            pdu.add_field(
                Reserved8.parse(bits)
            )

            if len(bits):
                present = bits.read_int(1)

                if present:
                    pdu.add_field(
                        ScchInformationAndDistributionOn18thFrame.parse(
                            bits
                        )
                    )

        elif status_value == "MS frequency bands request":
            # No mandatory payload in the base definition.
            pass

        elif status_value == "Periodic distance reporting":
            pdu.add_field(
                DistanceReportingTimer.parse(bits)
            )

            pdu.add_field(
                DistanceReportingValidity.parse(bits)
            )

        else:
            # Unknown / DMO / future status:
            # retain the remainder exactly.
            if len(bits):
                pdu.add_field(
                    MmRawBits.parse(bits, len(bits))
                )

        if len(bits):
            raise PduDecodingException(
                "Trailing bits at end of D-MM STATUS: %d"
                % len(bits)
            )

        return pdu


# ============================================================================
# MM PDU discriminator
# ============================================================================

class MmPdu:
    """
    ETSI EN 300 392-2, clause 16.10.39.

    DOWNLINK mapping only.
    """

    element = PduType

    pdu_types = {
        0x0: DOtar,
        0x1: DAuthentication,
        0x2: DCkChangeDemand,
        0x3: DDisable,
        0x4: DEnable,
        0x5: DLocationUpdateAccept,
        0x6: DLocationUpdateCommand,
        0x7: DLocationUpdateReject,
        0x8: MmReservedPdu,
        0x9: DLocationUpdateProceeding,
        0xA: DAttachDetachGroupIdentity,
        0xB: DAttachDetachGroupIdentityAcknowledgement,
        0xC: DMmStatus,
        0xD: MmReservedPdu,
        0xE: MmReservedPdu,
        0xF: DMmFunctionNotSupported,
    }

    @classmethod
    def parse(cls, bits):
        if len(bits) < 4:
            raise PduDecodingException(
                "MM PDU too short: %d bits" % len(bits)
            )

        pdu_type = bits.peek_int(0, 4)

        pdu_class = cls.pdu_types.get(pdu_type)

        if pdu_class is None:
            raise PduDecodingException(
                "Unknown MM downlink PDU type 0x%X"
                % pdu_type
            )

        return pdu_class.parse(bits)
