# Layer 3 audit

Target: ETSI EN 300 392-2 V3.8.1 (2016-08), downlink processing.

The decoder follows a strict rule: it rejects truncated structures and never
creates missing bits. Assigned structures that are not decoded semantically
are retained as named PDUs with their remaining payload intact.

## MLE

Semantically decoded: D-MLE-SYNC, D-MLE-SYSINFO and D-NWRK-BROADCAST.
D-NEW-CELL, D-PREPARE-FAIL and D-RESTORE-FAIL retain their service payload.
D-RESTORE-ACK retains and routes its CMCE payload.
Reserved MLE discriminators are retained as `MleReservedPdu` diagnostics.

## CMCE

Semantically decoded: D-ALERT, D-CALL-PROCEEDING, D-CALL-RESTORE, D-CONNECT,
D-CONNECT-ACKNOWLEDGE, D-DISCONNECT, D-RELEASE, D-SETUP, D-STATUS,
D-TX-CEASED, D-TX-GRANTED and D-SDS-DATA.

Assigned but currently raw-preserved: D-INFO, D-TX-CONTINUE, D-TX-WAIT,
D-TX-INTERRUPT, D-FACILITY and FUNCTION-NOT-SUPPORTED. Reserved discriminator
values are also preserved instead of being misclassified.

The shared Type 3/4 extension decoder supports chained elements, checks
declared lengths and retains unknown identifiers as `UnknownType34Element`.

## MM

All 4-bit downlink discriminator values dispatch safely. Semantic decoders are
present for D-OTAR, D-AUTHENTICATION, D-LOCATION-UPDATE-ACCEPT,
D-LOCATION-UPDATE-COMMAND, D-LOCATION-UPDATE-REJECT,
D-LOCATION-UPDATE-PROCEEDING, D-ATTACH/DETACH-GROUP-IDENTITY,
D-ATTACH/DETACH-GROUP-IDENTITY-ACKNOWLEDGEMENT and D-MM-STATUS.

D-CK-CHANGE-DEMAND, D-DISABLE and D-ENABLE are retained as named raw PDUs.
Reserved or unsupported discriminators and unknown Type 3/4 elements are
retained without inventing fields.

## SNDCP

SN-DATA and SN-UNITDATA common headers are decoded. SN-UNITDATA parses the
first-segment compression fields, segment number and N-PDU number. Segments
are reassembled only after a first segment and exact modulo-16 sequence; gaps
discard the partial N-PDU. SN-DATA payload remains raw because acknowledged
mode state handling is outside this downlink decoder.

## Validation

- 74 unit tests pass, including PHY, MAC, LLC, MLE, CMCE, MM, SNDCP and shared
  Type 3/4 extension tests.
- Full `tetra11.bits` replay completes without rejected PDUs, delivery errors
  or tracebacks.
- Observed: 32,063 D-MLE-SYNC; 59,168 D-MLE-SYSINFO; 3,513
  D-NWRK-BROADCAST; 14 D-AUTHENTICATION; 7 D-LOCATION-UPDATE-ACCEPT.
- No CMCE or SNDCP traffic occurs in this recording, so their live-air paths
  are covered by synthetic unit tests rather than this capture.
- Default output contains none of the debug-only Layer 1, Lower-MAC, LLC,
  SYNC, ACCESS-ASSIGN, SYSINFO, ACCESS-DEFINE, NULL, MAC-FRAG or MAC-END data.
- A MAC-RESOURCE addressed to `SSI(0)`, broadcast `SSI(16777215)` (`0xFFFFFF`),
  or without an SSI (`SSI(None)`) is decoded normally but its Layer-2 and
  downstream Layer-3 output is suppressed unless `--debug` is active.
- The full replay contains no visible `SSI(None)`, `SSI(0)` or
  `SSI(16777215)` entries after filtering; visible MAC-RESOURCE output falls
  from 31,378 to 743 entries. The 3,513 causally downstream
  D-NWRK-BROADCAST PDUs are suppressed with the broadcast SSI chain.
- Diagnostic-only SYNC and SYSINFO Upper-MAC sources suppress their downstream
  D-MLE-SYNC and D-MLE-SYSINFO output in normal mode, preventing orphaned
  Layer-3 log entries. Their internal state updates continue normally.
- Full normal-mode replay now contains 743 visible MAC-RESOURCE PDUs and 21 MM
  PDUs. Every visible Layer-3 PDU has a visible, permitted Upper-MAC source;
  there are no standalone D-MLE-SYNC, D-MLE-SYSINFO or D-NWRK-BROADCAST lines.

## Normal output model

Normal mode buffers exposed PDUs for the duration of one physical burst and
correlates them inside the active MAC-resource context. Only a permitted,
concrete SSI starts a summary chain. General SYSINFO/SYNC data and empty
SSI-less companion PDUs are ignored. The highest decoded PDU replaces the
lower-layer representation, producing one horizontal line per valid SSI chain.

The supplied authentication-result bits are covered by a regression test and
produce `MM(DAuthentication)` with `Authentication successful` and response
value `400645741`. Debug mode bypasses summary collection and retains the full
legacy per-layer trace.

Raw MAC SDU bits are excluded from horizontal normal-mode summaries and remain
available in the debug trace.
