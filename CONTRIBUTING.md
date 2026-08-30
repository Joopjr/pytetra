# Contributing

Contributions should preserve the decoder's conservative protocol policy:

- target ETSI EN 300 392-2 V3.8.1 (2016-08) unless a change explicitly updates
  the baseline;
- implement downlink behavior only unless uplink scope is separately agreed;
- never synthesize missing bits or silently accept a failed CRC;
- retain unknown assigned content as named raw data rather than guessing;
- keep code, comments, variables, diagnostics, and documentation in English;
- remove temporary diagnostics after a decoder path is validated;
- add a regression test for every parser or routing fix.

Run before submitting:

```bash
python3 -m compileall -q pytetra examples tests
python3 -m unittest discover -s tests -v
```

Do not include captures or logs containing subscriber identities or private
network information in issues or pull requests. Reduce protocol examples to the
minimum bit vector needed to reproduce a defect.
