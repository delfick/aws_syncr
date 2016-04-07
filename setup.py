from setuptools import setup, find_packages
from aws_syncr import VERSION

setup(
      name = "aws_syncr"
    , version = VERSION
    , packages = ['aws_syncr'] + ['aws_syncr.%s' % pkg for pkg in find_packages('aws_syncr')]
    , include_package_data = True

    , install_requires =
      [ "delfick_app==0.7.4.1"
      , "option_merge==0.9.9.7"
      , "input_algorithms==0.4.5.5"

      , "six"
      , "datadiff"
      , "requests"

      , "boto3==1.2.1"
      , "pyYaml==3.10"
      , 'pycrypto==2.6.1'
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
    , author_email = "stephen.moore@rea-group.com"
    , description = "Application that reads yaml and syncs definitions with amazon"
    , license = "WTFPL"
    , keywords = "aws"
    )

