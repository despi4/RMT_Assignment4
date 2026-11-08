DEFINITIONS = {
    'distractor_copy': 'The response exactly names a distractor city instead of the target.',
    'wrong_entity_or_binding': 'A wrong entity/property association is evident; not an exact distractor-copy response.',
    'unsupported_answer': 'A substantive answer is provided when the target evidence is absent.',
    'unnecessary_abstention': 'UNKNOWN is returned even though the target is supplied.',
    'format_error': 'The correct city appears, but extra material violates the frozen exact-match output rule.',
    'other': 'Empty output or another error not covered above; describe specifically.',
}

def review_selection(rows):
    import random
    from collections import defaultdict
    failures=[r for r in rows if not r['correct']]
    random.Random(991).shuffle(failures)
    queues=defaultdict(list)
    for r in failures: queues[r['condition']].append(r)
    selected,used=[],set()
    while len(selected)<min(30,len(failures)) and any(queues.values()):
        for condition in sorted(queues):
            if queues[condition] and len(selected)<min(30,len(failures)):
                candidates=queues[condition]
                index=next((j for j,r in enumerate(candidates) if r['fact_id'] not in used),0)
                item=candidates.pop(index); selected.append(item); used.add(item['fact_id'])
    return selected

def validate_review(rows, selection):
    immutable=['record_id','condition','question','context','expected','answer']
    expected={r['record_id']:r for r in selection}
    if len(rows)!=len(expected) or {r['record_id'] for r in rows}!=set(expected):
        raise ValueError('Review must include every selected error exactly once; rows cannot be deleted or added.')
    for row in rows:
        original=expected[row['record_id']]
        if any(row[k]!=original[k] for k in immutable):
            raise ValueError('Review question/context/response was altered; restore the selected raw case.')
        if any(row[k] not in DEFINITIONS for k in ['rater_1','rater_2','final_category']) or not row['explanation'].strip():
            raise ValueError('Complete both independent codes, adjudicated category and explanation for every sampled error.')
