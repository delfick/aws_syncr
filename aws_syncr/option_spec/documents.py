from aws_syncr.errors import InvalidDocument

from input_algorithms.dictobj import dictobj

import json

class Document(dictobj):
    fields = ["statements"]

    @property
    def document(self):
        if not self.statements:
            return None

        document = {"Version": "2012-10-17", "Statement": [s.statement for s in self.statements]}

        try:
            return json.dumps(document, indent=2)
        except (TypeError, ValueError) as err:
            raise InvalidDocument("Document wasn't valid json", error=err, document=document)

