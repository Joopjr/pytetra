from collections import OrderedDict
from pytetra.pdu.pdu import PduDecodingException

# PDU encoding for sublayers 3.2 (CMCE, MM, SNDCP)


class Element(object):
    name = None
    identifier = None

    def __repr__(self):
        raise NotImplementedError

    @classmethod
    def parse(cls, bits):
        raise NotImplementedError


class UnknownType34Element(Element):
    def __init__(self, identifier, length, value):
        self.identifier = identifier
        self.length = length
        self.value = value

    def __repr__(self):
        return "UnknownType34Element(Identifier(%d), Length(%d), Value(%r))" % (
            self.identifier,
            self.length,
            self.value,
        )


class LeafElement(Element):
    length = None

    def __init__(self, value):
        self.value = value

    def __repr__(self):
        return '%s(%s)' % (self.__class__.__name__, repr(self.value))

    def __eq__(self, other):
        if isinstance(other, self.__class__):
            return self.value == other.value


class IntElement(LeafElement):
    @classmethod
    def parse(cls, bits, length=None):
        return cls(bits.read_int(length if length is not None else cls.length))


class BitsElement(LeafElement):
    @classmethod
    def parse(cls, bits, length=None):
        return cls(bits.read(length if length is not None else cls.length))


class EnumElement(LeafElement):
    @classmethod
    def parse(cls, bits, length=None):
        return cls(cls.enum[bits.read_int(length if length is not None else cls.length)])


class CompoundElement(Element):
    type1 = None
    type2 = None
    type34 = None
    sdu = False
    has_o_bit = False

    def __init__(self, *args):
        self.fields = OrderedDict()
        for elem in args:
            self.add_field(elem)

    @classmethod
    def parse(cls, bits, length=None):
        if length is not None:
            if length > len(bits):
                raise PduDecodingException(
                    "%s length %d exceeds %d available bits"
                    % (cls.__name__, length, len(bits))
                )
            bounded = bits.read(length)
            result = cls.parse(bounded)
            if len(bounded):
                raise PduDecodingException(
                    "%s left %d bits inside bounded element"
                    % (cls.__name__, len(bounded))
                )
            return result

        compound_element = cls()

        for elem in compound_element.type1:
            elem.decode(compound_element, bits)

        if cls.has_o_bit or compound_element.type2 or compound_element.type34:
            o_bit = bits.read_int(1)
            if o_bit:
                for elem in compound_element.type2:
                    elem.decode(compound_element, bits)

                if compound_element.type34:
                    compound_element._decode_type34_chain(bits)

        if compound_element.sdu:
            compound_element.add_field(SduElement(bits.read(len(bits))))

        return compound_element

    def _decode_type34_chain(self, bits):
        descriptors = {
            field.element.identifier: field
            for field in self.type34
            if getattr(field.element, "identifier", None) is not None
        }

        while True:
            if len(bits) < 1:
                raise PduDecodingException("Missing final M-bit")
            if bits.peek_int(0, 1) == 0:
                bits.read(1)
                return
            if len(bits) < 16:
                raise PduDecodingException("Truncated Type 3/4 header")

            identifier = bits.peek_int(1, 4)
            descriptor = descriptors.get(identifier)
            if descriptor is not None:
                before = len(bits)
                descriptor.decode(self, bits)
                if len(bits) >= before:
                    raise PduDecodingException(
                        "Type 3/4 decoder consumed no bits for identifier %d"
                        % identifier
                    )
                continue

            bits.read(1)
            bits.read(4)
            length = bits.read_int(11)
            if length > len(bits):
                raise PduDecodingException(
                    "Unknown Type 3/4 element %d length %d exceeds %d bits"
                    % (identifier, length, len(bits))
                )
            self.add_field(
                UnknownType34Element(identifier, length, bits.read(length))
            )

    def add_field(self, field):
        if isinstance(field, list):
            if not field:
                return
            key = field[0].__class__
        else:
            key = field.__class__

        if key not in self.fields:
            self.fields[key] = field
            return

        current = self.fields[key]
        if not isinstance(current, list):
            current = [current]
            self.fields[key] = current
        if isinstance(field, list):
            current.extend(field)
        else:
            current.append(field)

    def __getitem__(self, item):
        return self.fields[item]

    def __repr__(self):
        return self.__class__.__name__ + '(' + ', '.join(map(repr, list(self.fields.values()))) + ')'

    def __eq__(self, other):
        if isinstance(other, self.__class__):
            return self.fields == other.fields
        return False


class Pdu(CompoundElement):
    has_o_bit = True

    @classmethod
    def parse(cls, bits):
        res = super(Pdu, cls).parse(bits)
        if len(bits):
            raise PduDecodingException('Trailing bits at the end of PDU')
        return res


class PduDiscriminator(Pdu):
    element = None
    pdu_types = None

    @classmethod
    def parse(cls, bits):
        t = bits.peek_int(0, cls.element.length)

        if t not in cls.pdu_types:
            raise PduDecodingException(
                "Unknown %s PDU type %d (0x%X), %d bits remaining: %s"
                % (
                    cls.__name__,
                    t,
                    t,
                    len(bits),
                    bits.bits
                )
            )

        pdu_class = cls.pdu_types[t]

        return pdu_class.parse(bits)


class TypeField(object):
    def __repr__(self):
        return '%s(%s)' % (self.__class__.__name__, self.element.__name__)


class Type1(TypeField):
    def __init__(self, element, cond=None, length_func=None):
        self.element = element
        self.cond = cond
        self.length_func = length_func

    def decode(self, parent, bits):
        length = self.length_func(parent) if self.length_func else None
        if self.cond is None or self.cond(parent):
            parent.add_field(self.element.parse(bits, length))


class Type2(TypeField):
    def __init__(self, element, cond=None):
        self.element = element
        self.cond = cond

    def decode(self, parent, bits):
        if self.cond is None:
            p_bit = bits.read_int(1)
            if p_bit:
                parent.add_field(self.element.parse(bits))
        elif self.cond(parent):
            parent.add_field(self.element.parse(bits))


class Type3(TypeField):
    def __init__(self, element):
        self.element = element

    def decode(self, parent, bits):
        m_bit = bits.peek_int(0, 1)
        if m_bit:
            element_identifier = bits.peek_int(1, 4)
            if element_identifier == self.element.identifier:
                bits.read(5)
                length = bits.read_int(11)
                parent.add_field(self.element.parse(bits, length))


class Type4(TypeField):
    def __init__(self, element):
        self.element = element

    def decode(self, parent, bits):
        m_bit = bits.peek_int(0, 1)
        if m_bit:
            element_identifier = bits.peek_int(1, 4)
            if element_identifier == self.element.identifier:
                bits.read(5)
                length = bits.read_int(11)
                if length > len(bits):
                    raise PduDecodingException(
                        "Type 4 length %d exceeds %d available bits"
                        % (length, len(bits))
                    )
                payload = bits.read(length)
                if len(payload) < 6:
                    raise PduDecodingException("Type 4 element misses repeat count")
                repeat = payload.read_int(6)
                if repeat == 0:
                    raise PduDecodingException("Invalid Type 4 repeat count 0")
                parent.add_field([
                    self.element.parse(payload)
                    for r in range(repeat)
                ])
                if len(payload):
                    raise PduDecodingException(
                        "Type 4 element left %d trailing bits" % len(payload)
                    )


class Repeat(TypeField):
    def __init__(self, element, num):
        self.element = element
        self.num = num

    def decode(self, parent, bits):
        parent.add_field([self.element.parse(bits) for r in range(self.num(parent))])


class SduElement(BitsElement):
    @classmethod
    def parse(cls, bits):
        return cls(bits)
