# base.py
# Defines the base class for all agents.

class AtomicAgent:
    """
    Base class for all agents.
    Every agent must implement the execute() method.
    """

    def execute(self, conn, context):
        raise NotImplementedError
