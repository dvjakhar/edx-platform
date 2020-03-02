"""
Feature flag support for experiments
"""

import logging
import pytz

import dateutil
from crum import get_current_request
from edx_django_utils.cache import RequestCache

from experiments.stable_bucketing import stable_bucketing_hash_group
from openedx.core.djangoapps.waffle_utils import CourseWaffleFlag
from track import segment

log = logging.getLogger(__name__)


class ExperimentWaffleFlag(CourseWaffleFlag):
    """
    ExperimentWaffleFlag handles logic around experimental bucketing and whitelisting.

    You'll have one main flag that gates the experiment. This allows you to control the scope
    of your experiment and always provides a quick kill switch.

    But you'll also have smaller related flags that can force bucketing certain users into
    specific buckets of your experiment. Those can be set using a waffle named like
    "main_flag.BUCKET_NUM" (e.g. "course_experience.animated_exy.0") to force
    users that pass the first main waffle check into a specific bucket experience.

    You can also control whether the experiment only affects future enrollments by setting
    an ExperimentKeyValue model object with a key of 'enrollment_start' to the date of the
    first enrollments that should be bucketed.

    Bucket 0 is assumed to be the control bucket.

    .. no_pii:
    """
    def __init__(self, waffle_namespace, flag_name, num_buckets=2, experiment_id=None, **kwargs):
        super().__init__(waffle_namespace, flag_name, **kwargs)
        self.num_buckets = num_buckets
        self.experiment_id = experiment_id
        self.bucket_flags = [
            CourseWaffleFlag(waffle_namespace, '{}.{}'.format(flag_name, bucket), flag_undefined_default=False)
            for bucket in range(num_buckets)
        ]

    def _save_bucket(self, value):
        request_cache = RequestCache('experiments')
        request_cache.set(self.namespaced_flag_name, value)
        return value

    def get_bucket(self, course_key=None, track=True):
        """
        Return which bucket number the specified user is in.

        Bucket 0 is assumed to be the control bucket and will be returned if the experiment is not enabled for
        this user and course.
        """
        # Keep some imports in here, because this class is commonly used at a module level, and we want to avoid
        # circular imports for any models.
        from experiments.models import ExperimentKeyValue
        from student.models import CourseEnrollment

        request = get_current_request()
        if not request:
            return 0

        experiment_name = self.namespaced_flag_name

        # Check if we have a cache for this request already
        request_cache = RequestCache('experiments')
        cache_response = request_cache.get_cached_response(experiment_name)
        if cache_response.is_found:
            return cache_response.value

        # Check if the main flag is even enabled for this user and course.
        if not self._is_enabled(course_key):  # grabs user from the current request, if any
            return self._save_bucket(0)

        # Check if the enrollment should even be considered (if it started before the experiment wants, we ignore)
        if course_key and self.experiment_id is not None:
            start_val = ExperimentKeyValue.objects.filter(experiment_id=self.experiment_id, key='enrollment_start')
            if start_val:
                try:
                    start_date = dateutil.parser.parse(start_val.first().value).replace(tzinfo=pytz.UTC)
                except ValueError:
                    log.exception('Could not parse enrollment start date for experiment %d' % (self.experiment_id,))
                    return self._save_bucket(0)
                enrollment = CourseEnrollment.get_enrollment(request.user, course_key)
                # Only bail if they have an enrollment and it's old -- if they don't have an enrollment, we want to do
                # normal bucketing -- consider the case where the experiment has bits that show before you enroll. We
                # want to keep your bucketing stable before and after you do enroll.
                if enrollment and enrollment.created < start_date:
                    return self._save_bucket(0)

        bucket = stable_bucketing_hash_group(experiment_name, self.num_buckets, request.user.username, extra=course_key)

        # Now check if the user is forced into a particular bucket, using our subordinate bucket flags
        for i, bucket_flag in enumerate(self.bucket_flags):
            if bucket_flag._is_enabled(course_key):
                bucket = i
                break

        session_key = 'tracked.{}'.format(experiment_name)
        if track and hasattr(request, 'session') and session_key not in request.session:
            segment.track(
                user_id=request.user.id,
                event_name='edx.bi.experiment.user.bucketed',
                properties={
                    'site': request.site.domain,
                    'app_label': self.waffle_namespace.name,
                    'experiment': self.flag_name,
                    'bucket': bucket,
                    'is_staff': request.user.is_staff,
                }
            )

            # Mark that we've recorded this bucketing, so that we don't do it again this session
            request.session[session_key] = True

        return self._save_bucket(bucket)
