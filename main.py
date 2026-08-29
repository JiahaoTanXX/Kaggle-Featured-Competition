"""Kaggle submission entrypoint.

For local runs this imports the modular implementation. build_submission.py bundles
the same package beside this file into submission.tar.gz.
"""

from src.kaggriculture_agent import Policy


_POLICY = Policy()


def agent(obs):
    return _POLICY.act(obs)
