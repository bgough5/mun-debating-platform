"""Voting rules (spec §5.4, §5.8): GA majority and ties, two-thirds edges, SC veto and P5 abstention."""
import pytest

from app.engine.rules import GA_SIMPLE, GA_TWO_THIRDS, SC_PROCEDURAL, SC_SUBSTANTIVE, VotingRule, passes, tally


@pytest.mark.parametrize("yes,ab,no,expected", [
    (16, 0, 15, True),
    (15, 1, 15, False),     # tie fails
    (1, 30, 0, True),       # abstentions don't count
    (0, 31, 0, False),      # nobody voted yes or no
    (10, 0, 11, False),
])
def test_ga_simple(yes, ab, no, expected):
    assert passes(GA_SIMPLE, yes, ab, no, yes + ab + no) is expected


@pytest.mark.parametrize("yes,no,expected", [
    (20, 10, True),    # exactly two-thirds passes
    (19, 10, False),   # 19/29 = 0.655
    (2, 1, True),
    (1, 1, False),
    (0, 0, False),
])
def test_ga_two_thirds_edges(yes, no, expected):
    assert passes(GA_TWO_THIRDS, yes, 5, no, 40) is expected


def sc_votes(yes_list, no_list, abstain_list):
    v = {c: "yes" for c in yes_list}
    v.update({c: "no" for c in no_list})
    v.update({c: "abstain" for c in abstain_list})
    return v


ELECTED = ["DNK", "GRC", "PAK", "PAN", "SOM", "BHR", "COL", "COD", "LVA", "LBR"]


def test_sc_nine_yes_passes():
    v = sc_votes(["CHN", "FRA", "RUS", "GBR", "USA"] + ELECTED[:4], ELECTED[4:], [])
    assert tally(SC_SUBSTANTIVE, v).passed


def test_sc_eight_yes_fails():
    v = sc_votes(["CHN", "FRA", "RUS", "GBR", "USA"] + ELECTED[:3], [], ELECTED[3:])
    assert not tally(SC_SUBSTANTIVE, v).passed


def test_sc_p5_no_is_veto():
    v = sc_votes(["CHN", "FRA", "GBR", "USA"] + ELECTED, ["RUS"], [])
    out = tally(SC_SUBSTANTIVE, v)
    assert out.yes == 14 and not out.passed and out.vetoed_by == ("RUS",)


def test_sc_p5_abstention_is_not_veto():
    v = sc_votes(["CHN", "FRA", "GBR", "USA"] + ELECTED[:5], ELECTED[5:], ["RUS"])
    out = tally(SC_SUBSTANTIVE, v)
    assert out.yes == 9 and out.passed and out.vetoed_by == ()


def test_sc_elected_no_is_not_veto():
    v = sc_votes(["CHN", "FRA", "RUS", "GBR", "USA"] + ELECTED[:4], ELECTED[4:], [])
    assert tally(SC_SUBSTANTIVE, v).passed


def test_sc_procedural_has_no_veto():
    v = sc_votes(["CHN", "FRA", "GBR", "USA"] + ELECTED[:5], ["RUS"] + ELECTED[5:], [])
    assert tally(SC_PROCEDURAL, v).passed


def test_custom_members_denominator_counts_absent():
    rule = VotingRule("c", "Majority of members", 1, 2, "members", "fail")
    v = {"A": "yes", "B": "yes", "C": "absent", "D": "absent", "E": "no"}
    assert not tally(rule, v).passed            # 2 of 5 members
    v["C"] = "yes"
    assert tally(rule, v).passed                # 3 of 5


def test_custom_present_denominator_abstain_counts_against():
    rule = VotingRule("c", "Majority present", 1, 2, "present", "fail")
    assert not passes(rule, 5, 2, 4, 11)        # 5/11
    assert passes(rule, 6, 1, 4, 11)


def test_custom_tie_result_configurable():
    pass_on_tie = VotingRule("c", "Tie passes", 1, 2, "voting", "pass")
    assert passes(pass_on_tie, 5, 0, 5, 10)
    assert not passes(GA_SIMPLE, 5, 0, 5, 10)


def test_describe_mentions_veto():
    assert "abstaining is not a veto" in SC_SUBSTANTIVE.describe()
