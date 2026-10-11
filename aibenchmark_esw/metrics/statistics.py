"""Descriptive independent-run statistics and labeled approximate intervals."""

import math
import statistics

# Two-sided 95% Student-t critical values, df=1..30 (NIST table):
# https://www.itl.nist.gov/div898/handbook/eda/section3/eda3672.htm
_T95 = (12.706, 4.303, 3.182, 2.776, 2.571, 2.447, 2.365, 2.306, 2.262, 2.228,
        2.201, 2.179, 2.160, 2.145, 2.131, 2.120, 2.110, 2.101, 2.093, 2.086,
        2.080, 2.074, 2.069, 2.064, 2.060, 2.056, 2.052, 2.048, 2.045, 2.042)


def score_statistics(values):
    if not values:
        return {'mean': None, 'sample_stddev': None, 'mean_ci95_approx': None}
    mean = statistics.mean(values)
    deviation = statistics.stdev(values) if len(values) > 1 else None
    degrees = len(values) - 1
    critical = _T95[min(degrees, 30) - 1] if degrees else None
    margin = critical * deviation / math.sqrt(len(values)) if deviation is not None else None
    interval = ({'lower': round(max(0, mean - margin), 6), 'upper': round(min(100, mean + margin), 6),
                 'method': 'Student-t 95% mean interval; independent samples, clipped to score bounds'
                 + ('; conservative df=30 critical value' if degrees > 30 else '')} if margin is not None else None)
    return {'mean': round(mean, 6), 'sample_stddev': round(deviation, 6) if deviation is not None else None,
            'mean_ci95_approx': interval}


def interval_text(interval):
    return ('approximate 95% mean interval unavailable (one sample)' if interval is None else
            f"approximate 95% mean interval {interval['lower']:.2f}..{interval['upper']:.2f}; {interval['method']}")
