from pytetra.logger import field_name
from pytetra.pdu import Bits
from pytetra.layer.mac.pdu import mac_resource_identity_field_name


LAYER3_NAMES = {
    "Mle": "MLE",
    "Cmce": "CMCE",
    "Mm": "MM",
    "Sndcp": "SNDCP",
}


MAC_RESOURCE_COMPACT_FIELDS = (
    "fill_bits_indication",
    "position_of_grant",
    "encryption_mode",
    "random_access_flag",
    "length_indication",
    "address_type",
    "event_label",
    "usage_marker",
    "power_control_flag",
    "power_control_element",
    "slot_granting_flag",
    "slot_granting_element",
    "channel_allocation_flag",
    "channel_allocation",
    "allocation_type",
    "timeslot_assigned",
    "up_down_assigned",
    "clch_permission",
    "cell_change",
    "carrier_number",
    "ext_carrier_number",
    "freq_band",
    "offset",
    "duplex_spacing",
    "reverse_operation",
    "monitoring_pattern",
    "frame_18_monitoring_pattern",
)


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


def _identity_field(chain):
    """Render the MAC address value using its over-the-air identity type."""
    pdu = chain["layer2"]
    label = mac_resource_identity_field_name(
        getattr(pdu, "address_type", None),
        getattr(pdu, "encryption_mode", None),
    )
    return "%s(%d)" % (field_name(label), chain["ssi"])


def format_chain(chain):
    cell = "MCC(%s), MNC(%s), LA(%s)" % (
        chain.get("mcc"),
        chain.get("mnc"),
        chain.get("la"),
    )
    pdu = chain["layer2"]
    if type(pdu).__name__ == "AccessAssignPdu":
        fields = [
            _format_scalar("carrier_frequency", chain.get("carrier_frequency")),
            _format_scalar("timeslot", chain.get("timeslot")),
        ]
        previous = chain.get("previous_usage_marker")
        if previous is not None:
            fields.append(_format_scalar("previous_usage_marker", previous))
        fields.append(_format_scalar(
            "usage_marker",
            chain.get("usage_marker", getattr(pdu, "field1", None)),
        ))
        return "DL; %s; Layer 2 - MAC(AccessAssignPdu); %s" % (
            cell,
            ", ".join(fields),
        )

    layer3 = chain.get("layer3")
    if layer3 is not None:
        layer_name, pdu = layer3
        fields = [_identity_field(chain)]
        fields.extend(_flatten_layer3_value(pdu))
        return "DL; %s; Layer 3 - %s(%s); %s" % (
            cell,
            LAYER3_NAMES.get(layer_name, layer_name.upper()),
            type(pdu).__name__,
            ", ".join(fields),
        )

    pdu = chain["layer2"]
    fields = [_identity_field(chain)]
    for name in MAC_RESOURCE_COMPACT_FIELDS:
        if name == "channel_allocation":
            value = (
                "encrypted"
                if getattr(pdu, "channel_allocation_flag", 0)
                and getattr(pdu, "encryption_mode", 0) != 0
                else None
            )
        else:
            value = getattr(pdu, name, None)
        if value is not None:
            fields.append(_format_scalar(name, value))
    return "DL; %s; Layer 2 - MAC(%s); %s" % (
        cell,
        type(pdu).__name__,
        ", ".join(fields),
    )
