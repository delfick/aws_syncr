# coding: spec

from aws_syncr.option_spec.documents import Document
from aws_syncr.errors import InvalidDocument

from tests.helpers import TestCase
import json
import mock

describe TestCase, "Document":
    it "Returns json with Version and statements":
        s1 = mock.Mock(name="s1", statement="911d45ba-6fd2-11e5-9078-c8600005e21b")
        s2 = mock.Mock(name="s2", statement="9950ad9e-6fd2-11e5-9078-c8600005e21b")
        s3 = mock.Mock(name="s3", statement="a171e52e-6fd2-11e5-9078-c8600005e21b")
        statements = [s1, s2, s3]
        document = Document(statements)
        self.assertEqual(document.document, json.dumps({"Version": "2012-10-17", "Statement": [s1.statement, s2.statement, s3.statement]}, indent=2))

    it "complains if the statements make invalid json":
        s1 = mock.Mock(name="s1", statement=lambda: 4)
        statements = [s1]
        document = Document(statements)
        with self.fuzzyAssertRaisesError(InvalidDocument, "Document wasn't valid json"):
            self.assertEqual(document.document, json.dumps({"Version": "2012-10-17", "Statement": [s1.statement]}, indent=2))
