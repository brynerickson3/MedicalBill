"""
Bot tests. Run with:   otree test medical_bill
They play the strategies from the design doc's bonus table and check the numbers.
"""
from otree.api import Bot, Submission, expect, SubmissionMustFail
from . import *


class PlayerBot(Bot):
    cases = [
        'accept_open', 'counter_4160', 'counter_3120', 'counter_1', 'decline_final',
        'accept_round2', 'invalid_inputs', 'retry_then_pass', 'fail_comprehension', 'no_consent',
    ]

    def play_round(self):
        case = self.case
        if case == 'no_consent':
            yield Consent, dict(consent=False)
            expect(self.player.excluded, 'declined_consent')
            yield Submission(ConsentDeclined, check_html=False)
            return

        yield Consent, dict(consent=True)
        yield Instructions
        yield Scenario

        if case == 'fail_comprehension':
            yield Comprehension, dict(comp_q1='speed', comp_q2='full')
            yield ComprehensionRetry, dict(comp_q1_retry='speed', comp_q2_retry='zero')
            expect(self.player.excluded, 'failed_comprehension')
            yield Submission(ScreenedOut, check_html=False)
            return
        if case == 'retry_then_pass':
            yield Comprehension, dict(comp_q1='speed', comp_q2='zero')
            yield ComprehensionRetry, dict(comp_q1_retry='saving', comp_q2_retry='zero')
            expect(self.player.comp_attempts, 2)
        else:
            yield Comprehension, dict(comp_q1='saving', comp_q2='zero')
            expect(self.player.comp_attempts, 1)
        expect(self.player.comp_passed, True)

        yield CounterpartIntro
        yield Submission(Negotiate, check_html=False)

        expected = EXPECTED.get(case)
        if expected:
            for key, value in expected.items():
                expect(self.player.field_maybe_none(key), value)

        yield Outcome
        yield Checks, dict(mc_counterpart='person', mc_personal=4, mc_real_person=3,
                           mc_bonus_motivation=6, study_guess='')
        yield Feelings, {f: 3 for f in Feelings.form_fields}
        answers = {f: 4 for f in Power.form_fields}
        answers['attn_check'] = 5
        yield Power, answers
        expect(self.player.attn_pass, True)
        yield SES, dict(education=5, parent_education=3, income=2, household_size=3, ladder=4)
        yield WorkInsurance, dict(employment_type='part_time', occupation='routine_nonmanual',
                                  union_covered='no', could_negotiate_pay='not_sure', insurance='medicaid',
                                  prior_bill_dispute='no', fl_interest='more', fl_inflation='less', fl_risk='true')
        expect(self.player.fin_literacy_score, 2)
        demo = dict(age=34, gender='self_describe', gender_self_describe='',
                    tipi_extraverted=5, tipi_reserved=3, tipi_critical=2, tipi_sympathetic=6, race_asian=1)
        yield SubmissionMustFail(Demographics, demo)  # self-describe left blank
        demo['gender_self_describe'] = 'genderfluid'
        yield Demographics, demo
        yield Debrief, dict(withdraw_data=False, comments='')
        yield Submission(Finish, check_html=False)


# Expected outcomes. The design doc's table (computed without rounding between
# rounds) gives $4,385 for the 4,160 strategy; this app rounds every offer to the
# dollar the participant actually sees, which gives $4,384. Same bonus.
EXPECTED = {
    'accept_open': dict(final_amount=5200, pct_saved=0.0, bonus=0.0, countered=False,
                        rounds_to_agreement=1, agreement=True),
    'counter_4160': dict(offer_1=5200, offer_2=4784, offer_3=4534, offer_4=4384,
                         final_amount=4384, bonus=0.31, first_counter=4160, n_counters=3,
                         rounds_to_agreement=4),
    'counter_3120': dict(offer_2=4368, offer_3=3869, offer_4=3569, final_amount=3569, bonus=0.63),
    'counter_1': dict(offer_2=3120, offer_3=2860, offer_4=2860, final_amount=2860,
                      pct_saved=45.0, bonus=0.9, hit_floor=True),
    'decline_final': dict(agreement=False, final_amount=5200, bonus=0.0, n_counters=3,
                          rounds_to_agreement=None),
    'accept_round2': dict(offer_2=4720, final_amount=4720, rounds_to_agreement=2, n_counters=1,
                          first_counter=4000, first_counter_pct_off=23.08),
    'invalid_inputs': dict(final_amount=5200, n_counters=0, countered=False),
}

STRATEGY = {
    'accept_open': [],
    'counter_4160': [4160] * 3,
    'counter_3120': [3120] * 3,
    'counter_1': [1] * 3,
    'decline_final': [3120] * 3,
    'accept_round2': [4000],
    'retry_then_pass': [4500],
}


def call_live_method(method, case, group, **kwargs):
    # oTree calls this once per group, so negotiate for every player in it
    for p in group.get_players():
        _negotiate(lambda d, i=p.id_in_group: _unwrap(method(i, d), i), case)


def _negotiate(send, case):

    assert send({'type': 'peek'})['status'] == 'not_started'
    state = send({'type': 'init', 'answer_sec': 2.5})
    assert state['current_offer'] == 5200
    assert state['messages'][0]['actor'] == 'hospital'

    if case == 'invalid_inputs':
        assert send({'type': 'counter', 'amount': 6000})['error']   # above current offer
        assert send({'type': 'counter', 'amount': 5200})['error']   # equal to current offer
        assert send({'type': 'counter', 'amount': 0})['error']      # not positive
        assert send({'type': 'counter', 'amount': 'abc'})['error']
        assert send({'type': 'decline'})['error']                   # can only decline the final offer
        send({'type': 'accept', 'rt': 1.5})
        return

    counters = STRATEGY.get(case, [])
    for amount in counters:
        state = send({'type': 'counter', 'amount': amount, 'rt': 2.0})
        assert not state['error'], state['error']
    if case == 'decline_final':
        assert state['is_final']
        state = send({'type': 'decline', 'rt': 3.0})
        assert state['status'] == 'declined'
        return
    if state['is_final']:
        assert send({'type': 'counter', 'amount': 100})['error']   # no counters on the final offer
    state = send({'type': 'accept', 'rt': 1.0})
    assert state['status'] == 'accepted'


def _unwrap(result, id_in_group):
    """method() returns an async generator of {id_in_group: payload}; take the payload."""
    import asyncio

    async def first():
        async for item in result:
            return item
    item = asyncio.get_event_loop().run_until_complete(first()) if hasattr(result, '__anext__') else result
    return item[id_in_group]
