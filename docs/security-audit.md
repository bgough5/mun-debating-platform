# Security audit and fixes: 29 October 2026

**Scope:** the platform in `app/`, run on Ben's laptop (Windows 10) with **fake demo data only**. The frozen v2 game in `shared/`, `server/` and `client/` is out of scope.
**Outcome:** five issues found; all five fixed and covered by tests in `tests/security/test_hardening.py`.
- Four were real weaknesses (S-1, S-2, S-4, S-5).
- One (S-3) turned out not to be exploitable and was tightened anyway.
- None was being exploited, and none exposed student data across classes.

Decision record: D-083.

## 1. How the issues were found

The stress test had three parts:
1. **A harness.** It signed in as several demo students: two in the same committee on different delegations, and one in a different class. Each submitted every form they could reach with a unique marker in every text box; each marker also contained page code.
2. **Leak and injection checks.** As one student, the harness then requested every page a student can open, with every likely ID number in the address. It looked for (a) another student's marker where it shouldn't be, and (b) a marker that came back as live page code instead of text.
3. **A code review** of every place the app turns off escaping, builds a database query from text, redirects to an address it was given, writes a CSV file, or throttles sign-in attempts.

Each suspected issue was then written as an automated test of the **secure** behaviour and run against the unfixed code. A finding is only listed as real if its test failed there.

| Finding | Test on the old code | Test after the fix |
|---|---|---|
| S-1 | Failed | Passes |
| S-2 | Failed | Passes |
| S-3 | Failed (see the note under S-3) | Passes |
| S-4 | Failed | Passes |
| S-5 | Failed | Passes |

**Two corrections to my first report**, kept here so the record is honest:
- **The first pass reported live script injection on 11 pages. That was my mistake.** The project's own test client un-escapes every page so tests can search for plain words, and it turned the app's correctly escaped `&lt;svg…` back into `<svg…`. Re-checked on the raw bytes the server sends: **0 of 616 pages** contained live injected code.
- **S-3 was reported as an open redirect; it is not exploitable.** See S-3 below.

## 2. What held up

Rows marked *(code review)* were checked by reading the code, not by a test.

| Area | Result |
|---|---|
| Script injection through anything students or staff type | **None.** Every page escapes user text (616 pages checked as a student and as the coordinator). |
| Database injection | **None found.** Every value is passed as a parameter. Table and column names come from the code's own lists, never from a request. |
| Students reading other students' private work | **None.** Speech drafts, friends-and-foes sheets, prep cases, practice and AI-practice stayed private. A classmate's text appeared only in shared committee documents (resolution, amendments, class evidence), which is by design. Nothing from the other class's student appeared at all. |
| Students reaching staff pages | Covered by the existing permissions test (`tests/api/test_permissions_matrix.py`, passing), which checks every route against its required role. It was not re-tested independently in this audit. |
| Debate ballots *(code review)* | Scores outside the rubric's range, including "nan" and "inf", are refused. A student can only enter a ballot for a debate they adjudicate. |
| Amendments, tasks and undo *(code review)* | Students can only withdraw their own amendment, only edit their own delegation's tasks, and only undo their own change. |
| Sign-in cookie | It can't be read by page scripts, and it isn't sent on requests started by other websites. |
| Headers | Other sites can't frame the app, browsers don't guess file types, and "came from" information stays on this site. |

## 3. The five findings

| ID | Finding | Severity | Status |
|---|---|---|---|
| S-1 | CSV exports could carry spreadsheet formulas | Medium | Fixed |
| S-2 | Anyone could lock the coordinator out of signing in | Medium | Fixed |
| S-3 | Redirect targets were checked inconsistently | Low (not exploitable) | Hardened |
| S-4 | Evidence could be deleted by the wrong person | Medium | Fixed |
| S-5 | Flag graphics were shown without any checking | Low (defence in depth) | Fixed |

### S-1: CSV exports could carry spreadsheet formulas (Medium, fixed)

- **Issue:** exports wrote text exactly as typed. A cell starting with `=`, `+`, `-` or `@` is run as a formula by Excel and Google Sheets when the file is opened. Students type text that reaches exports, such as evidence summaries.
- **What could happen:** a student plants a formula that runs on the teacher's computer when they open the export. Modern Excel warns before running some kinds, but not all.
- **Confirmed:** a student's evidence summary `=1+1` appeared unchanged in `/admin/csv/evidence.csv`.
- **Fix:** every exported text cell that starts like a formula gets a leading apostrophe, which spreadsheets display as plain text. Numbers are untouched. When a CSV is imported, the apostrophe is removed again, so exporting and re-importing a file doesn't change it. Code: `app/web/safety.py` (`csv_safe`, `csv_unguard`) and `app/exports.py`.
- **Tests:** `test_csv_cells_that_start_like_formulas_are_neutralised`, `test_student_text_reaches_exports_neutralised`.

### S-2: anyone could lock the coordinator out of signing in (Medium, fixed)

- **Issue:** wrong passphrases were counted per account only. Because the coordinator account is the same for everyone, five wrong guesses from **any** laptop locked the coordinator out on **every** laptop for a minute, and it could be repeated indefinitely.
- **What could happen:** a student repeatedly locks the teacher out mid-lesson.
- **Confirmed:** after five wrong tries from one laptop, the correct passphrase was refused on a different laptop.
- **Fix:** attempts are counted per account **and per laptop**. The laptop making wrong guesses is still limited to five a minute, but other laptops are unaffected. Code: `app/modules/core/routes.py`.
- **Remaining risk:** guessing spread across many laptops (about 25 a minute each, 5 at a time) is still possible in principle. Passphrases must be at least 10 characters, so a real four-word passphrase is far beyond reach. A weak 10-character one is not, so passphrases should be four random words.
- **Test:** `test_throttle_is_per_laptop_not_per_account`.

### S-3: redirect targets were checked inconsistently (Low, not exploitable, hardened)

- **Issue:** four different checks guarded where the app sends you after an action:
  - sign-in blocked `//other-site`, but did not mention a backslash;
  - two "back" links checked only for a leading `/`;
  - two undo buttons went back to whatever address the browser said it came from.
- **What testing showed:** the backslash form was not exploitable. The web framework percent-encodes a backslash when it builds a redirect, so `/\other-site` becomes `/%5Cother-site`, a page on this same site. The undo redirects can only be reached through a form request that carries the app's anti-forgery token, which another website can't supply.
- **Fix (consistency):** one strict check, `safe_path`, is used for every redirect taken from a form. A path must start with a single `/` and contain no backslash, control characters, scheme or host. A second check, `safe_back`, follows a "came from" address only if it is on this same site. Code: `app/web/safety.py`, the core and MUN routes, and admin undo. The floor module's own check (`_safe_next`) was already strict and is unchanged.
- **Tests:** `test_safe_path_rules`, `test_login_next_cannot_leave_the_site`, `test_back_links_and_referer_cannot_leave_the_site`.

### S-4: evidence could be deleted by the wrong person (Medium, fixed)

- **Issue:** removing a piece of evidence was allowed if either:
  - (a) your display name matched the name stored with it (e.g. "Alex L."), or
  - (b) you taught the committee named **in the submitted form**, not the committee the evidence belonged to.
- **What could happen:**
  - two students with the same display name could delete each other's evidence;
  - a teacher of one class could delete another class's evidence by naming their own committee in the form.
- **Confirmed:** both cases succeeded on the old code.
- **Fix:** the evidence itself decides.
  - **Its committee** comes from the paragraph, amendment or resolution it is about. Evidence about a tag or a whole topic has no committee.
  - **"Recorded it"** means the change log shows **this account** created it, not a matching name.
  - **Allowed:** the person who recorded it, a teacher of its committee, or the coordinator. The form is used only to choose which page to return to, and only if you can open that page.
  - **Code:** `app/modules/mun/routes.py` (`evidence_delete`).
- **Tests:** `test_same_display_name_does_not_make_you_the_owner`, `test_teacher_of_another_class_cannot_delete_by_naming_their_own_committee`.

### S-5: flag graphics were shown without any checking (Low, defence in depth, fixed)

- **Issue:** country flags are SVG markup stored in the database, editable under Admin → Countries and importable by CSV. They were inserted into every page, students' included, without escaping.
- **What could happen:** markup containing a script would run on every page that shows that flag. Only the coordinator can edit flags, so the realistic route is importing a country list from an untrusted file.
- **Confirmed:** the old code rendered a flag containing a script, and admin saved such a flag without complaint.
- **Fix:**
  - **When pages are drawn:** flag markup is parsed and rebuilt from an allowlist of plain SVG shapes and their geometry and colour attributes. Anything else (scripts, links, styles, event attributes, `javascript:` or `data:` values, comments, encoded characters) blanks that flag. The browser receives only what passed the check.
  - **When saving:** admin and CSV import refuse such markup with a plain-English message.
  - **Verified in a real browser:** all 31 seeded flags still render correctly.
  - **Code:** `app/web/safety.py` (`safe_svg`, `svg_is_safe`), `app/templates/_macros.html`, the admin table and admin saving.
- **Tests:** `test_unsafe_flag_markup_is_not_rendered`, `test_every_seeded_flag_still_renders`, `test_admin_refuses_to_save_unsafe_flag_markup`.

## 4. Not covered, and remaining risks

These are known limits, not findings. They're listed so nobody assumes they were tested.

- **Plain HTTP on the school network.** Traffic, including sign-in codes and staff passphrases, isn't encrypted between laptops. Anyone able to watch the Wi-Fi could read it. Fixing this means HTTPS, which is a hosting and network decision for the school (D-002).
- **Sign-in codes are bearer secrets** (D-079). Anyone who sees a student's card can sign in as them. Mitigations already in the app: **New code** stops the old one, and every action is in the change log under the account that did it.
- **No Content-Security-Policy header.** It would be a further layer against script injection. None was found, so it's a recommendation, not a fix.
- **The anti-forgery token isn't tied to the session.** It's the "double-submit" pattern, which together with the cookie setting that blocks cross-site use is adequate here. Tying it to the session would be stronger.
- **Not stress-tested independently in this audit:**
  - live-update channel permissions (covered by the existing tests);
  - load-based denial of service beyond the 90-minute soak;
  - staff in one class against another class's other pages;
  - the frozen v2 game.
- **The coordinator is fully trusted.** Admin can change anything; that's by design.
- **Limited cross-class coverage.** The other-class student could reach only a few forms, so cross-class coverage is thinner than within-class.

## 5. Recommendations

1. Before the pilot, make sure every staff passphrase is four random words (S-2).
2. Raise HTTPS with ICT if the platform is ever used beyond the classroom pilot.
3. Add a Content-Security-Policy as a later hardening step. The templates contain no inline scripts, which makes it straightforward. The inline `style` attributes and htmx's settings need checking first.
4. Re-run `tests/security` after any change to sign-in, exports, redirects, evidence or admin data. It runs in under 10 seconds.
