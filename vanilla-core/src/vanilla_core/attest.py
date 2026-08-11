"""Attestation: quantities that may only move one way, and checks that can fail.

Three disciplines, generalised out of ACI so every flavor inherits them
instead of each one rediscovering them. All pure stdlib, no storage
assumptions, no imports of flavor code.

## Naming, deliberately not "floor"

`vanilla_core.floor` already means something else in this package: the
minimum a flavor must satisfy before Vanilla Core will run it — *refuse
rather than degrade*. ACI uses "floor" for the opposite kind of thing, a
count that may only rise.

Two meanings of one word inside one stack is how the canonical Spire
work-stream lost a day: plan gates and build gates were both G-numbered, and
a status file read beside the gameplan said gates were cleared that had never
been touched. So this module says `Direction.DEFECT` and
`Direction.CAPABILITY` and never says floor at all.

## 1. Direction

A measured quantity is one of two things, and conflating them is the bug this
module exists to prevent:

    DEFECT      may only FALL.  Regressions are failures.
    CAPABILITY  may only RISE.  Losses are failures.

A system that measures only defects has an exploitable hole, and it is not
hypothetical — it was demonstrated in ACI. Deleting an entire failure corpus
took the "untested failures" counter from 1 to 0, which a defect-only ratchet
reports as an improvement, and every readiness gate still passed because every
gate passes more easily over a smaller population.

    Derivation catches a number written down; a floor catches a number lost.

Pairing the two directions in one registry makes the omission visible: a
measure must declare which it is, so "we never counted what could be lost"
becomes a thing you can see rather than a thing nobody thought of.

## 2. Vacuity

`count == 0` over an empty population is true and meaningless. "No unmined
failures" reads identically whether nothing failed or nothing is tracked.

A DEFECT measure may declare a `population` callable. When that population is
empty the reading is **vacuous**, and a vacuous reading never counts as
passing.

    An assertion of absence is meaningful only against a demonstrated presence.

## 3. Falsifiability

A check that cannot fail certifies nothing. `falsify()` pairs each check with
a mutation that must break it; a check that stays green under its own mutation
SURVIVED and is decorative.

This found a real one in ACI: a gate required "zero world-ID collisions"
while a UNIQUE constraint made collisions unrepresentable. It had passed every
run since it was written and could not have done otherwise.

The honest reading of a clean result is narrow — *these mutations are killed*,
not *the checks are complete*. A mutation nobody thought to write cannot
survive.

## Legitimate loss

Knowledge shrinks for good reasons: two entries merged that were always one, a
source superseded. So the CAPABILITY check is not "did it go down" but **did
it go down without a record**. `supersede()` requires a reason and a named
witness, which inverts the usual relation between a check and a log: normally
the log records what the check permitted, here the log is what makes the
decrease permissible at all.

    A supersession with no reasoning is a deletion with a nicer name.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

__all__ = [
    "Direction", "Measure", "Reading", "Attestor", "Mutation",
    "FalsifyResult", "falsify",
]


class Direction:
    """Which way a quantity is allowed to move."""

    DEFECT = "defect"          # may only fall
    CAPABILITY = "capability"  # may only rise

    ALL = (DEFECT, CAPABILITY)


@dataclass(frozen=True)
class Measure:
    """One named quantity, and the direction it is permitted to move.

    `population` applies to DEFECT measures only and is the vacuity guard: a
    callable returning how many things the measure is measuring *over*. A
    defect count of zero across an empty population asserts nothing.
    """

    name: str
    direction: str
    read: Callable[[], int]
    population: Callable[[], int] | None = None
    note: str = ""

    def __post_init__(self) -> None:
        if self.direction not in Direction.ALL:
            raise ValueError(
                f"{self.name}: direction must be one of {Direction.ALL}, "
                f"got {self.direction!r}")
        if self.population is not None and self.direction != Direction.DEFECT:
            raise ValueError(
                f"{self.name}: a population guard only applies to a DEFECT "
                "measure. A capability count of zero is a real finding, not a "
                "vacuous one — it means the capability is gone.")


@dataclass(frozen=True)
class Reading:
    name: str
    direction: str
    value: int
    baseline: int | None
    vacuous: bool = False

    @property
    def unmeasured(self) -> bool:
        """No baseline on record. Reported, never silently passed over: a
        quantity nobody has a baseline for is one nobody would miss."""
        return self.baseline is None

    @property
    def ok(self) -> bool:
        if self.vacuous:
            return False
        if self.baseline is None:
            return True          # new measure: recorded, not a failure
        if self.direction == Direction.DEFECT:
            return self.value <= self.baseline
        return self.value >= self.baseline

    def describe(self) -> str:
        if self.vacuous:
            return f"VACUOUS — population is empty, so {self.value} asserts nothing"
        if self.baseline is None:
            return f"{self.value} (new measure, no baseline)"
        if self.value == self.baseline:
            return f"{self.value} at baseline"
        delta = self.value - self.baseline
        moved = "rose" if delta > 0 else "fell"
        good = self.ok
        return (f"{self.baseline} -> {self.value} ({moved} by {abs(delta)}) "
                f"{'ok' if good else 'REGRESSION'}")


@dataclass
class Attestor:
    """A registry of measures plus a JSON baseline on disk."""

    measures: list[Measure]
    baseline_path: Path
    _superseded: dict[str, int] = field(default_factory=dict)

    # ── fingerprint ───────────────────────────────────────────────────────
    def fingerprint(self) -> str:
        """Hash of the measure definitions.

        A baseline is only comparable to readings taken under the same
        definitions. Changing what you measure and keeping the old baseline
        makes a number that falls prove nothing.
        """
        blob = "\n".join(
            f"{m.name}={m.direction}={m.population is not None}"
            for m in sorted(self.measures, key=lambda m: m.name))
        return hashlib.sha256(blob.encode()).hexdigest()

    # ── reading ───────────────────────────────────────────────────────────
    def read(self) -> list[Reading]:
        data = self._load()
        baselines = data.get("baselines", {})
        out = []
        for m in sorted(self.measures, key=lambda m: m.name):
            value = m.read()
            vacuous = False
            if m.population is not None and m.population() == 0:
                vacuous = True
            base = baselines.get(m.name)
            if (m.direction == Direction.CAPABILITY
                    and base is not None
                    and m.name in self._superseded
                    and value >= self._superseded[m.name]):
                base = self._superseded[m.name]
            out.append(Reading(m.name, m.direction, value, base, vacuous))
        return out

    def check(self) -> tuple[bool, list[Reading]]:
        """(held, readings). `held` is False on any regression or vacuity."""
        data = self._load()
        readings = self.read()
        if data and data.get("fingerprint") != self.fingerprint():
            return False, readings
        return all(r.ok for r in readings), readings

    # ── recording ─────────────────────────────────────────────────────────
    def record(self, *, allow_regression: bool = False,
               reason: str | None = None) -> list[str]:
        """Write the current readings as the new baseline.

        Refuses to record a regression unless explicitly allowed with a
        reason. Recording a worse baseline inside a routine update hides the
        thing twice: once in the data, once in the operation that was
        supposed to only ever move the right way.
        """
        readings = self.read()
        bad = [r for r in readings if not r.ok and not r.unmeasured]
        if bad and not allow_regression:
            return [f"{r.name}: {r.describe()}" for r in bad]
        if bad and not reason:
            raise ValueError("allow_regression requires a reason")
        data = self._load()
        history = data.get("history", [])
        prior = data.get("baselines", {})
        changed = {r.name: {"from": prior.get(r.name), "to": r.value}
                   for r in readings if prior.get(r.name) != r.value}
        if changed:
            entry = {"at": _now(), "changed": changed}
            if reason:
                entry["reason"] = reason
            history.append(entry)
        self._save({
            "fingerprint": self.fingerprint(),
            "updated_utc": _now(),
            "baselines": {r.name: r.value for r in readings},
            "history": history[-50:],
        })
        return []

    def supersede(self, name: str, to: int, *, reason: str, witness: str) -> None:
        """Permit a CAPABILITY measure to sit below its baseline.

        Knowledge legitimately shrinks. What must not happen is that it
        shrinks with nothing on record — a decrease with an empty log is
        indistinguishable from data loss.
        """
        m = next((m for m in self.measures if m.name == name), None)
        if m is None:
            raise KeyError(name)
        if m.direction != Direction.CAPABILITY:
            raise ValueError(
                f"{name} is a DEFECT measure; a defect falling needs no excuse")
        if not reason or not reason.strip():
            raise ValueError(
                "a supersession with no reasoning is a deletion with a nicer name")
        if not witness or not witness.strip():
            raise ValueError("a supersession requires a named witness")
        data = self._load()
        base = data.get("baselines", {}).get(name)
        if base is not None and to >= base:
            raise ValueError(
                f"{name}: {to} is not below the baseline {base}. Growth never "
                "needs excusing — use record().")
        self._superseded[name] = to
        sups = data.get("supersessions", [])
        sups.append({"metric": name, "from": base, "to": to, "reason": reason,
                     "witness": witness, "at": _now()})
        data["supersessions"] = sups
        data.setdefault("baselines", {})[name] = to
        self._save(data)

    # ── disk ──────────────────────────────────────────────────────────────
    def _load(self) -> dict:
        if not self.baseline_path.exists():
            return {}
        data = json.loads(self.baseline_path.read_text())
        self._superseded = {s["metric"]: s["to"]
                            for s in data.get("supersessions", [])}
        return data

    def _save(self, data: dict) -> None:
        self.baseline_path.parent.mkdir(parents=True, exist_ok=True)
        self.baseline_path.write_text(
            json.dumps(data, indent=2, sort_keys=True) + "\n")


# ── falsification ─────────────────────────────────────────────────────────

@dataclass(frozen=True)
class Mutation:
    """A deliberate break, paired with the check that must catch it."""

    check: str
    apply: Callable[[], None]
    note: str = ""


@dataclass(frozen=True)
class FalsifyResult:
    check: str
    status: str      # "killed" | "SURVIVED" | "UNPROVEN"
    detail: str = ""

    @property
    def ok(self) -> bool:
        return self.status == "killed"


def falsify(checks: dict[str, Callable[[], bool]],
            mutations: list[Mutation]) -> list[FalsifyResult]:
    """Prove each check can fail.

    `checks` maps a name to a callable returning True when the check passes.
    Each mutation breaks something and the named check must then return False.

    A check already failing is demonstrably falsifiable and needs no mutation.
    A check with neither is UNPROVEN and reported as such — not passed over,
    for the same reason an unmeasured quantity is reported.

    The caller is responsible for isolation: mutations are destructive by
    design and must be applied to a copy. In ACI this means a copied database
    FILE rather than a `simulated` flag, because a flag is something a query
    can forget to filter on.
    """
    results: list[FalsifyResult] = []
    by_check: dict[str, list[Mutation]] = {}
    for mut in mutations:
        by_check.setdefault(mut.check, []).append(mut)

    for name, probe in sorted(checks.items()):
        if not probe():
            results.append(FalsifyResult(name, "killed", "currently failing"))
            continue
        muts = by_check.get(name)
        if not muts:
            results.append(FalsifyResult(name, "UNPROVEN", "no mutation declared"))
            continue
        killed = False
        for mut in muts:
            mut.apply()
            if not probe():
                killed = True
                break
        results.append(FalsifyResult(
            name, "killed" if killed else "SURVIVED",
            "mutation flipped it" if killed
            else "mutation applied and the check stayed green"))
    return results


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
