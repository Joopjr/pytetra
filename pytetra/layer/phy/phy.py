from pytetra.layer.phy.burst import (
    Burst,
    SynchronizationContinuousDownlinkBurst,
    NormalContinuousDownlinkBurst,
    SynchronizationDiscontinuousDownlinkBurst,
    NormalDiscontinuousDownlinkBurst,
)
from pytetra.timebase import g_timebase
from pytetra.layer import Layer
from pytetra.logger import format_record


BURST_BITS = 510
READ_BLOCK_BYTES = 64 * 1024


class Phy(Layer):
    """Parse downlink bursts and deliver their physical blocks to Lower MAC."""

    layer_number = 1

    def __init__(self, stack, burst_aligned=True, burst_bits=BURST_BITS,
                 log_layer1=False):
        super(Phy, self).__init__(stack)
        if burst_bits not in (492, 510):
            raise ValueError("Downlink burst length must be 492 or 510 bits")
        self.burst_aligned = bool(burst_aligned)
        self.burst_bits = burst_bits
        self.log_layer1 = bool(log_layer1)
        self.locked = False
        self.stream = []
        self.index = 0
        self.bursts_decoded = 0
        self.bursts_rejected = 0
        self.sync_bursts = 0
        self.normal_bursts = 0
        self.resynchronizations = 0
        self.skipped_bits = 0

    def sync(self):
        """Search for the first valid burst boundary."""
        search_start = self.index

        while len(self.stream) >= self.burst_bits and not self.locked:
            bits = self.stream[:self.burst_bits]
            burst = Burst.parse(bits)

            if burst is not None:
                self.locked = True
                skipped = (
                    self.index - search_start
                    if not self.burst_aligned
                    else 0
                )
                self.skipped_bits += skipped
                if self.bursts_decoded or skipped:
                    self.resynchronizations += 1
                if skipped and self.log_layer1:
                    self.protocol(
                        "L1 acquisition | skipped_bits=%d | bit_index=%d"
                        % (skipped, self.index)
                    )
                return

            if self.burst_aligned:
                self.bursts_rejected += 1
                self._log_rejected()
                self.delete(self.burst_bits)
                g_timebase.increment()
            else:
                self.delete(1)

    def _log_rejected(self):
        if not self.log_layer1:
            return
        self.protocol(
            "Rejected burst | bit_index=%d | length_bits=%d | "
            "reason=no_matching_downlink_training_sequence"
            % (self.index, self.burst_bits)
        )

    def _deliver(self, burst):
        """Map an ETSI downlink burst to the TP-SAP primitive."""
        if isinstance(
            burst,
            (
                SynchronizationContinuousDownlinkBurst,
                SynchronizationDiscontinuousDownlinkBurst,
            ),
        ):
            self.sync_bursts += 1
            self.stack.lower_mac.tp_sb_indication(
                burst.sb,
                burst.bb,
                burst.bkn2,
            )
            return

        if isinstance(
            burst,
            (
                NormalContinuousDownlinkBurst,
                NormalDiscontinuousDownlinkBurst,
            ),
        ):
            self.normal_bursts += 1
            self.stack.lower_mac.tp_ndb_indication(
                burst.bb,
                burst.bkn1,
                burst.bkn2,
                int(bool(burst.sf)),
            )
            return

        raise TypeError("Unsupported downlink burst type: %s" % type(burst).__name__)

    def decode(self):
        """Decode one aligned burst and advance the PHY timebase once."""
        bits = self.stream[:self.burst_bits]
        burst = Burst.parse(bits)

        if burst is None:
            self.bursts_rejected += 1

            if self.burst_aligned:
                # An aligned demodulator emits complete records. Never slide
                # inside a rejected record and accidentally lock to payload.
                self._log_rejected()
                self.delete(self.burst_bits)
                g_timebase.increment()
                return

            self.locked = False
            return

        if self.log_layer1:
            fields = burst.layer1_fields()
            details = [
                ("bit_index", self.index),
                ("length_bits", self.burst_bits),
            ]
            details.extend(fields.items())
            self.protocol(format_record(burst.__class__.__name__, details))

        begin_burst = getattr(self.stack, "begin_burst", None)
        finish_burst = getattr(self.stack, "finish_burst", None)
        if begin_burst is not None:
            begin_burst()
        try:
            try:
                self._deliver(burst)
            except Exception as exc:
                if self.log_layer1:
                    self.protocol(
                        "Layer 1 to Layer 2 delivery failed | bit_index=%d | "
                        "burst_type=%s | error=%s"
                        % (self.index, burst.__class__.__name__, exc)
                    )
        finally:
            if finish_burst is not None:
                finish_burst()

        self.bursts_decoded += 1
        self.delete(self.burst_bits)
        g_timebase.increment()

    def feed(self, data):
        values = list(data)
        if any(bit not in (0, 1) for bit in values):
            raise ValueError("PHY input must contain unpacked binary values 0 or 1")

        self.stream.extend(values)

        while len(self.stream) >= self.burst_bits:
            if not self.locked:
                self.sync()
                if not self.locked:
                    return

            self.decode()

    def feed_from_file(self, filename):
        with open(filename, "rb") as handle:
            while True:
                data = handle.read(READ_BLOCK_BYTES)
                if not data:
                    break
                self.feed(data)

        if self.log_layer1:
            self.protocol(
                "Layer 1 summary | decoded=%d | synchronization=%d | normal=%d | "
                "rejected=%d | resynchronizations=%d | skipped_bits=%d | trailing_bits=%d"
                % (
                    self.bursts_decoded,
                    self.sync_bursts,
                    self.normal_bursts,
                    self.bursts_rejected,
                    self.resynchronizations,
                    self.skipped_bits,
                    len(self.stream),
                )
            )

        lower_mac = getattr(self.stack, "lower_mac", None)
        upper_mac = getattr(self.stack, "upper_mac", None)
        llc = getattr(self.stack, "llc", None)
        if lower_mac is not None and hasattr(lower_mac, "log_summary"):
            lower_mac.log_summary()
        if upper_mac is not None and hasattr(upper_mac, "log_summary"):
            upper_mac.log_summary()
        if llc is not None and hasattr(llc, "log_summary"):
            llc.log_summary()

    def delete(self, size):
        del self.stream[:size]
        self.index += size
