# Changelog

This release is compared with the original PyTetra master branch at commit
[`fa7deb5`](https://github.com/Tim---/pytetra/commit/fa7deb594491cfcc69081a2494484f7533a40db7)
from 10 November 2015. The upstream project already provided the protocol-stack
structure, continuous downlink burst parsing, channel-code primitives, basic
MAC/LLC/MLE dispatch, and a subset of CMCE and MM PDUs.

## 1.0.0

- vectorized all sixteen Viterbi trellis states with NumPy to remove the
  real-time convolutional-decoder bottleneck without weakening soft-decision
  error correction;
- corrected soft-input detection for NumPy floating-point values in Viterbi,
  AACH, and TCH/S decoding;
- centralized MAC-RESOURCE address-field selection in an ETSI table, retained
  type-specific `SSI`, `EventLabel`, and `UsageMarker` keys, and suppressed
  address types 2, 3 and 6 plus their downstream chains from compact output;
- replaced captured SSI, GSSI and location-area identifiers in public
  documentation and regression fixtures with synthetic example values;
- added an optional line-writer hook so live frontends can timestamp all
  compact, section and diagnostic output while offline decoding keeps stdout;
- treated every non-zero MAC encryption mode as opaque cipher text and stopped
  residual MAC-block parsing after a bounded encrypted SDU, preventing false
  SSI and downstream Layer-3 interpretation from encrypted payload bits;

- added optional live soft-bit confidence from PHY through unscrambling and
  deinterleaving into a soft-decision Viterbi decoder;
- retained normal CRC gating so uncertain or uncorrectable blocks are dropped;
- added lightweight stream-gap resets for MAC, LLC, and SNDCP reassembly state;
- kept malformed Upper MAC PDU diagnostics behind the explicit debug option;

### Python 3, packaging, and command line

- ported the Python 2 codebase to Python 3.9 and newer, including iterator,
  byte-input, print, exception, and import behavior;
- added `pyproject.toml`, package metadata, the `pytetra-dump` console command,
  and a source-checkout wrapper with identical behavior;
- retained the GPL-2.0 license and original-author attribution;
- added GitHub Actions testing on Python 3.9 and 3.12.

### Layer 1: physical layer

- hardened continuous synchronization and normal burst recognition with strict
  binary input and length validation;
- added synchronization and normal discontinuous downlink burst classes;
- added training-sequence error accounting, stealing indication, phase fields,
  aligned-record rejection, optional resynchronization, and end-of-stream
  statistics;
- corrected physical-block delivery and timebase advancement so rejected data
  cannot silently manufacture or shift bursts.

### Layer 2: Lower and Upper MAC

- initialized and updated the extended colour code consistently across channel
  decoders;
- hardened BSCH, AACH, SCH/F, SCH/HD, STCH, and TCH/S routing, CRC gating, and
  decoder-failure handling;
- corrected AACH usage-marker interpretation and normal-versus-stolen channel
  selection;
- expanded Upper-MAC parsing with `AccessDefinePdu`, safer `MacResourcePdu`
  length handling, multiple-PDU block parsing, fill-bit handling, and bounded
  fragment reassembly;
- ensured CRC-failed and truncated blocks are dropped instead of being parsed
  as subscriber addresses or higher-layer data;
- prevented encrypted MAC SDUs from entering clear-text LLC parsing.

### Layer 2: LLC

- expanded the upstream LLC subset to cover all assigned downlink discriminator
  values, including basic-link FCS variants and advanced-link setup, data,
  acknowledgement, reconnect, and disconnect PDUs;
- added TETRA LLC CRC-32 verification and strict handling of missing, truncated,
  or failed FCS data;
- added basic sequence tracking, advanced-link segment reassembly, reset rules,
  and safe retention of reserved or unsupported discriminator data;
- forwards only valid, complete SDUs to MLE without inventing missing bits.

### MLE and Layer 3

- hardened MLE discriminator dispatch and added downlink handling for
  `DNewCell`, `DPrepareFail`, `DRestoreFail`, and reserved MLE PDUs;
- expanded CMCE dispatch with additional assigned downlink PDUs and safe raw
  retention for bodies that are not yet semantically decoded;
- substantially expanded MM parsing, including authentication result fields,
  location-update procedures, enable/disable, status, cipher-control, key-change,
  and OTAR-related downlink types;
- added strict Type 3 and Type 4 optional-element parsing with bounds checks and
  preservation of unknown elements;
- added the SNDCP layer with SN-DATA, SN-UNITDATA, segmentation, reassembly, and
  malformed-sequence rejection.

### Output and diagnostics

- added readable and visually distinct Layer 1, Layer 2, and Layer 3 diagnostic
  sections under `--debug`;
- added compact horizontal output correlated from an addressed Upper-MAC PDU to
  the highest decoded layer in the same physical burst;
- added causal filtering for absent SSI, null SSI, and collective SSI
  `0xFFFFFF`, preventing orphan Layer-3 output when its Layer-2 source is hidden;
- removed raw MAC SDUs from compact output while retaining them in debug mode;
- standardized displayed fields as `FieldName(Value)`.

### Tests, examples, and documentation

- expanded the upstream decoder tests to 75 regression tests covering PHY,
  channel decoding, MAC, LLC, MLE, CMCE, MM, SNDCP, filtering, and correlation;
- added a synthetic 200-burst example containing one synchronization burst and
  199 normal bursts, without copied subscriber data;
- added the user manual, architecture description, implementation-status notes,
  contribution guide, release guide, and Layer-3 audit notes;
- replaced the obsolete upstream sample capture with the deterministic synthetic
  regression stream.

### Known scope limits

- downlink only; uplink decoding is not implemented;
- accepts unpacked byte-per-bit input and does not include IQ demodulation,
  WAV/SDR input, or a SpyServer client;
- encrypted payload decryption, vocoder output, and formal ETSI conformance
  certification are outside this release.
