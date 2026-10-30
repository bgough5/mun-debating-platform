# Staff guide

For teachers helping with debating and Model UN. You don't need to know anything about the software to use this.

## Before class (the coordinator does this once)

1. On the coordinator's laptop, double-click `start_platform.bat`. A black window opens and prints two web addresses. Leave it open the whole session; closing it stops the platform.
2. Students use the address that ends in `/join`, for example `http://10.1.2.3:8080/join`, or the personal address on their sign-in card.
3. Staff open the same address without `/join`, then **Sign in**, choose their name and type their passphrase. The coordinator sets staff passphrases under **People → Staff**.

The laptop and every student laptop must be on the same school Wi-Fi. If students can't reach the address, see "If something goes wrong".

## Starting an activity

On the Dashboard, choose **Start an activity**:

1. **What you're running:** UNAA or Evatt Model UN, a class debate, public speaking, or your own format.
2. **Who's taking part today:** tick them, or use **Tick all** for a year level. **Find a student** searches by name and **Show** narrows the list to one year level; anyone already ticked stays ticked. Students stay on the list once entered. For first-timers, open **First time here?**, type one per line with their year level after the name (for example "Sam L, 9") and press **Add and tick them**.
3. **Difficulty:** junior, middle or senior, or let it suggest one from the year levels of the students ticked. It sets speech times and which motions and impromptu topics come up.
4. Press **Start**.

Any number of students works:
- **Model UN** shares the countries out. Countries without a student are voted by the engine.
- **Debates:** more than eight students are split into several debates on the same motion.
- **Public speaking** takes everyone ticked.

Everything is saved as you go. Next time, find it on the Dashboard under **In progress**:
- **Resume** asks who's here today. Last time's students are ticked: untick anyone away and tick anyone joining, then press **Continue**.
  - **Speaking round:** anyone who has spoken keeps their place. Students who are away leave the rest of the order, and new students go on the end.
  - **Debate:** an away student's slot is freed for someone new.
  - **Model UN:** newcomers get a country. Students who are away need nothing.
- **Open** goes straight in with nothing changed.

Year levels are set or changed under **People → Students**.

**Saved groups** (People → Groups): name the students you often run together, for example "Debating Jr BGO", and tick them. A student can be in several groups.
- On **Start an activity** or **Who's here today?**, press **Tick Debating Jr BGO** to tick the whole group, then untick anyone who's away.
- You can also tick students and use **Save the ticked students as a group**.
- Anyone can use a group; only the person who made it, or the coordinator, can change it.

**Teacher access** (People → Teacher access) decides which students each teacher sees. You only need it when a teacher should see some students and not others.

## Students signing in

1. Print **sign-in cards** from **People → Students** (all students, or one year level): one card per student, with their own address and a six-character code. The code already knows the student's name; there is no list of names to pick from.
2. A student opens the address on their card, or goes to `/join` and types their code. They're in, as themselves, on any school laptop. Signing in on another laptop signs them out of the first one.
3. A student who's away simply doesn't sign in. Nothing waits for them: in a vote, the engine casts their country's vote, labelled computed, and if they arrive in time their own vote replaces it.
4. Lost card, or a code seen by someone else? On the class page, **Show** reveals a student's code; **Manage → New code** gives them a new one and stops the old one.

At most 25 students can be in one live session. Everything also works with fewer, down to one.

## Model UN

**Set up (coordinator or class teacher):** MUN → conference → committee. Add delegations (countries) and **Allocate** students to them. Countries without a student are still voted, by the prediction engine, and labelled "computed".

**Several students on one country** is fine, in any numbers (one on France, four on Australia):
- Each of them has every tab.
- Everything they do is signed with their name and country, for example "Ben G, Australia": messages, points, motions, the speakers list, amendments and signatures.
- They can read each other's speech drafts but not change them.
- A country still has **one vote**: any of its students can cast or change it, and everyone sees who cast it.

**Resolution workspace:** each paragraph has one editor at a time. Choose **Edit** to take a paragraph; others see who is editing. Anyone else proposes a change as an **amendment**, which the class supports or the chair puts to a vote. **History** shows every version and can restore one. **Undo** (top of the page) undoes your last action.

**Whip count and prediction:** the committee's **Evidence** page records what each country has said, with its source. **Prediction** shows the chance the resolution passes, the countries most likely to swing it, and **Create lobbying tasks** to turn the swing list into lobbying tasks. Predictions are estimates: the page shows how uncertain each country is, and "unknown" where there's no evidence.

**Running a live session (chair):** Chair → **Open a session** for the committee. The chair console has:
- **Speakers list:** add delegations, **Next speaker**, **Yield**. Students can add themselves from their own screen.
- **Timers:** start, pause, extend. A student who needs more time can be given an adjustment (WCAG 2.2.1); it applies only to them.
- **Motions:** record a motion, a second, then pass it "with no objection" or put it to a vote.
- **Votes (divisions):** open a vote on a paragraph, amendment or the whole resolution. Students vote on their own devices; computed countries vote automatically. Close the vote to see the result under the committee's voting rules (Security Council vetoes included).
- **Projector:** the "Projector" link opens a view for the big screen with the speakers list, timer and results only.
- **Minutes:** generated from what happened; edit, print or download as Word.

**The committee flow (D-068).** A session has six stages: roll call, agenda, opening statements, **the floor**, voting procedure and debrief. The guide at the top of the chair console shows what to say at each one. The debate happens out loud; the platform records it and puts it on every screen.
- **Before the lesson:** students open **Prepare** from their page: their country brief (with evidence badges), the proposed resolution, and a pad for their opening statement in their own words.
- **On the floor:** ask "Are there any points or motions on the floor?" Take motions most disruptive first. An unmoderated caucus is at most 10 minutes a motion; students move to extend it when it ends. With no motion, the general speakers list continues.
- **Points:** students raise their placard and can also log the point on their device. Waiting points appear at the top of the floor panel: **Answered**, **Decline**, or for a right of reply **Grant** (they go to the top of the list).
- **Amendments:** students draft privately, then submit. Everyone sees submitted amendments on the **Amendment board** as tracked changes, can sign them and suggest edits; the sponsors accept or decline suggestions. When an amendment has its signatories (a fifth of the delegations with students, at least two), **Bring to the floor**: the speakers list switches to speakers for and against it. Then **Vote on the amendment**; if it passes, the clause changes on every screen. **Accept as friendly** adds it with no vote.
- **Close debate** (two-thirds; nine in the Security Council) moves the committee into voting procedure. Vote on the resolution; if a delegation moves for a roll-call vote, the guide shows the order (drawn by lot). If the resolution fails and another draft is ready, **Reopen the floor with it**.
- **Messages:** students can message other delegations from the Messages tab. They are not marked, and students are told that you can read them: **Delegate messages** (under Tools) shows every message, and **Hide** removes one from both students' screens. No messages in voting procedure.
- **Friends and foes and speech drafts** belong to each student and are private. Erasing a student deletes them.
- **Security Council:** the vote panel and the projector warn as soon as a permanent member votes no ("Veto").

If the chair's laptop or browser crashes, open the chair console again: everything is as it was. Students' screens catch up by themselves.

## Debating and public speaking

The Debating page leads with two classroom tools and the students' preparation. Tournaments and carnivals are lower down.

**Class debate:** Debating → **New class debate**. Choose the class (optional: it suggests names and lets each student see their own scores), pick or type a motion, and type each team's speakers (first names only; **Fill empty places from the class list at random** does it for you). Set the speakers per team, the speech length, the warning bell, preparation time and reply speeches. **Set it up.**

**Speaking round:** Debating → **New speaking round**. One first name per line (**The whole class in random order** fills it). Choose **Prepared** (students bring a speech; add a topic after a dash if you like) or **Impromptu** (each speaker gets a surprise topic when their turn starts, with thinking time first).

**Running it:** open **the projector view** on the screen the class sees, and keep your own page in front of you. **Space** starts or pauses the timer, **→** moves to the next speaker, **←** goes back; a presentation clicker works too. The timer shows the bells: green while speaking, amber after the warning bell (one ring), red at time (two rings), and it keeps counting past time. The bell sounds on your laptop; switch it off under the controls. Each speaker's time is recorded when you move on. If the laptop restarts, open the page again: the run is where you left it.

**Scores and results:** score each speaker (matter, manner, method for debates; the speech rubric for speeches), add a comment, pick the winner. Students whose typed name matched the class list see their own time, scores and comment under **Prep and practise**; nobody sees anyone else's. Names that didn't match the class list stay on that run only and are replaced with "Speaker 1", "Speaker 2" after a year.

**Student preparation:** Debating → **Student preparation** → choose a class. Each student's debate cases (arguments and rebuttals), speech drafts and practice speeches. Open a case to score each argument and rebuttal on its rubric and leave a comment. The "structure check" the students see only counts which parts they've written; quality is your score.

**What students can do on their own** (their **Prep and practise** page):
- **Debate case:** pick a motion and a side; write a team line, a definition, and arguments in four parts (claim, reasoning, example, impact).
- **Rebuttal:** for every motion in the bank, the other side's three likely arguments are listed; students rebut each in four steps (they say, but, because, so), and add arguments they expect. The listed arguments are starting points written for the platform, labelled as not evidence; edit them under Admin → Likely arguments for each motion.
- **Speeches:** four prepared-speech structures (persuasive, informative, personal story, tribute) with a prompt for each part, a live word count and speaking-time estimate, a rehearsal view and printable cue cards.
- **Practise a speech:** impromptu (a topic from the bank, thinking time on a structure card, then the speech), prepared (rehearse their own speech) or a rebuttal drill (answer one likely argument in a minute). Bells ring as in class. They score themselves and save it; you can comment under **Practice speeches**.

Topics, templates and likely arguments are all editable under Admin (Debating group).

## Tournaments and carnivals

**Events:** Debating → **New event** (class debates, a house carnival or a competition). In **Setup**, add teams (or **Make teams** from a class), rooms and adjudicators.

**Rounds:** **Generate the draw**. Round 1 is a random draw; later rounds are power-paired (teams on the same wins meet). The draw never repeats a pairing or puts two teams from the same house together where it can avoid it, and balances affirmative and negative. Anything it couldn't avoid is shown on the draw. You can swap teams by hand.

**Ballots:** each adjudicator opens their debate's ballot and scores every speaker (matter, manner, method). The winner must be the team with more points; if the totals are level, choose the winner. A panel decides by majority; a 1–1 split goes to the chair adjudicator.

**Results:** the ladder and speaker tab update as ballots come in. Students see only their own scores and feedback.

**House points:** **Award house points for this round** (or for all rounds, or final placings) adds points from the house points rules (Admin → House points rules; set these to the school's real rules). Every entry shows who added it and why. To fix a mistake, **Reverse** the entry; nothing is ever deleted. A corrected ballot moves the win points on the next award.

**Run sheets and MC scripts:** Documents → choose one; edit, print or download as Word.

**Practice in class (any number of students):** Debating → **Practice**. Tick who's here and the platform splits them into debates: 1 student gets solo speech practice with a timer, 2 debate one-on-one, 3 adds a student adjudicator, and bigger groups get full rooms with student adjudicators so no one sits out.

## Speeches, cue cards and debate teams (students)

Under **Prep and practise**, students can:
- **Write a speech:** with a structure, or "Write it your way" (one box: paste or type the whole speech).
- **Write out their speech for a debate,** at the bottom of their debate case.
- **Make cue cards** from either: **dot points** (their own sentences shortened, never new words) or the **full speech**. They can edit any card, then print four to an A4 landscape page with cut lines and card numbers, in normal or large text.

Their writing saves itself every 30 seconds and when they leave the page. The page opens with "Carry on where you left off", so next club or next class they pick up straight away.

**Debate teams:** students on the same side of a class debate see each other's arguments and speeches (read-only), with a flag on arguments that look alike, so they can split the points before the debate. The other side can't see them.

## Students' own pages

Students see **Me**: their delegation, tasks, live session, debates and their pathway milestones; **Prep and practise** holds their debate cases, speeches, practice and their scores from class debates and speaking rounds. Teachers record milestones under **People → student**.

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
- **A student's code doesn't work:** check it on the class page (**Show**). If it was seen by someone else or the card is lost, **Manage → New code** issues a new one and stops the old one. Too many wrong tries locks that laptop out for 30 seconds.
- **Something looks wrong in a vote or score:** don't delete anything. Tell the coordinator, who can see exactly who changed what (Admin → Change log) and undo it.

## Privacy, in short

Students are minors. Use first names only. Don't type anything into the platform you wouldn't put on a class noticeboard. AI features are off unless the school approves them. See the Privacy page in the platform and `docs/privacy-summary.md`.
