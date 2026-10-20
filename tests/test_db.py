import pytest

from app import db


def test_unknown_job_field_is_rejected_before_touching_the_database():
    # column names can't be SQL parameters, so the allow-list is what keeps update_job injection-safe
    with pytest.raises(ValueError, match="Unknown job fields"):
        db.update_job("job-1", **{"status = 'completed'; DROP TABLE jobs; --": "x"})
