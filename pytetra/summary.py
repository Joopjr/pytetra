from pytetra.logger import field_name
from pytetra.pdu import Bits


LAYER3_NAMES = {
    "Mle": "MLE",
    "Cmce": "CMCE",
    "Mm": "MM",
    "Sndcp": "SNDCP",
}


def _format_scalar(name, value):
    if isinstance(value, Bits):
        rendered = repr(value)
    elif isinstance(value, str):
        rendered = repr(value)
    else:
        rendered = str(value)
    return "%s(%s)" % (field_name(name), rendered)


def _flatten_layer3_value(value):
    if isinstance(value, list):
        result = []
        for item in value:
            result.extend(_flatten_layer3_value(item))
        return result

    fields = getattr(value, "fields", None)
    if fields is not None:
        result = []
        if fields and all(isinstance(key, str) for key in fields):
            for key, item in fields.items():
                if key in ("payload", "data") and isinstance(item, Bits):
                    result.append(_format_scalar(key, item))
                else:
                    result.extend(_flatten_named_value(key, item))
            return result
        for item in fields.values():
            result.extend(_flatten_layer3_value(item))
        return result

    class_name = type(value).__name__
    if class_name in (
        "PduType",
        "SduElement",
        "MmTrailingBits",
        "MmRawBits",
        "MmUnknownType34",
    ):
        return []

    if hasattr(value, "value"):
        return [repr(value)]
    return []


def _flatten_named_value(name, value):
    if isinstance(value, (int, str, Bits)) or value is None:
        return [_format_scalar(name, value)]
    return _flatten_layer3_value(value)


def format_chain(chain):
    ssi = chain["ssi"]
    cell = "MCC(%s), MNC(%s), LA(%s)" % (
        chain.get("mcc"),
        chain.get("mnc"),
        chain.get("la"),
    )
    layer3 = chain.get("layer3")
    if layer3 is not None:
        layer_name, pdu = layer3
        fields = ["SSI(%d)" % ssi]
        fields.extend(_flatten_layer3_value(pdu))
        return "DL; %s; Layer 3 - %s(%s); %s" % (
            cell,
            LAYER3_NAMES.get(layer_name, layer_name.upper()),
            type(pdu).__name__,
            ", ".join(fields),
        )

    pdu = chain["layer2"]
    fields = ["SSI(%d)" % ssi]
    for name in (
        "address_type",
        "encryption_mode",
        "random_access_flag",
        "length_indication",
    ):
        fields.append(_format_scalar(name, getattr(pdu, name, None)))
    return "DL; %s; Layer 2 - MAC(%s); %s" % (
        cell,
        type(pdu).__name__,
        ", ".join(fields),
    )
