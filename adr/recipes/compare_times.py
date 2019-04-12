"""
Given multiple revisions compare job runtimes across revisions

.. code-block:: bash

    adr compare_times

`View Results <https://mozilla.github.io/active-data-recipes/#compare_times>`__
"""
from __future__ import absolute_import, print_function

from ..context import override
from ..query import run_query

DEFAULT_BRANCHES = [
    'try',
]

RUN_CONTEXTS = [
    override('branches', default=DEFAULT_BRANCHES),
    override('limit', default=50, help="Maximum number of jobs in result"),
    override('sort_key', default=0, help="Key to sort on (int, 0-based index)"),
]


def run(config, args):

    limit = args.limit
    delattr(args, 'limit')

    data = run_query('compare_times', config, args)['data']
    result = []
    rev_results = {}
    revs = []
    for record in data:
        if record[2] is None:
            continue
        if record[1] not in revs:
            revs.append(record[1])

        if record[0] not in rev_results:
           rev_results[record[0]] = {}
        rev_results[record[0]][record[1]] = record[2]

    for job in rev_results.keys():
        val = [job]
        for r in revs:
            val.append(rev_results[job][r])
        result.append(val)

    result = sorted(result, key=lambda k: k[args.sort_key], reverse=True)[:limit]

    val = ['Taskname']
    for r in revs:
        val.append(r)
    result.insert(0, val)
    return result
