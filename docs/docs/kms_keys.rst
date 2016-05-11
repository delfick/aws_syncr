.. _kms_keys:

KMS keys
========

KMS is an amazon service for encrypting and decrypting data. Amazon will store a
Master key in it's infrastructure and never let's you have access to it. You
then use the API to send data to it for decryption/encryption.

Access is controlled through the policy on the key directly and through what
are called ``grants``.

These keys can be defined under the ``encryption_keys`` section of your
configuration:

.. code-block:: yaml

    ---

    encryption_keys:
      project:
        location: 'ap-southeast-2'
        description: Key for my amazing project`
        admin_users:
            - { iam: role/encryption/encryptor }

        grant:
          - grantee: { iam: "role/ci/project-encryptor" }
            operations: [ "Encrypt", "GenerateDataKey", "GenerateDataKeyWithoutPlaintext" ]

          - grantee: { iam: "role/encryption/project-decryptor" }
            operations: [ "Decrypt" ]

Here we've defined a key with an alias of ``project`` that sits in the
``ap-southeast-2`` region. It has a description and two grants allowing an
encryptor role the ability to encrypt and a decryptor role the ability to
decrypt.

Available keys
--------------

You can use the following keys when defining your key:

location
    The region to put the key in

description
    The description for the key

grant
    A list of grants to apply to the key

permission
    A list of policies to add to the key policy

admin_users
    A list of iam users to add ``kms:*`` permissions for in the key policy

Statements
----------

See the :ref:`statements` section for what is valid in a grant.

