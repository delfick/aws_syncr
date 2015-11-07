.. _dns:

Route 53
========

Route53 is Amazon's Domain Name Service. AWS Syncr let's you use this service to
define CNAME records.

.. code-block:: yaml

    ---

    dns:
      my-record:
        zone: my-zone.com.au
        record_type: CNAME
        record_target: somewhere.else.com.au

This definition will create a CNAME for ``my-record.my-zone.com.au`` that points
at ``somewhere.else.com.au``.

Available Keys
--------------

zone
  The DNS zone the record goes under

record_type
  Currently CNAME is the only supported record type. Please create a github issue
  if you want it to support other record types.

record_target
  The address the CNAME points at

.. _dns_apigateway:

ApiGateway
----------

There is integration with apigateway in that you can define the record_target as
``apigateway.<gateway_name>.domain_names.<domain_name>`` and aws_syncr will
determine the cloudfront url for that domain.

For example:

.. code-block:: yaml

  ---

  vars:
    zone: company.prod.com.au
    certifcate:
      [..]

  apigateway:
    monitors:
      stages:
        - prod

      domain_names:
        monitoring:
          zone: "{vars.zone}"
          stage: prod
          certificate: "{vars.certificate}"

      resources:
        [..]

  dns:
    monitoring:
      zone: "{vars.zone}"
      record_type: CNAME
      record_target: "{apigateway.monitors.domain_names.monitoring}"

This will create an apigateway with a registered custom domain name, and then
register the domain name itself with route53 to the value it needs to be.

