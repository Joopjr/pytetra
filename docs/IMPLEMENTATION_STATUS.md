# Implementation status

Baseline: ETSI EN 300 392-2 V3.8.1 (2016-08), downlink only.

Uplink processing is not implemented in 1.0.0. Adding it with independent PHY,
MAC, and protocol regression coverage is a desired later-version extension.

| Area | Status | Notes |
| --- | --- | --- |
| Physical layer | Implemented | Four downlink burst classes; aligned 510/492-bit modes |
| Lower MAC | Implemented | Descrambling, deinterleaving, channel decoding and CRC |
| Upper MAC | Implemented | Addressing, broadcast PDUs, resource PDUs and reassembly |
| LLC | Implemented | All discriminator values; Basic and Advanced Link handling |
| MLE | Implemented with raw preservation | Core downlink control PDUs decoded |
| CMCE | Partial semantic coverage | Assigned unsupported bodies remain named raw PDUs |
| MM | Broad semantic coverage | Reserved/unsupported and selected security bodies remain raw |
| SNDCP | Partial | SN-UNITDATA parsing/reassembly; SN-DATA body retained raw |
| Uplink | Not implemented | Deliberately outside current scope |
| Speech codec | Not implemented | Speech blocks can be delivered to an application callback |
| Decryption | Not implemented | Encrypted SDUs are never treated as clear LLC data |
| IQ/SDR input | Not implemented | Requires a separate demodulator |

## Safety rules

- CRC-failed Lower-MAC blocks are dropped.
- Truncated structures are rejected.
- Fragment chains require a valid start and continuous sequence.
- Missing bits and fields are never synthesized.
- Unknown Type 3/4 elements are retained with identifier, length, and raw value.
- Encrypted MAC payload is not routed into clear LLC parsing.

## Layer 3 details

Semantically decoded MLE includes D-MLE-SYNC, D-MLE-SYSINFO, and
D-NWRK-BROADCAST. D-NEW-CELL, D-PREPARE-FAIL, D-RESTORE-ACK, and
D-RESTORE-FAIL are routed or retained conservatively according to available
structure.

CMCE semantic classes include D-ALERT, D-CALL-PROCEEDING, D-CALL-RESTORE,
D-CONNECT, D-CONNECT-ACKNOWLEDGE, D-DISCONNECT, D-RELEASE, D-SETUP, D-STATUS,
D-TX-CEASED, D-TX-GRANTED, and D-SDS-DATA. D-INFO, D-TX-CONTINUE, D-TX-WAIT,
D-TX-INTERRUPT, D-FACILITY, and FUNCTION-NOT-SUPPORTED retain raw bodies.

MM semantic classes include D-OTAR, D-AUTHENTICATION,
D-LOCATION-UPDATE-ACCEPT, D-LOCATION-UPDATE-COMMAND,
D-LOCATION-UPDATE-REJECT, D-LOCATION-UPDATE-PROCEEDING,
D-ATTACH/DETACH-GROUP-IDENTITY, its acknowledgement, and D-MM-STATUS.
D-CK-CHANGE-DEMAND, D-DISABLE, and D-ENABLE retain named raw bodies.

## Regression evidence

The release test suite contains 75 tests. A full replay of the development
recording completes without decoder exceptions or delivery failures and
produces 743 compact SSI-chain summaries: 722 at Layer 2 and 21 at Layer 3.
The observed Layer-3 messages comprise 14 D-AUTHENTICATION and 7
D-LOCATION-UPDATE-ACCEPT PDUs.

CMCE and SNDCP do not occur in that recording and are covered by synthetic
tests. These results demonstrate regression stability, not formal ETSI
conformance certification.
