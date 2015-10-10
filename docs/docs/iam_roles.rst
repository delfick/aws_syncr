.. _iam_role:

IAM Roles
=========

IAM is amazon's access management service. You use this service to create
user accounts and roles. Aws_syncr currently only supports creating and
modifying roles. These can be created under the ``roles`` section of your
configuration.

.. code-block:: yaml

  ---

  roles:
    "ci/deployer":
      description: Role for deploying my amazing application
      allow_to_assume_me:
        - { iam: "role/bamboo/bamboo-agent-role", account: devprod }
        - { iam: "assumed-role/Stg-Administrator", account: stg, users: [smoore] }
        - { iam: "assumed-role/Dev-Administrator", account: dev, users: [smoore] }

      allow_permission:
        - { action: "ec2:*", resource: "*" }
        - { action: "route53:*", resource: "*" }
        - { action: "autoscaling:*", resource: "*" }
        - { action: "cloudformation:*", resource: "*" }
        - { action: "elasticloadbalancing:*", resource: "*"}

        - { action: "s3:*", resource: { "s3": "project-artifacts"} }

        - { action: "iam:*", resource: { "iam": "__self__" } }
        - { action: "iam:*", resource: { "iam": "role/project/*" } }
        - { action: "iam:*", resource: { "iam": "instance-profile/project/*" } }

    "project/instance":
      description: Instance role for my project
      make_instance_profile: true

      allow_to_assume_me:
        - service: ec2

      allow_permission:
        - { action: "s3:*", resource: { "s3": "project-artifacts" } }
        - { action: "iam:*", resource: { "iam": "__self__" } }

This definition will create a role called ``deployer`` with a path of ``ci`` and a role called
``instance`` with a path of ``project``.

This definition make it so ``deployer`` has this trust policy

.. code-block:: json

    {
      "Version": "2012-10-17",
      "Statement": [
        {
          "Sid": "",
          "Effect": "Allow",
          "Principal": {
            "AWS": "arn:aws:iam::892834939:role/bamboo/bamboo-agent-role"
          },
          "Action": "sts:AssumeRole"
        },
        {
          "Sid": "",
          "Effect": "Allow",
          "Principal": {
            "AWS": "arn:aws:sts::382093840:assumed-role/Stg-Administrator/smoore"
          },
          "Action": "sts:AssumeRole"
        },
        {
          "Sid": "",
          "Effect": "Allow",
          "Principal": {
            "AWS": "arn:aws:sts::123456789:assumed-role/Dev-Administrator/smoore"
          },
          "Action": "sts:AssumeRole"
        },
      ]
    }

And the ``instance`` role has this trust policy

.. code-block:: json

    {
      "Version": "2012-10-17",
      "Statement": [
        {
          "Sid": "",
          "Effect": "Allow",
          "Principal": {
            "Service": "ec2.amazonaws.com"
          },
          "Action": "sts:AssumeRole"
        }
      ]
    }

The ``allow_permission`` block of the definition will create this inline policy
for ``deployer``.

.. code-block:: json

    {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Action": [
                    "ec2:*"
                ],
                "Resource": [
                    "*"
                ],
                "Effect": "Allow"
            },
            {
                "Action": [
                    "route53:*"
                ],
                "Resource": [
                    "*"
                ],
                "Effect": "Allow"
            },
            {
                "Action": [
                    "autoscaling:*"
                ],
                "Resource": [
                    "*"
                ],
                "Effect": "Allow"
            },
            {
                "Action": [
                    "cloudformation:*"
                ],
                "Resource": [
                    "*"
                ],
                "Effect": "Allow"
            },
            {
                "Action": [
                    "elasticloadbalancing:*"
                ],
                "Resource": [
                    "*"
                ],
                "Effect": "Allow"
            },
            {
                "Action": [
                    "s3:*"
                ],
                "Resource": [
                    "arn:aws:s3:::project-artifacts",
                    "arn:aws:s3:::project-artifacts/*"
                ],
                "Effect": "Allow"
            },
            {
                "Action": [
                    "iam:*"
                ],
                "Resource": [
                    "arn:aws:iam::123456789:role/ci/deployer"
                ],
                "Effect": "Allow"
            },
            {
                "Action": [
                    "iam:*"
                ],
                "Resource": [
                    "arn:aws:iam::123456789:role/project/*"
                ],
                "Effect": "Allow"
            },
            {
                "Action": [
                    "iam:*"
                ],
                "Resource": [
                    "arn:aws:iam::023709156796:instance-profile/project/*"
                ],
                "Effect": "Allow"
            }
        ]
    }

and the following policy for ``instance``

.. code-block:: json

    {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Effect": "Allow",
                "Action": "s3:*",
                "Resource": [
                    "arn:aws:s3:::project-artifacts",
                    "arn:aws:s3:::project-artifacts/*"
                ]
            },
            {
                "Effect": "Allow",
                "Action": "iam:*",
                "Resource": "arn:aws:iam::123456789:role/project/instance"
            }
        ]
    }

And when you sync with ``stg``, then the appropriate account ids in the policies
are replaced with the ``stg`` account id.

Available keys
--------------

You can specify the following options for each role:

description
  The description given to the role

make_instance_profile
  A boolean specifying whether to make an instance profile of the same name
  with this role attached to it.

allow_to_assume_me, disallow_to_assume_me
  Used for allowing or disallowing certain trust relationships.

permission, allow_permission, deny_permission
  Used for specifying statements to go into the role policy.

Statements
----------

Go to the :ref:`statements` section to see what are valid statements for the
trust policy and role policy.

