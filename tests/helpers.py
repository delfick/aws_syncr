from input_algorithms.errors import DeprecatedKey, BadSpecValue
from unittest import TestCase as UnitTestTestCase
from delfick_error import DelfickErrorTestMixin
from contextlib import contextmanager
import tempfile
import shutil
import os

class TestCase(UnitTestTestCase, DelfickErrorTestMixin):
    def assertSortedEqual(self, listone, listtwo):
        self.assertEqual(sorted(listone), sorted(listtwo))

    @contextmanager
    def a_file(self, contents=None, removed=False):
        location = None
        try:
            location = tempfile.NamedTemporaryFile(delete=False).name
            if contents:
                with open(location, 'w') as fle:
                    fle.write(contents)
            if removed:
                os.remove(location)
            yield location
        finally:
            if location and os.path.exists(location):
                os.remove(location)

    @contextmanager
    def a_directory(self, removed=False):
        location = None
        try:
            location = tempfile.mkdtemp()
            if removed:
                shutil.rmtree(location)
            yield location
        finally:
            if location and os.path.exists(location):
                shutil.rmtree(location)

    @contextmanager
    def assertRaisesDeprecated(self, key, reason, meta):
        depre = DeprecatedKey(key=key, reason=reason, meta=meta)
        with self.fuzzyAssertRaisesError(BadSpecValue, "Failed to validate", _errors=[depre]):
            yield

