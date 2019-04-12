"""
Show CI backlog for a given platform by week

.. code-block:: bash

    adr job_simulation [-B <branch>] [--from <date> [--to <date>]]
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


def get_stats_for_date(args, config, queue, first, last, jobnames, jobtimes):
    # query all jobs that are related to platform- map each revision to lag times:
    # <revision>: [{<0-5>: x, <6-30>: y, <31-60>: z, <61>: zz}]
    try:
        # TODO: consider adjusting query to have include/exclude for less data
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
    
    # fill up queue with all jobs ordered by request
    counter = -1
    keys = []
    for item in buildrev:
        counter += 1

        if not 'raptor' in jobname[counter]:
            continue
        if 'power' in jobname[counter]:
            continue
        if 'cold' in jobname[counter]:
            continue

        if request[counter] not in keys:
            queue[request[counter]] = []
            keys.append(request[counter])

        if jobname[counter] not in jobnames:
            jobnames.append(jobname[counter])
            jobtimes.append([])

        begin = start[counter]
        stop = end[counter]
        jnid = jobnames.index(jobname[counter])

        if begin == 0 and stop > 0 and jobtimes[jnid]:
            begin = stop - int(sum(jobtimes[jnid]) / len(jobtimes[jnid]))

        if stop == 0 and begin > 0 and jobtimes[jnid]:
            stop = begin + int(sum(jobtimes[jnid]) / len(jobtimes[jnid]))

        if stop == 0 or begin == 0:
            continue

        if 'tp6m' in jobname[counter]:
            elapsed = stop - begin
#            stop = begin + int(elapsed*1.3)
            cold = begin + int(elapsed*5)
            # TODO: proper jnid is needed
            queue[request[counter]].append({'start': begin, 'end': cold, 'jobname': jnid})

        jobtimes[jnid].append(stop - begin)

        item = {'start': begin,
                'end': stop,
                'jobname': jnid}

        if begin < first:
            first = begin
        if stop > last:
            last = stop

        queue[request[counter]].append(item)

    return queue, first, last, jobnames, jobtimes


def run_simulation(queue, first, last, num_devices):
    requested = []
    devices = []
    downtime = []
    uptime = []
    for iter in range(0, num_devices):
        devices.append(None)
        downtime.append([0]) # array of downtime requests
        uptime.append([0]) # array of execution requests

    time = first - 1
    keys = queue.keys()
    print("doing iteration for:  %s" % (last - first))
    total_jobs = 0
    while time < last:
        time += 1
        # other queue of jobs that have been requested at this time
        if time in keys:
            todo = queue[time]
            total_jobs += len(todo)
            requested.extend(todo)

        # remove scheduled jobs
        for item in range(0, num_devices):
            if devices[item] and devices[item]['end'] <= time:
                downtime[item].append(0)
                uptime[item].append(devices[item]['end'] - devices[item]['start'])
                devices[item] = None
 
        # schedule new jobs
        for item in range(0, num_devices):
            if not devices[item] is None:
                continue
            todo = [x for x in requested if x['start'] <= time]
            if len(todo) == 0:
                break
            devices[item] = todo[0]
            delay = time - devices[item]['start']
            devices[item]['end'] += delay
            requested.remove(devices[item])

        # calculate downtime of device - primarily due to scheduling timing
        for item in range(0, num_devices):
            if devices[item] is None:
                downtime[item][-1] += 1

    jobs = 0
    dt = 0
    ut = 0
    for item in range(0, num_devices):
#        if devices[item]:
#            print("leftover device: %s" % devices[item])
        device_time = sum(downtime[item]) + sum(uptime[item])
#        if device_time > last-first:
        print("device: %s, rest periods: %s, total rest: %s, execution time: %s, total time: %s (%s)" % (item, len(downtime[item]), sum(downtime[item]), sum(uptime[item]), last-first, device_time))
        jobs += len(downtime[item])
        dt += sum(downtime[item])
        ut += sum(uptime[item])
    print("totals- jobs: %s, rest: %s, execution: %s" % (total_jobs, dt, ut))
    print("remaining queue: %s" % len(requested))


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
    if args.platform_config == 'test-android-hw':
        include = ['raptor']
        exclude = ['power']

 
    day = date(int(from_date[0]), int(from_date[1]), int(from_date[2]))
    end = date(int(to_date[0]), int(to_date[1]), int(to_date[2]))
    results = []

    queue = {}
    first = 1551777235
    last = 0
    jobnames = []
    jobtimes = []

    while day < end:
        args.from_date = str(day)
        day += timedelta(days=1)
        args.to_date = str(day)
        queue, first, last, jobnames, jobtimes = get_stats_for_date(args, config,queue, first, last, jobnames, jobtimes)

    run_simulation(queue, first, last, num_devices=60)

    header = ['day']
    results.insert(0, header)
    return results
