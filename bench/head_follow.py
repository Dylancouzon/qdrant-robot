"""Compare following controllers on identical delayed projected face paths without hardware."""
import argparse
import hashlib
import json
import math
import platform
import types
from collections import deque
from pathlib import Path


def load(path):
    """Compile each snapshot directly so rapid equal-length edits cannot reuse stale bytecode."""
    module = types.ModuleType('following_snapshot')
    module.__file__ = str(path)
    exec(compile(path.read_text(), str(path), 'exec'), module.__dict__)
    return module


def path(t):
    if t < 4:
        return 5 * t
    if t < 8:
        return 20.
    if t < 16:
        return 20 - 5 * (t - 8)
    return -20.


def measure(module, delay, speed=10):
    motor = module.SimMotor(speed=speed)
    motor.tolerance = 1.5
    suppressed = [False]
    head = module.Head(motor, blocked=lambda: suppressed[0])
    pending, errors = deque(), []
    stationary = active = wrong = 0
    overshoot = excursion = 0.
    stopped_at = None
    for step in range(2201):
        t, now = step / 100, 100 + step / 100
        suppressed[0] = 12 <= t < 13
        head.tick(now)
        if step % 7 == 0:
            error = math.tan(math.radians(path(t) - head.angle)) / (2 * math.tan(math.radians(35)))
            pending.append((now + delay, now, error, not 10 <= t < 11))
        while pending and pending[0][0] <= now + 1e-8:
            _, taken, error, visible = pending.popleft()
            if visible:
                center = 1280 * (.5 + error)
                result = head.follow((center - 50, 0, center + 50, 100), 1280, taken, now)
                if result == 'goal' and (head.goal - head.angle) * (path(t) - head.angle) < 0:
                    wrong += 1
            else:
                head.hold()
        actual_error = path(t) - head.angle
        errors.append(abs(actual_error))
        eligible = not (10 <= t < 11 or 12 <= t < 13) and t < 20
        active += eligible
        if abs(actual_error) > 5 and eligible:
            stationary += abs(motor.target - motor.angle) < .01
        if t >= 4 and t < 8:
            overshoot = max(overshoot, max(0, head.angle - 20))
        if step == 2000:
            stopped_at = head.angle
            # Use the production request without making wall-clock time part of this simulation.
            head.request('stop')
        if stopped_at is not None:
            excursion = max(excursion, abs(head.angle - stopped_at))
        assert abs(head.goal) <= head.limit and not head.error
    return {'mean_error_deg': sum(errors) / len(errors),
            'offcenter_stationary_fraction': stationary / max(1, active),
            'offcenter_stationary_s': stationary / 100,
            'active_s': active / 100,
            'maximum_overshoot_deg': overshoot, 'wrong_way_corrections': wrong,
            'stop_excursion_deg': excursion, 'goal_count': len(motor.goals)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('baseline', type=Path)
    parser.add_argument('output', type=Path)
    parser.add_argument('--speed', type=float, default=10)
    args = parser.parse_args()
    baseline = load(args.baseline)
    candidate = load(Path(__file__).resolve().parents[1] / 'robot/head.py')
    result = {'machine': platform.node(), 'hardware_motion': False,
              'speed_deg_s': args.speed, 'arrival_tolerance_deg': 1.5,
              'baseline_source': str(args.baseline), 'capture_period_s': .07,
              'scenario': 'ramp, plateau, reversal, face loss10..11s, speech12..13s, Stop20s',
              'baseline_sha256': hashlib.sha256(args.baseline.read_bytes()).hexdigest(),
              'candidate_sha256': hashlib.sha256(Path(candidate.__file__).read_bytes()).hexdigest(),
              'runs': []}
    for delay in (0., .15, .3):
        old, new = measure(baseline, delay, args.speed), measure(candidate, delay, args.speed)
        performance_passed = (new['mean_error_deg'] < old['mean_error_deg'] and
                  new['offcenter_stationary_fraction'] < old['offcenter_stationary_fraction'] and
                  all(new[key] <= old[key] + 1e-8 for key in (
                      'maximum_overshoot_deg', 'wrong_way_corrections', 'stop_excursion_deg')))
        # A source delivered at its expiry cannot authorize future travel. Report its
        # tracking regression separately rather than weakening the capture-age limit.
        expired_hold = delay == .3 and new['goal_count'] == 1
        result['runs'].append({'capture_delay_s': delay, 'baseline': old,
                               'candidate': new, 'performance_passed': performance_passed,
                               'expiry_hold_passed': expired_hold,
                               'passed': expired_hold if delay == .3 else performance_passed})
    result['passed'] = all(row['passed'] for row in result['runs'])
    args.output.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result, indent=2))
    assert result['passed'], 'Candidate missed frozen comparison criteria'


if __name__ == '__main__':
    main()
