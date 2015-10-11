.. _statements:

Statements
==========

You can specify iam role policies, iam role trust policies, s3 bucket policies
and kms grants with aws_syncr.

Trust policies
--------------

``{service: ec2}``
   Sets the principle to ``{"Service": "ec2.amazonaws.com"}``

   You'll want to do this if you want to use metdata credentials on an ec2 box

``<iam_specifier>``
   See below, it specifies an iam resource

   Basically allows the iam role specified to call assume role to be this role.

``{federated: <string>}``
   Sets the principle to ``{"Federated": <string>}``

   With an ``Action`` of ``AssumeRoleWithSAML``.

``{federated: <iam_specifier>}``
   Sets the principle to ``{"Federated": <expanded iam specifier>}``

   With an ``Action`` of ``AssumeRoleWithSAML``.

Anything in the dictionary starting with an upper case character is included as
is in the statement.

Also, the difference between ``allow_to_assume_me`` and ``disallow_to_assume_me``
is one sets ``Principle`` in the trust document, whereas the other sets ``NotPrinciple``.

Permission statements
---------------------

You can specify these under a role policy and under an s3 bucket policy

``{"action": <action>, resource: <resource>, "allow":<True|False>}``
   Allows ``<action>`` for specified ``<resource>`` (string or list of strings)

   "allow" will override any default allow or "Effect" you specify

   And anything starting with an upper case character is included in the
   statement as is.

   ``allow_permission`` statements will default ``allow`` to True and
   ``deny_permission`` statements will default ``allow`` to False.

Where ``action`` and ``resource`` can be ``notaction`` and ``notresource``.

And ``<resource>`` can be:

A single string
   Placed in the policy as a list of that one string

A list of ``<resource>``
   Placed in the policy with each ``<resource>`` expanded

``<iam_specifier>``
   See below, it specifies an iam resource

``<kms_specifier>``
   See below, it specifies a kms resource

``{"s3": <s3_specifier>}``
   "arn:aws:s3:::<s3_specifier>

``{"s3": [<s3_specifier>, <s3_specifier>, ...]}``
   ["arn:aws:s3:::<s3_specifier>", "arn:aws:s3:::<s3_specifier>", ...]

``<arn_specifier>``
   See below, it specifies a generic arn

Where ``<iam_specifer>`` can be:

``{"iam":"__self__"}``
   arn for the role/user this policy is being given to

``{"iam":<specifier>, "account":<account>"}``
   "arn:aws:iam::<account>:<specifier>"

   Where account is retrieved from our accounts dictionary from accounts.yaml

Where ``<kms_specifier>`` can be:

``{"kms": "__self__"}``
    arn for the kms this policy is being given to

``{"kms": "<alias>", "location":<location>, "account":<account>}``
    "arn:aws:kms::<account>:alias/<alias>"

    Where account is retrieved from our accounts dictionary from accounts.yaml

Where ``<s3_specifier>`` can be:

``__self__``
  arn for the bucket this policy is being given to

``<name>``
  Name of a bucket

``<name>/<path>``
  Name of a bucket with some path

Where ``<arn_specifier>`` is

``{"arn":<service>, "location":<location>, "account":<account>, "identity":<identity>}``
    "arn:aws:<service>:<location>:<account>:<identity>"

.. note:: For the special specifiers, account and identity can be a list of
  values.

Grant statements
----------------

Grants can be specified as

``{"operations": [<operation>, ...], "grantee": [<iam_specifier>, ...], "retiree": [<iam_specifer>, ...], "grant_tokens": [<grant_token>, ...], "constraints": <constraints>}``

  Only ``operations`` and ``grantee`` are required. Also, capitalized keys
  are included in the policy.

See http://docs.aws.amazon.com/kms/latest/developerguide/grants.html for more
information.

