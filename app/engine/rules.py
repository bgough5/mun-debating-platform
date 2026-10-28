"""Voting rules as data (spec §5.4, D-011).

A rule passes when:
    yes >= min_yes
    AND yes / denominator compared with threshold_num / threshold_den:
        above  -> pass;  exactly at -> `at_threshold`;  below -> fail
    AND no member of `veto` voted no (an abstention is not a veto).
Denominator: 'voting' = yes + no; 'present' = yes + no + abstain;
'members' = all members of the committee, including absent ones.
If the denominator is zero the motion fails (nobody voted for it).
"""
from __future__ import annotations

from dataclasses import dataclass, field

VOTES = ("yes", "abstain", "no")


@dataclass(frozen=True)
class VotingRule:
    code: str
    name: str
    threshold_num: int = 1
    threshold_den: int = 2
    denominator: str = "voting"
    at_threshold: str = "fail"
    min_yes: int = 0
    veto: frozenset = field(default_factory=frozenset)

    @classmethod
    def from_row(cls, row: dict) -> "VotingRule":
        veto = frozenset(x.strip().upper() for x in (row.get("veto_iso3") or "").split(",") if x.strip())
        return cls(code=row["code"], name=row["name"], threshold_num=int(row["threshold_num"]),
                   threshold_den=int(row["threshold_den"]), denominator=row["denominator"],
                   at_threshold=row["at_threshold"], min_yes=int(row["min_yes"]), veto=veto)

    def describe(self) -> str:
        parts = []
        frac = f"{self.threshold_num}/{self.threshold_den}"
        cmp = "at least" if self.at_threshold == "pass" else "more than"
        den = {"voting": "of members voting yes or no", "present": "of members present (abstentions count against)",
               "members": "of all members"}[self.denominator]
        if self.threshold_num > 0:
            parts.append(f"{cmp} {frac} {den}")
        if self.min_yes:
            parts.append(f"at least {self.min_yes} yes votes")
        if self.veto:
            parts.append("no veto (a no vote from " + ", ".join(sorted(self.veto)) + "; abstaining is not a veto)")
        return "Passes with " + " and ".join(parts) + "." if parts else "Passes with any vote."


def passes(rule: VotingRule, yes: int, abstain: int, no: int, members: int, veto_no: bool = False) -> bool:
    if yes < rule.min_yes or veto_no:
        return False
    den = {"voting": yes + no, "present": yes + no + abstain, "members": members}[rule.denominator]
    if den <= 0:
        return False
    lhs = yes * rule.threshold_den
    rhs = rule.threshold_num * den
    if lhs > rhs:
        return True
    if lhs == rhs:
        return rule.at_threshold == "pass"
    return False


@dataclass(frozen=True)
class Outcome:
    passed: bool
    yes: int
    abstain: int
    no: int
    absent: int
    vetoed_by: tuple

    @property
    def summary(self) -> str:
        s = f"{self.yes} yes, {self.no} no, {self.abstain} abstaining"
        if self.absent:
            s += f", {self.absent} absent"
        if self.vetoed_by:
            s += "; vetoed by " + ", ".join(self.vetoed_by)
        return s + (" — passed" if self.passed else " — failed")


def tally(rule: VotingRule, votes: dict[str, str], members: int | None = None) -> Outcome:
    """votes: iso3 -> 'yes' | 'abstain' | 'no' | 'absent'."""
    yes = sum(1 for v in votes.values() if v == "yes")
    no = sum(1 for v in votes.values() if v == "no")
    abstain = sum(1 for v in votes.values() if v == "abstain")
    absent = sum(1 for v in votes.values() if v == "absent")
    vetoed_by = tuple(sorted(c for c, v in votes.items() if v == "no" and c.upper() in rule.veto))
    m = members if members is not None else len(votes)
    return Outcome(passes(rule, yes, abstain, no, m, bool(vetoed_by)), yes, abstain, no, absent, vetoed_by)


# Built-in definitions, mirrored in app/db/seed/voting_rules.csv.
GA_SIMPLE = VotingRule("ga_simple", "GA simple majority", 1, 2, "voting", "fail")
GA_TWO_THIRDS = VotingRule("ga_two_thirds", "GA two-thirds (important questions)", 2, 3, "voting", "pass")
SC_SUBSTANTIVE = VotingRule("sc_substantive", "Security Council substantive", 0, 1, "voting", "pass", 9,
                            frozenset({"CHN", "FRA", "RUS", "GBR", "USA"}))
SC_PROCEDURAL = VotingRule("sc_procedural", "Security Council procedural", 0, 1, "voting", "pass", 9)
