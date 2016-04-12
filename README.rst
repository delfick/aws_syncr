AWS Syncr
=========

A python application that reads YAML and syncs definitions with amazon.

It currently supports:

* Creation and modification of IAM roles permissions
* Creation of instance profiles for an IAM role
* Creation of s3 buckets
* Modification of s3 bucket policy and s3 bucket tags
* Modification of bucket website, logging and lifecycle configuration
* Creation and modification of KMS keys
* Creation and modification of KMS key grants
* Creation and modification of Lambda functions
* Creation and modification of apigateways
* Creation and modification of Route53 CNAMEs

See more documentation at http://aws_syncr.readthedocs.org

Installation
------------

aws_syncr is on pypi!::

    $ pip install aws_syncr

Running
-------

aws_syncr is designed to configure the same definition across multiple accounts.

To run it you have the following file structure::

    accounts.yaml
    <environment1>/
        config1.yaml
        config2.yaml
    <environment2>/
        config1.yaml
        config2.yaml

And then you run::

    $ aws_syncr <environment> sync

For example, let's say you have a ``dev`` environment and a ``stg`` environment::

    accounts.yaml

        ---

        accounts:
            dev: 123456789
            stg: 382093840

    roles.yaml

        ---

        roles:
            my_role:
                [..]

    dev/
        roles.yaml - symlink to ../roles.yaml

    stg/
        roles.yaml - symlink to ../roles.yaml

Then from that folder::

    $ aws_syncr dev sync --dry-run
    $ aws_syncr dev sync

Or if you are not in that folder::

    $ AWS_SYNCR_CONFIG_FOLDER=<folder> aws_syncr [..]

Tests
-----

Run the following::

    $ pip install -e .
    $ pip install -e ".[tests]"
    $ ./test.sh

Or use tox::

    $ tox

