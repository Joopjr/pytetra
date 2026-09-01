# PyTetra Downlink

PyTetra Downlink is a Python 3 decoder for unpacked TETRA downlink bit streams.
It implements physical burst framing, Lower and Upper MAC, LLC, MLE, CMCE, MM,
and SNDCP processing against ETSI EN 300 392-2 V3.8.1 (2016-08).

This repository is a substantially revised fork of the original PyTetra
project. It is intended for protocol research and passive analysis; it is not
an ETSI conformance-certified receiver.

## Features

- continuous and discontinuous downlink burst parsing;
- channel decoding, deinterleaving, descrambling, CRC verification and MAC
  reassembly;
- all downlink LLC discriminator values with strict FCS handling;
- MLE routing to CMCE, MM, and SNDCP;
- compact, causally correlated one-line output per permitted SSI chain;
- complete per-layer diagnostics through `--debug`;
- strict truncation and sequence checks without inventing missing bits;
- Python standard-library runtime with no mandatory third-party dependency.

## Requirements

- Python 3.9 or newer;
- an unpacked `.bits` file containing one byte per bit (`0x00` or `0x01`);
- aligned 510-bit records for normal continuous operation.

The repository does not currently contain an IQ demodulator or a SpyServer
client. IQ must first be demodulated to the unpacked bit format described in
[the manual](docs/MANUAL.md#input-format).

## Installation

```bash
git clone https://github.com/Joopjr/pytetra.git
cd pytetra
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install --upgrade pip
python3 -m pip install .
```

## Usage

After installation:

```bash
pytetra-dump recording.bits
```

The command accepts the required unpacked `filename`, `--debug` for the full
protocol trace, `--show-esi` for encrypted-identity chains in compact output,
and `-h`/`--help` for concise usage information.

From a source checkout without installation:

```bash
PYTHONPATH=. python3 examples/dump.py recording.bits
```

Normal output selects the highest decoded layer for each permitted SSI chain:

The identities and location-area values below are synthetic examples.

```text
DL; MCC(204), MNC(9999), LA(42); Layer 2 - MAC(MacResourcePdu); SSI(424242), AddressType(1), EncryptionMode(0), RandomAccessFlag(1), LengthIndication(6)
DL; MCC(204), MNC(9999), LA(42); Layer 3 - MM(DLocationUpdateAccept); SSI(424242), LocationUpdateAcceptType('ITSI attach'), SubscriberClass(5), ScchInformation(8), DistributionOn18thFrame(0), LaTimer('1 hour'), La(42)
```

Enable the complete Layer 1, Lower MAC, Upper MAC, LLC, and Layer 3 trace with:

```bash
pytetra-dump --debug recording.bits
```

Raw MAC SDUs are intentionally omitted from compact output and remain visible
in debug mode.

Encryption-mode 2/3 ESI records are also hidden from compact output by
default. Use `--show-esi` to include them without enabling the complete debug
trace. The first complete MCC/MNC/LA/CCK security context is reported once per
run as soon as it becomes known.

Compact output also suppresses MAC-RESOURCE address types 2, 3 and 6, including
the Layer-3 output causally decoded from those resources. `--debug` retains the
complete ETSI-named address fields: `SSI`, `EventLabel`, and `UsageMarker` as
selected by the MAC-RESOURCE address-type table.

## Example capture

The repository includes `examples/example.bits`. It is a deterministic,
synthetic 200-burst downlink example built from validated protocol vectors. It
contains one synchronization burst and 199 normal bursts with valid PHY
training, BSCH, AACH, SCH/F, MAC, LLC, and MM data, without subscriber data
copied from a real recording.

Run it from the repository root:

```bash
PYTHONPATH=. python3 examples/dump.py examples/example.bits
```

Use `--debug` to inspect every decoded layer.

## Output filtering

Normal output suppresses MAC chains addressed to:

- `SSI(None)` — no SSI is present;
- `SSI(0)` — null SSI;
- `SSI(16777215)` / `0xFFFFFF` — collective broadcast SSI.

The corresponding downstream LLC and Layer 3 output is suppressed as one
causal chain. General SYNC and SYSINFO traffic is also diagnostic-only. All of
it remains available with `--debug`.

## Tests

Run the complete suite from the repository root:

```bash
python3 -m unittest discover -s tests -v
```

The release suite covers PHY, channel decoding, MAC, LLC, MLE, CMCE, MM,
SNDCP, Type 3/4 extensions, visibility filtering, and compact summary
correlation.

## Documentation

- [User and developer manual](docs/MANUAL.md)
- [Protocol architecture](docs/ARCHITECTURE.md)
- [Implementation status](docs/IMPLEMENTATION_STATUS.md)
- [Publishing on GitHub](docs/PUBLISHING.md)
- [Contributing](CONTRIBUTING.md)
- [Changelog](CHANGELOG.md)

## Scope and limitations

- downlink only; uplink is intentionally not implemented;
- encrypted MAC SDUs are retained for diagnostics but never decoded as clear
  LLC data;
- several assigned Layer 3 PDU bodies are safely retained as named raw PDUs
  where complete semantic layouts are not implemented;
- SNDCP SN-UNITDATA reassembly is implemented, but no SNDCP traffic occurs in
  the supplied regression recording;
- direct SDR, IQ, and SpyServer input are not included in this release.

See [Implementation status](docs/IMPLEMENTATION_STATUS.md) for exact coverage.

## License and attribution

This project is distributed under the GNU General Public License version 2.0
only. See [LICENSE](LICENSE). Preserve the original project history and author
attribution when publishing a fork, and document substantial modifications in
the repository history and changelog.

TETRA is a standardized radio technology. ETSI standards are not included in
this repository. Users are responsible for complying with applicable laws,
radio regulations, privacy requirements, and network authorization rules.
