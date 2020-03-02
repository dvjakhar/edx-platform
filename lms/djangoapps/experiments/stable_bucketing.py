"""
An implementation of a stable bucketing algorithm that can be used
to reliably group users into experiments.

An implementation of this is available as a standalone command-line
tool, `scripts/stable_bucketer`, which can both validate the
bucketing of a username and generate recognizable usernames for
particular experiment buckets for testing.
"""

import hashlib
import re


def stable_bucketing_hash_group(group_name, group_count, username, extra=None):
    """
    Return the bucket that a user should be in for a given stable bucketing assignment.

    This function has been verified to return the same values as the stable bucketing
    functions in javascript and the master experiments table.

    Arguments:
        group_name: The name of the grouping/experiment.
        group_count: How many groups to bucket users into.
        username: The username of the user being bucketed.
        extra: Any extra string to further control bucketing, e.g. a course id
    """
    hasher = hashlib.md5()
    hasher.update(group_name.encode('utf-8'))
    hasher.update(username.encode('utf-8'))
    if extra is not None:
        hasher.update(str(extra).encode('utf-8'))
    hash_str = hasher.hexdigest()

    return int(re.sub('[8-9a-f]', '1', re.sub('[0-7]', '0', hash_str)), 2) % group_count
