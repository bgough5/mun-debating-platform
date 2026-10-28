# Ben's walkthrough: first real use (demo data)

**Purpose.** The platform has passed hundreds of automated tests, but no person has used it. This walkthrough is the first real use. The goal is not to admire it: it's to find every place where you hesitate, get confused, or something looks or behaves wrong.

**Time:** about 2 hours. It splits into parts you can do on different days.
**Data:** demo only (fake students). A yellow "DEMO" banner shows on every page.
**Log:** `docs/walkthrough-log.csv`. Open it in Excel. Each step below has an ID, and the log sheet has a row for each one already.

## How to log

Log a row whenever **anything** makes you pause. Don't filter: a pause of a few seconds is still worth a row. For each row:

| Column | What to write |
|---|---|
| What happened | What you saw, in a few words |
| Severity | **Blocker:** couldn't continue, or something wrong would reach a student.<br>**Confusing:** worked, but you had to think, guess or retry.<br>**Cosmetic:** looks off, but nothing is wrong.<br>**Idea:** not a fault; something you'd want. |
| Expected | What you thought would happen, if it was different |
| Time | Roughly how long the step took, if it felt slow |

If a step goes fine, leave its row blank. You don't need to write "OK" everywhere.

Screenshots help: press Windows + Shift + S and paste into an email to yourself, or just note the step ID.

## 0. Set up (10 min)

| ID | Do | You should see |
|---|---|---|
| 0.1 | Double-click `start_platform.bat` in the project folder. | A black window prints two addresses. Leave it open. |
| 0.2 | In Edge, open `http://localhost:8080/` and sign in as coordinator. | The dashboard, with the DEMO banner. If it isn't demo, switch under Admin → Data. |
| 0.3 | Open an **InPrivate** Edge window (Ctrl + Shift + N) at `http://localhost:8080/join`. This is your "student laptop". | The student sign-in page. |
| 0.4 | Keep the two windows side by side. | |

(The one-click desktop launcher will replace steps 0.1 to 0.4 once it's built.)

## A. Classes and sign-in (15 min)

| ID | Do | You should see |
|---|---|---|
| A.1 | People → **Year 9 Model UN (demo)**. | The class list, with each student's code hidden. |
| A.2 | Open the **sign-in cards** and use print preview (Ctrl + P). | One card per student: name, code and address. Would you hand these out as they are? |
| A.3 | **Show** one student's code. In the student window, type it at `/join`. | You're in as that student, on their own page. |
| A.4 | Type a wrong code five times in a row. | A clear message each time, then a short wait. |
| A.5 | Staff window: **Manage → New code** for that student. Student window: reload. | The student is signed out; the old code no longer works. |
| A.6 | Sign the student in again with the new code. | |

## B. A Model UN lesson (45 min)

Use the **United Nations General Assembly (demo)** committee. Staff window = chair, student window = the student from part A.

| ID | Do | You should see |
|---|---|---|
| B.1 | Student: **Prepare**. | Country brief with evidence badges, the resolution, and an opening statement pad. Is the brief clear to a Year 9? |
| B.2 | Chair → **Open a session** for the committee. Open the **Projector** link in a third window. | Chair console with the six-stage guide; projector view. |
| B.3 | Run **roll call**. The student answers on their screen. | The roll fills in on the chair and projector screens. |
| B.4 | **Agenda**, then **opening statements**: add the student's country to the speakers list, start the timer, give that student extra time. | The timer runs on the projector. Extra time applies only to that student. |
| B.5 | **The floor**: the student raises a point and proposes a motion (unmoderated caucus, 5 min). Chair seconds and passes it. | The point appears on the chair console; the motion goes through. |
| B.6 | Student: draft an amendment to one operative paragraph, then submit it. | It appears on the Amendment board as tracked changes. |
| B.7 | Chair: sign it with other delegations if needed, **Bring to the floor**, **Vote on the amendment**. The student votes. | Computed countries vote automatically and are labelled. If it passes, the clause changes on every screen. |
| B.8 | **Close debate**, then into voting procedure. Start the **whip count**: the student predicts how named delegations will vote. | Predictions are locked when the vote opens. |
| B.9 | Vote on the whole resolution. Close the vote. | Result under GA rules. |
| B.10 | Open the **debrief** (chair and student). | Chair sees everyone. The student sees only their own whip accuracy and profile. |
| B.11 | **Minutes**: edit a line, then download as Word. Open it in Word. | A clean document with the College letterhead. |
| B.12 | MUN → committee → **Prediction** for a paragraph. | The chance it passes, the swing list, and "estimate only" badges. Would a student understand what "estimate only" means? |
| B.13 | **Create lobbying tasks** from the swing list. Check the student sees their task. | |
| B.14 | Repeat B.9 quickly in the **Security Council (demo)**, with a permanent member voting no. | A "Veto" warning on the vote panel and the projector. |

## C. Classroom debating (30 min)

| ID | Do | You should see |
|---|---|---|
| C.1 | Debating → **New class debate**. Pick the Year 8 Debating class, a motion, and **Fill empty places from the class list**. Set it up. | A run of show. |
| C.2 | Open the **projector view**. Use Space, → and ← to run two speeches. | Green, then amber with one bell, then red with two bells; the timer counts past time. |
| C.3 | Score each speaker, add a comment, choose the winner. | Results saved. |
| C.4 | Sign the student window in as one of those Year 8 students. | They see only their own scores and comment. |
| C.5 | Debating → **New speaking round** → Impromptu, the whole class in random order. Run one turn. | A surprise topic with thinking time, then the speech timer. |

## D. Students preparing on their own (15 min)

In the student window, on **Prep and practise**:

| ID | Do | You should see |
|---|---|---|
| D.1 | Start a **debate case**: a motion and a side, plus one argument in four parts. | The structure check updates as you write. |
| D.2 | **Rebuttal**: answer one of the three likely arguments. | Likely arguments are labelled as starting points, not evidence. |
| D.3 | **Speeches**: pick a template; check the word count and cue cards. | |
| D.4 | **Practise a speech**: an impromptu drill. Score yourself and save. | |
| D.5 | Staff window: Debating → **Student preparation**. Find that work and leave a comment. | The student sees the comment. |

## E. When things go wrong (10 min)

| ID | Do | You should see |
|---|---|---|
| E.1 | During a live session, close the black window. Wait 10 seconds, then start it again. | Both windows reconnect by themselves, and nothing is lost. |
| E.2 | Refresh the chair console mid-vote. | Everything is still there. |
| E.3 | Make a change, then press **Undo**. | The change is reversed, and the change log says who did what. |
| E.4 | Delete something from an Admin table, then restore it ("Show deleted"). | |

## F. Accessibility spot-checks (10 min)

| ID | Do | You should see |
|---|---|---|
| F.1 | Student window: do B.3 to B.7 with the **keyboard only** (Tab, Enter, Space). | Every control can be reached and you can always see where you are. |
| F.2 | Zoom the student window to 200% (Ctrl + +). | Nothing cut off; no sideways scrolling. |
| F.3 | Footer → **Easy-read text**. | Text gets more spacing. |
| F.4 | If NVDA is installed: listen to one live student page. | The timer and speakers list changes are announced, but not constantly. |

## When you're done

Save the log. Then tell me, or send it over: I'll sort every row by severity, fix the Blockers and Confusing ones that are quick, and bring the rest to you with a recommendation. Nothing new gets built until this list is worked through (D-082).
