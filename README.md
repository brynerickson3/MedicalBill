# Medical Bill Negotiation Game (oTree)

An online negotiation task for studying whether socioeconomic status (SES) affects how people negotiate a medical bill, and whether that depends on who is on the other side: a **named case manager (Jake Taylor)** or an **anonymous billing department**. It is built in [oTree](https://www.otree.org) and set up to run through Prolific.

## What participants see (~15 min)
Consent → Instructions & bonus rule → Scenario and itemized $5,200 ER bill → Comprehension check (one retry, then screened out with pay) → Counterpart intro → **Negotiation** (named: an incoming phone call from an illustrated Jake, then a live call view with speech bubbles; anonymous: text notices from the Billing Department) → Outcome → Manipulation and belief checks → Backlash and nervousness → Power, plus an embedded attention check → SES (education, parental education, income, household size, MacArthur ladder) → Work, insurance, financial literacy → Demographics and TIPI → Debrief with a withdrawal option → Redirect to Prolific.

## Negotiation rules (identical in both conditions, never shown to participants)
- The hospital opens at the full bill ($5,200). Each round the participant accepts the offer or makes a lower whole-dollar counteroffer.
- Next hospital offer = current − 40% × (current − counteroffer), rounded to the dollar, with a floor of 55% of the bill ($2,860).
- The 4th hospital offer is final: accept, or decline and pay the full bill.
- Bonus = 2¢ per percentage point saved, capped at $1.50. No agreement means no bonus.

All of these settings live in `settings.py` (`STUDY_DEFAULTS`). The counterpart's wording is in `medical_bill/script.py`.

## Playable preview
`preview/index.html` is a single-page version of the negotiation (same rules and wording, both conditions, no data saved). Open it in any browser to try the game without running oTree. If you change the wording in `medical_bill/script.py`, update the preview as well.

## Run locally
```bash
pip install -r requirements.txt
otree devserver          # then open http://localhost:8000
otree test medical_bill  # bot tests that replay the bonus-table strategies
```
Use the **Preview: named** and **Preview: anonymous** sessions to see each condition.

## Prolific
1. Deploy (for example on oTree Hub or Heroku), then set `OTREE_PRODUCTION=1`, `OTREE_ADMIN_PASSWORD` and `OTREE_SECRET_KEY`.
2. Create a `medical_bill` session in the `prolific` room, with more participant slots than you plan to recruit.
3. Study URL on Prolific: `https://YOUR-APP/room/prolific/?participant_label={{%PROLIFIC_PID%}}`
4. Set `prolific_completion_code` and `prolific_screened_out_code` in `settings.py` to the codes Prolific gives you.

## Data
- **All apps — wide format:** one row per participant. Includes condition, `offer_1..`, `counter_1..`, response times `rt_1..`, `countered`, `first_counter`, `first_counter_pct_off`, `rounds_to_agreement`, `final_amount`, `total_concession`, `pct_saved`, `bonus`, and every survey item.
- **medical_bill (custom):** the full chat transcript, one row per message with timestamps.
- **custom_export_prolific_bonus:** `PID,amount`, ready for Prolific's bulk bonus upload.

Reverse-scored items: `nerv_comfortable`, `nerv_relaxed`, `pw_hospital_power`, `tipi_reserved`, `tipi_critical`. Income codes 1–7 are brackets (99 = prefer not to say); parental education 99 = don't know. Exclude anyone with `withdraw_data = 1`.

## Still to do before launch
- Replace the placeholder consent and debrief text with the IRB-approved versions.
- Confirm the bonus rate: the design doc says 3¢ in one place and 2¢ elsewhere. The app uses 2¢, which matches the bonus table.
- The two opening messages come from the design doc and differ in warmth ("Hello! This is Jake…" vs "Your balance due is…"). Consider making them parallel so voice is the only difference.
