"""
This is currently broken.

.. code-block:: bash

    adr byplatform
"""
from __future__ import absolute_import, print_function
from datetime import date, timedelta
from adr.query import run_query

import json
import os
import requests

INTEGRATION = [
    'mozilla-inbound',
    'autoland'
]

CENTRAL = ['mozilla-central']

BRANCH_WHITELIST = [
    'mozilla-inbound',
    'autoland',
    'mozilla-central'
]


def get_unique_failures_for_week(args):
    # query all jobs that are fixed by commit- build a map and determine for each regression:
    # <fixed_rev>: [{<broken_rev>: "time_from_build_to_job", "job_name">}, ...]
    try:
        backouts = run_query('fixed_by_commit_jobs', args)['data']
    except Exception:
        return [], []

    if backouts == {}:
        return [], []

    builddate = backouts['build.date']
    jobname = backouts['job.type.name']
    jobdate = backouts['action.request_time']
    buildrev = backouts['build.revision12']
    fixedrev = backouts['failure.notes.text']
    branch = backouts['repo.branch.name']
    fbc = {}
    if len(builddate) != len(fixedrev) != len(buildrev) != len(jobname) != len(jobdate):
        print("invalid length detected in the data found")

    counter = -1
    configs = []
    for item in fixedrev:
        counter += 1
        if counter > len(fixedrev):
            break
        if item is None:
            continue

        if branch[counter] in ['try', 'mozilla-release']:
            continue
        if branch[counter].startswith('mozilla-esr'):
            continue
        if not jobname[counter].startswith('test'):
            continue

        item = item[0:12]

        # TODO: this is hacky, it can get out of date and my shorthand is sloppy
        # parse: test-macosx64/opt-mochitest-browser-chrome-e10s-5
        config = '-'.join(jobname[counter].split('-')[1:])
        config = config.split('/')[0]
        other = jobname[counter].split('/')[1]
        buildtype = other.split('-')[0]
        config = "%s/%s" % (config, buildtype)
        suite = parseJobName(jobname[counter], buildtype)
        date = builddate[counter]

        if config not in configs:
            configs.append(config)

        # sometimes we have a list and some items are None
        if isinstance(item, list):
            i = None
            iter = 0
            while i is None and iter < len(item):
                i = item[iter]
                iter += 1
            if i is None:
                continue
            item = i

        item = item[0:12]
        if item not in fbc:
            fbc[item] = {'rootrev': buildrev[counter],
                         'branch': [],
                         'rootdate': date,
                         'revisions': [],
                         'jobnames': [],
                         'configs': [],
                         'harnesses': []}

        if buildrev[counter] not in fbc[item]['revisions']:
            fbc[item]['revisions'].append(buildrev[counter])

        if date < fbc[item]['rootdate']:
            fbc[item]['rootdate'] = date
            fbc[item]['rootrev'] = buildrev[counter]

        if branch[counter] not in fbc[item]['branch']:
            fbc[item]['branch'].append(branch[counter])

        if jobname[counter] not in fbc[item]['jobnames']:
            fbc[item]['jobnames'].append(jobname[counter])

        if config not in fbc[item]['configs']:
            fbc[item]['configs'].append(config)

        if suite not in fbc[item]['harnesses']:
            fbc[item]['harnesses'].append(suite)
    configs.sort()

    # TODO: find a solution for 'unique' - basically a single job failure
    return fbc


def parseJobName(jobname, buildtype):
    suite = jobname.split(buildtype)[1]
    chunk = suite.split('-')[-1]
    try:
        if chunk == "%s" % int(chunk):
            suite = '-'.join(suite.split('-')[:-1])
    except Exception:
        pass
    if suite.startswith('/opt-'):
        suite = '-'.join(suite.split('-')[1:])
    suite = suite.replace('-e10s', '')

    suite = suite.strip('-')
    for sub in ['raptor', 'talos', 'mochitest-webgl', 'awsy', 'test-verify', 'firefox-ui']:
        if suite.startswith(sub):
            suite = sub
            break
    return suite


def getBugInfo(bugid):
    if bugid.strip() == '':
        return None, None

    url = "https://bugzilla.mozilla.org/rest/bug/%s" % bugid
    response = requests.get(url, headers={'User-agent': 'Mozilla/5.0'})
    data = response.json()
    if not data or ('code' in data and data['code'] == 102):
        return None, None

    try:
        product = data['bugs'][0]['product']
        component = data['bugs'][0]['component']
    except Exception:
        return None, None

    return product, component


def run(args):
    search = 'web-platform'

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

    start = date(int(from_date[0]), int(from_date[1]), int(from_date[2]))
    end = date(int(to_date[0]), int(to_date[1]), int(to_date[2]))
    startday = start + timedelta(days=(6 - start.weekday()))
    startday -= timedelta(days=7)

    # reasons.csv is something I have hand edited to provide meta data
    with open('reasons.csv', 'r') as f:
        reason_data = f.read()

    bugs = {}
    if os.path.exists('fbc_bugs.json'):
        with open('fbc_bugs.json', 'r') as f:
            bugs = json.load(f)

    reasons = {}
    for line in reason_data.split('\n'):
        parts = line.split(',')
        if len(parts) != 7:
            continue

        fbcrev = parts[1].split('=')[-1]
        if fbcrev not in reasons.keys():
            bugid = parts[4].split('=')[-1]
            if bugid not in bugs.keys():
                product, component = getBugInfo(bugid)
                bugs[bugid] = {'product': product, 'component': component}
            else:
                product = bugs[bugid]['product']
                component = bugs[bugid]['component']

            reasons[fbcrev] = {'bug': parts[4],
                               'reason': parts[5],
                               'otherrev': parts[6],
                               'product': product,
                               'component': component}

    with open('fbc_bugs.json', 'w') as f:
        json.dump(bugs, f)

    day = startday
    all_fbc = {}
    all_jobs = []
    remaining_jobs = []

    # do daily to avoid 10K query limit for metrics
    while day <= end:
        args.from_date = str(day)
        day += timedelta(days=1)
        args.to_date = str(day)

        if os.path.exists('.cache/%s-fbc.json' % args.to_date):
            with open('.cache/%s-fbc.json' % args.to_date, 'r') as f:
                fbc = json.load(f)
        else:
            fbc = get_unique_failures_for_week(args)

        for item in fbc:
            if not item:
                continue
            if item not in list(all_fbc.keys()):
                all_fbc[item] = {'rootrev': '',
                                 'rootdate': '',
                                 'branch': [],
                                 'revisions': [],
                                 'jobnames': [],
                                 'configs': [],
                                 'harnesses': []}
            all_fbc[item]['rootrev'] = fbc[item]['rootrev']
            all_fbc[item]['rootdate'] = fbc[item]['rootdate']
            all_fbc[item]['branch'].extend(fbc[item]['branch'])
            all_fbc[item]['revisions'].extend(fbc[item]['revisions'])
            all_fbc[item]['jobnames'].extend(fbc[item]['jobnames'])
            for j in fbc[item]['jobnames']:
                if j not in all_jobs:
                    all_jobs.append(j)
            all_fbc[item]['configs'].extend(fbc[item]['configs'])
            all_fbc[item]['harnesses'].extend(fbc[item]['harnesses'])

    for item in all_fbc:
        if item == []:
            continue

        remaining = []
        # filter out jobs so we can focus on one area
        if len(all_fbc[item]['jobnames']) < 1:
            continue

        for job in all_fbc[item]['jobnames']:
            # filter out jobs with a search term
            if search != '':
                if search not in job:
                    remaining.append(job)

        if remaining == []:
            if item not in reasons.keys():
                reason = ''
                bug = ''
                product = ''
                component = ''
            else:
                reason = reasons[item]['reason']
                bug = reasons[item]['bug']
                bugid = bug.split('=')[-1]
                bug = bugid
                product = bugs[bugid]['product']
                component = bugs[bugid]['component']

#            baseurl = 'https://treeherder.mozilla.org/#/jobs?repo=%s&revision'
#            print("%s, %s=%s, %s=%s" % (all_fbc[item]['rootdate'],
#                                        baseurl,
#                                        all_fbc[item]['branch'][0],
#                                        baseurl, item,
#                                        all_fbc[item]['branch'][0],
#                                        all_fbc[item]['rootrev']))
            print("%s, %s, %s, %s::%s" % (item, reason, bug, product, component))
            for j in all_fbc[item]['jobnames']:
                if j not in remaining_jobs:
                    remaining_jobs.append(j)

        with open('.cache/%s-fbc.json' % args.to_date, 'w') as f:
            json.dump(fbc, f)

    result = []
    return result
