from pytetra.sap.tlasap import UpperTlaSap
from pytetra.sap.tlbsap import UpperTlbSap
from pytetra.pdu.sublayer32pdu import SduElement
from pytetra.layer.mle.pdu import (
    MlePdu,
    DMleSync,
    DMleSysinfo,
    MleServicePdu,
    DRestoreAck,
)
from pytetra.layer.mle.elements import (
    La,
    Mcc,
    Mnc,
    ProtocolDiscriminator,
)
from pytetra.layer import Layer


class Mle(Layer, UpperTlaSap, UpperTlbSap):
    layer_number = 3

    def tl_unitdata_indication(self, sdu):

        # ------------------------------------------------------------
        # MLE Service PDU
        # ------------------------------------------------------------

        try:
            pdu = MleServicePdu.parse(sdu)

        except Exception as exc:
            self.warning(
                "MLE service PDU rejected | Bits(%d) | ErrorType(%s) | Error(%s)"
                % (len(sdu), type(exc).__name__, exc)
            )
            return

        # ------------------------------------------------------------
        # Protocol discriminator
        # ------------------------------------------------------------

        try:
            pd = pdu[ProtocolDiscriminator]
            payload = pdu[SduElement].value

        except Exception as exc:
            self.warning(
                "MLE service PDU missing payload | ErrorType(%s) | Error(%s)"
                % (type(exc).__name__, exc)
            )
            return

        # ============================================================
        # MM
        # ============================================================

        if pd.value == "MM":
            try:
                self.stack.mm.mle_unitdata_indication(payload)
            except Exception as exc:
                self.warning(
                    "MM delivery failed | ErrorType(%s) | Error(%s)"
                    % (type(exc).__name__, exc)
                )
                return

            return

        # ============================================================
        # CMCE
        # ============================================================

        if pd.value == "CMCE":
            try:
                self.stack.cmce.mle_unitdata_indication(payload)
            except Exception as exc:
                self.warning(
                    "CMCE delivery failed | ErrorType(%s) | Error(%s)"
                    % (type(exc).__name__, exc)
                )
                return

            return

        # ============================================================
        # SNDCP
        # ============================================================

        if pd.value == "SNDCP":
            # SNDCP is optional in a stack configuration.

            sndcp = getattr(self.stack, "sndcp", None)

            if sndcp is None:
                return

            try:
                sndcp.mle_unitdata_indication(payload)
            except Exception as exc:
                self.warning(
                    "SNDCP delivery failed | ErrorType(%s) | Error(%s)"
                    % (type(exc).__name__, exc)
                )
                return

            return

        # ============================================================
        # MLE
        # ============================================================

        if pd.value == "MLE":

            try:
                mle_pdu = MlePdu.parse(payload)

            except Exception as exc:
                self.warning(
                    "MLE control PDU rejected | Bits(%d) | ErrorType(%s) | Error(%s)"
                    % (len(payload), type(exc).__name__, exc)
                )
                return

            self.expose_pdu(mle_pdu)

            # --------------------------------------------------------
            # D-RESTORE-ACK
            # --------------------------------------------------------

            if isinstance(mle_pdu, DRestoreAck):

                try:
                    restore_payload = mle_pdu[SduElement].value

                except Exception as exc:
                    self.warning(
                        "D-RESTORE-ACK missing payload | ErrorType(%s) | Error(%s)"
                        % (type(exc).__name__, exc)
                    )
                    return

                try:
                    self.stack.cmce.mle_unitdata_indication(
                        restore_payload
                    )

                except Exception as exc:
                    self.warning(
                        "Restore payload delivery failed | ErrorType(%s) | Error(%s)"
                        % (type(exc).__name__, exc)
                    )
                    return

            return

        # ============================================================
        # RESERVED / TETRA MANAGEMENT / TESTING
        # ============================================================

        return

    # ----------------------------------------------------------------
    # TETRA MLE SYNC
    # ----------------------------------------------------------------

    def tl_sync_indication(self, sdu):

        try:
            pdu = DMleSync.parse(sdu)

        except Exception as exc:
            self.warning(
                "D-MLE-SYNC rejected | Bits(%d) | ErrorType(%s) | Error(%s)"
                % (len(sdu), type(exc).__name__, exc)
            )
            return

        try:
            self.stack.lower_mac.set_mobile_codes(
                pdu[Mcc].value,
                pdu[Mnc].value,
            )

        except Exception as exc:
            self.warning(
                "Cell identity update failed | ErrorType(%s) | Error(%s)"
                % (type(exc).__name__, exc)
            )

        self.expose_pdu(pdu)

    # ----------------------------------------------------------------
    # TETRA MLE SYSINFO
    # ----------------------------------------------------------------

    def tl_sysinfo_indication(self, sdu):

        try:
            pdu = DMleSysinfo.parse(sdu)

        except Exception as exc:
            self.warning(
                "D-MLE-SYSINFO rejected | Bits(%d) | ErrorType(%s) | Error(%s)"
                % (len(sdu), type(exc).__name__, exc)
            )
            return

        try:
            self.stack.lower_mac.set_location_area(pdu[La].value)
        except Exception as exc:
            self.warning(
                "Location area update failed | ErrorType(%s) | Error(%s)"
                % (type(exc).__name__, exc)
            )

        self.expose_pdu(pdu)
