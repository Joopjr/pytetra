#!/usr/bin/env python

# from pytetra.pdu import Pdu, UIntField, BitsField
from pytetra.pdu.sublayer32pdu import Pdu, Type1, Type2, Type3, PduDiscriminator, Repeat
from pytetra.layer.mle.elements import *


# 18.4.2.1 D-MLE-SYNC
class DMleSync(Pdu):
    name = "D-MLE-SYNC"
    type1 = [
        Type1(Mcc),
        Type1(Mnc),
        Type1(NeighbourCellBroadcast),
        Type1(CellServiceLevel),
        Type1(LateEntrySupported),
    ]
    type2 = []
    type34 = []
    has_o_bit = False


# 18.4.2.2 D-MLE-SYSINFO
class DMleSysinfo(Pdu):
    name = "D-MLE-SYSINFO"
    type1 = [
        Type1(La),
        Type1(SubscriberClass),
        Type1(BsServiceDetails),
    ]
    type2 = []
    type34 = []
    has_o_bit = False


# 18.4.1.3 MLE service user PDUs
class MleServicePdu(Pdu):
    name = "MLE PDU"
    type1 = [
        Type1(ProtocolDiscriminator),
    ]
    type2 = []
    type34 = []
    sdu = True
    has_o_bit = False


class DNewCell(Pdu):
    """D-NEW CELL; preserve its service payload without guessing fields."""
    name = "D-NEW CELL"
    type1 = [Type1(PduType)]
    type2 = []
    type34 = []
    sdu = True


class DPrepareFail(Pdu):
    """D-PREPARE FAIL; preserve its service payload without guessing fields."""
    name = "D-PREPARE FAIL"
    type1 = [Type1(PduType)]
    type2 = []
    type34 = []
    sdu = True


# 18.4.1.4.1 D-NWRK-BROADCAST
class DNwrkBroadcast(Pdu):
    name = "D-NWRK-BROADCAST"
    type1 = [
        Type1(PduType),
        Type1(CellReselectParameters),
        Type1(CellServiceLevel),
    ]
    type2 = [
        Type2(TetraNetworkTime),
        Type2(NumberOfNeighbourCells),
        Repeat(
            NeighbourCellInformation,
            lambda pkt: (
                pkt.fields[NumberOfNeighbourCells].value
                if NumberOfNeighbourCells in pkt.fields
                else 0
            ),
        ),
    ]
    type34 = []


# 18.4.1.4.4 D-RESTORE-ACK
class DRestoreAck(Pdu):
    name = "D-RESTORE-ACK"
    type1 = [
        Type1(PduType),
    ]
    type2 = []
    type34 = []
    sdu = True


class DRestoreFail(Pdu):
    """D-RESTORE FAIL; preserve its service payload without guessing fields."""
    name = "D-RESTORE-FAIL"
    type1 = [Type1(PduType)]
    type2 = []
    type34 = []
    sdu = True


class MleReservedPdu(Pdu):
    """Reserved MLE discriminator; preserve the body for diagnostics."""
    name = "MLE-RESERVED"
    type1 = [Type1(PduType)]
    type2 = []
    type34 = []
    sdu = True
    has_o_bit = False


# 18.4.1.2 PDU type
class MlePdu(PduDiscriminator):
    element = PduType
    pdu_types = {
        0: DNewCell,
        1: DPrepareFail,
        2: DNwrkBroadcast,
        3: MleReservedPdu,
        4: DRestoreAck,
        5: DRestoreFail,
        6: MleReservedPdu,
        7: MleReservedPdu,
    }
