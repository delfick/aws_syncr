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
      require_mfa_to_delete: true
  
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
        },
        {
          "Sid": "",
          "Effect": "Allow",
          'Resource': [
            'arn:aws:s3:::project-artifacts',
            'arn:aws:s3:::project-artifacts/*'
          ],
          'Action': 's3:DeleteBucket'
          'Condition': {'Bool': {'aws:MultiFactorAuthPresent': True}},
        }
      ]
    }

Note that the ``require_mfa_to_delete`` option is a shortcut for that last
policy so that you require an mfa device to delete the bucket and anything in it.

Available Keys
--------------

You can use the following keys when defining a bucket:

location
    The region to place the bucket in.

require_mfa_to_delete:
    Whether to include a permission to only allow deletion if an mfa device is
    used

tags
    A dictionary of {Key:Value} tags to attach to the bucket

permission, allow_permission, deny_permission
    Used to specify statements for the bucket policy

Statements
----------

See the :ref:`statements` section for more information of what can go into the
bucket policy.

Logging Configuration
---------------------

We can specify access logs for the bucket to be placed in another s3 bucket with
the ``logging`` key:

.. code-block:: json

  buckets:
    amazing_bucket:
      location: ap-southeast-2

      logging:
        prefix: amazing_bucket/
        destination: my_bucket_logs

This will make access logs go into ``s3://my_bucket_logs/amazing_bucket``.

See http://docs.aws.amazon.com/AmazonS3/latest/UG/ManagingBucketLogging.html for
more information.

Website Configuration
---------------------

You can also specify website configuration for the bucket with the ``website``
key:

.. code-block:: json

  buckets:
    my_public_website.com:
      location: ap-southeast-2

      website:
        redirect_all_requests_to: "www.my_public_website.com"

    www.my_public_website.com:
      location: ap-southeast-2

      website:
        index_document: index.html
        error_document: error.html

This will create two buckets, both with a website configuration. The first bucket
``my_public_website.com`` will have a website configuration equal to:

.. code-block:: json

  { "IndexDocument": None
  , "ErrorDocument": None
  , "RedirectAllRequestsTo":
    { "HostName": "www.my_public_website.com"
    }
  , "RoutingRules": None
  }

And the second bucket ``www.my_public_website.com`` will have this website config:

.. code-block:: json

  { "IndexDocument": { "Suffix": "index.html" }
  , "ErrorDocument": { "Key": "error.html" }
  , "RedirectAllRequestsTo": None
  , "RoutingRules": None
  }

Note that ``RoutingRules`` can be specified as ``RoutingRules`` and will be put
into the policy as is.

For more information on what these configurations mean, see
http://docs.aws.amazon.com/AmazonS3/latest/dev/HowDoIWebsiteConfiguration.html
