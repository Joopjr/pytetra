from pytetra.logger import Logger


class Layer(object):
    layer_number = None

    def __init__(self, stack):
        self.stack = stack

    def warning(self, message):
        if self.layer_number in (2, 3) and getattr(self.stack, "output_suppressed", False):
            return
        Logger.log(
            '%s: %s' % (self.__class__.__name__, message),
            self.layer_number,
        )

    def info(self, message):
        if self.layer_number in (2, 3) and getattr(self.stack, "output_suppressed", False):
            return
        Logger.log(
            '%s: %s' % (self.__class__.__name__, message),
            self.layer_number,
        )

    def protocol(self, message):
        if self.layer_number in (2, 3) and getattr(self.stack, "output_suppressed", False):
            return
        Logger.log(message, self.layer_number)

    def expose_pdu(self, pdu):
        if self.layer_number in (2, 3) and getattr(self.stack, "output_suppressed", False):
            return
        record_pdu = getattr(self.stack, "record_pdu", None)
        if record_pdu is not None:
            record_pdu(self.__class__.__name__, pdu)
        self.stack.user.pdu_indication(self.__class__.__name__, pdu)
