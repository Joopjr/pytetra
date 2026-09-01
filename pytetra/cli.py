"""Command-line interface for decoding unpacked TETRA downlink bits."""

import argparse

from pytetra.layer.user import UserLayer
from pytetra.logger import Logger
from pytetra.stack import TetraStack
from pytetra.summary import format_chain


class ConsoleUserLayer(UserLayer):
    """Render compact summaries or the complete diagnostic protocol trace."""

    def pdu_indication(self, layer, pdu):
        if not self.stack.debug:
            return
        layer_number = {
            "UpperMac": 2,
            "Llc": 2,
            "Mle": 3,
            "Cmce": 3,
            "Mm": 3,
            "Sndcp": 3,
        }.get(layer)
        Logger.log("%s: %s" % (layer, pdu), layer_number)

    def burst_summary_indication(self, chains):
        for chain in chains:
            Logger.log(format_chain(chain))


def build_argument_parser():
    parser = argparse.ArgumentParser(
        description="Decode an unpacked TETRA downlink bit stream"
    )
    parser.add_argument(
        "filename",
        help="input file containing one unpacked bit (0x00 or 0x01) per byte",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help=(
            "show the complete Layer 1, Lower MAC, Upper MAC, LLC, and "
            "Layer 3 diagnostic trace"
        ),
    )
    parser.add_argument(
        "--show-esi",
        action="store_true",
        help="include encryption-mode 2/3 ESI records in compact output",
    )
    parser.add_argument(
        "--show-security-context",
        action="store_true",
        help="report MCC/MNC/LA/CCK context changes",
    )
    return parser


def main(argv=None):
    arguments = build_argument_parser().parse_args(argv)
    stack = TetraStack(
        ConsoleUserLayer,
        debug=arguments.debug,
        show_esi=arguments.show_esi,
        show_security_context=arguments.show_security_context,
    )
    stack.phy.feed_from_file(arguments.filename)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
