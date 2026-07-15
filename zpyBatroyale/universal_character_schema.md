# Universal Character Master Schema

This schema defines a single canonical CSV roster that can be read by multiple Python simulations. Each row represents one persistent character, identified by an immutable `character_id`.

## Files and conventions

- **Canonical file:** `universal_characters_master.csv`
- **Schema version:** `1.0`
- **Encoding:** UTF-8 with BOM, for reliable spreadsheet compatibility
- **Attribute range:** integers from **1 to 99**
- **Political orientation:** `left2right`, where **1 = far left**, **50 = political centre**, and **99 = far right**
- **Moral alignment:** `evil2good`, where **1 = thoroughly evil**, **50 = morally neutral**, and **99 = profoundly good**
- **Missing values:** leave cells blank rather than entering mixed placeholders
- **Measurements:** `height_cm` and `weight_kg` are physical measurements, not 1–99 ratings
- **Permanent key:** never reuse or change a character's `character_id`
- **Birth year:** simulations should calculate age from `birth_year` and their own simulation year

## Rating guide

| Score | General interpretation |
|---:|---|
| 1–9 | Extremely low |
| 10–24 | Very low |
| 25–39 | Below average |
| 40–59 | Average range |
| 60–74 | Above average |
| 75–89 | Excellent |
| 90–98 | Exceptional |
| 99 | Maximum represented rating |

Ratings describe relative potential or tendency. They are not direct success percentages.

## Identity columns

| Column | Meaning |
|---|---|
| `schema_version` | Version of the character schema used by the row. |
| `character_id` | Permanent, unique identifier such as `CHR0001`. |
| `first_name` | Character's given name. |
| `last_name` | Character's family name. |
| `display_name` | Full name shown in interfaces and reports. |
| `short_name` | Compact three-character name for scoreboards or tables. |
| `sex` | Character sex, currently represented as `F` or `M` in the sample roster. |
| `birth_year` | Year of birth; age is calculated by each simulation. |
| `nationality` | Character's national identity. |
| `religion` | One of: `christian`, `atheist`, `muslim`, `hindu`, or `buddhist`. |
| `left2right` | Political orientation from far left (`1`) to far right (`99`). |
| `evil2good` | Moral alignment from thoroughly evil (`1`) through neutral (`50`) to profoundly good (`99`). |
| `species` | Biological or fictional species. |
| `height_cm` | Height in centimetres. |
| `weight_kg` | Weight in kilograms. |
| `description` | Brief human-readable characterization. |

## Physical attributes

| Attribute | Meaning |
|---|---|
| `strength` | Capacity to exert physical force. |
| `stamina` | Ability to sustain prolonged physical effort. |
| `speed` | Maximum movement velocity. |
| `agility` | Ability to accelerate, turn, and change direction quickly. |
| `coordination` | Integration and timing of whole-body movements. |
| `dexterity` | Fine motor control and precise manipulation. |
| `balance` | Ability to remain stable during movement or impact. |
| `recovery` | Rate of recovery from fatigue, exertion, or minor injury. |
| `resilience` | Ability to withstand hardship, stress, illness, or injury. |
| `metabolism` | Rate of energy use, food demand, and physiological turnover. |
| `lifespan` | Relative potential for longevity and resistance to age-related decline. |

## Cognitive attributes

| Attribute | Meaning |
|---|---|
| `intelligence` | General reasoning and problem-solving capacity. |
| `perception` | Ability to detect relevant details, threats, and opportunities. |
| `focus` | Ability to sustain attention and resist distraction. |
| `memory` | Ability to retain and recall information. |
| `creativity` | Ability to devise original ideas and unconventional solutions. |
| `learning` | Speed and effectiveness of acquiring new knowledge or skills. |
| `technical_aptitude` | Ability to understand and operate tools, machines, and systems. |
| `tactical_awareness` | Ability to interpret immediate competitive or positional situations. |

## Psychological attributes

| Attribute | Meaning |
|---|---|
| `willpower` | Ability to resist impulses and continue despite discomfort. |
| `faith` | Intensity of religious or spiritual interest and conviction. |
| `courage` | Willingness to act despite fear or danger. |
| `composure` | Ability to remain functional and calm under pressure. |
| `discipline` | Consistency in following plans, rules, and routines. |
| `determination` | Persistence in pursuing goals despite setbacks. |
| `adaptability` | Ability to adjust behaviour when circumstances change. |
| `patience` | Ability to wait, observe, and avoid premature action. |
| `risk_assessment` | Accuracy in identifying, comparing, and judging risk. |

## Social and behavioural attributes

| Attribute | Meaning |
|---|---|
| `charisma` | Ability to attract attention, inspire, and influence others. |
| `empathy` | Ability to understand and respond to others' emotions. |
| `conversation` | Ability to communicate naturally, clearly, and engagingly. |
| `deception` | Ability to conceal intentions or communicate false information convincingly. |
| `loyalty` | Tendency to honour commitments to people, groups, or causes. |
| `aggression` | Tendency to confront, dominate, or escalate conflict. |

## Important distinctions

- **Courage** governs willingness to face danger; **risk_assessment** governs how accurately danger is judged.
- **Resilience** is resistance to hardship; **recovery** is how quickly the character returns toward baseline.
- **Agility** concerns rapid body movement; **balance** concerns stability; **coordination** concerns integrated movement; **dexterity** concerns fine control.
- **Religion** is categorical identity; **faith** is the intensity of religious or spiritual conviction. An atheist should normally have low faith, though simulations may interpret this more broadly as ideological or existential conviction.
- **Charisma** concerns personal influence; **conversation** concerns interactive communication; **empathy** concerns understanding others.
- **Aggression** is a behavioural tendency, not combat ability.
- **evil2good** is overall moral disposition; **empathy**, **loyalty**, **deception**, and **aggression** are behavioural tendencies that usually correlate with it but need not — a loyal, aggressive enforcer can be evil, and a deceptive spy can be good.
- **Lifespan** is a relative biological potential rather than a literal number of years.

## Recommended use

Treat the master CSV as read-only during simulation runs. A simulation may derive specialized ratings from these attributes, but temporary health, equipment, teams, wins, injuries, relationships, and save-state data should be stored separately.

Example:

```python
cornering = (
    coordination * 0.30
    + agility * 0.25
    + balance * 0.20
    + perception * 0.15
    + risk_assessment * 0.10
)
```

The root attributes should remain stable unless deliberately edited in the canonical CSV.
