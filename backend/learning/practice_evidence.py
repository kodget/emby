"""Image-round scores reconstructed from the questions originally presented."""
from types import SimpleNamespace


def snapshot(station):
    return {name: getattr(station, name) for name in (
        'id', 'prompt', 'accepted_answers', 'supporting_question', 'true_false_question',
        'image_url', 'section', 'marker', 'explanation', 'structure')}


def saved_stations(session):
    rows = session.station_snapshots
    if (not isinstance(rows, list) or not rows or not all(isinstance(r, dict) for r in rows)
            or not isinstance(session.station_ids, list) or not all(isinstance(s, str) for s in session.station_ids)
            or [r.get('id') for r in rows] != session.station_ids
            or len(set(session.station_ids)) != len(session.station_ids)):
        return None
    for row in rows:
        if (not all(isinstance(row.get(key), str) for key in (
                'prompt', 'image_url', 'section', 'explanation', 'structure'))
                or not isinstance(row.get('accepted_answers'), list) or not row['accepted_answers']
                or not all(isinstance(a, str) and a.strip() for a in row['accepted_answers'])
                or not isinstance(row.get('marker'), dict)):
            return None
        supporting, tf = row.get('supporting_question'), row.get('true_false_question')
        if not isinstance(supporting, dict) or not isinstance(tf, dict):
            return None
        if supporting.get('enabled'):
            options, key = supporting.get('options'), supporting.get('correct_index')
            if (not isinstance(options, list) or not 2 <= len(options) <= 4
                    or not all(isinstance(option, str) and option.strip() for option in options)
                    or type(key) is not int or not 0 <= key < len(options)
                    or not isinstance(supporting.get('question'), str) or not supporting['question'].strip()):
                return None
        if tf.get('enabled') and (type(tf.get('answer')) is not bool
                or not isinstance(tf.get('statement'), str) or not tf['statement'].strip()):
            return None
    return {r['id']: SimpleNamespace(**r) for r in rows}


def counts(session):
    """No current keys or cached score counters; missing answers count as incorrect."""
    from .practice import grade_main_answer
    stations = saved_stations(session)
    if stations is None:
        return None
    answers = {a.station_id: a for a in session.attempts.all()}
    out = dict(total=0, correct=0, main_correct=0, supporting_correct=0,
               true_false_correct=0, timed_out=0, seconds=0, answered=0, breakdown={})
    for sid, station in stations.items():
        answer = answers.get(sid)
        main = bool(answer and grade_main_answer(answer.main_answer, station.accepted_answers))
        out['total'] += 1
        out['correct'] += int(main)
        out['main_correct'] += int(main)
        for field, response, key, counter in (
                ('supporting_question', 'supporting_choice', 'correct_index', 'supporting_correct'),
                ('true_false_question', 'true_false_answer', 'answer', 'true_false_correct')):
            question = getattr(station, field) or {}
            if question.get('enabled'):
                given = getattr(answer, response, None)
                right = given is not None and given == question.get(key)
                out['total'] += 1
                out['correct'] += int(right)
                out[counter] += int(right)
        if answer:
            out['answered'] += 1
            out['timed_out'] += int(answer.timed_out)
            out['seconds'] += max(0, min(answer.seconds_taken, max(0, session.seconds_per_station) * 3))
        bucket = out['breakdown'].setdefault(station.section, {'attempted': 0, 'correct': 0})
        bucket['attempted'] += 1
        bucket['correct'] += int(main)
    for bucket in out['breakdown'].values():
        bucket['accuracy'] = round(bucket['correct'] / bucket['attempted'], 3)
    return out
