"""
Everything the hospital counterpart "says" lives in this file, so you can edit
wording without touching the game logic.

Rules for keeping the two conditions comparable (per the design doc):
  * Every number, timing and rule is identical across conditions.
  * Only the identity cues differ: name/label, icon, voice ("I" vs "We"),
    and Jake's sign-off.

Placeholders filled in automatically:
  {amount}   the offer in this message, e.g. $4,784
  {bill}     the original bill, e.g. $5,200
  {hospital} the hospital name from the session config
"""

COUNTERPART = {
    'named': {
        'display_name': 'Jake Taylor',
        'subtitle': 'Case Manager, Patient Financial Services',
        'icon': 'person',
        'signoff': '– Jake',
        'intro_heading': 'You will be talking with Jake Taylor',
        'intro_text': (
            'Your bill has been assigned to <b>Jake Taylor</b>, a case manager in '
            '{hospital}\'s Patient Financial Services office. Jake handles '
            'questions about patient balances.'
        ),
    },
    'anonymous': {
        'display_name': 'Billing Department',
        'subtitle': '{hospital}',
        'icon': 'hospital',
        'signoff': None,
        'intro_heading': 'You will be contacting the Billing Department',
        'intro_text': (
            'Questions about your bill are handled by <b>{hospital}\'s Billing '
            'Department</b>, which manages patient balances.'
        ),
    },
}

MESSAGES = {
    'named': {
        # Opening wording taken from the design doc's sample text.
        'opening': (
            'Hello! This is Jake from Patient Financial Services. Please pay your '
            'outstanding balance of {amount}, or tell me what you can pay.'
        ),
        # One entry per hospital offer after the opening (offer 2, offer 3, ...).
        # If there are more offers than entries, the list repeats.
        'counter': [
            "I've reviewed your request. I can lower your balance to {amount}.",
            "I've looked at your account again. I can bring your balance down to {amount}.",
        ],
        'no_change': "I'm not able to go any lower than {amount}.",
        'final': (
            'My final offer is {amount}. You can accept it, or decline and the full '
            'balance of {bill} remains due.'
        ),
        'accepted': "Thank you. I've updated your account. Your new balance is {amount}.",
        'declined': 'Understood. The full balance of {bill} remains due.',
    },
    'anonymous': {
        # Opening wording taken from the design doc's sample text.
        'opening': (
            'Your balance due is {amount}. Please pay {hospital} in full or request '
            'a different amount.'
        ),
        'counter': [
            'We have reviewed your request. The balance can be lowered to {amount}.',
            'We have reviewed the account again. The balance can be reduced to {amount}.',
        ],
        'no_change': 'The balance cannot be reduced below {amount}.',
        'final': (
            'The final offer is {amount}. You may accept it, or decline, in which case '
            'the full balance of {bill} remains due.'
        ),
        'accepted': 'Thank you. The account has been updated. Your new balance is {amount}.',
        'declined': 'Understood. The full balance of {bill} remains due.',
    },
}

# What the participant's own chat bubbles say (same in both conditions).
PARTICIPANT_MESSAGES = {
    'counter': 'I can pay {amount}.',
    'accept': 'I accept {amount}.',
    'decline': 'I decline the offer.',
}

# The itemized bill shown on the scenario page and in the bill widget.
BILL_ITEMS = [
    ('Emergency room facility fee', 2400),
    ('Physician fee', 900),
    ('CT scan / test', 1300),
    ('Laboratory tests (blood)', 350),
    ('IV fluids and supplies', 250),
]
