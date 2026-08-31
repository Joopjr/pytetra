
import re


def field_name(name):
    aliases = {"min_rxlevel": "MinRxLevel"}
    if name in aliases:
        return aliases[name]
    return "".join(part[:1].upper() + part[1:] for part in name.split("_"))


def format_record(name, fields):
    values = ", ".join(
        "%s(%s)" % (field_name(key), value)
        for key, value in fields
    )
    return "%s(%s)" % (name, values)


class Logger(object):
    SECTION_WIDTH = 86
    SECTION_STYLES = {
        1: ("Layer 1 - physical layer", "═", "╔", "╗"),
        2: ("Layer 2 - MAC / LLC", "▓", "", ""),
        3: ("Layer 3 - MLE / CMCE / MM / SNDCP", "─", "┌", "┐"),
    }
    current_layer = None
    writer = None
    KEY_VALUE = re.compile(
        r"(?<![A-Za-z0-9_])([A-Za-z][A-Za-z0-9_]*)=([^|]+?)(?=\s*\||$)"
    )

    @classmethod
    def reset(cls):
        cls.current_layer = None

    @classmethod
    def set_writer(cls, writer=None):
        """Select an optional line writer; None retains normal console output."""
        cls.writer = writer

    @classmethod
    def write(cls, message):
        if cls.writer is None:
            print(message)
        else:
            cls.writer(message)

    @classmethod
    def section(cls, layer_number):
        if layer_number == cls.current_layer:
            return
        cls.current_layer = layer_number
        title, fill, left, right = cls.SECTION_STYLES.get(
            layer_number,
            ("Layer %d" % layer_number, "=", "", ""),
        )
        inner_width = cls.SECTION_WIDTH - len(left) - len(right)
        cls.write(left + (" %s " % title).center(inner_width, fill) + right)

    @classmethod
    def log(cls, message, layer_number=None):
        if layer_number is not None:
            cls.section(layer_number)
        cls.write(cls.KEY_VALUE.sub(cls._format_match, message))

    @staticmethod
    def _format_match(match):
        return "%s(%s)" % (
            field_name(match.group(1)),
            match.group(2).strip(),
        )
