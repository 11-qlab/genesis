"""Exception hierarchy for the platform."""


class AGIError(Exception):
    """Base class for all platform errors."""


class ConfigError(AGIError):
    """Configuration could not be loaded or validated."""


class ProviderError(AGIError):
    """A model provider failed, returned garbage, or is misconfigured."""


class ToolError(AGIError):
    """A tool failed to validate its arguments or execute."""


class ToolNotFound(ToolError):
    """The requested tool is not registered."""


class PlanValidationError(AGIError):
    """A model-produced plan did not satisfy the plan schema or DAG rules."""


class BudgetExceeded(AGIError):
    """A run exceeded its wall-clock or tool-call budget."""
