# PyTetra Downlink manual

## 1. Purpose

PyTetra Downlink decodes an already-demodulated TETRA downlink bit stream. The
processing path is:

```text
unpacked bits → physical burst → Lower MAC → Upper MAC → LLC → MLE
                                                       ├→ CMCE
                                                       ├→ MM
                                                       └→ SNDCP
```

The implementation baseline is ETSI EN 300 392-2 V3.8.1 (2016-08). Uplink,
voice decoding, key management, and decryption are outside the current scope.

## 2. Installation

Create an isolated Python environment and install the repository:

```bash
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install --upgrade pip
python3 -m pip install .
```

Verify the command:

```bash
pytetra-dump --help
```

No non-standard runtime dependency is required.

## 3. Input format

The CLI accepts one positional input file. It is not a packed bit file: every
bit occupies one complete byte.

| Logical bit | Stored byte |
| ---: | ---: |
| 0 | `0x00` |
| 1 | `0x01` |

The default stream consists of aligned 510-bit continuous-downlink records.
The parser rejects any byte other than zero or one and never shifts inside a
rejected aligned record to manufacture a valid burst.

The library can also construct `Phy(..., burst_bits=492)` for discontinuous
downlink records. The command-line interface currently uses the standard
510-bit continuous setting.

IQ, WAV, SDR, and SpyServer streams are not input formats for this release.
They require an IQ demodulator that produces the byte-per-bit contract above.

## 4. Running the decoder

Compact output:

```bash
pytetra-dump capture.bits
```

Complete diagnostics:

```bash
pytetra-dump --debug capture.bits
```

The source wrapper is equivalent:

```bash
PYTHONPATH=. python3 examples/dump.py capture.bits
```

The included synthetic 200-burst example can be decoded without installation:

```bash
PYTHONPATH=. python3 examples/dump.py examples/example.bits
```

## 5. Compact output

Compact mode correlates all synchronously decoded PDUs with their originating
MAC resource for the duration of a physical burst. It emits the highest layer
reached by each permitted SSI chain.

Layer-2-only example:

```text
DL; Layer 2 - MAC(MacResourcePdu); SSI(450407), AddressType(1), EncryptionMode(3), RandomAccessFlag(0), LengthIndication(16)
```

Layer-3 example:

```text
DL; Layer 3 - MM(DAuthentication); SSI(3436244), AuthenticationSubtype('D-AUTHENTICATION RESULT'), AuthenticationResult('Authentication successful'), MutualAuthenticationFlag('Mutual authentication requested'), ResponseValue(400645741)
```

`DL` means downlink. `Layer 2 - MAC` or `Layer 3 - MM` identifies the highest
visible decoder. The PDU class is shown in parentheses, followed by its fields.

Raw MAC SDU bits are excluded from compact output because they are transport
payload rather than a user-readable semantic field.

## 6. Visibility rules

A concrete MAC resource starts a compact output chain only when its SSI is not:

- absent (`None`);
- zero;
- the collective address `16777215` (`0xFFFFFF`).

SYNC, SYSINFO, ACCESS-ASSIGN, ACCESS-DEFINE, NULL, MAC-FRAG, MAC-END, Lower MAC,
and LLC details remain available in debug mode. When one of these sources is
hidden, causally downstream output is hidden with it; orphan Layer-3 lines are
not printed.

If one physical burst contains several genuinely addressed MAC chains, each
chain receives its own line so no addressed protocol data is discarded.

## 7. Address types 1 and 6

Both forms contain a 24-bit SSI:

| Address type | Fields | Use |
| ---: | --- | --- |
| 1 | SSI | Direct individual addressing |
| 6 | SSI and 6-bit usage marker | Individual addressing tied to a channel/traffic usage context |

The usage marker helps associate the addressed subscriber with a physical
channel allocation. It does not replace the SSI.

## 8. Encryption mode

An `EncryptionMode(3)` MAC resource is shown in compact Layer-2 output, but its
SDU is not passed to LLC as clear text. The MAC address remains useful for
traffic observation; the protected payload cannot be interpreted without the
appropriate authorized security context.

## 9. Debug output

`--debug` restores the detailed processing trace:

- physical burst type, training sequences and errors;
- Lower-MAC channel choice, block sizes and CRC result;
- all Upper-MAC PDU fields, including raw SDUs;
- LLC parsing, sequence handling and delivery;
- MLE, CMCE, MM, and SNDCP PDU representations;
- decoder rejection reasons and end-of-stream summaries.

Debug mode is intentionally verbose and is intended for protocol diagnosis,
not routine subscriber-level summaries.

## 10. Interpreting reliability

A displayed SSI came from a channel block whose Lower-MAC CRC passed. A valid
CRC, correct MAC length, plausible address type, and repeated coherent Layer-3
procedures together provide strong evidence that the SSI bits were received
correctly. A single observation does not prove that an identity is assigned to
a currently registered device.

The decoder drops CRC-failed channel blocks instead of attempting to extract
addresses or higher-layer messages from them.

## 11. Library use

Applications can instantiate `TetraStack` with a custom `UserLayer`. Override:

- `pdu_indication(layer, pdu)` for the detailed PDU stream;
- `burst_summary_indication(chains)` for compact correlated chains;
- `speech_indication(block, bfi, marker)` for undecoded user-plane speech
  blocks.

`examples/dump.py` is deliberately a thin wrapper around `pytetra.cli:main` so
installed and source-checkout behavior cannot drift apart.

## 12. Troubleshooting

### Input rejected immediately

Confirm that the file contains byte values zero and one, not ASCII characters
`"0"` and `"1"`, packed bits, complex IQ samples, or a WAV header.

### No compact output

Run with `--debug`. The recording may contain only synchronization, system
information, collective SSI traffic, CRC failures, or encrypted/unaddressed
resources filtered from compact mode.

### Layer 2 appears but Layer 3 does not

Common reasons are an empty SDU, air-interface encryption, a control-only MAC
resource, or an LLC/PDU type that carries no Layer-3 payload.

### A Layer-3 PDU is retained as raw data

Some assigned PDU bodies are named and safely retained without semantic field
guessing. Consult `IMPLEMENTATION_STATUS.md` before treating absence of decoded
fields as corruption.

## 13. Responsible use

Use the decoder only where reception and analysis are lawful and authorized.
Do not publish subscriber identities or intercepted communications without a
valid legal and ethical basis.
