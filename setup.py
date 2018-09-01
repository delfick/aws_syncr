from setuptools import setup, find_packages
from aws_syncr import VERSION

setup(
      name = "aws_syncr"
    , version = VERSION
    , packages = ['aws_syncr'] + ['aws_syncr.%s' % pkg for pkg in find_packages('aws_syncr')]
    , include_package_data = True

    , install_requires =
      [ "delfick_app==0.9.6"
      , "option_merge==1.6"
      , "input_algorithms==0.6.0"

      , "datadiff"
      , "requests"

      , "boto3==1.7.69"
      , "pyYaml==3.13"
      , 'pycryptodome==3.6.6'
      ]

    , extras_require =
      { "tests":
        [ "noseOfYeti>=1.5.0"
        , "nose"
        , "mock==1.0.1"
        , "tox"
        ]
      }

    , entry_points =
      { 'console_scripts' :
        [ 'aws_syncr = aws_syncr.executor:main'
        ]
      }

    # metadata for upload to PyPI
    , url = "https://github.com/delfick/aws_syncr"
    , author = "Stephen Moore"
    , author_email = "delfick755@gmail.com"
    , description = "Application that reads yaml and syncs definitions with amazon"
    , long_description = open("README.rst").read()
    , license = "MIT"
    , keywords = "aws"
    )
