.. _s3_buckets:

S3 Buckets
==========

S3 is amazon's storage solution and implements a blob store for your data.
It is designed such that you have buckets in particular regions and store your
data as key to blob. These buckets can be created under the ``buckets`` section
of your configuration.

.. code-block:: yaml

  ---

  buckets:
    project-artifacts:
      location: ap-southeast-2
  
      tags:
        application: Artifacts
  
      allow_permission:
        - resource: {s3: __self__ }
          action: ["s3:Get*", "s3:List*"]
          principal:
            - iam: role
              account: [stg, prod]
              users:
                - ci/project1-deployer
                - ci/project2-deployer
 
This will create a bucket called ``project-artifacts`` in the ``ap-southeast-2``
region with an ``application`` tag equal to ``Artifacts`` and the following
bucket policy:

.. code-block:: json

    {
      "Version": "2012-10-17",
      "Statement": [
        {
          "Sid": "",
          "Effect": "Allow",
          "Principal": {
            "AWS": [
              "arn:aws:iam::991147164:role/ci/project1-deployer",
              "arn:aws:iam::382093840:role/ci/project1-deployer",
              "arn:aws:iam::991147164:role/ci/project2-deployer",
              "arn:aws:iam::382093940:role/ci/project2-deployer",
            ]
          },
          "Action": [
            "s3:List*",
            "s3:Get*"
          ],
          "Resource": [
            "arn:aws:s3:::project-artifacts",
            "arn:aws:s3:::project-artifacts/*"
          ]
        }
      ]
    }

Available Keys
--------------

You can use the following keys when defining a bucket:

location
    The region to place the bucket in.

tags
    A dictionary of {Key:Value} tags to attach to the bucket

permission, allow_permission, deny_permission
    Used to specify statements for the bucket policy

Statements
----------

See the :ref:`statements` section for more information of what can go into the
bucket policy.

