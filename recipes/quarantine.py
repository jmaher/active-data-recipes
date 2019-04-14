"""
This is currently broken.

.. code-block:: bash

    adr intermittent_tests
"""
from __future__ import absolute_import, print_function

from adr.query import run_query


def run(args):
    # These 4 args are defined so that we can share the queries with the
    # 'intermittent_test_data' recipe.
    args.test_name = '(~(file.*|http.*))'
    args.groupby = 'result.test'
#    args.result = [false]
    args.platform_config = "test-%s/%s" % (args.platform, args.build_type)

    tests = run_query('quarantine', args)['data']

    intermittent_tests = []
    # for each result, match up the revision/name with jobs, if a match, save testname
    index = -1
    # result.test, run.key, pass, total
    result = []
    passed = {}
    failed = {}
    skipped = {}

    for index in tests:
        config = index[1]
        if not config:
            print("no config: %s" % index)
            continue

        if config not in passed:
            passed[config] = []
        if config not in failed:
            failed[config] = []
        if config not in skipped:
            skipped[config] = []

        if index[2] == 10:
            if index[0] not in passed[config]:
                passed[config].append(index[0])
        if index[3] == 10:
            if index[0] not in failed[config]:
                failed[config].append(index[0])
        if index[4] == 10:
            if index[0] not in skipped[config]:
                skipped[config].append(index[0])


    configs = []
    unique_tests = {}
    for config in passed.keys():
        parts = str(config).split('/')
        c = parts[0] + '/' + parts[1].split('-')[0]
        if c not in configs:
            configs.append(c)
        for item in passed[config]:
            if item not in unique_tests.keys():
                unique_tests[item] = {}
            unique_tests[item][c] = 1
 #       result.append([config, len(passed[config]), len(failed[config]), len(skipped[config])])

    header = "test"
    for c in configs:
        header += ",%s" % c
#    print(header)
    for item in unique_tests.keys():
        string = item
        test = unique_tests[item]
        for c in configs:
            value = 0
            if c in test.keys():
                value = test[c]
            string += ",%s" % value
#        print("%s" % string)

    result.insert(0, ['Config', 'Pass', 'Fail', "skip"])
    return result
