"""
Show CI backlog for a given platform by week

.. code-block:: bash

    adr backlog [-B <branch>] [--from <date> [--to <date>]]
"""

from __future__ import absolute_import, print_function

import logging
from datetime import date, timedelta

from ..query import run_query
from adr.errors import MissingDataError

log = logging.getLogger('adr')

# TODO: try should be separate as it is lower priority
BRANCH_WHITELIST = [
    'mozilla-central',
    'mozilla-beta',
    'mozilla-inbound',
    'autoland',
    'try'
]


def get_stats_for_week(args, config, buckets, avg_times={}, include=[], exclude=[]):
    # query all jobs that are related to platform- map each revision to lag times:
    # <revision>: [{<0-5>: x, <6-30>: y, <31-60>: z, <61>: zz}]
    try:
        backouts = run_query('backlog', config, args)['data']
    except MissingDataError:
        return [], avg_times, 0

    if backouts == {}:
        return [], avg_times, 0

    jobname = backouts['job.type.name']
    request = backouts['action.request_time']
    start = backouts['action.start_time']
    end = backouts['action.end_time']
    buildrev = backouts['build.revision12']
    branch = backouts['repo.branch.name']

    backlog = {}
    time = {}
    if len(end) != len(start) != len(buildrev) != len(jobname) != len(request) != len(branch):
        print("invalid length detected in the data found")

    counter = -1
    if len(buildrev) >= 10000:
        print("potential data loss, found %s records" % len(buildrev))

    for item in buildrev:
        counter += 1
        if counter > len(buildrev):
            break
        if item is None:
            continue

        if [x for x in include if not x in jobname[counter]]:
            continue

        if [x for x in exclude if x in jobname[counter]]:
            continue

        if jobname[counter] not in avg_times.keys():
            avg_times[jobname[counter]] = []

        item = item[0:12]
        if item not in backlog:
            backlog[item] = {}
            time[item] = {}
            for b in buckets.keys():
                backlog[item][b] = 0
                time[item][b] = 0

        # delay indicates backlog
        delay = start[counter] - request[counter]

        # duration in minutes
        duration = int((end[counter] - start[counter]) / 60)
        if end[counter] - start[counter] > 0 and duration == 0:
            duration = 1

        if delay < 0:
            # here we have bad information from treeherder||activedata, use best guess at duration
            duration = 0
            if len(avg_times[jobname[counter]]) > 0:
                duration = int(sum([x for x in avg_times[jobname[counter]]]) / len(avg_times[jobname[counter]]))
                delay = (int((end[counter] - request[counter]) / 60) - duration) * 60
        else:
            avg_times[jobname[counter]].append(duration)

        if duration <= 0:
            continue

        for b in buckets.keys():
            if delay < buckets[b]:
                backlog[item][b] += 1 # increment for job count
                time[item][b] += duration
                break

    # summarize across all revs for data set
    bucket_vals = {}
    time_vals = {}
    for b in buckets.keys():
        bucket_vals[b] = 0
        time_vals[b] = 0

    for item in backlog:
#        print("%s, jobs: %s, minutes: %s" % (item, sum([backlog[item][x] for x in backlog[item]]), sum([time[item][x] for x in time[item]])))
        for b in buckets.keys():
            bucket_vals[b] += backlog[item][b]
            time_vals[b] += time[item][b]

    total = 0
    total_time = 0
    for b in buckets.keys():
        total += bucket_vals[b]
        total_time += time_vals[b]

    results = []
    for b in buckets.keys():
        results.append(round((bucket_vals[b] / total) * 100, 2))
    results.append(total)
    results.append(total_time)

    return results, avg_times, len(buildrev)


def run(config, args):

    # Between these dates on a particular branch
    to_date = args.to_date
    if to_date == 'eod':
        to_date = str(date.today())
    to_date = to_date.split('-')

    from_date = args.from_date
    if from_date == 'today-week':
        from_date = str(date.today())
    from_date = from_date.split('-')

    if not args.branches or args.branches == ['mozilla-central']:
        args.branches = BRANCH_WHITELIST

    include = []
    exclude = []
    if not args.platform_config or args.platform_config == 'test-':
        args.platform_config = 'test-android-hw'

    # TODO: determine how to input or use predefined pools/jobs/#
#    if args.platform_config == 'test-android-hw':
#        include = ['raptor']
#        exclude = ['power']

 
    day = date(int(from_date[0]), int(from_date[1]), int(from_date[2]))
    end = date(int(to_date[0]), int(to_date[1]), int(to_date[2]))
    results = []
    total_minutes = 0
    avg_times = {}
    total_jobs = 0
    total_days = 0
    saturated_days = 0
    saturated_minutes = 0
    buckets = {'half': 1800, 'one': 3600, 'six': 21600, 'twelve': 43200, 'more': 1000000}

    while day < end:
        args.from_date = str(day)
        day += timedelta(days=1)
        args.to_date = str(day)

        retVal, job_times, num_jobs = get_stats_for_week(args, config, buckets, avg_times, include, exclude)
        if not retVal:
            continue

        r = [args.from_date]
        for b in range(0,len(retVal)):
            r.append(retVal[b])
        results.append(r)

        total_minutes += retVal[6]
        total_jobs += retVal[5]
        total_days += 1
        if r[4] > 2 or r[5] > 0:
            saturated_days += 1
            saturated_minutes += retVal[6]

    if total_days > 0 and saturated_days > 0:
        average = total_minutes / (total_days *1.0)
        average += saturated_minutes / (saturated_days * 1.0)
        print("saturation point: %s minutes/day" % (round(average / 2, 2)))

    print("total minutes: %s" % total_minutes)
    print("total jobs: %s" % total_jobs)

    header = ['day']
    for b in buckets.keys():
        header.append("%s hour" % b)
    header.append('total jobs')
    header.append('total minutes')
    results.insert(0, header)
    return results
