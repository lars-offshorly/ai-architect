"""customization_merger — merge workspace customisation data into the base config.

Applies user- or session-supplied customisation (company name, team names,
custom labels, etc.) on top of the bundle base config produced by the encoding
step.  The merge is non-destructive: keys present in ``customization`` override
the corresponding keys in ``base_config``, while all other base keys are
preserved unchanged.

Responsibility
--------------
- Accept a base config dict and a customisation dict.
- Deep-merge customisation values into the base config.
- Return the merged config without mutating either input.

# TODO(CORE-AI-012 Subtask) This module is a stub pending full implementation.
"""

from __future__ import annotations


def merge_customization(  # noqa: V103
    base_config: dict[str, object],
    customization: dict[str, object],
) -> dict[str, object]:
    """Merge customisation data into the base bundle config.

    Args:
        base_config:    The assembled base config dict (output of
                        ``encode_config`` or loaded from the template).
        customization:  Workspace-specific overrides extracted from the
                        onboarding conversation (slots, company name, etc.).

    Returns:
        A new dict with customisation values applied over the base config.
        Neither input dict is mutated.

    Raises:
        NotImplementedError: Pending implementation (CORE-AI-015 —
                             Customization Merge Engine).
    """
    del base_config, customization
    raise NotImplementedError(
        "merge_customization is not yet implemented (CORE-AI-015 — "
        "Customization Merge Engine)."
    )
