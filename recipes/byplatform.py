"""
This is currently broken.

.. code-block:: bash

    adr byplatform
"""
from __future__ import absolute_import, print_function
from datetime import date, timedelta
from adr.query import run_query

import json
import math
import os

# gecko-t-linux-large: $0.04/hour (default)
# gecko-t-linux-xlarge: $0.07/hour (.*-ccov/*, awsy*, android-em*/cpp|jittest, gtest, android-em/junit|robocop|test-verify, android-em/mochitest*, asan/devtools, android-em/crashtest|reftest, web-platform-test*, android-em/xpcshell)
# gecko-t-linux-medium: $0.02/hour (n/a?)
# gecko-t-linux-talos: $0.17/hour (talos/raptor/jsshell)
# gecko-t-win10-64: $0.26/hour (default)
# gecko-t-win10-64-hw: $0.17/hour (talos/raptor/jsshell)
# gecko-t-win10-64-gpu: $0.77/hour (awsy*, marionette-gpu, test-verify-gpu, test-coverage-gpu, qr/mochitest*, qr/wpt*, mochitest-gpu, mochitest-webgl*, qr/crashtest, reftest*)
# gecko-t-win7-32: $0.27/hour (default)
# gecko-t-win7-32-gpu: $0.57/hour (test-verify-gpu, test-coverage-gpu, reftest*)
# t-osx-1010: $0.17/hour
# t-osx-1014: $0.17/hour



# there are specific suites we can optimize as well (like gpu) - good list of platforms we have :)
cost_per_platform = {'windows10-64-shippable': 0.16,
                     'windows10-64-shippable-qr': 0.16,
                     'windows10-64': 0.16,
                     'windows10-64-devedition': 0.16,
                     'windows10-64-pgo-qr': 0.16,
                     'windows10-64-qr': 0.16,
                     'windows10-64-ccov': 0.16,
                     'windows10-aarch64': 0.61,
                     'windows10-64-nightly': 0.16,
                     'windows10-64-mingwclang': 0.16,
                     'windows10-64-ux': 0.61,
                     'windows7-32-shippable': 0.16,
                     'windows7-32-devedition': 0.16,
                     'windows7-32-nightly': 0.16,
                     'windows7-32': 0.16,
                     'android-em-4-3-armv7-api16': 0.16,
                     'android-em-4-3-armv7-api16-ccov': 0.16,
                     'android-em-4-3-armv7-api16-pgo': 0.16,
                     'android-em-7-0-x86': 0.15, # TODO: verify packet.net costs - assuming 2x/instance
                     'android-em-7-0-x86_64': 0.15, # TODO: verify packet.net costs
                     'android-hw-p2-8-0-arm7-api-16': 0.61,
                     'android-hw-p2-8-0-arm7-api-16-nightly': 0.61,
                     'android-hw-p2-8-0-arm7-api-16-pgo': 0.61,
                     'android-hw-p2-8-0-android-aarch64': 0.61,
                     'android-hw-p2-8-0-android-aarch64-nightly': 0.61,
                     'android-hw-g5-7-0-arm7-api-16': 0.61,
                     'android-hw-g5-7-0-arm7-api-16-pgo': 0.61,
                     'osx-10-10': 0.17,
                     'osx-10-10-shippable': 0.17,
                     'macosx64-devedition': 0.17,
                     'macosx64-nightly': 0.17,
                     'macosx64-ccov': 0.17,
                     'macosx64-qr': 0.17,
                     'macosx64-shippable-qr': 0.17,
                     'linux32': 0.16,
                     'linux32-nightly': 0.16,
                     'linux32-shippable': 0.16,
                     'linux32-devedition': 0.16,
                     'linux64-qr': 0.16,
                     'linux64': 0.16,
                     'linux64-shippable': 0.16,
                     'linux64-shippable-qr': 0.16,
                     'linux64-asan-qr': 0.16,
                     'linux64-pgo-qr': 0.16,
                     'linux64-stylo-sequential': 0.16,
                     'linux64-devedition': 0.16,
                     'linux64-nightly': 0.16,
                     'linux64-ccov': 0.16
                     }

INTEGRATION = [
    'mozilla-inbound',
    'autoland'
]

CENTRAL = ['mozilla-central']

TRY = ['try']

OTHER = [
    'maple',
    'ash',
    'larch',
    'oak',
    'mozilla-beta',
    'mozilla-release',
    'mozilla-esr60',
    'mozilla-esr68'
]

BRANCH_WHITELIST = [
    'mozilla-inbound',
    'autoland',
    'mozilla-central',
#    'try',
    'maple',
    'ash',
    'larch',
    'oak',
    'mozilla-beta',
    'mozilla-release',
    'mozilla-esr68',
    'mozilla-esr60'
]

# gecko-t-linux-large: $0.04/hour (default)
# gecko-t-linux-xlarge: $0.07/hour (.*-ccov/*, awsy*, android-em*/cpp|jittest, gtest, android-em/junit|robocop|test-verify, android-em/mochitest*, asan/devtools, android-em/crashtest|reftest, web-platform-test*, android-em/xpcshell)
# gecko-t-linux-medium: $0.02/hour (n/a?)
# gecko-t-linux-talos: $0.17/hour (talos/raptor/jsshell)
# gecko-t-win10-64: $0.26/hour (default)
# gecko-t-win10-64-hw: $0.17/hour (talos/raptor/jsshell)
# gecko-t-win10-64-gpu: $0.77/hour (awsy*, marionette-gpu, test-verify-gpu, test-coverage-gpu, qr/mochitest*, qr/wpt*, mochitest-gpu, mochitest-webgl*, qr/crashtest, reftest*)
# gecko-t-win7-32: $0.27/hour (default)
# gecko-t-win7-32-gpu: $0.57/hour (test-verify-gpu, test-coverage-gpu, reftest*)
# t-osx-1010: $0.17/hour
# t-osx-1014: $0.17/hour
# TODO: how to get this programatically as we shift load, how do we verify this
def calculate_cost(jobname):
    cost = 0.00
    if 'linux' in jobname or 'ndroid' in jobname:
        cost = 0.04
        xlarge = ['ccov', 'awsy', 'gtest', 'web-platform-test']
        xlarge.append('asan/opt-mochitest-devtool')
        if 'android-em' in jobname:
            xlarge.extend(['cppunit', 'jittest', 'junit', 'robocop', 'test-verify', 'mochitest', 'crashtest', 'reftest', 'xpcshell'])
        hw = ['raptor', 'talos']
        for item in xlarge:
            if item in jobname:
                cost = 0.07
        for item in hw:
            if item in jobname:
                cost = 0.17
        if 'android-hw' in jobname:
            cost = 0.61 # bitbar
        if 'Android-7' in jobname:
            cost = 0.15 # packet.net
    elif 'osx' in jobname:
        cost = 0.17
    elif 'windows10' in jobname:
        cost = 0.26
        gpu = ['awsy', 'marionette-gpu', 'test-verify-gpu', 'test-coverage-gpu', 'mochitest-gpu', 'mochitest-webgl', '-reftest']
        if '-qr' in jobname:
            gpu.extend(['mochitest', 'web-platform-test', 'crashtest'])
        hw = ['raptor', 'talos']
        for item in gpu:
            if item in jobname:
                cost = 0.77
        for item in hw:
            if item in jobname:
                cost = 0.17
        if 'aarch64' in jobname:
            cost = 0.61
    elif 'windows7' in jobname:
        cost = 0.27
        gpu = ['test-verify-gpu', 'test-coverage-gpu', 'reftest']
        hw = ['raptor', 'talos']
        for item in gpu:
            if item in jobname:
                cost = 0.57
        for item in hw:
            if item in jobname:
                cost = 0.17
    if cost == 0.00:
        print("unable to determine cost for jobname: %s" % jobname)
        cost = 0.16

    return cost


def percentile(data, percent):
    size = len(data)
    if size == 0:
        return 0
    return sorted(data)[int(math.ceil((size * percent) / 100)) - 1]


def get_unique_failures_for_week(args):
    # query all jobs that are fixed by commit- build a map and determine for each regression:
    # <fixed_rev>: [{<broken_rev>: "time_from_build_to_job", "job_name">}, ...]
    try:
        backouts = run_query('fixed_by_commit_jobs', args)['data']
    except:
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
            fbc[item] = {'revisions': [], 'branch': {}}

        fbc[item]['revisions'].append(buildrev[counter])

        b = branch[counter]
        if b not in fbc[item]['branch']:
            fbc[item]['branch'][b] = {}
        if config not in fbc[item]['branch'][b]:
            fbc[item]['branch'][b][config] = []
        fbc[item]['branch'][b][config].append(suite)

    configs.sort()

    results = []
    for item in fbc:
        branches = list(fbc[item]['branch'])
        confs = fbc[item]['branch'][branches[0]]
        for c in confs:
            total = 1 if len(confs[c]) > 0 else 0
            # assume same test fails, not multiple tests and we disable the one failing test
            unique = 1 if (sum([len(confs[x]) for x in confs]) - len(confs[c])) == 0 else 0
            jobs = []

            # this is a bit misleading/confusing- to find unique failures/suite, we need to explode
            # a single FBC instance into all unique jobs, it will make summary numbers higher
            for jn in fbc[item]['branch'][branches[0]][c]:
                if jn not in jobs:
                    jobs.append(jn)
            for jn in jobs:
                results.append([c, jn, total, unique])
    return results, configs


def parseJobName(jobname, buildtype):
    suite = jobname.split(buildtype)[1]
    chunk = suite.split('-')[-1]
    try:
        if chunk == "%s" % int(chunk):
            suite = '-'.join(suite.split('-')[:-1])
    except:
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


def get_metrics_for_day(args, lag_by_rev):
    # These 4 args are defined so that we can share the queries with the
    # 'intermittent_test_data' recipe.
    args.platform_config = "test-%s" % (args.platform)

    try:
        result = run_query('byplatform', args)['data']
    except:
        return {}, lag_by_rev

    results = {}
    # for each result, match up the revision/name with jobs, if a match, save testname
    index = -1
    if len(result['build.type']) == 10000:
        print("JMAHER: WARNING: hit 10K max items for %s, %s, %s" % (args.from_date, args.build_type, args.branches))

    revisions = {}
    for item in result['job.type.name']:
        index += 1

        if result['build.revision'][index] not in revisions.keys():
            revisions[result['build.revision'][index]] = {'branch': result['repo.branch.name'][index], 'taskids': []}
        revisions[result['build.revision'][index]]['taskids'].append(result['run.taskcluster.id'][index])

        tier = result['run.tier'][index]
        platform = result['build.platform'][index]
        buildtype = result['build.type'][index]
        duration = result['action.end_time'][index] - result['action.start_time'][index]
        failure = result['failure.classification'][index]
        if failure == 'not classified':
            failure = 'pass'
        elif failure == 'intermittent':
            failure = 'intermittent'
        else:
            failure = 'failure'
        if duration < 0 or duration > 100000:
            duration = 1200

        suite = parseJobName(item, buildtype)
        config = "%s/%s" % (platform, buildtype)
        if config not in results.keys():
            results[config] = {}
        
        if suite not in results[config].keys():
            results[config][suite] = {'tier': 0, 'duration': 0, 'trylag': [], 'trunklag': [], 'taskids': {}, 'totaljobs': 0, 'nontryjobs': 0, 'failures': 0, 'intermittents': 0}

        # assuming tier is static for a suite/chunk
        results[config][suite]['tier'] = tier
        results[config][suite]['duration'] += duration
        if result['repo.branch.name'][index] != 'try':
            results[config][suite]['nontryjobs'] += 1
        results[config][suite]['totaljobs'] += 1

        if failure == 'intermittent':
            results[config][suite]['intermittents'] += 1
        if failure == 'failure':
            results[config][suite]['failures'] += 1

        if result['build.revision'][index] not in results[config][suite]['taskids'].keys():
            results[config][suite]['taskids'][result['build.revision'][index]] = []
        results[config][suite]['taskids'][result['build.revision'][index]].append(result['run.taskcluster.id'][index])


    for rev in revisions.keys():
        if rev in lag_by_rev.keys():
            continue

        lag_by_rev[rev] = {}
        branch = revisions[rev]['branch']
        args.route = "tc-treeherder.v2.%s.%s" % (branch, rev)
        try:
            tctimes = run_query('byplatform_tasks', args)['data']
        except Exception as e:
            print("failure to run query: %s" % e)
            continue

        index = -1
        for item in tctimes['task.id']:
            index += 1
            tid = tctimes['task.id'][index]
            if tid not in lag_by_rev.keys():
                if not tctimes['task.run.start_time'][index] or not tctimes['task.run.scheduled'][index]:
                   lag = -1
                else:
                    lag = int(tctimes['task.run.start_time'][index] - tctimes['task.run.scheduled'][index])

                if lag < 0 or lag > 100000:
                    continue
                lag_by_rev[rev][tid] = lag

    tids = lag_by_rev.keys()
    # TODO: match task.id with results[...] and add lag
    for c in results.keys():
        for s in results[c].keys():
            for tid_rev in results[c][s]['taskids']:
                if tid_rev not in tids:
                    continue
                branch = revisions[rev]['branch']
                for tid in results[c][s]['taskids'][tid_rev]:
                    if tid not in lag_by_rev[tid_rev].keys():
                        continue
                    if 'try' in branch.lower():
                        results[c][s]['trylag'].append(lag_by_rev[tid_rev][tid])
                    else:
                        results[c][s]['trunklag'].append(lag_by_rev[tid_rev][tid])

    for type in results:
        total = {'tier': 0, 'duration': 0, 'trylag': [], 'trunklag': [], 'totaljobs': 0, 'nontryjobs': 0, 'intermittents': 0, 'failures': 0}
        for s in results[type]:
            total['duration'] += results[type][s]['duration']
            total['trylag'].extend(results[type][s]['trylag'])
            total['trunklag'].extend(results[type][s]['trunklag'])
            total['totaljobs'] += results[type][s]['totaljobs']
            total['nontryjobs'] += results[type][s]['nontryjobs']
            total['intermittents'] += results[type][s]['intermittents']
            total['failures'] += results[type][s]['failures']
        results[type]['total'] = total
    return results, lag_by_rev


def merge_results(master, new):
    for type in new.keys():
        if not master or type not in master.keys():
            master[type] = {}
        for suite in new[type].keys():
            if suite not in master[type].keys():
                master[type][suite] = {'tier': 0, 'duration': 0, 'trylag': [], 'trunklag': [], 'totaljobs': 0, 'nontryjobs': 0, 'failures': 0, 'intermittents': 0}

            master[type][suite]['tier'] = new[type][suite]['tier']
            master[type][suite]['duration'] += new[type][suite]['duration']
            master[type][suite]['trylag'].extend(new[type][suite]['trylag'])
            master[type][suite]['trunklag'].extend(new[type][suite]['trunklag'])
            master[type][suite]['totaljobs'] += new[type][suite]['totaljobs']
            master[type][suite]['nontryjobs'] += new[type][suite]['nontryjobs']
            master[type][suite]['failures'] += new[type][suite]['failures']
            master[type][suite]['intermittents'] += new[type][suite]['intermittents']
    return master


def merge_failures(master, new):
    # retval = [config, suite, unique regressions]
    for row in new:
        if not master or row[0] not in master.keys():
            master[row[0]] = {'total': {'unique': 0, 'regressions': 0}}
        if row[1] not in master[row[0]].keys():
            master[row[0]][row[1]] = {'unique': 0, 'regressions': 0}
        master[row[0]][row[1]]['unique'] += row[3]
        master[row[0]][row[1]]['regressions'] += row[2]
    
    for config in master.keys():
        master[config]['total'] = {'unique': 0, 'regressions': 0}
        for suite in master[config].keys():
            master[config]['total']['unique'] += master[config][suite]['unique']
            master[config]['total']['regressions'] += master[config][suite]['regressions']
    return master


def writeFile(data, type, platform, date):
    filename = '.cache/%s-%s-%s' % (date, type, platform)
    # if blank, write stub
    if not data:
        data = {"blank": True}

    print("writing file: %s" % filename)
    with open(filename, 'w') as f:
        json.dump(data, f)


def readFile(type, platform, date):
    filename = '.cache/%s-%s-%s' % (date, type, platform)
    retVal = {}
    if os.path.exists(filename):
        with open(filename, 'r') as f:
            retVal = json.load(f)
    return retVal


def run(args):
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

    results = {}
    failures = {}

    platforms = ['windows10', 'windows7', 'linux64', 'linux32', 'macosx', 'android']
#    platforms = ['linux64', 'linux32', 'macosx']
#    platforms = ['windows10', 'windows7', 'android']
    platforms = ['windows7']
    for platform in platforms:
        args.platform = platform
        day = startday

        # do daily to avoid 10K query limit for metrics
        lag_by_rev = readFile("tids", "all", "all")
        while day <= end:
            args.from_date = str(day)
            day += timedelta(days=1)
            args.to_date = str(day)
            if str(day) != '2019-07-29':
                continue

            t = readFile("stats", args.platform, args.from_date)
            f = readFile("failures", args.platform, args.from_date)
            
            branches = [CENTRAL, INTEGRATION, TRY, OTHER]
            if not t:
                t = {}
                for branch in branches:
                    args.branches = branch
                    for buildtype in [['debug'], ['asan'], ['opt', 'pgo']]:
                        args.build_type = buildtype
                        retVal, lag_by_rev = get_metrics_for_day(args, lag_by_rev)
                        t = merge_results(t, retVal)

                writeFile(t, "stats", args.platform, args.from_date)
            if t == {"blank": True}:
                t = {}
            results = merge_results(results, t)
            print(day)
            print(results)
            for item in results:
                print(item)
                if 'xpcshell' in results[item].keys():
                    print(results[item]['xpcshell'])
                print('')

            if not f:
                f, c = get_unique_failures_for_week(args)
                writeFile(f, "failures", args.platform, args.from_date)
            if f == {"blank": True}:
                f = {}
            failures = merge_failures(failures, f)
        writeFile(lag_by_rev, "tids", "all", "all")


    # type scope
    result = []
    result.insert(0, ['Date', 'Platform', 'Config', "# total jobs", "# !try jobs", "# intermittents", "try lag 95% (secs)", "other lag 95% (secs)", "seconds", "hours", "price", "total regressions seen", "unique regressions"])
    for type in results:
        parts = type.split('/')
        price = sum([(results[type][s]['duration'] / 3600.0) * calculate_cost("%s-%s" % (type, s)) for s in results[type] if s != 'total'])
        unique = 0
        regressions = 0
        if type in failures.keys():
            unique = failures[type]['total']['unique']
            regressions = failures[type]['total']['regressions']

        value = [parts[0],
                 parts[1],
                 results[type]['total']['totaljobs'],
                 results[type]['total']['nontryjobs'],
                 results[type]['total']['intermittents'],
                 percentile(results[type]['total']['trylag'], percent=0.95),
                 percentile(results[type]['total']['trunklag'], percent=0.95),
                 results[type]['total']['duration'],
                 "%.02f" % (results[type]['total']['duration'] / 3600.0),
                 "%0.02f" % price,
                 regressions,
                 unique]
        result.append(value)
#    return result

    result = []
#    result.append([])
#    result.append([])
    # suite scope
    result.append(['Platform', 'Config', 'Suite', "tier", "# total jobs", "# !try jobs", "# intermittents", "try lag 95% (secs)", "other lag 95% (secs)", "seconds", "hours", "price", "total regressions seen", "unique regressions"])
    for type in results:
        for s in results[type]:
            if s == 'total':
                continue
            unique = 0
            regressions = 0
            if type in failures.keys():
                if s in failures[type].keys():
                    unique = failures[type][s]['unique']
                    regressions = failures[type][s]['regressions']

            parts = type.split('/')
            price = (results[type][s]['duration'] / 3600.0) * calculate_cost("%s-%s" % (type, s))
            value = [parts[0],
                     parts[1],
                     s,
                     results[type][s]['tier'],
                     results[type][s]['totaljobs'],
                     results[type][s]['nontryjobs'],
                     results[type][s]['intermittents'],
                     percentile(results[type][s]['trylag'], percent=0.95),
                     percentile(results[type][s]['trunklag'], percent=0.95),
                     results[type][s]['duration'],
                     "%0.02f" % (results[type][s]['duration'] / 3600.0),
                     "%0.02f" % price,
                     regressions,
                     unique]
            result.append(value)
    result = []
    return result
