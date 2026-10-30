"""Registry of admin-editable tables (spec R2, C-2, C-3).

Each entry describes columns so one set of screens can list, add, edit,
soft-delete, restore, show history, and import/export CSV for every table
without code per table. Columns: (name, label, type, extra) where type is
text | textarea | int | real | bool | ref | choice | json.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Col:
    name: str
    label: str
    type: str = "text"
    ref: str = ""            # for type 'ref': "table:key_col:label_col"
    choices: tuple = ()
    required: bool = False
    hint: str = ""


@dataclass(frozen=True)
class Table:
    name: str
    label: str
    cols: tuple
    natural_key: tuple = ()      # for CSV upsert, e.g. ('code',)
    order_by: str = "id"
    group: str = "Reference data"
    note: str = ""
    editable: bool = True


def C(*a, **k) -> Col:
    return Col(*a, **k)


REFERENCE = [
    Table("country", "Countries", (
        C("iso3", "ISO-3 code", required=True, hint="Three letters, e.g. AUS"),
        C("name", "Name", required=True), C("un_member", "UN member", "bool"), C("p5", "Permanent Security Council member", "bool"),
        C("region", "UN regional group code", hint="AFR, APG, EEG, GRULAC or WEOG"),
        C("flag_svg", "Flag (SVG markup)", "textarea", hint="Optional. Simple inline SVG, viewBox 0 0 24 16."),
        C("notes", "Notes", "textarea")), natural_key=("iso3",), order_by="name"),
    Table("bloc", "Blocs", (
        C("code", "Code", required=True), C("name", "Name", required=True),
        C("kind", "Kind", "choice", choices=("regional_group", "negotiating_bloc", "political_group", "economic_group")),
        C("cohesion", "Cohesion (0 to 0.95)", "real", hint="How much members vote together. Unvalidated defaults; tune by calibration."),
        C("source", "Source", hint="Where the membership list comes from"), C("verified", "Membership checked against source", "bool"),
        C("notes", "Notes", "textarea")), natural_key=("code",), order_by="code"),
    Table("bloc_member", "Bloc memberships", (
        C("bloc_id", "Bloc", "ref", ref="bloc:id:name", required=True), C("iso3", "Country", "ref", ref="country:iso3:name", required=True),
        C("from_date", "From"), C("to_date", "To"), C("source", "Source")), natural_key=("bloc_id", "iso3"), order_by="bloc_id, iso3"),
    Table("voting_rule", "Voting rules", (
        C("code", "Code", required=True), C("name", "Name", required=True),
        C("threshold_num", "Threshold numerator", "int"), C("threshold_den", "Threshold denominator", "int"),
        C("denominator", "Counted against", "choice", choices=("voting", "present", "members"),
          hint="voting = yes+no; present = yes+no+abstain; members = everyone"),
        C("at_threshold", "Exactly at the threshold", "choice", choices=("pass", "fail")),
        C("min_yes", "Minimum yes votes", "int"), C("veto_iso3", "Veto holders (ISO-3, comma separated)"),
        C("notes", "Notes", "textarea")), natural_key=("code",), order_by="code"),
    Table("procedure_rule_set", "Rules of procedure", (
        C("code", "Code", required=True), C("name", "Name", required=True),
        C("speaking_time_default", "Default speaking time (seconds)", "int"), C("notes", "Notes", "textarea")),
        natural_key=("code",), order_by="code"),
    Table("procedure_motion", "Motions", (
        C("rule_set_id", "Rule set", "ref", ref="procedure_rule_set:id:name", required=True), C("code", "Code", required=True),
        C("name", "Name", required=True), C("precedence", "Precedence (higher is considered first)", "int"),
        C("voting_rule_id", "Voting rule", "ref", ref="voting_rule:id:name"), C("needs_second", "Needs a second", "bool"),
        C("has_duration", "Has a duration", "bool"), C("has_speaking_time", "Has a speaking time", "bool"),
        C("description", "Description", "textarea")), natural_key=("rule_set_id", "code"), order_by="rule_set_id, precedence DESC"),
    Table("procedure_stage", "Procedure stages (chair script)", (
        C("rule_set_id", "Rule set", "ref", ref="procedure_rule_set:id:name", required=True),
        C("code", "Stage", "choice", choices=("roll_call", "agenda", "opening_speeches", "floor", "voting_procedure", "debrief"),
          required=True),
        C("position", "Order", "int"), C("name", "Name", required=True),
        C("chair_script", "What the chair says", "textarea",
          hint="Placeholders: {committee}, {agenda}, {present}, {majority}, {speaking_time}, {target}, {yes}, {no}, {abstain}, {result}"),
        C("chair_next", "What happens next (for the chair)", "textarea"),
        C("student_prompt", "What students can do now", "textarea")),
        natural_key=("rule_set_id", "code"), order_by="rule_set_id, position",
        note="The committee session (D-060, D-068) shows these to the chair and students at each stage."),
    Table("committee_type", "Committee types", (
        C("code", "Code", required=True), C("name", "Name", required=True),
        C("default_rule_id", "Default voting rule", "ref", ref="voting_rule:id:name"),
        C("default_procedure_id", "Default rules of procedure", "ref", ref="procedure_rule_set:id:name"),
        C("notes", "Notes", "textarea")), natural_key=("code",), order_by="name"),
    Table("topic", "Topics", (C("code", "Code", required=True), C("name", "Name", required=True), C("notes", "Notes", "textarea")),
          natural_key=("code",), order_by="name"),
    Table("tag", "Tags", (C("topic_id", "Topic", "ref", ref="topic:id:name", required=True), C("code", "Code", required=True),
                          C("label", "Meaning", required=True)), natural_key=("topic_id", "code"), order_by="topic_id, code",
          note="Tags are per topic: a disarmament topic gets its own tags (audit §5.3)."),
    Table("archetype", "Archetypes", (C("code", "Code", required=True), C("name", "Name", required=True),
                                      C("blurb", "Description", "textarea")), natural_key=("code",), order_by="name"),
    Table("archetype_affinity", "Archetype affinities", (
        C("archetype_id", "Archetype", "ref", ref="archetype:id:name", required=True),
        C("tag_id", "Tag", "ref", ref="tag:id:code", required=True), C("value", "Affinity (-2 to +2)", "real"),
        C("source", "Source")), natural_key=("archetype_id", "tag_id"), order_by="archetype_id, tag_id"),
    Table("country_archetype", "Country archetype blends", (
        C("iso3", "Country", "ref", ref="country:iso3:name", required=True),
        C("archetype_id", "Archetype", "ref", ref="archetype:id:name", required=True),
        C("topic_id", "Topic", "ref", ref="topic:id:name", required=True), C("weight", "Weight", "real"), C("source", "Source")),
        natural_key=("iso3", "archetype_id", "topic_id"), order_by="id"),
    Table("archetype_line", "Archetype reaction lines", (
        C("archetype_id", "Archetype", "ref", ref="archetype:id:name", required=True), C("stance", "Stance (-2 to 2)", "int"),
        C("line", "Line", "textarea")), natural_key=("archetype_id", "stance"), order_by="archetype_id, stance"),
    Table("source_type", "Evidence source types", (
        C("code", "Code", required=True), C("label", "Label", required=True), C("shown_as", "Shown as", required=True),
        C("weight", "Weight", "real"), C("requires_source", "Requires a source", "bool"), C("notes", "Notes", "textarea")),
        natural_key=("code",), order_by="weight DESC"),
    Table("rubric", "Rubrics", (
        C("code", "Code", required=True), C("name", "Name", required=True),
        C("kind", "Kind", "choice", choices=("mun", "debate_speaker", "speech", "adjudicator")),
        C("levels", "Number of levels", "int"), C("notes", "Notes", "textarea")), natural_key=("code",), order_by="name"),
    Table("rubric_criterion", "Rubric criteria", (
        C("rubric_id", "Rubric", "ref", ref="rubric:id:name", required=True), C("position", "Order", "int"),
        C("code", "Code", required=True), C("name", "Name", required=True), C("min_score", "Minimum score", "real"),
        C("max_score", "Maximum score", "real"), C("weight", "Weight", "real"), C("hint", "Hint", "textarea")),
        natural_key=("rubric_id", "code"), order_by="rubric_id, position"),
    Table("rubric_descriptor", "Rubric level descriptors", (
        C("criterion_id", "Criterion", "ref", ref="rubric_criterion:id:name", required=True), C("level", "Level", "int"),
        C("descriptor", "Descriptor", "textarea")), natural_key=("criterion_id", "level"), order_by="criterion_id, level"),
    Table("template", "Templates", (
        C("code", "Code", required=True), C("kind", "Kind", "choice",
                                            choices=("minutes", "run_sheet", "mc_script", "position_paper", "certificate", "other")),
        C("name", "Name", required=True), C("body", "Body", "textarea",
                                            hint="Placeholders in {{ double braces }}; loops with {% for %}. Safe: templates run in a sandbox.")),
        natural_key=("code",), order_by="kind, name"),
    Table("house", "Houses", (C("code", "Code", required=True), C("name", "Name", required=True),
                              C("colour", "Colour (for display)", hint="e.g. #2E7D32")), natural_key=("code",), order_by="name",
          group="Debating"),
    Table("debate_format", "Debate formats", (
        C("code", "Code", required=True), C("name", "Name", required=True), C("speakers_per_team", "Speakers per team (1-4)", "int"),
        C("reply", "Reply speeches", "bool"), C("speech_seconds", "Speech length (seconds)", "int"),
        C("reply_seconds", "Reply length (seconds)", "int"), C("prep_minutes", "Preparation (minutes)", "int"),
        C("notes", "Notes", "textarea")), natural_key=("code",), order_by="id", group="Debating"),
    Table("motion_bank", "Motion bank", (C("motion", "Motion", required=True), C("topic", "Topic"),
                                         C("level", "Level", "choice", choices=("junior", "middle", "senior")), C("source", "Source")),
          order_by="level, id", group="Debating"),
    Table("motion_argument", "Likely arguments for each motion", (
        C("motion_id", "Motion", "ref", ref="motion_bank:id:motion", required=True),
        C("side", "Side", "choice", choices=("aff", "neg"), required=True), C("position", "Order", "int"),
        C("argument", "Argument", "textarea", required=True, hint="One line: a starting point students rebut. Not evidence.")),
          order_by="motion_id, side, position", group="Debating",
          note="Shown to students preparing a case, as the other side's likely arguments to rebut (D-076)."),
    Table("impromptu_topic", "Impromptu topics", (
        C("topic", "Topic", required=True), C("kind", "Kind", "choice", choices=("question", "object", "scenario", "word", "opinion")),
        C("level", "Year level", "choice", choices=("any", "junior", "middle", "senior"))), order_by="level, id", group="Debating",
          note="Drawn at random for impromptu practice and speaking rounds (D-077)."),
    Table("speech_template", "Speech templates", (
        C("code", "Code", required=True), C("name", "Name", required=True),
        C("kind", "Kind", "choice", choices=("prepared", "impromptu"), required=True), C("blurb", "What it's for", "textarea"),
        C("sections", "Sections", "json", hint='A list of {"key": "hook", "label": "Hook", "prompt": "…"}'),
        C("position", "Order", "int")), natural_key=("code",), order_by="kind, position", group="Debating",
          note="Structures for the speech writer and impromptu structure cards (D-077)."),
    Table("feedback_prompt", "Adjudicator feedback prompts", (
        C("criterion", "Criterion", "choice", choices=("matter", "manner", "method", "reply", "overall"), required=True),
        C("position", "Order", "int"), C("prompt", "Prompt", "textarea", required=True)),
        order_by="criterion, position", group="Debating", note="Shown to adjudicators on the ballot page."),
    Table("house_points_rule", "House points rules", (
        C("code", "Code", required=True), C("label", "Label", required=True),
        C("kind", "Kind", "choice", choices=("win", "participation", "team_place", "speaker_place")),
        C("place", "Place (for placings)", "int"), C("points", "Points", "real")), natural_key=("code",), order_by="kind, place",
          group="Debating", note="Assumed defaults. Set them to the school's own house points rules."),
    Table("pathway_milestone", "Pathway milestones", (
        C("code", "Code", required=True), C("name", "Name", required=True),
        C("track", "Track", "choice", choices=("mun", "debating", "speaking", "both")), C("position", "Order", "int"),
        C("description", "Description", "textarea")), natural_key=("code",), order_by="position", group="People"),
]

# Read-only exports of everything else (C-3: "import and export any table as CSV").
EXPORT_ONLY = [
    "class", "student", "staff_class", "conference", "committee", "delegation", "delegation_member", "resolution",
    "paragraph", "paragraph_version", "amendment", "amendment_support", "evidence", "prediction", "prediction_country",
    "actual_vote", "task", "student_milestone", "model_version", "event_log",
    "live_session", "speakers_list_entry", "motion", "division", "division_vote", "minutes",
    "roll_call", "whip_round", "whip_prediction", "fidelity_override", "sim_practice", "sim_practice_member", "sim_practice_lobby",
    "floor_point", "delegate_message", "amendment_suggestion",
    "debate_event", "team", "team_member", "adjudicator", "room", "debate_round", "pairing", "pairing_adjudicator",
    "ballot", "ballot_score", "house_points_entry", "event_document", "practice_speech",
    "class_run", "class_run_speaker", "prep_case", "prep_point", "prep_speech",
    "student_group", "student_group_member",
]
# Columns never exported or shown.
SECRET_COLUMNS = {"pass_hash", "token_hash", "csrf", "login_code"}

BY_NAME = {t.name: t for t in REFERENCE}
