from datadiff import diff
import logging
import json
import six

log = logging.getLogger("aws_syncr.operations.differ")

class Differ(object):
    @classmethod
    def compare_two_documents(kls, doc1, doc2):
        """Compare two documents by converting them into json objects and back to strings and compare"""
        first = doc1
        if isinstance(doc1, six.string_types):
            try:
                first = json.loads(doc1)
            except (ValueError, TypeError) as error:
                log.warning("Failed to convert doc into a json object\terror=%s", error)
                yield error.args[0]
                return

        second = doc2
        if isinstance(doc2, six.string_types):
            try:
                second = json.loads(doc2)
            except (ValueError, TypeError) as error:
                log.warning("Failed to convert doc into a json object\terror=%s", error)
                yield error.args[0]
                return

        # Ordering the principals because the ordering amazon gives me hates me
        def sort_statement(statement):
            for principal in (statement.get("Principal", None), statement.get("NotPrincipal", None)):
                if principal:
                    for principal_type in ("AWS", "Federated", "Service"):
                        if principal_type in principal and type(principal[principal_type]) is list:
                            principal[principal_type] = sorted(principal[principal_type])
        def sort_key(statement, key):
            if key in statement and type(statement[key]) is list:
                statement[key] = sorted(statement[key])
        for document in (first, second):
            if "Statement" in document:
                if type(document["Statement"]) is dict:
                    sort_statement(document["Statement"])
                    sort_key(document["Statement"], "Action")
                    sort_key(document["Statement"], "NotAction")
                    sort_key(document["Statement"], "Resource")
                    sort_key(document["Statement"], "NotResource")
                else:
                    for statement in document["Statement"]:
                        sort_statement(statement)
                        sort_key(statement, "Action")
                        sort_key(statement, "NotAction")
                        sort_key(statement, "Resource")
                        sort_key(statement, "NotResource")

        difference = diff(first, second, fromfile="current", tofile="new").stringify()
        if difference:
            lines = difference.split('\n')
            if not first or not second or first != second:
                for line in lines:
                    yield line

