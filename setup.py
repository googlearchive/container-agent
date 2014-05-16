from setuptools import setup

setup(
  name = 'container-agent',
  version = '0.0.1',
  license = 'Apache 2.0',
  install_requires = [
    'pyyaml',
  ],
  packages = ['container_agent'],
  entry_points = {
    'console_scripts': [
      'container-agent = container_agent.run_containers:run'
    ],
  },
)
