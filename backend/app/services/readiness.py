"""Injectable readiness probes.

Readiness policy for PR-02 (documented, deliberate):

* ``GET /api/v1/health/ready`` reports whether the **configured, required**
  application dependencies are ready.
* PR-02 configures **no** required external dependencies: the default
  probe set is empty, so readiness returns ``200`` with an empty checks
  list. The API deliberately does *not* pretend to check a PostgreSQL
  database that is not integrated yet (that arrives in PR-03).
* When PR-03 adds PostgreSQL, it will register a probe here. The public
  response contract (:class:`~app.contracts.common.ReadinessResponse` and
  the 503 ``SERVICE_NOT_READY`` error envelope) stays unchanged.
* Optional research datasets are **not** readiness dependencies: an
  unavailable optional artifact must not make the whole API unready.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable


@dataclass(frozen=True)
class ReadinessProbe:
    """A named, injectable dependency check.

    ``check`` must be a cheap, deterministic, side-effect-free callable
    returning ``True`` when the dependency is usable. Exceptions are
    treated as "not ready"; their details are never exposed in responses.
    """

    name: str
    check: Callable[[], bool]

    def __post_init__(self) -> None:
        if not self.name or not self.name.strip():
            raise ValueError("A readiness probe must have a non-empty name.")


def evaluate_probes(probes: tuple[ReadinessProbe, ...]) -> tuple[list[str], list[str]]:
    """Evaluate probes; return ``(ready_names, unavailable_names)``.

    A raising probe counts as unavailable, and its exception detail is
    intentionally discarded (no internal connection details may leak into
    responses or logs at this layer).
    """
    ready: list[str] = []
    unavailable: list[str] = []
    for probe in probes:
        try:
            ok = bool(probe.check())
        except Exception:  # noqa: BLE001 - deliberate: any failure means "not ready"
            ok = False
        (ready if ok else unavailable).append(probe.name)
    return ready, unavailable
