import sys
sys.path.insert(0, 'sehat-saathi')

def compute_triage(symptoms, duration, severity):
    text = ' '.join(symptoms) + ' ' + duration
    T3 = ['chest pain','rapid breathing','shortness of breath','high fever',
          'baby fever','newborn sick','pregnant fever','pregnant bleeding',
          'blood in stool','blood in urine','stiff neck','extreme weakness',
          'no urine','dizziness']
    T2 = ['fever','cough','rash','swelling','diarrhea','vomiting','nausea',
          'joint pain','body ache','burning urine','earache','eye pain',
          'sore throat','abdominal pain','chills','child fever']
    tier = 1
    for kw in T3:
        if kw in text.lower():
            tier = 3
            break
    if tier < 3:
        for kw in T2:
            if kw in text.lower():
                tier = 2
                break
    if severity >= 4 and tier < 3:
        tier += 1
    if '2 weeks' in duration and tier == 1:
        tier = 2
    labels = {1:'Self-care at home', 2:'See a doctor', 3:'URGENT care now'}
    return {'label': labels[tier], 'tier': tier}

tests = [
    (['runny nose', 'sneezing'],        'Just started (today)', 1, 1),
    (['fever', 'cough'],                '3-5 days',             3, 2),
    (['chest pain', 'rapid breathing'], 'Just started (today)', 4, 3),
    (['headache'],                      'More than 2 weeks',    2, 2),
    (['fatigue'],                       'Just started (today)', 5, 2),
]

all_pass = True
for symptoms, duration, severity, expected_tier in tests:
    r = compute_triage(symptoms, duration, severity)
    ok = r['tier'] == expected_tier
    if not ok:
        all_pass = False
    tag = 'PASS' if ok else 'FAIL'
    print(tag, symptoms, '| sev=' + str(severity), '=> tier=' + str(r['tier']), '(expected ' + str(expected_tier) + ') --', r['label'])

print()
print('All triage tests PASSED' if all_pass else 'SOME TESTS FAILED')
