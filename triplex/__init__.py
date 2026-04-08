"""
CFO Silvia TRIPLEX — Multi-agent triple-verification pipeline.

Every post passes through 8 specialized agents plus 2 deterministic
reconciliation stages plus 1 mandatory human sign-off gate.

Core principle: no data point reaches the writer unless at least 2 of 3
independent sources agree on it. No post reaches the human gate unless
every sentence traces back to a locked data point.
"""

__version__ = "0.1.0"
