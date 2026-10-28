"""Dependency-free NLI configuration constants.

Kept free of ML imports so that the human-review and evaluation tooling can read
the model identifier without loading torch or transformers.
"""

MODEL_NAME = "cross-encoder/nli-deberta-v3-small"
