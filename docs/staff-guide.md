# Staff guide

For teachers helping with debating and Model UN. You don't need to know anything about the software to use this.

## Before class (the coordinator does this once)

1. On the coordinator's laptop, double-click `start_platform.bat`. A black window opens and prints two web addresses. Leave it open the whole session; closing it stops the platform.
2. Students use the address that ends in `/join`, for example `http://10.1.2.3:8080/join`. Write it on the board.
3. Staff open the same address without `/join`, then **Sign in**, choose their name and type their passphrase. The coordinator sets staff passphrases under **People → Staff**.

The laptop and every student device must be on the same school Wi-Fi. If students can't reach the address, see "If something goes wrong".

## Students joining

1. A student opens the `/join` address, types the class code (shown on the class page under **People**) and taps their name.
2. Their name is now locked to that device. If a student changes device, or someone took their name by mistake, go to **People → your class → Manage** next to their name, and choose **Release name**. If a second device tries the name, a request appears on the class page for you to approve or deny.
3. If the code gets shared outside the class, choose **New class code** on the class page. Students already signed in stay signed in.

At most 25 students can be in one live session. Everything also works with fewer, down to one.

## Model UN

**Set up (coordinator or class teacher):** MUN → conference → committee. Add delegations (countries) and **Allocate** students to them. Countries without a student are still voted, by the prediction engine, and labelled "computed".

**Resolution workspace:** each paragraph has one editor at a time. Choose **Edit** to take a paragraph; others see who is editing. Anyone else proposes a change as an **amendment**, which the class supports or the chair puts to a vote. **History** shows every version and can restore one. **Undo** (top of the page) undoes your last action.

**Whip count and prediction:** the committee's **Evidence** page records what each country has said, with its source. **Prediction** shows the chance the resolution passes, the countries most likely to swing it, and **Create lobbying tasks** to turn the swing list into lobbying tasks. Predictions are estimates: the page shows how uncertain each country is, and "unknown" where there's no evidence.

**Running a live session (chair):** Chair → **Open a session** for the committee. The chair console has:
- **Speakers list:** add delegations, **Next speaker**, **Yield**. Students can add themselves from their own screen.
- **Timers:** start, pause, extend. A student who needs more time can be given an adjustment (WCAG 2.2.1); it applies only to them.
- **Motions:** record a motion, a second, then pass it "with no objection" or put it to a vote.
- **Votes (divisions):** open a vote on a paragraph, amendment or the whole resolution. Students vote on their own devices; computed countries vote automatically. Close the vote to see the result under the committee's voting rules (Security Council vetoes included).
- **Projector:** the "Projector" link opens a view for the big screen with the speakers list, timer and results only.
- **Minutes:** generated from what happened; edit, print or download as Word.

If the chair's laptop or browser crashes, open the chair console again: everything is as it was. Students' screens catch up by themselves.

## Debating

**Events:** Debating → **New event** (class debates, a house carnival or a competition). In **Setup**, add teams (or **Make teams** from a class), rooms and adjudicators.

**Rounds:** **Generate the draw**. Round 1 is a random draw; later rounds are power-paired (teams on the same wins meet). The draw never repeats a pairing or puts two teams from the same house together where it can avoid it, and balances affirmative and negative. Anything it couldn't avoid is shown on the draw. You can swap teams by hand.

**Ballots:** each adjudicator opens their debate's ballot and scores every speaker (matter, manner, method). The winner must be the team with more points; if the totals are level, choose the winner. A panel decides by majority; a 1–1 split goes to the chair adjudicator.

**Results:** the ladder and speaker tab update as ballots come in. Students see only their own scores and feedback.

**House points:** **Award house points for this round** (or for all rounds, or final placings) adds points from the house points rules (Admin → House points rules; set these to the school's real rules). Every entry shows who added it and why. To fix a mistake, **Reverse** the entry; nothing is ever deleted. A corrected ballot moves the win points on the next award.

**Run sheets and MC scripts:** Documents → choose one; edit, print or download as Word.

**Practice in class (any number of students):** Debating → **Practice**. Tick who's here and the platform splits them into debates: 1 student gets solo speech practice with a timer, 2 debate one-on-one, 3 adds a student adjudicator, and bigger groups get full rooms with student adjudicators so no one sits out.

## Students' own pages

Students see **Me**: their delegation, tasks, live session, debates, practice speeches (with a timer and rubric self-review) and their pathway milestones. Teachers record milestones under **People → student**.

## Fixing mistakes

- **Undo** undoes your last action (or a whole group of changes made at once).
- **History** on a paragraph or any admin table restores an earlier version.
- Deleted things can be restored for 30 days (Admin → the table → "Show deleted").
- House points and ballots are corrected by reversing or re-entering, never by deleting.

## Demo mode

The coordinator can switch to the **demo** dataset (Admin → Data). It holds fake students and a ready-made conference and debating event, for training and trying things out. A banner shows when demo data is on. Nothing in demo mode touches the real data.

## If something goes wrong

- **Students can't reach the address:** check the laptop and the device are on the same Wi-Fi, and that Windows allowed the app through the firewall when first asked (if not, the coordinator allows "Python" in Windows Defender Firewall). Some school networks block devices from reaching each other; ask ICT.
- **A page says "reload":** the coordinator switched or restored the data. Reload the page.
- **The black window closed:** double-click `start_platform.bat` again. Nothing is lost: every change is saved as it is made.
- **A student is stuck on "waiting for a teacher":** approve their request on the class page, or release their name.
- **Something looks wrong in a vote or score:** don't delete anything. Tell the coordinator, who can see exactly who changed what (Admin → Change log) and undo it.

## Privacy, in short

Students are minors. Use first names only. Don't type anything into the platform you wouldn't put on a class noticeboard. AI features are off unless the school approves them. See the Privacy page in the platform and `docs/privacy-summary.md`.
