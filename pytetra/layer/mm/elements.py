#!/usr/bin/env python3

"""
TETRA Mobility Management (MM) information elements.

Basis:
    ETSI EN 300 392-2 V3.8.1
    clause 16.10

This module implements downlink MM only.

Important:
    - PDU Type is 4 bits.
    - Type 2 elements are indicated by P-bits.
    - Type 3/4 elements are identified by:
          M-bit
          4-bit Type 3/4 identifier
          11-bit length
          [6-bit repeat count for Type 4]
    - Security-related elements defined in EN 300 392-7 are deliberately
      retained as raw bits when their full definition is unavailable here.
"""

from pytetra.pdu.sublayer32pdu import (
    IntElement,
    EnumElement,
    CompoundElement,
    Type1,
    Type2,
    Type4,
)


# ============================================================================
# Generic helpers
# ============================================================================

class FixedBits(IntElement):
    """
    Generic fixed-length integer element.

    Subclasses define 'length'.
    """
    pass


class AcknowledgementFlag(EnumElement):
    name = "Acknowledgement"
    length = 1
    enum = ["Not requested", "Requested"]


class ChangeOfSecurityClass(EnumElement):
    name = "Change of security class"
    length = 2
    enum = ["No change", "Class 1", "Class 2", "Class 3"]


class KeyChangeType(EnumElement):
    name = "Key change type"
    length = 3
    enum = ["SCK", "CCK", "GCK", "Class 3 CCK/GCK activation",
            "All GCKs", "No cipher key", "Reserved", "Reserved"]


class SckUse(FixedBits):
    name, length = "SCK use", 1


class NumberOfScksChanged(FixedBits):
    name, length = "Number of SCKs changed", 4


class SckSubsetGroupingType(FixedBits):
    name, length = "SCK subset grouping type", 4


class SckSubsetNumber(FixedBits):
    name, length = "SCK subset number", 5


class SckVersionNumber(FixedBits):
    name, length = "SCK version number", 16


class SckData(FixedBits):
    name, length = "SCK data", 21


class CckId(FixedBits):
    name, length = "CCK identifier", 16


class NumberOfGcksChanged(FixedBits):
    name, length = "Number of GCKs changed", 4


class GckData(FixedBits):
    name, length = "GCK data", 32


class GckVersionNumber(FixedBits):
    name, length = "GCK version number", 16


class TimeType(EnumElement):
    name = "Time type"
    length = 2
    enum = ["Absolute IV", "Network time", "Immediate", "Currently in use"]


class SlotNumber(FixedBits):
    name, length = "Slot number", 2


class HyperframeNumber(FixedBits):
    name, length = "Hyperframe number", 16


class NetworkTime(FixedBits):
    name, length = "Network time", 48


class IntentConfirm(EnumElement):
    name = "Intent or confirmation"
    length = 1
    enum = ["Intent", "Confirmation"]


class DisablingType(EnumElement):
    name = "Disabling type"
    length = 1
    enum = ["Temporary", "Permanent"]


class EquipmentDisableFlag(FixedBits):
    name, length = "Equipment disable", 1


class EquipmentEnableFlag(FixedBits):
    name, length = "Equipment enable", 1


class SubscriptionDisableFlag(FixedBits):
    name, length = "Subscription disable", 1


class SubscriptionEnableFlag(FixedBits):
    name, length = "Subscription enable", 1


class TetraEquipmentIdentity(FixedBits):
    name, length = "TETRA equipment identity", 60


# ============================================================================
# 16.10.39 PDU type
# ============================================================================

class PduType(IntElement):
    name = "PDU type"
    length = 4



class OtarSubtype(EnumElement):
    name = "OTAR subtype"
    length = 4

    enum = [
        "CCK provide",
        "CCK reject",
        "SCK provide",
        "SCK reject",
        "GCK provide",
        "GCK reject",
        "Key associate demand",
        "OTAR new cell",
        "GSKO provide",
        "GSKO reject",
        "Key delete demand",
        "Key status demand",
        "CMG GTSI provide",
        "DM SCK activate",
        "Reserved",
        "Reserved",
    ]


# ============================================================================
# Basic MM information elements
# ============================================================================

class Ssi(IntElement):
    name = "SSI"
    length = 24


class Mcc(IntElement):
    name = "MCC"
    length = 10


class Mnc(IntElement):
    name = "MNC"
    length = 14


class SubscriberClass(IntElement):
    name = "Subscriber class"
    length = 16


class Reserved(IntElement):
    name = "Reserved"
    length = 1


# ============================================================================
# Address extension
# 16.10.1
# ============================================================================

class AddressExtension(CompoundElement):
    name = "Address extension"

    type1 = [
        Type1(Mcc),
        Type1(Mnc),
    ]

    type2 = []
    type34 = []


# ============================================================================
# Cipher control / ciphering parameters
# 16.10.2 / 16.10.3
# ============================================================================

class CipherControl(EnumElement):
    name = "Cipher control"
    length = 1

    enum = [
        "ciphering off",
        "ciphering on",
    ]


class CipheringParameters(IntElement):
    """
    EN 300 392-2 refers the actual coding to EN 300 392-7.

    The MM PDU definition specifies 10 bits here.
    """

    name = "Ciphering parameters"
    length = 10


# ============================================================================
# Energy saving
# 16.10.9 / 16.10.10
# ============================================================================

class EnergySavingMode(EnumElement):
    name = "Energy saving mode"
    length = 3

    enum = [
        "Stay alive",
        "Economy mode 1 (EG1)",
        "Economy mode 2 (EG2)",
        "Economy mode 3 (EG3)",
        "Economy mode 4 (EG4)",
        "Economy mode 5 (EG5)",
        "Economy mode 6 (EG6)",
        "Economy mode 7 (EG7)",
    ]


class FrameNumber(IntElement):
    name = "Frame number"
    length = 5


class MultiframeNumber(IntElement):
    name = "Multiframe number"
    length = 6


class EnergySavingInformation(CompoundElement):
    name = "Energy saving information"

    type1 = [
        Type1(EnergySavingMode),
        Type1(FrameNumber),
        Type1(MultiframeNumber),
    ]

    type2 = []
    type34 = []


# ============================================================================
# SCCH
# 16.10.45 / 16.10.46
# ============================================================================

class ScchInformation(IntElement):
    name = "SCCH information"
    length = 4


class DistributionOn18thFrame(IntElement):
    name = "Distribution on 18th frame"
    length = 2


class ScchInformationAndDistributionOn18thFrame(CompoundElement):
    name = "SCCH information and distribution on 18th frame"

    type1 = [
        Type1(ScchInformation),
        Type1(DistributionOn18thFrame),
    ]

    type2 = []
    type34 = []


# ============================================================================
# Location update
# 16.10.35 / 16.10.35a
# ============================================================================

class LocationUpdateAcceptType(EnumElement):
    name = "Location update accept type"
    length = 3

    enum = [
        "Roaming location updating",
        "Temporary registration",
        "Periodic location updating",
        "ITSI attach",
        "Call restoration roaming location updating",
        "Migrating or call restoration migrating location updating",
        "Demand location updating",
        "Disabled MS updating",
    ]


class LocationUpdateType(EnumElement):
    name = "Location update type"
    length = 3

    enum = [
        "Roaming location updating",
        "Migrating location updating",
        "Periodic location updating",
        "ITSI attach",
        "Call restoration roaming location updating",
        "Call restoration migrating location updating",
        "Demand location updating",
        "Disabled MS updating",
    ]


class RejectCause(IntElement):
    name = "Reject cause"
    length = 5


# ============================================================================
# LA / registered area
# 16.10.30 - 16.10.33 / 16.10.40
# ============================================================================

class LaTimer(EnumElement):
    name = "LA timer"
    length = 3

    enum = [
        "10 min",
        "30 min",
        "1 hour",
        "2 hours",
        "4 hours",
        "8 hours",
        "24 hours",
        "no timing",
    ]


class La(IntElement):
    name = "LA"
    length = 14


class Lacc(IntElement):
    name = "LACC"
    length = 10


class Lanc(IntElement):
    name = "LANC"
    length = 14


class NewRegisteredArea(CompoundElement):
    """
    Type 3 element.

    Standard:
        LA timer       3 bits
        LA            14 bits
        LACC           10 bits, Type 2 optional
        LANC           14 bits, Type 2 optional
    """

    name = "New registered area"
    identifier = 2

    type1 = [
        Type1(LaTimer),
        Type1(La),
    ]

    type2 = [
        Type2(Lacc),
        Type2(Lanc),
    ]

    type34 = []


# ============================================================================
# Group identity
# 16.10.12 - 16.10.28
# ============================================================================

class GroupIdentityReport(EnumElement):
    name = "Group identity report"
    length = 1

    enum = [
        "Not report request",
        "Report request",
    ]


class GroupIdentityAcknowledgementRequest(EnumElement):
    name = "Group identity acknowledgement request"
    length = 1

    enum = [
        "Acknowledgement not requested",
        "Acknowledgement requested",
    ]


class GroupIdentityAcceptReject(EnumElement):
    name = "Group identity accept/reject"
    length = 1

    enum = [
        "All attachment/detachments accepted",
        "At least one attachment/detachment rejected",
    ]


class GroupIdentityAcknowledgementType(EnumElement):
    name = "Group identity acknowledgement type"
    length = 1

    enum = [
        "All attachment/detachments accepted",
        "At least one attachment rejected",
    ]


class GroupIdentityAttachDetachMode(EnumElement):
    name = "Group identity attach/detach mode"
    length = 1

    enum = [
        "Amendment",
        "Detach all currently attached group identities and "
        "attach group identities defined in the group "
        "identity (downlink/uplink) element",
    ]


class GroupIdentityAttachDetachTypeIdentifier(EnumElement):
    name = "Group identity attach/detach type identifier"
    length = 1

    enum = [
        "Attachment",
        "Detachment",
    ]


class GroupIdentityAttachmentLifetime(EnumElement):
    name = "Group identity attachment lifetime"
    length = 2

    enum = [
        "Attachment not needed",
        "Attachment for next ITSI attach required",
        "Attachment not allowed for next ITSI attach",
        "Attachment for next location update required",
    ]


class ClassOfUsage(EnumElement):
    name = "Class of usage"
    length = 3

    enum = [
        "Class of usage 1",
        "Class of usage 2",
        "Class of usage 3",
        "Class of usage 4",
        "Class of usage 5",
        "Class of usage 6",
        "Class of usage 7",
        "Class of usage 8",
    ]


class GroupIdentityDetachmentDownlink(EnumElement):
    name = "Group identity detachment downlink"
    length = 2

    enum = [
        "Unknown group identity",
        "Temporary 1 detachment",
        "Temporary 2 detachment",
        "Permanent detachment",
    ]


class GroupIdentityAddressType(EnumElement):
    name = "Group identity address type"
    length = 2

    enum = [
        "GSSI",
        "GSSI + Address Extension (GTSI)",
        "(V)GSSI",
        "GSSI + Address Extension + (V)GSSI (GTSI-V(GSSI))",
    ]


class Gssi(IntElement):
    name = "GSSI"
    length = 24


class VGssi(IntElement):
    name = "(V)GSSI"
    length = 24


class GroupIdentityAttachment(CompoundElement):
    name = "Group identity attachment"

    type1 = [
        Type1(GroupIdentityAttachmentLifetime),
        Type1(ClassOfUsage),
    ]

    type2 = []
    type34 = []


class GroupIdentityDownlink(CompoundElement):
    """
    16.10.22

    Type 4 element.

    GIADTI:
        0 -> Group Identity Attachment
        1 -> Group Identity Detachment Downlink

    GIAT:
        0 -> GSSI
        1 -> GSSI + Address Extension
        2 -> (V)GSSI
        3 -> GSSI + Address Extension + (V)GSSI
    """

    name = "Group identity downlink"
    identifier = 7

    type1 = [
        Type1(GroupIdentityAttachDetachTypeIdentifier),

        Type1(
            GroupIdentityAttachment,
            cond=lambda pdu:
                pdu[GroupIdentityAttachDetachTypeIdentifier].value
                == "Attachment",
        ),

        Type1(
            GroupIdentityDetachmentDownlink,
            cond=lambda pdu:
                pdu[GroupIdentityAttachDetachTypeIdentifier].value
                == "Detachment",
        ),

        Type1(GroupIdentityAddressType),

        Type1(
            Gssi,
            cond=lambda pdu:
                pdu[GroupIdentityAddressType].value in (
                    "GSSI",
                    "GSSI + Address Extension (GTSI)",
                    "GSSI + Address Extension + (V)GSSI "
                    "(GTSI-V(GSSI))",
                ),
        ),

        Type1(
            AddressExtension,
            cond=lambda pdu:
                pdu[GroupIdentityAddressType].value in (
                    "GSSI + Address Extension (GTSI)",
                    "GSSI + Address Extension + (V)GSSI "
                    "(GTSI-V(GSSI))",
                ),
        ),

        Type1(
            VGssi,
            cond=lambda pdu:
                pdu[GroupIdentityAddressType].value in (
                    "(V)GSSI",
                    "GSSI + Address Extension + (V)GSSI "
                    "(GTSI-V(GSSI))",
                ),
        ),
    ]

    type2 = []
    type34 = []


class GroupIdentityLocationAccept(CompoundElement):
    """
    16.10.23

    Type 3 element.

    Mandatory:
        Group identity accept/reject  1 bit
        Reserved                     1 bit

    Optional:
        Group identity downlink      Type 4
    """

    name = "Group identity location accept"
    identifier = 5

    type1 = [
        Type1(GroupIdentityAcceptReject),
        Type1(Reserved),
    ]

    type2 = []

    type34 = [
        Type4(GroupIdentityDownlink),
    ]

    has_o_bit = True


# ============================================================================
# Type 3 / Type 4 identifiers
# 16.10.51
# ============================================================================

class DefaultGroupAttachmentLifetime(GroupIdentityAttachmentLifetime):
    name = "Default group attachment lifetime"
    identifier = 1


class AuthenticationDownlink(IntElement):
    """
    Security-related Type 3 element.
    Detailed coding is defined in EN 300 392-7.
    """

    name = "Authentication downlink"
    identifier = 10

class DmMsAddress(IntElement):
    """
    DM-MS address.

    The detailed coding/length shall be verified against the applicable
    ETSI EN 300 392-2 specification.
    The MM Type 3 decoder supplies the element length.
    """

    name = "DM-MS address"
    identifier = 13
    length = None


class GroupIdentityLocationDemand(CompoundElement):
    """
    16.10.24

    Reserved                       1
    Group identity attach/detach  1
    mode
    """

    name = "Group identity location demand"
    identifier = 3

    type1 = [
        Type1(Reserved),
        Type1(GroupIdentityAttachDetachMode),
    ]

    type2 = []
    type34 = []


class GroupReportResponse(EnumElement):
    name = "Group report response"
    length = 1

    enum = [
        "Group report complete",
        "Reserved",
    ]

    identifier = 4


class Proprietary(IntElement):
    """
    Variable-length Type 3 element.

    The actual length comes from the Type 3/4 length indicator.
    """

    name = "Proprietary"
    identifier = 15


class GroupIdentitySecurityRelatedInformation(IntElement):
    """
    Security-related Type 4 element.

    Actual coding is defined in EN 300 392-7.
    """

    name = "Group Identity Security Related Information"
    identifier = 12

class SecurityDownlink(IntElement):
    """
    Security-related Type 3 element.

    The detailed coding is defined by ETSI EN 300 392-7.
    The length is supplied by the Type 3 header, so the payload
    is preserved as raw bits by the MM PDU decoder.
    """

    name = "Security downlink"
    identifier = 11
    length = None

class CellTypeControl(IntElement):
    name = "Cell type control"
    identifier = 13


# ============================================================================
# Status downlink
# 16.10.48
# ============================================================================

class StatusDownlink(EnumElement):
    name = "Status downlink"
    length = 6

    enum = [
        # 000000 - 001111
        "Reserved",
        "Change of energy saving mode request",
        "Change of energy saving mode response",
        "Dual watch mode response",
        "Terminating dual watch mode response",
        "Change of dual watch mode request",
        "Reserved (energy saving / dual watch purpose)",
        "MS frequency bands request",
        "Periodic distance reporting",
        "Reserved",
        "Reserved",
        "Reserved",
        "Reserved",
        "Reserved",
        "Reserved",
        "Reserved",

        # 010000 - 011111
        "Refer to EN 300 396-5",
        "Refer to EN 300 396-5",
        "Refer to EN 300 396-5",
        "Refer to EN 300 396-5",
        "Refer to EN 300 396-5",
        "Refer to EN 300 396-5",
        "Refer to EN 300 396-5",
        "Refer to EN 300 396-5",
        "Refer to EN 300 396-5",
        "Refer to EN 300 396-5",
        "Refer to EN 300 396-5",
        "Refer to EN 300 396-5",
        "Refer to EN 300 396-5",
        "Refer to EN 300 396-5",
        "Refer to EN 300 396-5",
        "Refer to EN 300 396-5",

        # 100000 - 101111
        "Available for TETRA network and user specific definitions",
        "Available for TETRA network and user specific definitions",
        "Available for TETRA network and user specific definitions",
        "Available for TETRA network and user specific definitions",
        "Available for TETRA network and user specific definitions",
        "Available for TETRA network and user specific definitions",
        "Available for TETRA network and user specific definitions",
        "Available for TETRA network and user specific definitions",
        "Available for TETRA network and user specific definitions",
        "Available for TETRA network and user specific definitions",
        "Available for TETRA network and user specific definitions",
        "Available for TETRA network and user specific definitions",
        "Available for TETRA network and user specific definitions",
        "Available for TETRA network and user specific definitions",
        "Available for TETRA network and user specific definitions",
        "Available for TETRA network and user specific definitions",

        # 110000 - 111111
        "Reserved",
        "Reserved",
        "Reserved",
        "Reserved",
        "Reserved",
        "Reserved",
        "Reserved",
        "Reserved",
        "Reserved",
        "Reserved",
        "Reserved",
        "Reserved",
        "Reserved",
        "Reserved",
        "Reserved",
        "Reserved",
    ]


class DistanceReportingTimer(IntElement):
    name = "Distance reporting timer"
    length = 7


class DistanceReportingValidity(EnumElement):
    name = "Distance reporting validity"
    length = 1

    enum = [
        "Report until next location update",
        "Report until next ITSI attach or migration",
    ]


class ResultOfDualWatchRequest(EnumElement):
    name = "Result of dual watch request"
    length = 3

    enum = [
        "Request rejected for undefined reason",
        "Dual watch not supported",
        "Request accepted with the dual watch energy economy group",
        "Reserved",
        "Reserved",
        "Reserved",
        "Reserved",
        "Reserved",
    ]


class ReasonForDualWatchChangeBySwmi(EnumElement):
    name = "Reason for dual watch change by SwMI"
    length = 3

    enum = [
        "Reserved",
        "Reserved",
        "Change of dual watch energy economy group",
        "Reserved",
        "Reserved",
        "Reserved",
        "Reserved",
        "Reserved",
    ]


class Reserved8(IntElement):
    name = "Reserved"
    length = 8


# ============================================================================
# Raw security / unsupported elements
# ============================================================================

class MmRawElement(IntElement):
    """
    Variable-length raw MM element.

    The actual length is supplied by the Type 3/4 decoder.
    """

    name = "MM raw element"
    length = None

# ============================================================================
# D-AUTHENTICATION
# EN 300 392-7, clause A.1
# ============================================================================


class AuthenticationSubtype(EnumElement):
    name = "Authentication subtype"
    length = 2

    enum = [
        "D-AUTHENTICATION DEMAND",
        "D-AUTHENTICATION RESPONSE",
        "D-AUTHENTICATION RESULT",
        "D-AUTHENTICATION REJECT",
    ]


class RandomChallenge(IntElement):
    name = "Random challenge [RAND1]"
    length = 80


class RandomSeed(IntElement):
    name = "Random seed [RS]"
    length = 80


class ResponseValue(IntElement):
    name = "Response value [RES2]"
    length = 32


class MutualAuthenticationFlag(EnumElement):
    name = "Mutual authentication flag"
    length = 1

    enum = [
        "No mutual authentication",
        "Mutual authentication requested",
    ]


class AuthenticationResult(EnumElement):
    name = "Authentication result"
    length = 1

    enum = [
        "Authentication failed",
        "Authentication successful",
    ]


class AuthenticationRejectReason(IntElement):
    name = "Authentication reject reason"
    length = 3
