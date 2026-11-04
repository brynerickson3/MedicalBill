import random
import time
from decimal import Decimal, ROUND_HALF_UP

from otree.api import *

from .script import COUNTERPART, MESSAGES, PARTICIPANT_MESSAGES, BILL_ITEMS

doc = """
Medical bill negotiation task (SES x counterpart study).
Participants negotiate a mock ER bill with a scripted hospital counterpart that is
either a named case manager (Jake Taylor) or an anonymous billing department.
The concession rule is identical in both conditions and never shown to participants.
"""


class C(BaseConstants):
    NAME_IN_URL = 'medical_bill'
    PLAYERS_PER_GROUP = None
    NUM_ROUNDS = 1

    BILL = sum(amount for _, amount in BILL_ITEMS)  # $5,200
    MAX_OFFERS_SUPPORTED = 8  # data columns exist for up to 8 hospital offers

    # Answer keys for the comprehension check
    COMP_Q1_CORRECT = 'saving'
    COMP_Q2_CORRECT = 'zero'

    LIKERT_7 = [1, 2, 3, 4, 5, 6, 7]
    AGREE_ANCHORS = [
        'Strongly disagree', 'Disagree', 'Somewhat disagree', 'Neither agree nor disagree',
        'Somewhat agree', 'Agree', 'Strongly agree',
    ]
    ATTENTION_CORRECT = 5  # "Somewhat agree"


# ---------------------------------------------------------------- helpers

def cfg(player, key, default=None):
    return player.session.config.get(key, default)


def money(x):
    return '${:,.0f}'.format(x)


def round_half_up(x):
    return int(Decimal(str(x)).quantize(Decimal('1'), rounding=ROUND_HALF_UP))


def next_hospital_offer(current_offer, counteroffer, concession_rate, floor):
    """The hidden hospital rule, identical in both conditions:
    new offer = current - rate * (current - counteroffer), rounded to the nearest
    dollar, never below the floor and never above the current offer."""
    raw = current_offer - concession_rate * (current_offer - counteroffer)
    return min(current_offer, max(floor, round_half_up(raw)))


def floor_amount(player):
    return round_half_up(C.BILL * cfg(player, 'floor_share', 0.55))


def max_offers(player):
    return max(2, min(C.MAX_OFFERS_SUPPORTED, int(cfg(player, 'max_hospital_offers', 4))))


def compute_bonus(player, pct_saved):
    per_point = Decimal(str(cfg(player, 'bonus_per_pct_point', 0.02)))
    cap = Decimal(str(cfg(player, 'bonus_cap', 1.50)))
    bonus = (Decimal(str(pct_saved)) * per_point).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    return float(min(bonus, cap))


def fill(template, player, amount=None):
    return template.format(
        amount=money(amount) if amount is not None else '',
        bill=money(C.BILL),
        hospital=cfg(player, 'hospital_name', 'the hospital'),
    )


NOT_AT_ALL = ['1<br>Not at all', '2', '3', '4', '5', '6', '7<br>Extremely']
AGREE = [
    'Strongly disagree', 'Disagree', 'Somewhat disagree', 'Neither agree nor disagree',
    'Somewhat agree', 'Agree', 'Strongly agree',
]

# Text of every 1–7 item, keyed by field name (used by the model and the page tables)
LIKERT_LABELS = {
    'mc_personal': 'How personal did the interaction feel?',
    'mc_real_person': "How likely is it that the hospital's replies came from a real person rather than an automated system?",
    'mc_bonus_motivation': 'How much did the bonus motivate you?',
    'attn_check': 'To show that you are reading, please select "Somewhat agree" for this statement.',
    'bl_demanding': 'Asking for a lower amount would make me seem demanding or rude',
    'bl_think_less': 'The hospital staff would think less of me',
    'bl_relationship': 'Pushing hard would damage my relationship with the hospital',
    'bl_uncooperative': 'I would come across as uncooperative',
    'bl_treat_worse': 'The hospital might treat me worse in the future',
    'nerv_embarrassed': 'Embarrassed',
    'nerv_nervous': 'Nervous',
    'nerv_anxious': 'Anxious',
    'nerv_comfortable': 'Comfortable',
    'nerv_relaxed': 'Relaxed',
    'pw_control': 'I felt I had control over the outcome',
    'pw_lower': 'I felt I could get the hospital to agree to a lower amount',
    'pw_pushback': 'I felt comfortable pushing back',
    'pw_hospital_power': 'The hospital had much more power than I did',
    'belief_asking_works': 'In real life, asking a hospital to lower a bill usually works',
    'tipi_extraverted': 'Extraverted, enthusiastic',
    'tipi_reserved': 'Reserved, quiet',
    'tipi_critical': 'Critical, quarrelsome',
    'tipi_sympathetic': 'Sympathetic, warm',
}


def likert(name):
    return models.IntegerField(label=LIKERT_LABELS[name], choices=C.LIKERT_7)


def likert_block(intro, anchors, fields):
    return dict(intro=intro, anchors=anchors, rows=[(f, LIKERT_LABELS[f]) for f in fields])


def offer_field(i):
    return models.IntegerField(blank=True, doc=f'Hospital offer #{i} (offer 1 = opening bill)')


def counter_field(i):
    return models.IntegerField(blank=True, doc=f'Participant counteroffer #{i} (made in response to hospital offer {i})')


def rt_field(i):
    return models.FloatField(blank=True, doc=f'Seconds between hospital offer {i} appearing and the participant responding')


# ---------------------------------------------------------------- models

class Subsession(BaseSubsession):
    pass


def creating_session(subsession: Subsession):
    """Random assignment. Conditions are shuffled in balanced pairs across the
    session's participant slots; Prolific participants fill slots in arrival order,
    so condition cannot depend on SES (measured only at the end)."""
    forced = subsession.session.config.get('force_condition')
    players = subsession.get_players()
    conditions = []
    while len(conditions) < len(players):
        pair = ['named', 'anonymous']
        random.shuffle(pair)
        conditions += pair
    for p, cond in zip(players, conditions):
        p.condition = forced or cond


class Group(BaseGroup):
    pass


class Player(BasePlayer):
    # --- assignment & flow
    condition = models.StringField(doc='named = Jake Taylor (case manager); anonymous = Billing Department')
    excluded = models.StringField(initial='', doc="'' = included; declined_consent; failed_comprehension")

    consent = models.BooleanField(
        label='Do you agree to take part in this study?',
        choices=[[True, 'Yes, I agree to take part'], [False, 'No, I do not agree']],
        widget=widgets.RadioSelect,
    )

    # --- comprehension check (two attempts)
    comp_q1 = models.StringField(
        label='1. What do you earn a bonus for?',
        choices=[
            ['saving', 'Lowering the amount you owe on the bill'],
            ['speed', 'Finishing the task quickly'],
            ['rounds', 'Making as many offers as possible'],
            ['nothing', 'There is no bonus'],
        ],
        widget=widgets.RadioSelect,
    )
    comp_q2 = models.StringField(
        label='2. What happens to your bonus if you accept the full bill?',
        choices=[
            ['zero', 'I earn no bonus'],
            ['half', 'I earn half of the maximum bonus'],
            ['full', 'I earn the maximum bonus'],
        ],
        widget=widgets.RadioSelect,
    )
    comp_q1_retry = models.StringField(
        label='1. What do you earn a bonus for?',
        choices=[
            ['saving', 'Lowering the amount you owe on the bill'],
            ['speed', 'Finishing the task quickly'],
            ['rounds', 'Making as many offers as possible'],
            ['nothing', 'There is no bonus'],
        ],
        widget=widgets.RadioSelect,
    )
    comp_q2_retry = models.StringField(
        label='2. What happens to your bonus if you accept the full bill?',
        choices=[
            ['zero', 'I earn no bonus'],
            ['half', 'I earn half of the maximum bonus'],
            ['full', 'I earn the maximum bonus'],
        ],
        widget=widgets.RadioSelect,
    )
    comp_attempts = models.IntegerField(initial=0)
    comp_passed = models.BooleanField(initial=False)

    # --- negotiation state & outcomes
    neg_status = models.StringField(initial='not_started', doc='not_started / in_progress / accepted / declined')
    current_offer = models.IntegerField(blank=True)
    n_offers = models.IntegerField(initial=0, doc='Number of hospital offers made so far (incl. opening)')

    offer_1 = offer_field(1)
    offer_2 = offer_field(2)
    offer_3 = offer_field(3)
    offer_4 = offer_field(4)
    offer_5 = offer_field(5)
    offer_6 = offer_field(6)
    offer_7 = offer_field(7)
    offer_8 = offer_field(8)

    counter_1 = counter_field(1)
    counter_2 = counter_field(2)
    counter_3 = counter_field(3)
    counter_4 = counter_field(4)
    counter_5 = counter_field(5)
    counter_6 = counter_field(6)
    counter_7 = counter_field(7)

    rt_1 = rt_field(1)
    rt_2 = rt_field(2)
    rt_3 = rt_field(3)
    rt_4 = rt_field(4)
    rt_5 = rt_field(5)
    rt_6 = rt_field(6)
    rt_7 = rt_field(7)
    rt_8 = rt_field(8)

    countered = models.BooleanField(blank=True, doc="Made at least one counteroffer (Lin et al.'s yes/no outcome)")
    n_counters = models.IntegerField(blank=True)
    first_counter = models.IntegerField(blank=True, doc='First counteroffer in dollars')
    first_counter_pct_off = models.FloatField(blank=True, doc='First counteroffer as % below the bill')
    agreement = models.BooleanField(blank=True)
    rounds_to_agreement = models.IntegerField(blank=True, doc='Number of the hospital offer that was accepted (1 = accepted opening)')
    final_amount = models.IntegerField(blank=True, doc='Amount owed at the end (full bill if declined)')
    total_concession = models.IntegerField(blank=True, doc='Bill minus final amount, in dollars')
    pct_saved = models.FloatField(blank=True)
    bonus = models.FloatField(blank=True)
    hit_floor = models.BooleanField(blank=True, doc='Final amount equals the hidden floor')
    neg_start_time = models.FloatField(blank=True)
    neg_end_time = models.FloatField(blank=True)
    neg_duration_sec = models.FloatField(blank=True)

    # --- manipulation & belief checks
    mc_counterpart = models.StringField(
        label='Who did you negotiate with?',
        choices=[['person', 'A named person'], ['department', 'A billing department'], ['dont_remember', "Don't remember"]],
        widget=widgets.RadioSelect,
    )
    mc_personal = likert('mc_personal')
    mc_real_person = likert('mc_real_person')
    mc_bonus_motivation = likert('mc_bonus_motivation')
    attn_check = likert('attn_check')
    attn_pass = models.BooleanField(blank=True)
    study_guess = models.LongStringField(
        label='In a sentence or two, what do you think this study was about? (optional)', blank=True,
    )

    # --- backlash concern (1 = not at all, 7 = extremely)
    bl_demanding = likert('bl_demanding')
    bl_think_less = likert('bl_think_less')
    bl_relationship = likert('bl_relationship')
    bl_uncooperative = likert('bl_uncooperative')
    bl_treat_worse = likert('bl_treat_worse')

    # --- nervousness (Bowles et al., 2007); comfortable & relaxed are reverse-scored
    nerv_embarrassed = likert('nerv_embarrassed')
    nerv_nervous = likert('nerv_nervous')
    nerv_anxious = likert('nerv_anxious')
    nerv_comfortable = likert('nerv_comfortable')
    nerv_relaxed = likert('nerv_relaxed')

    # --- sense of power (1 = strongly disagree, 7 = strongly agree); pw_hospital_power reverse-scored
    pw_control = likert('pw_control')
    pw_lower = likert('pw_lower')
    pw_pushback = likert('pw_pushback')
    pw_hospital_power = likert('pw_hospital_power')
    belief_asking_works = likert('belief_asking_works')

    # --- SES
    education = models.IntegerField(
        label='What is the highest level of education you have completed?',
        choices=[
            [1, 'Less than high school'], [2, 'High school diploma or GED'],
            [3, 'Some college, no degree'], [4, "Associate's degree"],
            [5, "Bachelor's degree"], [6, "Master's degree"],
            [7, 'Professional or doctoral degree (e.g., JD, MD, PhD)'],
        ],
    )
    parent_education = models.IntegerField(
        label='What is the highest level of education completed by either of your parents or guardians?',
        choices=[
            [1, 'Less than high school'], [2, 'High school diploma or GED'],
            [3, 'Some college, no degree'], [4, "Associate's degree"],
            [5, "Bachelor's degree"], [6, "Master's degree"],
            [7, 'Professional or doctoral degree (e.g., JD, MD, PhD)'], [99, "Don't know"],
        ],
    )
    income = models.IntegerField(
        label='What was your total household income last year, before taxes?',
        choices=[
            [1, 'Less than $25,000'], [2, '$25,000 – $49,999'], [3, '$50,000 – $74,999'],
            [4, '$75,000 – $99,999'], [5, '$100,000 – $149,999'], [6, '$150,000 – $199,999'],
            [7, '$200,000 or more'], [99, 'Prefer not to say'],
        ],
    )
    household_size = models.IntegerField(
        label='Including yourself, how many people does that income support?', min=1, max=20,
    )
    ladder = models.IntegerField(
        label='Subjective status ladder (1 = bottom, 10 = top)', choices=list(range(1, 11)),
    )

    # --- work & opportunity (Sauer et al., 2021)
    employment_type = models.StringField(
        label='Which best describes your current employment?',
        choices=[
            ['full_time', 'Employed full-time'], ['part_time', 'Employed part-time'],
            ['temporary', 'Temporary or contract work'], ['self_employed', 'Self-employed'],
            ['unemployed', 'Not employed, looking for work'], ['student', 'Student'],
            ['retired', 'Retired'], ['other', 'Other / not in the labor force'],
        ],
    )
    occupation = models.StringField(
        label='Which best describes your current or most recent job?',
        choices=[
            ['managerial', 'Managerial or professional'],
            ['routine_nonmanual', 'Routine non-manual (e.g., office, sales, service)'],
            ['skilled_manual', 'Skilled manual (e.g., electrician, mechanic)'],
            ['unskilled_manual', 'Semi- or unskilled manual (e.g., laborer, cleaner)'],
            ['never_worked', 'I have never had a paid job'],
        ],
    )
    union_covered = models.StringField(
        label='Is (or was) your pay set by a union or collective bargaining agreement?',
        choices=[['yes', 'Yes'], ['no', 'No'], ['not_sure', 'Not sure']],
        widget=widgets.RadioSelectHorizontal,
    )
    could_negotiate_pay = models.StringField(
        label='In your current or most recent job, could you have negotiated your pay?',
        choices=[['yes', 'Yes'], ['no', 'No'], ['not_sure', 'Not sure']],
        widget=widgets.RadioSelectHorizontal,
    )
    insurance = models.StringField(
        label='What is your main health insurance?',
        choices=[
            ['employer', 'Private insurance through an employer'],
            ['self_purchased', 'Private insurance I buy myself (incl. marketplace)'],
            ['medicare', 'Medicare'], ['medicaid', 'Medicaid'],
            ['other', 'Other (e.g., military, VA)'], ['uninsured', 'I do not have health insurance'],
        ],
    )
    prior_bill_dispute = models.StringField(
        label='Have you ever disputed or tried to negotiate a real medical bill?',
        choices=[['yes', 'Yes'], ['no', 'No'], ['not_sure', 'Not sure']],
        widget=widgets.RadioSelectHorizontal,
    )

    # --- financial literacy ("Big Three", Lusardi & Mitchell)
    fl_interest = models.StringField(
        label='Suppose you had $100 in a savings account and the interest rate was 2% per year. '
              'After 5 years, how much would you have if you left the money to grow?',
        choices=[['more', 'More than $102'], ['exactly', 'Exactly $102'], ['less', 'Less than $102'], ['dk', "Don't know"]],
        widget=widgets.RadioSelect,
    )
    fl_inflation = models.StringField(
        label='Imagine the interest rate on your savings account was 1% per year and inflation was 2% per year. '
              'After 1 year, how much would you be able to buy with the money in this account?',
        choices=[['more', 'More than today'], ['same', 'Exactly the same'], ['less', 'Less than today'], ['dk', "Don't know"]],
        widget=widgets.RadioSelect,
    )
    fl_risk = models.StringField(
        label='True or false: buying a single company\'s stock usually provides a safer return than a stock mutual fund.',
        choices=[['true', 'True'], ['false', 'False'], ['dk', "Don't know"]],
        widget=widgets.RadioSelect,
    )
    fin_literacy_score = models.IntegerField(blank=True, doc='0–3 correct on the Big Three')

    # --- demographics
    age = models.IntegerField(label='What is your age?', min=18, max=100)
    gender = models.StringField(
        label='What is your gender?',
        choices=[['woman', 'Woman'], ['man', 'Man'], ['nonbinary', 'Non-binary'], ['self_describe', 'Prefer to self-describe']],
        widget=widgets.RadioSelect,
    )
    gender_self_describe = models.StringField(label='If you prefer to self-describe, please do so here:', blank=True)
    race_white = models.IntegerField(blank=True)
    race_black = models.IntegerField(blank=True)
    race_hispanic = models.IntegerField(blank=True)
    race_asian = models.IntegerField(blank=True)
    race_native = models.IntegerField(blank=True)
    race_pacific = models.IntegerField(blank=True)
    race_other = models.IntegerField(blank=True)
    race_prefer_not = models.IntegerField(blank=True)

    # --- brief traits (TIPI items); reserved & critical are reverse-scored
    tipi_extraverted = likert('tipi_extraverted')
    tipi_reserved = likert('tipi_reserved')
    tipi_critical = likert('tipi_critical')
    tipi_sympathetic = likert('tipi_sympathetic')

    # --- debrief
    withdraw_data = models.BooleanField(
        label='Now that you know the full purpose of the study, do you want your data to be included?',
        choices=[[False, 'Yes, include my data'], [True, 'No, withdraw my data from the study']],
        widget=widgets.RadioSelect,
    )
    comments = models.LongStringField(label='Any comments about the study? (optional)', blank=True)


class NegEvent(ExtraModel):
    """One row per chat message, for the transcript export."""
    player = models.Link(Player)
    seq = models.IntegerField()
    timestamp = models.FloatField()
    actor = models.StringField()   # hospital / participant
    kind = models.StringField()    # opening / offer / final_offer / counter / accept / decline / accepted / declined
    offer_num = models.IntegerField()
    amount = models.IntegerField(blank=True)
    text = models.LongStringField()
    rt = models.FloatField(blank=True)


# ---------------------------------------------------------------- negotiation logic

def log_event(player, actor, kind, text, amount=None, rt=None):
    seq = len(NegEvent.filter(player=player)) + 1
    NegEvent.create(
        player=player, seq=seq, timestamp=time.time(), actor=actor, kind=kind,
        offer_num=player.n_offers, amount=amount, text=text, rt=rt,
    )


def hospital_text(player, key, amount=None, index=0):
    template = MESSAGES[player.condition][key]
    if isinstance(template, list):
        template = template[index % len(template)]
    text = fill(template, player, amount)
    signoff = COUNTERPART[player.condition]['signoff']
    return text + ('\n' + signoff if signoff else '')


def chat_state(player, animate=False, error=None):
    events = sorted(NegEvent.filter(player=player), key=lambda e: e.seq)
    offer = player.field_maybe_none('current_offer')
    return {
        'messages': [dict(actor=e.actor, text=e.text, kind=e.kind) for e in events],
        'status': player.neg_status,
        'current_offer': offer,
        'current_offer_fmt': money(offer) if offer else '',
        'offer_num': player.n_offers,
        'is_final': player.n_offers >= max_offers(player),
        'animate': animate,
        'error': error,
    }


def finish_negotiation(player, accepted):
    player.neg_end_time = time.time()
    player.neg_duration_sec = round(player.neg_end_time - player.neg_start_time, 2)
    player.agreement = accepted
    player.final_amount = player.current_offer if accepted else C.BILL
    player.rounds_to_agreement = player.n_offers if accepted else None
    player.total_concession = C.BILL - player.final_amount
    player.pct_saved = round(100 * player.total_concession / C.BILL, 2)
    player.bonus = compute_bonus(player, player.pct_saved) if accepted else 0.0
    player.payoff = cu(player.bonus)
    player.hit_floor = player.final_amount == floor_amount(player)
    counters = [player.field_maybe_none(f'counter_{i}') for i in range(1, C.MAX_OFFERS_SUPPORTED)]
    counters = [c for c in counters if c is not None]
    player.n_counters = len(counters)
    player.countered = len(counters) > 0
    if counters:
        player.first_counter = counters[0]
        player.first_counter_pct_off = round(100 * (C.BILL - counters[0]) / C.BILL, 2)


def live_negotiate(player: Player, data):
    kind = data.get('type')
    pid = player.id_in_group

    if kind == 'init':
        if player.neg_status == 'not_started':
            player.neg_status = 'in_progress'
            player.neg_start_time = time.time()
            player.n_offers = 1
            player.current_offer = C.BILL
            player.offer_1 = C.BILL
            log_event(player, 'hospital', 'opening', hospital_text(player, 'opening', C.BILL), amount=C.BILL)
            return {pid: chat_state(player, animate=True)}
        return {pid: chat_state(player)}

    if player.neg_status != 'in_progress':
        return {pid: chat_state(player)}

    rt = data.get('rt')
    try:
        rt = round(float(rt), 3) if rt is not None else None
    except (TypeError, ValueError):
        rt = None
    is_final = player.n_offers >= max_offers(player)

    if kind == 'counter':
        if is_final:
            return {pid: chat_state(player, error='This is the final offer. Please accept or decline it.')}
        try:
            amount = int(data.get('amount'))
        except (TypeError, ValueError):
            return {pid: chat_state(player, error='Please enter a whole-dollar amount.')}
        if amount < 1:
            return {pid: chat_state(player, error='Please enter an amount greater than $0.')}
        if amount >= player.current_offer:
            return {pid: chat_state(player, error=f'Your counteroffer must be lower than the current offer of {money(player.current_offer)}.')}

        k = player.n_offers
        setattr(player, f'counter_{k}', amount)
        setattr(player, f'rt_{k}', rt)
        log_event(player, 'participant', 'counter', fill(PARTICIPANT_MESSAGES['counter'], player, amount), amount=amount, rt=rt)

        previous = player.current_offer
        new_offer = next_hospital_offer(previous, amount, cfg(player, 'concession_rate', 0.40), floor_amount(player))
        player.n_offers = k + 1
        player.current_offer = new_offer
        setattr(player, f'offer_{k + 1}', new_offer)

        if player.n_offers >= max_offers(player):
            text, ev = hospital_text(player, 'final', new_offer), 'final_offer'
        elif new_offer == previous:
            text, ev = hospital_text(player, 'no_change', new_offer), 'offer'
        else:
            text, ev = hospital_text(player, 'counter', new_offer, index=k - 1), 'offer'
        log_event(player, 'hospital', ev, text, amount=new_offer)
        return {pid: chat_state(player, animate=True)}

    if kind == 'accept':
        k = player.n_offers
        setattr(player, f'rt_{k}', rt)
        log_event(player, 'participant', 'accept', fill(PARTICIPANT_MESSAGES['accept'], player, player.current_offer), amount=player.current_offer, rt=rt)
        player.neg_status = 'accepted'
        finish_negotiation(player, accepted=True)
        log_event(player, 'hospital', 'accepted', hospital_text(player, 'accepted', player.current_offer), amount=player.current_offer)
        return {pid: chat_state(player, animate=True)}

    if kind == 'decline':
        if not is_final:
            return {pid: chat_state(player, error='You can accept the offer or make a counteroffer.')}
        k = player.n_offers
        setattr(player, f'rt_{k}', rt)
        log_event(player, 'participant', 'decline', PARTICIPANT_MESSAGES['decline'], rt=rt)
        player.neg_status = 'declined'
        finish_negotiation(player, accepted=False)
        log_event(player, 'hospital', 'declined', hospital_text(player, 'declined'), amount=C.BILL)
        return {pid: chat_state(player, animate=True)}

    return {pid: chat_state(player)}


# ---------------------------------------------------------------- shared template vars

def common_vars(player):
    info = COUNTERPART[player.condition]
    hospital = cfg(player, 'hospital_name', 'the hospital')
    frame_ask = cfg(player, 'frame', 'negotiate') == 'ask'
    return dict(
        cp_name=info['display_name'],
        cp_subtitle=info['subtitle'].format(hospital=hospital),
        cp_icon=info['icon'],
        cp_intro_heading=info['intro_heading'],
        cp_intro_text=info['intro_text'].format(hospital=hospital),
        cp_contact=('Jake, the case manager,' if player.condition == 'named' else "the hospital's billing office"),
        hospital=hospital,
        bill_fmt=money(C.BILL),
        bill_items=[(name, money(a)) for name, a in BILL_ITEMS],
        task_verb=('ask for a reduction on' if frame_ask else 'negotiate'),
        tell_negotiable=cfg(player, 'tell_negotiable', True),
        base_pay='${:.2f}'.format(player.session.config['participation_fee']),
        bonus_cents='{:g}'.format(round(cfg(player, 'bonus_per_pct_point', 0.02) * 100, 2)),
        bonus_cap='${:.2f}'.format(cfg(player, 'bonus_cap', 1.50)),
        example_bonus='${:.2f}'.format(compute_bonus(player, 25)),
    )


# ---------------------------------------------------------------- pages

class StudyPage(Page):
    """Base page: hidden for anyone who has been excluded."""
    @staticmethod
    def is_displayed(player: Player):
        return player.excluded == ''


class Consent(StudyPage):
    form_model = 'player'
    form_fields = ['consent']

    @staticmethod
    def before_next_page(player: Player, timeout_happened):
        if not player.consent:
            player.excluded = 'declined_consent'


class Instructions(StudyPage):
    vars_for_template = common_vars


class Scenario(StudyPage):
    vars_for_template = common_vars


class Comprehension(StudyPage):
    form_model = 'player'
    form_fields = ['comp_q1', 'comp_q2']

    @staticmethod
    def before_next_page(player: Player, timeout_happened):
        player.comp_attempts = 1
        player.comp_passed = player.comp_q1 == C.COMP_Q1_CORRECT and player.comp_q2 == C.COMP_Q2_CORRECT


class ComprehensionRetry(StudyPage):
    form_model = 'player'
    form_fields = ['comp_q1_retry', 'comp_q2_retry']

    @staticmethod
    def is_displayed(player: Player):
        return player.excluded == '' and not player.comp_passed

    vars_for_template = common_vars

    @staticmethod
    def before_next_page(player: Player, timeout_happened):
        player.comp_attempts = 2
        player.comp_passed = player.comp_q1_retry == C.COMP_Q1_CORRECT and player.comp_q2_retry == C.COMP_Q2_CORRECT
        if not player.comp_passed:
            player.excluded = 'failed_comprehension'


class CounterpartIntro(StudyPage):
    vars_for_template = common_vars


class Negotiate(StudyPage):
    live_method = live_negotiate

    @staticmethod
    def vars_for_template(player: Player):
        return common_vars(player)

    @staticmethod
    def js_vars(player: Player):
        return dict(
            condition=player.condition,
            icon=COUNTERPART[player.condition]['icon'],
            typing_delay_ms=int(cfg(player, 'typing_delay_ms', 2200)),
        )

    @staticmethod
    def error_message(player: Player, values):
        if player.neg_status in ('not_started', 'in_progress'):
            return 'Please finish the negotiation first.'


class Outcome(StudyPage):
    @staticmethod
    def vars_for_template(player: Player):
        return dict(
            final_fmt=money(player.final_amount),
            saved_fmt=money(player.total_concession),
            bonus_fmt='${:.2f}'.format(player.bonus),
            **common_vars(player),
        )


class Checks(StudyPage):
    form_model = 'player'
    form_fields = ['mc_counterpart', 'mc_personal', 'mc_real_person', 'mc_bonus_motivation', 'study_guess']

    @staticmethod
    def vars_for_template(player: Player):
        return dict(likert_blocks=[
            likert_block(None, NOT_AT_ALL, ['mc_personal', 'mc_real_person', 'mc_bonus_motivation']),
        ])


class Feelings(StudyPage):
    form_model = 'player'
    form_fields = [
        'bl_demanding', 'bl_think_less', 'bl_relationship', 'bl_uncooperative', 'bl_treat_worse',
        'nerv_embarrassed', 'nerv_nervous', 'nerv_anxious', 'nerv_comfortable', 'nerv_relaxed',
    ]

    @staticmethod
    def vars_for_template(player: Player):
        return dict(likert_blocks=[
            likert_block('During the negotiation, I was concerned that…', NOT_AT_ALL,
                         ['bl_demanding', 'bl_think_less', 'bl_relationship', 'bl_uncooperative', 'bl_treat_worse']),
            likert_block('During the negotiation, how much did you feel…', NOT_AT_ALL,
                         ['nerv_embarrassed', 'nerv_nervous', 'nerv_anxious', 'nerv_comfortable', 'nerv_relaxed']),
        ])


class Power(StudyPage):
    form_model = 'player'
    # the attention check sits among the agree/disagree items so it is not obvious
    form_fields = ['pw_control', 'pw_lower', 'attn_check', 'pw_pushback', 'pw_hospital_power', 'belief_asking_works']

    @staticmethod
    def vars_for_template(player: Player):
        return dict(likert_blocks=[
            likert_block('How much do you agree with each statement about the negotiation?', AGREE,
                         ['pw_control', 'pw_lower', 'attn_check', 'pw_pushback', 'pw_hospital_power']),
            likert_block('And one general question:', AGREE, ['belief_asking_works']),
        ])

    @staticmethod
    def before_next_page(player: Player, timeout_happened):
        player.attn_pass = player.attn_check == C.ATTENTION_CORRECT


class SES(StudyPage):
    form_model = 'player'
    form_fields = ['education', 'parent_education', 'income', 'household_size', 'ladder']

    @staticmethod
    def vars_for_template(player: Player):
        return dict(player_ladder_rungs=list(range(1, 11)))


class WorkInsurance(StudyPage):
    form_model = 'player'
    form_fields = [
        'employment_type', 'occupation', 'union_covered', 'could_negotiate_pay',
        'insurance', 'prior_bill_dispute', 'fl_interest', 'fl_inflation', 'fl_risk',
    ]

    @staticmethod
    def before_next_page(player: Player, timeout_happened):
        player.fin_literacy_score = (
            (player.fl_interest == 'more') + (player.fl_inflation == 'less') + (player.fl_risk == 'false')
        )


class Demographics(StudyPage):
    form_model = 'player'
    form_fields = [
        'age', 'gender', 'gender_self_describe',
        'race_white', 'race_black', 'race_hispanic', 'race_asian', 'race_native',
        'race_pacific', 'race_other', 'race_prefer_not',
        'tipi_extraverted', 'tipi_reserved', 'tipi_critical', 'tipi_sympathetic',
    ]

    @staticmethod
    def vars_for_template(player: Player):
        return dict(
            race_options=[
                ('race_white', 'White'), ('race_black', 'Black or African American'),
                ('race_hispanic', 'Hispanic or Latino/a'), ('race_asian', 'Asian'),
                ('race_native', 'American Indian or Alaska Native'),
                ('race_pacific', 'Native Hawaiian or Pacific Islander'),
                ('race_other', 'Other'), ('race_prefer_not', 'Prefer not to say'),
            ],
            likert_blocks=[
                likert_block('I see myself as…', AGREE,
                             ['tipi_extraverted', 'tipi_reserved', 'tipi_critical', 'tipi_sympathetic']),
            ],
        )

    @staticmethod
    def error_message(player: Player, values):
        if values['gender'] == 'self_describe' and not (values['gender_self_describe'] or '').strip():
            return 'Please describe your gender, or choose another option.'


class Debrief(StudyPage):
    form_model = 'player'
    form_fields = ['withdraw_data', 'comments']
    vars_for_template = common_vars


class Finish(StudyPage):
    @staticmethod
    def vars_for_template(player: Player):
        code = cfg(player, 'prolific_completion_code', 'COMPLETE')
        return dict(code=code, redirect_url=cfg(player, 'prolific_return_url', '') + code)


class ConsentDeclined(Page):
    @staticmethod
    def is_displayed(player: Player):
        return player.excluded == 'declined_consent'


class ScreenedOut(Page):
    @staticmethod
    def is_displayed(player: Player):
        return player.excluded == 'failed_comprehension'

    @staticmethod
    def vars_for_template(player: Player):
        code = cfg(player, 'prolific_screened_out_code', 'SCREENED')
        return dict(code=code, redirect_url=cfg(player, 'prolific_return_url', '') + code)


page_sequence = [
    Consent, Instructions, Scenario, Comprehension, ComprehensionRetry,
    CounterpartIntro, Negotiate, Outcome,
    Checks, Feelings, Power, SES, WorkInsurance, Demographics, Debrief, Finish,
    # terminal pages for people who exit early (everyone else skips these)
    ConsentDeclined, ScreenedOut,
]


# ---------------------------------------------------------------- data export

def custom_export(players):
    """Chat transcript: one row per message. Download from the Data tab
    ('medical_bill (custom)')."""
    yield [
        'session', 'participant_code', 'prolific_pid', 'condition', 'seq', 'timestamp',
        'actor', 'kind', 'offer_num', 'amount', 'rt_sec', 'text',
    ]
    for p in players:
        for e in sorted(NegEvent.filter(player=p), key=lambda e: e.seq):
            yield [
                p.session.code, p.participant.code, p.participant.label, p.condition,
                e.seq, e.timestamp, e.actor, e.kind, e.offer_num, e.amount, e.rt,
                e.text.replace('\n', ' '),
            ]


def custom_export_prolific_bonus(players):
    """Prolific bulk-bonus format: PID,amount (only people who finished and have a bonus)."""
    for p in players:
        if p.participant.label and p.bonus and p.excluded == '':
            yield [p.participant.label, '{:.2f}'.format(p.bonus)]
