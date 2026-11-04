from os import environ

# ---------------------------------------------------------------------------
# Study settings. Change values here (or per session on the admin
# "Create session" page) rather than in the game code.
# ---------------------------------------------------------------------------
STUDY_DEFAULTS = dict(
    # pay
    participation_fee=3.75,          # base pay shown in instructions ($15/hr x 15 min)
    real_world_currency_per_point=1.00,
    bonus_per_pct_point=0.02,        # $ per percentage point saved (2 cents)
    bonus_cap=1.50,                  # maximum bonus in $

    # hidden hospital rule (identical across conditions)
    concession_rate=0.40,            # new offer = current - 0.40 x (current - counteroffer)
    floor_share=0.55,                # hospital never goes below 55% of the bill ($2,860)
    max_hospital_offers=4,           # opening + 3 replies; the 4th is the final offer (2-8)

    # framing (Small et al., 2007) — pilot these
    tell_negotiable=True,            # show "this bill can be negotiated"
    frame='negotiate',               # 'negotiate' or 'ask' (wording in the instructions)

    hospital_name='Riverside General Hospital',
    typing_delay_ms=2200,            # "typing..." pause before each hospital message

    # Prolific
    prolific_return_url='https://app.prolific.com/submissions/complete?cc=',
    prolific_completion_code='REPLACE_ME',
    prolific_screened_out_code='REPLACE_ME_SCREENED',

    force_condition='',              # '' = random; 'named' or 'anonymous' for previews
    doc='',
)

SESSION_CONFIGS = [
    dict(
        name='medical_bill',
        display_name='Medical bill negotiation (random condition) — use this for Prolific',
        app_sequence=['medical_bill'],
        num_demo_participants=2,
    ),
    dict(
        name='preview_named',
        display_name='Preview: named case manager (Jake)',
        app_sequence=['medical_bill'],
        num_demo_participants=1,
        force_condition='named',
    ),
    dict(
        name='preview_anonymous',
        display_name='Preview: anonymous billing department',
        app_sequence=['medical_bill'],
        num_demo_participants=1,
        force_condition='anonymous',
    ),
]

SESSION_CONFIG_DEFAULTS = STUDY_DEFAULTS

ROOMS = [
    dict(
        name='prolific',
        display_name='Medical bill study (Prolific)',
        # no participant_label_file: any Prolific ID passed in the URL is accepted
    ),
]

PARTICIPANT_FIELDS = []
SESSION_FIELDS = []

LANGUAGE_CODE = 'en'
REAL_WORLD_CURRENCY_CODE = 'USD'
USE_POINTS = False

ADMIN_USERNAME = 'admin'
ADMIN_PASSWORD = environ.get('OTREE_ADMIN_PASSWORD')
OTREE_PRODUCTION = environ.get('OTREE_PRODUCTION')

DEMO_PAGE_INTRO_HTML = """
Medical bill negotiation study. Use the two <b>Preview</b> sessions to see each condition.
"""

SECRET_KEY = environ.get('OTREE_SECRET_KEY', 'change-me-before-deploying')
