class CirculationError(Exception):
    pass


class PolicyViolation(CirculationError):
    pass


class NotAvailable(CirculationError):
    pass

