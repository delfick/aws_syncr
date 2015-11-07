.. _lambdas:

AWS Lambda
==========

Amazon Lambda is an execution engine that is priced by the millisecond.
It allows you to define a function of code that is executed in response to
events.

.. code-block:: yaml

  ---

  roles:
    "lambda/my_function_runner":
      description: Role that is assumed by lambda for running the lambda function
      allow_to_assume_me:
        - Principal: { Service: lambda.amazonaws.com }

      allow_permission:
        - action: ["logs:CreateLogGroup", "logs:CreateLogStream", "logs:PutLogEvents"]
          resource: "arn:aws:logs:*:*:*"

  lambda:
    my_function:
      description: random function
      role: { iam: role/lambda/my_function_runner }
      runtime: python2.7
      location: us-east-1
      memory_size: 128
      timeout: 30
      code:
        inline: |
          import json

          def lambda_handler(event, context):
            print("*:* Adding one and two in {0}".format(event))
            result = event.get("one", 0) + event.get("two", 0)

            # Return json
            ret = {"status": "OK", "output": result}

            # Print for cloudwatch logs
            print(json.dumps(ret))

            # Return for apigateway
            return result

      sample_event:
        one: 3
        two: 4
      desired_output_for_test:
        status: OK

This definition will create an IAM role that is used when running the lambda
function and a lambda function itself.

The lambda function is using python2.7 as the runtime and has the code defined
inline. The code can be defined for inline, a directory, or an object in S3.
See below for more details.

We also define a sample event and the desired output for when we invoke the
lambda function with that sample event.

Available Keys
--------------

description
  An optional sentence explaining the purpose of the function

role
  The iam role that will be assumed when running the lambda function. It's trust
  document must allow the ``lambda.amazonaws.com`` service to assume it.

runtime
  This can be ``python2.7``, ``nodejs`` or ``java8``

handler
  This is the location in the code for the lambda to execute. When the runtime
  is either python2.7 or nodejs, it will be defaulted appropriately.

  python2.7 = lambda_function.lambda_handler

  nodejs = index.handler

location
  The aws region to create this lambda function in

memory_size
  The amount of memory available to the function. This number must be a multiple
  of 64.

timeout
  The maximum amount of time the function may run for in seconds.

code
  This is the function itself and can be defined several ways

  { inline: <code> }
    As in the above example, the code can be defined within the configuration
    itself.

  { directory: <directory> }
    This will point at some directory and when it comes to creating the code, it
    will create a zipfile of that directory and upload that.

    It is recommended to refer to the directory relative to the configuration
    by saying "{config_folder}/../path/to/code".

  { directory: { directory: <directory>, exclude: [<pattern>, ...] } }
    Same as specifying a directory, but you get to exclude globs from the
    generated zipfile. Each glob is relative to that directory.

  { s3: { key: <key>, bucket: <bucket>, version: <version> } }
    Specify an object in S3 to use as the code. Version here is optional.

sample_event
  aws_syncr provides actions for testing the lambda function. When these are
  invoked, it looks for this object to use as the event object.

  This can be defined as a string or as a dictionary.

desired_output_for_test
  When aws_syncr invokes the lambda function, it'll look for this object to
  determine if the output is a success or not.

  If the output of the function is a string, then this is used as a regex against
  that string, otherwise, if it's an object, it will check that all the keys in
  desired_output_for_test exist and have the same value.

