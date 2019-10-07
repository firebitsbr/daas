import datetime
import string
import random
from typing import Dict

from ..test_utils.test_cases.generic import APITestCase
from ...utils.redis_status import FAILED, PROCESSING, QUEUED, DONE, CANCELLED
from ...models import RedisJob, Sample, Result
from ...utils.redis_manager import RedisManager
from ...utils import redis_status, result_status
from ...utils.charts.statistics_manager import StatisticsManager
from ..mocks.statistics_redis import StatisticsRedisMock

CSHARP = '/daas/daas/daas_app/tests/resources/460f0c273d1dc133ed7ac1e24049ac30.csharp'
TEXT = '/daas/daas/daas_app/tests/resources/text.txt'


class AbstractStatisticsTestCase(APITestCase):
    def setUp(self) -> None:
        RedisManager().__mock__()
        self.statistics_manager = StatisticsManager()
        self.statistics_manager._redis = StatisticsRedisMock()
        self.today = bytes(datetime.datetime.now().date().isoformat().encode('utf-8'))
        self.random_strings = set()
        self.today = datetime.date.today().isoformat()
        # Also flush keys here in case there are keys in the db due to unexpected reasons
        # (test aborted before teardown, for instance)
        self.statistics_manager._redis.flush_test_keys()

    def tearDown(self) -> None:
        self.statistics_manager._redis.flush_test_keys()

    def _get_random_with_length(self, length):
        random_string = ''.join(random.choices(string.ascii_uppercase + string.digits, k=length))
        while random_string in self.random_strings:
            random_string = ''.join(random.choices(string.ascii_uppercase + string.digits, k=length))
        return bytes(random_string.encode('utf-8'))

    def _create_sample(self, file_type: str, size: int):
        return Sample.objects.create(name='', content=self._get_random_with_length(size) * 1024, file_type=file_type)

    def _create_samples_with_result(self, file_type: str, size: int, amount: int, redis_job_status: int, result_status: int, elapsed_time: int):
        for i in range(amount):
            sample = self._create_sample(file_type=file_type, size=size)
            RedisJob.objects.create(sample=sample, job_id=str(i), status=redis_job_status)
            Result.objects.create(elapsed_time=elapsed_time, status=result_status, decompiler='', sample=sample, output='')

    def _get_statistics_from_redis(self, file_type: str, field: str) -> Dict[bytes, bytes]:
        return self.statistics_manager._redis.get_statistics_for(file_type, field)
    
    def _get_value_from_redis(self, file_type: str) -> str:
        return self.statistics_manager._redis.get_count_for_file_type(file_type)

    def _write_values_to_redis(self, file_type: str, field: str, value: str, increase=True, times=1) -> None:
        for _ in range(times):
            self.statistics_manager._redis.register_field_and_value(file_type, field, value, increase=increase)

    def _increase_count_for_file_type(self, file_type: str, times: int = 1):
        for _ in range(times):
            self.statistics_manager._redis.register_new_sample_for_type(file_type)

    def _get_iso_formatted_days_before(self, days: int) -> str:
        return (datetime.date.today() - datetime.timedelta(days=days)).isoformat()


class SameSampleStatisticsReadTest(AbstractStatisticsTestCase):
    def setUp(self) -> None:
        super().setUp()
        self._create_samples_with_result(file_type='flash', size=14, amount=7, redis_job_status=redis_status.DONE,
                                         result_status=result_status.SUCCESS, elapsed_time=13)

    def test_file_type_statistics(self):
        self.assertEquals(self._get_value_from_redis('flash'), 7)

    def test_size_statistics(self):
        self.assertDictEqual(self._get_statistics_from_redis('flash', 'size'), {b'14': b'7'})

    def test_uploaded_on_statistics(self):
        self.assertDictEqual(self._get_statistics_from_redis('flash', 'uploaded_on'), {self.today: b'7'})

    def test_processed_on_statistics(self):
        self.assertDictEqual(self._get_statistics_from_redis('flash', 'processed_on'), {self.today: b'7'})

    def test_elapsed_time_statistics(self):
        self.assertDictEqual(self._get_statistics_from_redis('flash', 'elapsed_time'), {b'13': b'7'})

    def test_status_statistics(self):
        self.assertDictEqual(self._get_statistics_from_redis('flash', 'status'), {b'0': b'7'})


class DifferentSamplesStatisticsReadTest(AbstractStatisticsTestCase):
    def setUp(self) -> None:
        super().setUp()
        self._create_samples_with_result(file_type='pe', size=10, amount=5, redis_job_status=redis_status.DONE,
                                         result_status=result_status.SUCCESS, elapsed_time=13)
        self._create_samples_with_result(file_type='pe', size=20, amount=7, redis_job_status=redis_status.FAILED,
                                         result_status=result_status.FAILED, elapsed_time=5)
        self._create_samples_with_result(file_type='pe', size=110, amount=3, redis_job_status=redis_status.DONE,
                                         result_status=result_status.SUCCESS, elapsed_time=5)

    def test_file_type_statistics(self):
        self.assertEquals(self._get_value_from_redis('pe'), 5 + 7 + 3)

    def test_size_statistics(self):
        self.assertDictEqual(self._get_statistics_from_redis('pe', 'size'),
                             {b'10': b'5', b'20': b'7', b'110': b'3'})

    def test_uploaded_on_statistics(self):
        self.assertDictEqual(self._get_statistics_from_redis('pe', 'uploaded_on'),
                             {self.today: bytes(str(5 + 7 + 3).encode('utf-8'))})

    def test_processed_on_statistics(self):
        self.assertDictEqual(self._get_statistics_from_redis('pe', 'processed_on'),
                             {self.today: bytes(str(5 + 7 + 3).encode('utf-8'))})

    def test_elapsed_time_statistics(self):
        self.assertDictEqual(self._get_statistics_from_redis('pe', 'elapsed_time'),
                             {b'5': bytes(str(7 + 3).encode('utf-8')), b'13': b'5'})

    def test_status_statistics(self):
        self.assertDictEqual(self._get_statistics_from_redis('pe', 'status'),
                             {b'0': bytes(str(5 + 3).encode('utf-8')), b'2': b'7'})


class DeletedResultRevertsSomeStatisticsReadTest(AbstractStatisticsTestCase):
    """ Deletes one sample's result.
        Therefore, only 'status' and 'elapsed_time' should be reduced by one. """
    def setUp(self) -> None:
        super().setUp()
        self._create_samples_with_result(file_type='flash', size=14, amount=7, redis_job_status=redis_status.DONE,
                                         result_status=result_status.SUCCESS, elapsed_time=13)
        Sample.objects.last().delete()

    def test_file_type_statistics_not_affected(self):
        self.assertEquals(self._get_value_from_redis('flash'), 7)

    def test_size_statistics_not_affected(self):
        self.assertDictEqual(self._get_statistics_from_redis('flash', 'size'), {b'14': b'7'})

    def test_uploaded_on_statistics_not_affected(self):
        self.assertDictEqual(self._get_statistics_from_redis('flash', 'uploaded_on'), {self.today: b'7'})

    def test_processed_on_statistics_not_affected(self):
        self.assertDictEqual(self._get_statistics_from_redis('flash', 'processed_on'), {self.today: b'7'})

    def test_elapsed_time_statistics_reduced_by_one(self):
        self.assertDictEqual(self._get_statistics_from_redis('flash', 'elapsed_time'), {b'13': b'6'})

    def test_status_statistics_reduced_by_one(self):
        self.assertDictEqual(self._get_statistics_from_redis('flash', 'status'), {b'0': b'6'})


class SizeStatisticsWriteTest(AbstractStatisticsTestCase):
    def setUp(self) -> None:
        super().setUp()
        self._write_values_to_redis('flash', 'size', '10', times=5)
        self._write_values_to_redis('flash', 'size', '12', times=2)
        self._write_values_to_redis('flash', 'size', '6', times=1)

    def test_size_for_file_type_captions(self):
        self.assertEquals(StatisticsManager().get_size_statistics_for_file_type('flash').captions,
                          ['0 - 1', '2 - 3', '4 - 7', '8 - 15'])

    def test_size_for_file_type_counts(self):
        self.assertEquals(StatisticsManager().get_size_statistics_for_file_type('flash').counts,
                          [0, 0, 1, 7])

    def test_size_for_file_type_captions_affected_by_other_file_types(self):
        self._write_values_to_redis('pe', 'size', '30', times=1)
        self.assertEquals(StatisticsManager().get_size_statistics_for_file_type('flash').captions,
                          ['0 - 1', '2 - 3', '4 - 7', '8 - 15', '16 - 31'])

    def test_size_for_file_type_counts_affected_by_other_file_types(self):
        """ The count list should be longer, but the number of samples for each bar of the
            chart should remain the same. """
        self._write_values_to_redis('pe', 'size', '30', times=1)
        self.assertEquals(StatisticsManager().get_size_statistics_for_file_type('flash').counts,
                          [0, 0, 1, 7, 0])


class ElapsedTimeStatisticsWriteTest(AbstractStatisticsTestCase):
    def setUp(self) -> None:
        super().setUp()
        self._write_values_to_redis('java', 'elapsed_time', '6', times=5)
        self._write_values_to_redis('java', 'elapsed_time', '6', times=1)
        self._write_values_to_redis('java', 'elapsed_time', '2', times=2)

    def test_elapsed_time_for_file_type_captions(self):
        self.assertEquals(StatisticsManager().get_elapsed_time_statistics_for_file_type('java').captions,
                          ['0 - 1', '2 - 3', '4 - 7'])

    def test_elapsed_time_for_file_type_counts(self):
        self.assertEquals(StatisticsManager().get_elapsed_time_statistics_for_file_type('java').counts,
                          [0, 2, 6])

    def test_elapsed_time_for_file_type_captions_affected_by_other_file_types(self):
        self._write_values_to_redis('pe', 'size', '30', times=1)
        self.assertEquals(StatisticsManager().get_elapsed_time_statistics_for_file_type('java').captions,
                          ['0 - 1', '2 - 3', '4 - 7'])

    def test_elapsed_time_for_file_type_counts_affected_by_other_file_types(self):
        """ The count list should be longer, but the number of samples for each bar of the
            chart should remain the same. """
        self._write_values_to_redis('pe', 'elapsed_time', '30', times=1)
        self._write_values_to_redis('flash', 'elapsed_time', '7', times=4)
        self.assertEquals(StatisticsManager().get_elapsed_time_statistics_for_file_type('java').counts,
                          [0, 2, 6, 0, 0])


class FileTypeStatisticsWriteTest(AbstractStatisticsTestCase):
    def setUp(self) -> None:
        super().setUp()
        self._increase_count_for_file_type('flash', times=5)
        self._increase_count_for_file_type('java', times=3)
        self._increase_count_for_file_type('pe', times=2)

    def test_file_type_captions_and_counts(self):
        self.assertEquals(StatisticsManager().get_sample_count_per_file_type(),
                          [('pe', 2), ('flash', 5), ('java', 3)])


class StatusStatisticsWriteTest(AbstractStatisticsTestCase):
    def setUp(self) -> None:
        super().setUp()
        self._write_values_to_redis('pe', 'status', 'timed_out', times=1)
        self._write_values_to_redis('pe', 'status', 'done', times=44)
        self._write_values_to_redis('pe', 'status', 'failed', times=6)

    def test_file_type_captions_and_counts(self):
        self.assertEquals(StatisticsManager().get_sample_count_per_status_for_type('pe'),
                          [(b'timed_out', 1), (b'done', 44), (b'failed', 6)])


class ProcessDateStatisticsWriteTest(AbstractStatisticsTestCase):
    def setUp(self) -> None:
        super().setUp()
        self._write_values_to_redis('java', 'processed_on', self.today, times=5)
        self._write_values_to_redis('java', 'processed_on', self._get_iso_formatted_days_before(1), times=1)
        self._write_values_to_redis('java', 'processed_on', self._get_iso_formatted_days_before(2), times=3)
        self._write_values_to_redis('java', 'processed_on', self._get_iso_formatted_days_before(3), times=20)

    def test_processed_on_for_file_type_captions(self):
        self.assertEquals(StatisticsManager().get_sample_counts_per_process_date('java').captions,
                          [self._get_iso_formatted_days_before(3),
                           self._get_iso_formatted_days_before(2),
                           self._get_iso_formatted_days_before(1),
                           self.today])

    def test_processed_on_for_file_type_counts(self):
        self.assertEquals(StatisticsManager().get_sample_counts_per_process_date('java').counts,
                          [20, 3, 1, 5])

    def test_processed_on_for_file_type_captions_affected_by_other_file_types(self):
        self._write_values_to_redis('pe', 'processed_on', self._get_iso_formatted_days_before(5), times=1)
        self.assertEquals(StatisticsManager().get_sample_counts_per_process_date('java').captions,
                          [self._get_iso_formatted_days_before(5),
                           self._get_iso_formatted_days_before(4),
                           self._get_iso_formatted_days_before(3),
                           self._get_iso_formatted_days_before(2),
                           self._get_iso_formatted_days_before(1),
                           self.today])

    def test_processed_on_for_file_type_counts_affected_by_other_file_types(self):
        """ The count list should be longer, but the number of samples for each bar of the
            chart should remain the same. """
        self._write_values_to_redis('pe', 'processed_on', self._get_iso_formatted_days_before(5), times=1)
        self.assertEquals(StatisticsManager().get_sample_counts_per_process_date('java').counts,
                          [0, 0, 20, 3, 1, 5])

    def test_processed_on_for_file_type_captions_affected_by_uploaded_on(self):
        self._write_values_to_redis('pe', 'processed_on', self._get_iso_formatted_days_before(4), times=1)
        self.assertEquals(StatisticsManager().get_sample_counts_per_process_date('java').captions,
                          [self._get_iso_formatted_days_before(4),
                           self._get_iso_formatted_days_before(3),
                           self._get_iso_formatted_days_before(2),
                           self._get_iso_formatted_days_before(1),
                           self.today])

    def test_processed_on_for_file_type_counts_affected_by_uploaded_on(self):
        """ The count list should be longer, but the number of samples for each bar of the
            chart should remain the same. """
        self._write_values_to_redis('pe', 'processed_on', self._get_iso_formatted_days_before(4), times=1)
        self.assertEquals(StatisticsManager().get_sample_counts_per_process_date('java').counts,
                          [0, 20, 3, 1, 5])


class UploadDateStatisticsWriteTest(AbstractStatisticsTestCase):
    def setUp(self) -> None:
        super().setUp()
        self._write_values_to_redis('java', 'uploaded_on', self.today, times=7)
        self._write_values_to_redis('java', 'uploaded_on', self._get_iso_formatted_days_before(1), times=3)
        self._write_values_to_redis('java', 'uploaded_on', self._get_iso_formatted_days_before(2), times=5)

    def test_processed_on_for_file_type_captions(self):
        self.assertEquals(StatisticsManager().get_sample_counts_per_upload_date('java').captions,
                          [self._get_iso_formatted_days_before(2),
                           self._get_iso_formatted_days_before(1),
                           self.today])

    def test_processed_on_for_file_type_counts(self):
        self.assertEquals(StatisticsManager().get_sample_counts_per_upload_date('java').counts,
                          [5, 3, 7])

    def test_processed_on_for_file_type_captions_affected_by_other_file_types(self):
        self._write_values_to_redis('pe', 'uploaded_on', self._get_iso_formatted_days_before(3), times=1)
        self.assertEquals(StatisticsManager().get_sample_counts_per_upload_date('java').captions,
                          [self._get_iso_formatted_days_before(3),
                           self._get_iso_formatted_days_before(2),
                           self._get_iso_formatted_days_before(1),
                           self.today])

    def test_processed_on_for_file_type_counts_affected_by_other_file_types(self):
        """ The count list should be longer, but the number of samples for each bar of the
            chart should remain the same. """
        self._write_values_to_redis('pe', 'uploaded_on', self._get_iso_formatted_days_before(3), times=1)
        self.assertEquals(StatisticsManager().get_sample_counts_per_upload_date('java').counts,
                          [0, 5, 3, 7])
