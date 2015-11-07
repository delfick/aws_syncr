.. _apigateway:

Api Gateway
===========

Api Gateway is a service that lets you define a RESTful api to sit infront of
your lambda functions, other http apis, or your static definitions.

Jargon
------

gateway
  The entire gateway

resource
  Essentially, an endpoint. i.e. /my-endpoint.

method
  A http method (GET, POST, DELETE, etc) associated with a resource

integration
  The action a method on an endpoint does.

  The integration can transform the input before supplying to the endpoint and
  can transform the output from the action before returning it.

stage
  A version of the gateway exposed as some public url.

Example
-------

.. code-block:: yaml
  
  ---

  lambda:
    random:
      [..]

  apigatway:
    my_gateway:
      location: us-east-1

      stages:
        - prod

      api_keys:
        - name: my_key
          stages: prod

      domain_names:
        random:
          zone: company.prod.com.au
          stage: prod
          certifcate:
            name: star.company.prod.com.au
            body: { plain: [..] }
            key: { plain: [..] }
            chain: { plain: [..] }

      resources:
        /endpoint1:
          methods:
            POST:
              integration: aws
              function: "{lambda.random}"
              require_api_key: true
              sample_event: "{lambda.random.sample_event}"
              desired_output_for_test: "{lambda.random.desired_output_for_test}"

        /empty:
          methods:
            GET:
              integration: mock
              mapping: { template: "empty!" }
              require_api_key: false

.. note:: See :ref:`dns_apigateway` for how to register your custom domain name
  in route53.

So, this example creates a lambda function called ``random`` and a gateway called
``my_gateway``. The gateway has a custom domain name of
``random.company.prod.com.au`` and has two endpoints.

POST /endpoint1 will invoke the ``random`` lambda function and requires an api
key, which we have one of.

GET /empty will just return the string "empty!".

The gateway is defined in the us-east-1 region and has one stage, called prod.

Available Keys
--------------

location
  The region to deploy the gateway into

stages
  A list of stages to create for this gateway

api_keys
  A list of {name: <name>, stages: [<stage>, ...] } specifying the name of the
  key and the stages to associate the key with.

domain_names
  A dictionary of {<name>: <options>} where options are

  zone
    The zone the dns name falls under

  stage
    The stage of this gateway to associate with this domain name

  certificate
    The certificate to upload for this domain

    It is of the form {name: <name>, body: <crt file>, key: <key file>, chain: <certificate chain>}

    Where the crt file, key file and certificate chain can either be specified
    in plain text as {plain: <content>} or as a kms encrypted string of the form
    {kms: <content>, kms_data_key: <encrypted kms data key>, location: <location of the kms key>}

    See below about the ``encrypt_certificate`` task for simplifying the process
    of providing the certificate as a kms encrypted string.

resources
  A dictionary of {<endpoint>: { methods: { <method>: <options> } } where
  <method> can be any valid http method and <options> is

  integration
    Either aws or mock. If you require integration with a http api, please
    raise a github issue.

    The options for the integration depends on the chosen integration, see below
    for those options.

AWS Integration
---------------

If you choose ``aws`` as the integration for your method, then you have these
extra options available:

function
  The name of the lambda function to invoke. If you have defined your lambda
  function in the same configuration, then you may reference it as
  "{lambda.<name>}"

require_api_key
  Boolean specifying if you need an api key to access this method

sample_event
  The sample event to invoke this method with when testing

desired_output_for_test
  The desired output for when we invoke this gateway.

Sample_event and desired_output_for_test work the same as they do when defining
them for a lambda function.

Mock Integration
----------------

If you choose ``mock`` as the integration for your method, then you have these
extra options available:

mapping:
  This takes the form of {template: <template>} where <template> is the string
  to return from the integration.

require_api_key
  Boolean specifying if you need an api key to access this method

sample_event
  The sample event to invoke this method with when testing

desired_output_for_test
  The desired output for when we invoke this gateway.

Sample_event and desired_output_for_test work the same as they do when defining
them for a lambda function.

Deploying and testing the gateway
---------------------------------

To deploy the gateway, we use the ``deploy_gateway`` task::

  $ aws_syncr <environment> deploy_gateway <gateway_name> --stage <stage>

To test the gateway we use the ``test_gateway`` task::

  $ aws_syncr <environment> test_gateway <gateway_name> --stage <stage> -- <method> <resource>

For example::
  
  $ aws_syncr prod test_gateway my_gateway --stage prod -- POST /endpoint1

To test all the endpoints in the one command, we use ``test_all_gateway_endpoints``::

  $ aws_syncr <environment> test_all_gateway_endpoints <gateway_name> --stage <stage>

Encrypting certificates
-----------------------

When you define a custom domain name, you must provide the ssl certificate for
that domain. This can be defined in plain text, or as a kms encrypted string.

To define as a kms encrypted string, you may use the ``encrypt_certificate``
task.

First you must define your custom domain and where your certificate is defined.

.. code-block:: yaml

  ---

  apigateway:
    my_gateway:
      domain_names:
        my_domain:
          zone: company.prod.com.au
          stage: prod
          certificate:
            name: star.company.prod.com.au

The ``encrypt_certificate`` task will modify the file the certificate is defined
in, so it is recommended that you define the certificate in a separate file and
then reference it from your configuration.

For example::

  accounts.yaml
  prod/
    deploy.yaml
    vars.yml

In ``deploy.yaml``

.. code-block:: yaml
  
  ---

  apigateway:
    my_gateway:
      domain_names:
        my_domain:
          zone: company.prod.com.au
          stage: prod
          certificate: "{vars.certificate}"

and in ``vars.yml``


.. code-block:: yaml

  ---

  vars:
    certificate:
      name: star.company.prod.com.au

Once that is sorted out you may call::

  $ aws_syncr <environment> encrypt_certificate <domain>

For example::

  $ aws_syncr prod encrypt_certificate my_domain.company.prod.com.au

Note that defining in a seperate ``vars.yml`` also means you can have the one
``deploy.yaml`` symlinked in your environment folders and have a different
certificate per environment.

Limitations
-----------

The current implementation doesn't support the full range of possibilities with
the apigateway, if you require more granularity, please create a github issue.

