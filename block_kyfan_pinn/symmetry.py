"""Reciprocal-lattice symmetry utilities for the triangular Bloch metric."""

from __future__ import annotations

from collections.abc import Sequence


def hexagonal_shell_index(mode: Sequence[int]) -> int:
    """Return the D6 shell index for ``m1^2 + m2^2 + m1*m2``."""

    if len(mode) != 2:
        raise ValueError("a reciprocal mode must have two components")
    first, second = (int(value) for value in mode)
    return max(abs(first), abs(second), abs(first + second))


def legacy_hexagonal_shell_index(mode: Sequence[int]) -> int:
    """Return the historical V2 shell index used by archived evidence."""

    if len(mode) != 2:
        raise ValueError("a reciprocal mode must have two components")
    first, second = (int(value) for value in mode)
    return max(abs(first), abs(second), abs(first - second))


def hexagonal_shell_modes(num_shells: int) -> list[tuple[int, int]]:
    """Return the complete reciprocal D6 orbit closure through one shell."""

    if num_shells < 0:
        raise ValueError("num_shells must be non-negative")
    return sorted(
        (first, second)
        for first in range(-num_shells, num_shells + 1)
        for second in range(-num_shells, num_shells + 1)
        if hexagonal_shell_index((first, second)) <= num_shells
    )


def legacy_hexagonal_shell_modes(num_shells: int) -> list[tuple[int, int]]:
    """Return the historical V2 dictionary without changing its semantics."""

    if num_shells < 0:
        raise ValueError("num_shells must be non-negative")
    return sorted(
        (first, second)
        for first in range(-num_shells, num_shells + 1)
        for second in range(-num_shells, num_shells + 1)
        if legacy_hexagonal_shell_index((first, second)) <= num_shells
    )


def lowest_kinetic_modes(
    wavevector: Sequence[float],
    *,
    rank: int,
    candidate_shell: int = 4,
) -> list[tuple[int, int]]:
    """Select a deterministic rank-limited Fourier control by kinetic energy."""

    if len(wavevector) != 2:
        raise ValueError("wavevector must have two components")
    candidates = hexagonal_shell_modes(candidate_shell)
    if rank < 1 or rank > len(candidates):
        raise ValueError("rank is outside the candidate dictionary")
    first_k, second_k = (float(value) for value in wavevector)

    def energy_value(mode: tuple[int, int]) -> float:
        first = mode[0] + first_k
        second = mode[1] + second_k
        return 0.5 * (first * first + second * second + first * second)

    ordered = sorted(candidates, key=lambda mode: (energy_value(mode), mode))
    boundary = energy_value(ordered[rank - 1])
    tolerance = 1e-7 * max(1.0, abs(boundary))
    return [mode for mode in ordered if energy_value(mode) <= boundary + tolerance]
