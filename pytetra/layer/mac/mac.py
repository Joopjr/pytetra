from pytetra.layer.mac.pdu import (
    MacPdu,
    NullPdu,
    SyncPdu,
    AccessAssignPdu,
    AccessDefinePdu,
    SysinfoPdu,
    MacResourcePdu,
    MacFrag,
    MacEnd,
)
from pytetra.layer.mac.decoder import Decoders
from pytetra.layer.mac.defragmenter import MacDefragmenter
from pytetra.sap.tpsap import UpperTpSap
from pytetra.sap.tmvsap import UpperTmvSap
from pytetra.timebase import g_timebase
from pytetra.layer import Layer
from pytetra.pdu import Bits
from collections import Counter


class LowerMac(Layer, UpperTpSap):
    """
    Lower MAC.

    Responsibilities:
      - receive decoded PHY blocks;
      - select the appropriate MAC channel decoder;
      - maintain MCC/MNC/colour-code state;
      - pass decoded MAC blocks to UpperMac;
      - pass speech blocks directly to the user layer.

    This class deliberately does not attempt to interpret MAC PDUs.
    """

    layer_number = 2

    def __init__(self, stack):
        super(LowerMac, self).__init__(stack)

        self.mcc = 0
        self.mnc = 0
        self.colour_code = 0

        # Indicates that BKN2 was stolen according to the MAC signalling.
        self.bkn2_stolen = False
        self.debug_enabled = bool(getattr(stack, "debug_layer2", True))
        self.decode_attempts = Counter()
        self.decode_successes = Counter()
        self.crc_failures = Counter()
        self.decoder_failures = Counter()

        self.decoder = Decoders()

        # The decoder must know the initial ECC immediately.
        # Previously ECC was calculated here but not installed in the
        # decoder until the first BSCH/SYNC update.
        self.decoder.set_extended_colour_code(
            self.get_extended_colour_code()
        )

    # ------------------------------------------------------------------
    # Transport SAP
    # ------------------------------------------------------------------

    def tp_sb_indication(self, sb, bb, bkn2):
        """
        Superframe / synchronisation burst indication.

        SB  -> BSCH
        BB  -> AACH
        BKN2 -> SCH/HD
        """
        if self.debug_enabled:
            self.info(
                "DEBUG input | primitive=TP-SB | SB_bits=%d | BB_bits=%d | "
                "BKN2_bits=%d"
                % (len(sb), len(bb), len(bkn2))
            )
        self.decode("BSCH", sb)
        self.decode("AACH", bb)
        self.decode("SCH/HD", bkn2)

    def tp_ndb_indication(self, bb, bkn1, bkn2, sf):
        """
        Normal data block indication.

        BB   -> AACH
        BKN1/BKN2 are interpreted according to the downlink usage marker.
        """
        if self.debug_enabled:
            self.info(
                "DEBUG input | primitive=TP-NDB | BB_bits=%d | BKN1_bits=%d | "
                "BKN2_bits=%d | stealing_flag=%d | usage_marker=%s"
                % (
                    len(bb),
                    len(bkn1),
                    len(bkn2),
                    int(bool(sf)),
                    self.stack.upper_mac.downlink_usage_marker,
                )
            )
        self.decode("AACH", bb)

        usage = self.stack.upper_mac.downlink_usage_marker

        if usage in (UpperMac.UMa, UpperMac.UMc):
            # Common control channel.
            if sf == 0:
                self.decode("SCH/F", bkn1 + bkn2)
            else:
                self.decode("SCH/HD", bkn1)
                self.decode("SCH/HD", bkn2)

            return

        if usage in UpperMac.Umt:
            # Traffic mode.
            #
            # For now the existing project behaviour is retained:
            # sf=0 -> normal TCH/S
            # sf!=0 -> STCH + BKN2 depending on stealing state.
            if sf == 0:
                self.decode("TCH/S normal", bkn1 + bkn2)
            else:
                self.decode("STCH", bkn1)

                if self.bkn2_stolen:
                    self.decode("STCH", bkn2)
                else:
                    self.decode("TCH/S stealing", bkn2)

                # Stealing applies to the current pair only.
                self.bkn2_stolen = False

    # ------------------------------------------------------------------
    # Cell identity / scrambling
    # ------------------------------------------------------------------

    def set_mobile_codes(self, mcc, mnc):
        """
        Update MCC/MNC and refresh the extended colour code.
        """
        try:
            mcc = int(mcc)
            mnc = int(mnc)
        except (TypeError, ValueError):
            return

        # TETRA ECC fields used here:
        # MCC       : 10 bits
        # MNC       : 14 bits
        # Colour   :  6 bits
        if not 0 <= mcc <= 0x3FF:
            raise ValueError("MCC must fit in 10 bits")

        if not 0 <= mnc <= 0x3FFF:
            raise ValueError("MNC must fit in 14 bits")

        if mcc == self.mcc and mnc == self.mnc:
            return

        self.mcc = mcc
        self.mnc = mnc

        self._update_extended_colour_code()

    def set_colour_code(self, colour_code):
        """
        Update colour code and refresh the extended colour code.
        """
        try:
            colour_code = int(colour_code)
        except (TypeError, ValueError):
            return

        if not 0 <= colour_code <= 0x3F:
            raise ValueError("Colour code must fit in 6 bits")

        if colour_code == self.colour_code:
            return

        self.colour_code = colour_code

        self._update_extended_colour_code()

    def _update_extended_colour_code(self):
        """
        Recalculate and install ECC in the PHY/MAC decoder.
        """
        ecc = self.get_extended_colour_code()
        self.decoder.set_extended_colour_code(ecc)

    def get_extended_colour_code(self):
        """
        Return MCC + MNC + colour code as a 30-bit list.

        10 + 14 + 6 = 30 bits.
        """
        return list(
            map(
                int,
                "{0:010b}{1:014b}{2:06b}".format(
                    self.mcc,
                    self.mnc,
                    self.colour_code,
                ),
            )
        )

    # Keep the original camel-case API for compatibility.
    def getExtendedColourCode(self):
        return self.get_extended_colour_code()

    # ------------------------------------------------------------------
    # PHY -> MAC
    # ------------------------------------------------------------------

    def decode(self, channel, b5):
        """
        Decode one PHY block and forward the resulting MAC data.

        The decoder returns:
            b1        decoded bits / decoded speech blocks
            crc_pass  CRC status
        """
        if b5 is None:
            return

        self.decode_attempts[channel] += 1

        try:
            b1, crc_pass = self.decoder.decode(channel, b5)
        except Exception as exc:
            self.decoder_failures[channel] += 1
            if self.debug_enabled:
                self.warning(
                    "DEBUG decoder failure | channel=%s | input_bits=%d | "
                    "error_type=%s | error=%s"
                    % (channel, len(b5), type(exc).__name__, exc)
                )
            return

        if crc_pass:
            self.decode_successes[channel] += 1
        else:
            self.crc_failures[channel] += 1

        if self.debug_enabled:
            output_length = (
                sum(len(frame) for frame in b1)
                if channel == "TCH/S normal"
                else len(b1)
            )
            self.info(
                "DEBUG decode | channel=%s | input_bits=%d | output_bits=%d | "
                "crc=%s"
                % (
                    channel,
                    len(b5),
                    output_length,
                    "pass" if crc_pass else "fail",
                )
            )

        if channel in (
            "BSCH",
            "SCH/F",
            "SCH/HD",
            "STCH",
            "AACH",
        ):
            self.stack.upper_mac.tmv_unitdata_indication(
                Bits("".join(map(str, b1))),
                channel,
                bool(crc_pass),
            )
            return

        if channel == "TCH/S normal":
            for frame in b1:
                self.stack.upper_mac.tmd_unitdata_indication(
                    Bits("".join(map(str, frame))),
                    channel,
                    bool(crc_pass),
                )
            return

        if channel == "TCH/S stealing":
            self.stack.upper_mac.tmd_unitdata_indication(
                Bits("".join(map(str, b1))),
                channel,
                bool(crc_pass),
            )

    def log_summary(self):
        if not self.debug_enabled:
            return
        self.info(
            "DEBUG summary | attempts=%s | crc_pass=%s | crc_fail=%s | "
            "decoder_failures=%s"
            % (
                dict(self.decode_attempts),
                dict(self.decode_successes),
                dict(self.crc_failures),
                dict(self.decoder_failures),
            )
        )


class UpperMac(Layer, UpperTmvSap):
    """
    Upper MAC.

    Handles:
      - BSCH / synchronisation;
      - AACH / access assignment;
      - SCH/F;
      - SCH/HD;
      - STCH;
      - MAC PDU segmentation / reassembly;
      - forwarding clear MAC SDUs to LLC;
      - forwarding speech to the user layer.
    """

    layer_number = 2

    # 21.4.7 MAC PDU structure for access assignment broadcast.
    UMx, UMa, UMc, UMr = range(4)

    # Traffic usage markers.
    Umt = range(4, 2 ** 6)

    # A MAC resource PDU has a minimum header of 19 bits in the
    # implementation used by this project.
    MIN_RESOURCE_PDU_BITS = 19

    # Anything below this is treated as trailing padding unless it
    # contains non-zero data, in which case we report it as malformed.
    MIN_TRAILING_BITS = 19

    def __init__(self, stack):
        super(UpperMac, self).__init__(stack)

        self.downlink_usage_marker = None
        self.defragmenter = MacDefragmenter()
        self.debug_enabled = bool(getattr(stack, "debug_layer2", True))
        self.channel_blocks = Counter()
        self.crc_drops = Counter()
        self.parsed_pdus = Counter()
        self.pdu_failures = Counter()
        self.reassembly_failures = Counter()
        self.llc_delivery_failures = 0

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _bits_to_string(bits):
        """
        Convert Bits/list/iterable to a plain 0/1 string.
        """
        if bits is None:
            return ""

        raw_bits = getattr(bits, "bits", None)
        if isinstance(raw_bits, str):
            return raw_bits

        try:
            return "".join(map(str, bits))
        except Exception:
            return str(bits)

    @classmethod
    def _is_all_zero(cls, bits):
        """
        Return True if the supplied bit sequence consists exclusively
        of zero bits.
        """
        data = cls._bits_to_string(bits)

        if not data:
            return True

        return all(bit == "0" for bit in data)

    @classmethod
    def _is_trailing_padding(cls, bits):
        """
        Determine whether remaining bits are merely padding.

        The important case from the observed capture is:

            000000...
            
        after one valid MAC resource PDU.

        Those bits must not be fed into MacPdu repeatedly.
        """
        if bits is None:
            return True

        try:
            length = len(bits)
        except Exception:
            return False

        if length == 0:
            return True

        return cls._is_all_zero(bits)

    @staticmethod
    def _safe_len(value):
        try:
            return len(value)
        except Exception:
            return None

    @staticmethod
    def _hide_filtered_ssi_output(pdu):
        """Hide MAC chains for absent, zero, or broadcast SSI values."""
        return getattr(pdu, "ssi", None) in (None, 0, 0xFFFFFF)

    # ------------------------------------------------------------------
    # BSCH / AACH / common control
    # ------------------------------------------------------------------

    def tmv_unitdata_indication(self, block, channel, crc_pass):
        """
        Entry point from LowerMac for TMV MAC blocks.
        """
        self.channel_blocks[channel] += 1
        if self.debug_enabled:
            self.info(
                "DEBUG block | channel=%s | bits=%d | crc=%s"
                % (channel, len(block), "pass" if crc_pass else "fail")
            )

        if channel == "AACH":
            self._handle_aach(block, crc_pass)
            return

        if not crc_pass:
            self.crc_drops[channel] += 1
            if self.debug_enabled:
                self.info("DEBUG drop | channel=%s | reason=crc_failed" % channel)
            # Never attempt to interpret a failed MAC block.
            return

        if channel == "BSCH":
            self._handle_bsch(block)
            return

        if channel in ("SCH/F", "SCH/HD", "STCH"):
            self._handle_mac_block(block, channel)
            return

    def _handle_aach(self, block, crc_pass):
        """
        Decode AACH and update downlink usage marker.
        """
        if not crc_pass:
            self.downlink_usage_marker = self.UMx
            self.crc_drops["AACH"] += 1
            if self.debug_enabled:
                self.info(
                    "DEBUG AACH | result=crc_failed | usage_marker=%d"
                    % self.downlink_usage_marker
                )
            return

        try:
            pdu = AccessAssignPdu(block)
        except Exception as exc:
            # An invalid AACH must not leave the old usage marker active.
            self.downlink_usage_marker = self.UMx
            if self.debug_enabled:
                self.warning(
                    "DEBUG AACH parse failure | error_type=%s | error=%s"
                    % (type(exc).__name__, exc)
                )
            return

        self.parsed_pdus[type(pdu).__name__] += 1

        self.expose_pdu(pdu)

        # Frame 18 has special handling in the existing stack.
        if g_timebase.fn == 18:
            self.downlink_usage_marker = self.UMc
            return

        header = getattr(pdu, "header", None)
        field1 = getattr(pdu, "field1", None)

        if header is None:
            self.downlink_usage_marker = self.UMx
            return

        if header == 0:
            self.downlink_usage_marker = self.UMc
        else:
            self.downlink_usage_marker = field1

        if self.debug_enabled:
            self.info(
                "DEBUG AACH | header=%s | field1=%s | field2=%s | "
                "usage_marker=%s"
                % (pdu.header, pdu.field1, pdu.field2, self.downlink_usage_marker)
            )

    def _handle_bsch(self, block):
        """
        Decode BSCH synchronisation PDU and update timebase/cell state.
        """
        try:
            pdu = SyncPdu(block)
        except Exception as exc:
            if self.debug_enabled:
                self.warning(
                    "DEBUG BSCH parse failure | error_type=%s | error=%s"
                    % (type(exc).__name__, exc)
                )
            return

        self.parsed_pdus[type(pdu).__name__] += 1

        # SYNC is diagnostic-only in normal output. Keep its entire causal
        # chain, including D-MLE-SYNC, under the same visibility context.
        with self.stack.output_context(True):
            self.expose_pdu(pdu)

            try:
                g_timebase.update(
                    pdu.timeslot_number + 1,
                    pdu.frame_number,
                    pdu.multiframe_number,
                )
            except Exception:
                # A malformed timebase update must not break MAC decoding.
                pass

            # The BSCH gives us the colour code used by the cell.
            try:
                self.stack.lower_mac.set_colour_code(
                    pdu.colour_code
                )
            except Exception:
                pass

            # Pass TM-SDU to LLC.
            tm_sdu = getattr(pdu, "tm_sdu", None)

            if tm_sdu is not None:
                try:
                    self.stack.llc.tmb_sync_indication(tm_sdu)
                except Exception:
                    pass

    # ------------------------------------------------------------------
    # MAC block parser
    # ------------------------------------------------------------------

    def _handle_mac_block(self, block, channel):
        """
        Parse one complete decoded MAC block.

        Bits is a destructive reader: MacPdu() consumes the bits directly
        from the supplied Bits object. Therefore we MUST NOT slice
        remaining again after MacPdu() has returned.
        """
        if block is None:
            return

        remaining = block

        if len(remaining) == 0:
            return

        pdu_number = 0

        while len(remaining):
            remaining_length = len(remaining)

            # ----------------------------------------------------------
            # 1. Completely empty / zero padding.
            # ----------------------------------------------------------
            if self._is_all_zero(remaining):
                break

            # ----------------------------------------------------------
            # 2. Too few bits for the mandatory MAC-RESOURCE header.
            # ----------------------------------------------------------
            if remaining_length < self.MIN_RESOURCE_PDU_BITS:
                break

            before = len(remaining)
            before_bits = self._bits_to_string(remaining)
            pdu_number += 1

            # ----------------------------------------------------------
            # 3. Look at the first two bits without consuming them.
            # ----------------------------------------------------------
            try:
                pdu_type = remaining.peek_int(0, 2)
            except Exception:
                break

            # ----------------------------------------------------------
            # 4. A MAC-RESOURCE with length_indication=0 and
            #    address_type=0 is padding/empty resource in this
            #    implementation.
            #
            #    Bit layout:
            #
            #      0..1   pdu_type
            #      2      fill_bits_indication
            #      3      position_of_grant
            #      4..5   encryption_mode
            #      6      random_access_flag
            #      7..12  length_indication
            #      13..15 address_type
            #
            #    Therefore length_indication is bits [7:13]
            #    and address_type is bits [13:16].
            # ----------------------------------------------------------
            if pdu_type == 0:
                try:
                    length_indication = remaining.peek_int(7, 6)
                    address_type = remaining.peek_int(13, 3)
                except Exception:
                    break

                if length_indication == 0 and address_type == 0:
                    break

            # ----------------------------------------------------------
            # 5. Parse the PDU.
            #
            # IMPORTANT:
            # MacPdu() consumes remaining IN PLACE.
            # ----------------------------------------------------------
            try:
                pdu = MacPdu(remaining)
            except Exception as exc:
                self.pdu_failures[channel] += 1
                self.info(
                    "DEBUG PDU parse failure | channel=%s | pdu_number=%d | "
                    "remaining_bits=%d | first_bits=%s | error_type=%s | error=%s"
                    % (
                        channel,
                        pdu_number,
                        remaining_length,
                        before_bits[:64],
                        type(exc).__name__,
                        exc,
                    )
                )
                break

            # ----------------------------------------------------------
            # 6. MacPdu() has already consumed the PDU from remaining.
            # ----------------------------------------------------------
            after = self._safe_len(remaining)

            if after is None:
                break

            consumed = before - after

            self.parsed_pdus[type(pdu).__name__] += 1

            if self.debug_enabled:
                self.info(
                    "DEBUG PDU | channel=%s | pdu_number=%d | type=%s | "
                    "consumed_bits=%d | remaining_bits=%d | fill_bits=%s | "
                    "length_indication=%s | address_type=%s | encryption_mode=%s"
                    % (
                        channel,
                        pdu_number,
                        type(pdu).__name__,
                        consumed,
                        after,
                        getattr(pdu, "fill_bits_indication", None),
                        getattr(pdu, "length_indication", None),
                        getattr(pdu, "address_type", None),
                        getattr(pdu, "encryption_mode", None),
                    )
                )

            if consumed <= 0:
                self.info(
                    "MAC PDU consumed zero bits channel=%s remaining=%d"
                    % (
                        channel,
                        before,
                    )
                )
                break

            # ----------------------------------------------------------
            # 7. Null / stealing indication.
            # ----------------------------------------------------------
            if isinstance(pdu, NullPdu):
                length_indication = getattr(
                    pdu,
                    "length_indication",
                    None,
                )

                if length_indication == 62:
                    self.stack.lower_mac.bkn2_stolen = True

                break

            # Fill bits occupy the remainder of this decoded MAC block.
            # They are not another MAC PDU and must never be parsed as one.
            if getattr(pdu, "fill_bits_indication", 0):
                if self.debug_enabled:
                    self.info(
                        "DEBUG fill | channel=%s | remaining_bits=%d | value=%s"
                        % (channel, after, before_bits[consumed:])
                    )

                if isinstance(pdu, SysinfoPdu):
                    self._handle_sysinfo_pdu(pdu)
                elif isinstance(pdu, AccessDefinePdu):
                    self.expose_pdu(pdu)
                elif isinstance(pdu, (MacResourcePdu, MacFrag, MacEnd)):
                    self._handle_data_pdu(pdu)
                break

            # ----------------------------------------------------------
            # 8. System information.
            # ----------------------------------------------------------
            if isinstance(pdu, SysinfoPdu):
                self._handle_sysinfo_pdu(pdu)

            elif isinstance(pdu, AccessDefinePdu):
                self.expose_pdu(pdu)

            # ----------------------------------------------------------
            # 9. Resource / fragment / end.
            # ----------------------------------------------------------
            elif isinstance(
                pdu,
                (MacResourcePdu, MacFrag, MacEnd),
            ):
                self._handle_data_pdu(pdu)

            # ----------------------------------------------------------
            # 10. Continue with whatever remains.
            #
            # DO NOT do:
            #
            #     remaining = remaining[consumed:]
            #
            # because MacPdu() already removed those bits.
            # ----------------------------------------------------------

            new_length = self._safe_len(remaining)

            if new_length is None:
                break

            if new_length >= before:
                break

        # Any remaining non-zero fragment smaller than the minimum
        # header is ignored rather than interpreted as another PDU.

    @staticmethod
    def _get_consumed_length(pdu, before):
        """
        Best-effort retrieval of consumed PDU length.

        Different versions of pytetra have exposed the consumed length
        under different names, so this helper is intentionally tolerant.
        """
        for name in (
            "consumed",
            "consumed_bits",
            "length",
            "bit_length",
        ):
            value = getattr(pdu, name, None)

            if isinstance(value, int):
                if 0 < value <= before:
                    return value

        return None

    # ------------------------------------------------------------------
    # Individual MAC PDUs
    # ------------------------------------------------------------------

    def _handle_sysinfo_pdu(self, pdu):
        """
        Forward SYSINFO SDU to LLC.
        """
        # SYSINFO is diagnostic-only in normal output. Keep D-MLE-SYSINFO
        # under the same visibility context as its hidden Upper-MAC source.
        with self.stack.output_context(True):
            self.expose_pdu(pdu)

            sdu = getattr(pdu, "sdu", None)

            if sdu is None:
                return

            try:
                if len(sdu) == 0:
                    return
            except Exception:
                pass

            try:
                self.stack.llc.tmb_sysinfo_indication(sdu)
            except Exception:
                pass

    def _handle_data_pdu(self, pdu):
        """
        Process MAC resource/fragment/end PDUs.

        Important:
          - zero-length resource PDUs containing only padding are ignored;
          - encrypted SDUs are never passed to LLC as if they were clear;
          - only a genuine, non-empty clear SDU is forwarded to LLC.
        """
        if isinstance(pdu, MacResourcePdu):
            length_indication = getattr(
                pdu,
                "length_indication",
                None,
            )
            address_type = getattr(
                pdu,
                "address_type",
                None,
            )
            encryption_mode = getattr(
                pdu,
                "encryption_mode",
                None,
            )

            sdu = getattr(pdu, "sdu", None)

            # ----------------------------------------------------------
            # Padding / empty MAC resource.
            #
            # This is exactly the pattern in the supplied trace:
            #
            #   length_indication=0
            #   address_type=0
            #   sdu=Bits('')
            #
            # It is not useful LLC data.
            # ----------------------------------------------------------
            if (
                length_indication == 0
                and address_type == 0
                and (
                    sdu is None
                    or len(sdu) == 0
                )
            ):
                return

            # ----------------------------------------------------------
            # No SDU.
            #
            # A resource PDU can legitimately contain control/resource
            # information without an LLC SDU.
            # ----------------------------------------------------------
            if sdu is None:
                with self.stack.mac_pdu_context(
                    pdu,
                    self._hide_filtered_ssi_output(pdu),
                ):
                    self.expose_pdu(pdu)
                return

            try:
                sdu_length = len(sdu)
            except Exception:
                sdu_length = 0

            if sdu_length == 0:
                with self.stack.mac_pdu_context(
                    pdu,
                    self._hide_filtered_ssi_output(pdu),
                ):
                    self.expose_pdu(pdu)
                return

            # ----------------------------------------------------------
            # Encryption.
            #
            # encryption_mode=3 in the observed capture means the SDU
            # cannot be handed to LLC as clear plaintext.
            #
            # Do NOT call tma_unitdata_indication() here.
            # ----------------------------------------------------------
            if encryption_mode == 3:
                with self.stack.mac_pdu_context(
                    pdu,
                    self._hide_filtered_ssi_output(pdu),
                ):
                    self.expose_pdu(pdu)
                return

        # --------------------------------------------------------------
        # Fragmentation / reassembly.
        #
        # For MacFrag/MacEnd and for genuine MacResourcePdu instances,
        # let the existing defragmenter decide whether a complete SDU
        # has become available.
        # --------------------------------------------------------------
        try:
            result = self.defragmenter.process_pdu(pdu)
        except Exception as exc:
            self.reassembly_failures[type(exc).__name__] += 1
            if self.debug_enabled:
                self.warning(
                    "DEBUG reassembly rejected | type=%s | error_type=%s | error=%s"
                    % (type(pdu).__name__, type(exc).__name__, exc)
                )
            return

        if result is None:
            return

        suppress_output = self._hide_filtered_ssi_output(result)
        with self.stack.mac_pdu_context(result, suppress_output):
            self.expose_pdu(result)

            sdu = getattr(result, "sdu", None)

            if sdu is None:
                return

            try:
                if len(sdu) == 0:
                    return
            except Exception:
                return

            encryption_mode = getattr(
                result,
                "encryption_mode",
                None,
            )

            # Never deliver encrypted data as clear LLC data.
            if encryption_mode == 3:
                return

            try:
                self.stack.llc.tma_unitdata_indication(sdu)
            except Exception as exc:
                self.llc_delivery_failures += 1
                self.warning(
                    "LLC delivery failed | bits=%d | error_type=%s | error=%s"
                    % (len(sdu), type(exc).__name__, exc)
                )
                return

    # ------------------------------------------------------------------
    # Speech
    # ------------------------------------------------------------------

    def tmd_unitdata_indication(self, block, channel, crc_pass):
        """
        Forward TCH/S speech to the user layer.

        Existing project convention:
            speech_indication(block, bad, usage_marker)

        Therefore bad == not crc_pass.
        """
        try:
            self.stack.user.speech_indication(
                block,
                not bool(crc_pass),
                self.downlink_usage_marker,
            )
        except Exception:
            pass

    def log_summary(self):
        if not self.debug_enabled:
            return
        self.info(
            "DEBUG summary | channel_blocks=%s | crc_drops=%s | "
            "parsed_pdus=%s | pdu_failures=%s | reassembly_failures=%s | "
            "llc_delivery_failures=%d"
            % (
                dict(self.channel_blocks),
                dict(self.crc_drops),
                dict(self.parsed_pdus),
                dict(self.pdu_failures),
                dict(self.reassembly_failures),
                self.llc_delivery_failures,
            )
        )
