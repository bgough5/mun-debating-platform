import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "server"))

from rooms import Phase, Room, RoomError, RoomRegistry, RoomSettings  # noqa: E402


class RoomSettingsTests(unittest.TestCase):
    def test_valid_player_counts_accepted(self):
        for n in (3, 5, 7, 9):
            RoomSettings(player_count=n)  # should not raise

    def test_even_player_count_rejected(self):
        for n in (2, 4, 6, 8):
            with self.assertRaises(RoomError):
                RoomSettings(player_count=n)

    def test_invalid_tone_mode_rejected(self):
        with self.assertRaises(RoomError):
            RoomSettings(tone_mode="silly")


class RoomLobbyTests(unittest.TestCase):
    def setUp(self):
        self.room = Room("TEST", RoomSettings(player_count=3))

    def test_add_players_up_to_capacity(self):
        self.room.add_player("Alex")
        self.room.add_player("Bao")
        self.room.add_player("Casey")
        self.assertTrue(self.room.is_full())

    def test_add_player_beyond_capacity_rejected(self):
        for name in ("Alex", "Bao", "Casey"):
            self.room.add_player(name)
        with self.assertRaises(RoomError):
            self.room.add_player("Dana")

    def test_remove_player_frees_a_slot(self):
        p1 = self.room.add_player("Alex")
        self.room.add_player("Bao")
        self.room.add_player("Casey")
        self.room.remove_player(p1.id)
        self.room.add_player("Dana")  # should not raise
        self.assertEqual(len(self.room.players), 3)

    def test_cannot_join_after_lobby(self):
        self.room.add_player("Alex")
        self.room.add_player("Bao")
        self.room.add_player("Casey")
        self.room.advance_phase()
        with self.assertRaises(RoomError):
            self.room.add_player("Late")


class PhaseAdvanceTests(unittest.TestCase):
    def setUp(self):
        self.room = Room("TEST", RoomSettings(player_count=3))
        for name in ("Alex", "Bao", "Casey"):
            self.room.add_player(name)

    def test_sequential_advance_order(self):
        expected = [Phase.CLAUSE_PITCH, Phase.BRIEF, Phase.WHIP, Phase.NEGOTIATION,
                    Phase.AMENDMENT, Phase.DIVISION, Phase.RESULTS]
        for phase in expected:
            self.assertEqual(self.room.advance_phase(), phase)

    def test_cannot_advance_past_results(self):
        for _ in range(7):
            self.room.advance_phase()
        with self.assertRaises(RoomError):
            self.room.advance_phase()

    def test_cannot_leave_lobby_with_even_roster(self):
        # player_count is set to 5, but only 2 have joined (e.g. absences) —
        # advancing must fail because the actual roster is even, regardless
        # of the target setting.
        room = Room("EVEN", RoomSettings(player_count=5))
        room.add_player("Alex")
        room.add_player("Bao")
        self.assertEqual(len(room.players), 2)
        with self.assertRaises(RoomError):
            room.advance_phase()

    def test_goto_phase_allows_teacher_to_jump(self):
        self.room.advance_phase()  # -> CLAUSE_PITCH
        self.room.goto_phase(Phase.AMENDMENT)
        self.assertEqual(self.room.phase, Phase.AMENDMENT)

    def test_goto_phase_rejects_non_phase(self):
        with self.assertRaises(RoomError):
            self.room.goto_phase("not-a-phase")


class CountryAssignmentTests(unittest.TestCase):
    def setUp(self):
        self.room = Room("TEST", RoomSettings(player_count=3))
        self.ids = [self.room.add_player(n).id for n in ("Alex", "Bao", "Casey")]

    def test_assign_countries_requires_full_roster_coverage(self):
        with self.assertRaises(RoomError):
            self.room.assign_countries({self.ids[0]: "Fiji"})

    def test_assign_countries_rejects_duplicates(self):
        with self.assertRaises(RoomError):
            self.room.assign_countries({i: "Fiji" for i in self.ids})

    def test_assign_countries_success(self):
        mapping = dict(zip(self.ids, ["Fiji", "Chile", "Kenya"]))
        self.room.assign_countries(mapping)
        for pid, country in mapping.items():
            self.assertEqual(self.room.players[pid].country, country)

    def test_random_assign_countries_covers_everyone_uniquely(self):
        self.room.random_assign_countries(["Fiji", "Chile", "Kenya", "Japan", "Egypt"])
        assigned = {p.country for p in self.room.players.values()}
        self.assertEqual(len(assigned), 3)

    def test_random_assign_countries_insufficient_pool(self):
        with self.assertRaises(RoomError):
            self.room.random_assign_countries(["Fiji", "Chile"])


class SettingsAndEventLogTests(unittest.TestCase):
    def setUp(self):
        self.room = Room("TEST", RoomSettings(player_count=3))
        for name in ("Alex", "Bao", "Casey"):
            self.room.add_player(name)

    def test_update_settings_in_lobby(self):
        self.room.update_settings(whip_count_enabled=False, tone_mode="junior")
        self.assertFalse(self.room.settings.whip_count_enabled)
        self.assertEqual(self.room.settings.tone_mode, "junior")

    def test_update_settings_allowed_during_clause_pitch(self):
        # Needed so the teacher's client can lock in the clauseId resolved
        # from the open pitch/second (11a) before advancing to BRIEF.
        self.room.advance_phase()  # -> CLAUSE_PITCH
        self.room.update_settings(clause_id="2.6")
        self.assertEqual(self.room.settings.clause_id, "2.6")

    def test_update_settings_rejected_outside_lobby_and_clause_pitch(self):
        self.room.advance_phase()  # -> CLAUSE_PITCH
        self.room.advance_phase()  # -> BRIEF
        with self.assertRaises(RoomError):
            self.room.update_settings(whip_count_enabled=False)

    def test_event_log_ordering_and_since(self):
        pid = next(iter(self.room.players))
        e1 = self.room.log_event(pid, "negotiation_message", {"text": "hello"})
        e2 = self.room.log_event(pid, "vote", {"choice": 1})
        self.assertEqual([e.seq for e in self.room.events_since(0)], [e1.seq, e2.seq])
        self.assertEqual(self.room.events_since(e1.seq), [e2])

    def test_event_log_entries_tagged_with_round_number(self):
        # A rejoining player must be able to tell which round a replayed
        # event belongs to, so stale rounds' votes/messages/amendments
        # don't leak into the current round's scoring.
        pid = next(iter(self.room.players))
        self.room.advance_phase()  # leave lobby; new_round() has no further phase precondition
        e1 = self.room.log_event(pid, "vote", {"choice": 1})
        self.assertEqual(e1.round_number, 1)
        self.assertEqual(e1.to_dict()["roundNumber"], 1)
        self.room.new_round()
        e2 = self.room.log_event(pid, "vote", {"choice": -1})
        self.assertEqual(e2.round_number, 2)
        self.assertEqual(e1.round_number, 1)  # earlier entry's tag is untouched

    def test_new_round_goes_to_clause_pitch_not_brief(self):
        # A fresh round means a fresh open pitch for the next clause (11a),
        # not a re-run of the previous round's clause.
        self.room.advance_phase()  # -> CLAUSE_PITCH
        self.room.update_settings(clause_id="2.6")
        self.room.advance_phase()  # -> BRIEF
        self.room.new_round()
        self.assertEqual(self.room.phase, Phase.CLAUSE_PITCH)
        self.assertIsNone(self.room.settings.clause_id)


class RoomRegistryTests(unittest.TestCase):
    def test_create_and_get_room(self):
        registry = RoomRegistry()
        room = registry.create_room(RoomSettings(player_count=5))
        self.assertIs(registry.get(room.code), room)

    def test_room_codes_are_unique(self):
        registry = RoomRegistry()
        codes = {registry.create_room().code for _ in range(50)}
        self.assertEqual(len(codes), 50)

    def test_get_is_case_insensitive(self):
        registry = RoomRegistry()
        room = registry.create_room()
        self.assertIs(registry.get(room.code.lower()), room)

    def test_drop_room(self):
        registry = RoomRegistry()
        room = registry.create_room()
        registry.drop(room.code)
        self.assertIsNone(registry.get(room.code))


class EventVisibilityTests(unittest.TestCase):
    def setUp(self):
        self.room = Room("TEST", RoomSettings(player_count=3))
        self.p1 = self.room.add_player("Alex").id
        self.p2 = self.room.add_player("Bao").id
        self.p3 = self.room.add_player("Casey").id

    def test_public_event_visible_to_every_player_and_teacher(self):
        self.room.log_event(self.p1, "vote", {"choice": 1})
        for viewer in (self.p1, self.p2, self.p3, None):
            self.assertEqual(len(self.room.events_since(0, viewer_player_id=viewer)), 1)

    def test_private_event_visible_only_to_its_parties_and_teacher(self):
        self.room.log_event(self.p1, "channel_message", {"to": "Bao"}, visible_to={self.p1, self.p2})
        self.assertEqual(len(self.room.events_since(0, viewer_player_id=self.p1)), 1)
        self.assertEqual(len(self.room.events_since(0, viewer_player_id=self.p2)), 1)
        self.assertEqual(len(self.room.events_since(0, viewer_player_id=self.p3)), 0)
        self.assertEqual(len(self.room.events_since(0, viewer_player_id=None)), 1)  # teacher

    def test_mixed_public_and_private_events_filtered_independently(self):
        self.room.log_event(self.p1, "channel_message", {"to": "Bao"}, visible_to={self.p1, self.p2})
        self.room.log_event(self.p3, "vote", {"choice": 0})
        casey_view = self.room.events_since(0, viewer_player_id=self.p3)
        self.assertEqual([e.kind for e in casey_view], ["vote"])
        teacher_view = self.room.events_since(0, viewer_player_id=None)
        self.assertEqual([e.kind for e in teacher_view], ["channel_message", "vote"])


if __name__ == "__main__":
    unittest.main()
