"""Invented mark arithmetic and raw-membership controls; no historical scores."""
import math
import unittest
from reproduction.score_replay.california_mark_replay import select_events, mark_score


def event(eid, stamp, magnitude):
    return dict(event_id=eid, origin_time_utc=stamp, magnitude=float(magnitude),
                source_tokens={'magnitude': magnitude})


class MarkArithmetic(unittest.TestCase):
    def test_hand_calculated(self):
        self.assertAlmostEqual(mark_score([0., .5, 1.], 2.), 3*math.log(2)-3)

    def test_window_and_threshold(self):
        data = [event('a', '1981-01-01T00:00:00Z', '4.40'),
                event('b', '1981-01-02T00:00:00Z', '4.50'),
                event('c', '1981-01-03T00:00:00Z', '5.00')]
        self.assertEqual([r['event_id'] for r in select_events(data, 0., 2., 4.)], ['a', 'b'])
        self.assertEqual(select_events(data, 0., 2., 4.5), [dict(event_id='b', time=1., excess=0.)])

    def test_fractional_time(self):
        rows = select_events([event('a', '1981-01-01T00:00:00.500Z', '4.14')], 0., 1., 4.)
        self.assertEqual(rows[0]['time'], .5/86400)
        self.assertEqual(rows[0]['excess'], float('4.14')-4.)

    def test_identity_and_order_fail(self):
        a = event('a', '1981-01-01T00:00:00Z', '4.5')
        b = event('b', '1981-01-02T00:00:00Z', '4.5')
        for rows in ([a, a], [b, a]):
            with self.assertRaises(ValueError): select_events(rows, 0., 3., 4.)

    def test_token_mismatch(self):
        a = event('a', '1981-01-01T00:00:00Z', '4.5'); a['magnitude'] = 5.
        with self.assertRaises(ValueError): select_events([a], 0., 1., 4.5)

    def test_invalid_mark_inputs(self):
        for q, beta in [([-1.], 2.), ([math.nan], 2.), ([1.], 0.), ([1.], True)]:
            with self.assertRaises(ValueError): mark_score(q, beta)


if __name__ == '__main__': unittest.main()
