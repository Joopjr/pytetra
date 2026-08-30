"""TETRA LLC 32-bit frame check sequence."""


FCS_BITS = 32
FCS_POLYNOMIAL = 0x04C11DB7
FCS_INITIAL = 0xFFFFFFFF
FCS_FINAL_XOR = 0xFFFFFFFF


def compute_fcs(bits):
    """Return the 32 FCS bits for an MSB-first binary string."""
    register = FCS_INITIAL

    for bit in bits:
        if bit not in "01":
            raise ValueError("FCS input must be a binary string")
        feedback = ((register >> 31) & 1) ^ int(bit)
        register = (register << 1) & 0xFFFFFFFF
        if feedback:
            register ^= FCS_POLYNOMIAL

    register ^= FCS_FINAL_XOR
    return format(register, "032b")


def check_fcs(protected_bits, received_fcs):
    """Return True when a received LLC FCS matches protected_bits."""
    if len(received_fcs) != FCS_BITS:
        return False
    return compute_fcs(protected_bits) == received_fcs
