#!/usr/bin/python

# Copyright 2014 Google Inc. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Launch containers specified by a Google container manifest.

This program interprets a blob of JSON or YAML as a container manifest and
launches those containers.  This assumes that the system's docker daemon runs
with the -r=false flag, otherwise the docker daemon itself will try to do
restarts whenever it gets a signal itself.

This will read one file, specified on the commandline, or stdin if no file is
provided.

This will log to syslog's LOCAL3 facility.

On networking:  This program assumes that all of the containers in the manifest
constitute a group.  For simplicity, a group shares a network namespace (via
--net=container:<name>).  This means that all containers can see each other as
"localhost", but it also means that the set of ports they use must be unique
across the group.  We want to revisit this.

Environmental requirements:
  - Docker 0.11 or higher (for the --net flag)
  - Docker daemon runs with =r=false (for safer restart behavior)

"""

import os
import re
import subprocess
import sys
import syslog
import time
import yaml


PROGNAME = 'containervm-agent'

SUPPORTED_CONFIG_VERSIONS = ['v1beta1']

PROTOCOL_TCP = 'TCP'
PROTOCOL_UDP = 'UDP'
VALID_PROTOCOLS = [PROTOCOL_TCP, PROTOCOL_UDP]

RE_RFC1035_NAME = re.compile(r"^[a-z]([-a-z0-9]*[a-z0-9])*$")
RE_C_TOKEN = re.compile(r"[A-Za-z_]\w*$")
MAX_PATH_LEN = 512

DOCKER_CMD = 'docker'
VOLUMES_ROOT_DIR = '/export'
LOG_CMD = 'logger -p local3.info -t %s --' % (PROGNAME)

KEEPALIVE_SCRIPT = """
  while true; do
    read PID </proc/self/stat; PID=$(echo $PID | cut -f1 -d' ');
    %(log)s "keepalive for container '%(name)s' (%(id)s) running as PID $PID";
    STATUS=$(%(docker)s wait '%(id)s' 2>/dev/null);
    %(log)s "container '%(name)s' (%(id)s) exited with status " $STATUS;
    if ! %(docker)s inspect '%(id)s' >/dev/null 2>&1; then
      %(log)s "container '%(name)s' (%(id)s) no longer exists: " \
          "halting keepalive (PID $PID)";
      break;
    fi;
    sleep 1;
    %(log)s "container '%(name)s' (%(id)s) restarting";
    %(docker)s restart '%(id)s' >/dev/null 2>&1;
  done &
  """


def LogInfo(msg):
    syslog.syslog(syslog.LOG_LOCAL3 | syslog.LOG_INFO, msg)


def LogError(msg):
    syslog.syslog(syslog.LOG_LOCAL3 | syslog.LOG_ERR, msg)


def Fatal(*args):
    """Logs a fatal error to syslog and stderr and exits."""
    err_str = 'FATAL: ' + ' '.join(map(str, args))
    sys.stderr.write(err_str + '\n')
    LogError(err_str)
    # TODO(thockin): It would probably be cleaner to raise an exception.
    sys.exit(1)


def IsValidProtocol(proto):
    return proto in VALID_PROTOCOLS


def ProtocolString(proto):
    if proto == PROTOCOL_UDP:
        return '/udp'
    return ''


def IsValidPort(port):
    return 0 < port <= 65535


def IsRfc1035Name(name):
    return RE_RFC1035_NAME.match(name)


def IsCToken(name):
    return RE_C_TOKEN.match(name)


def IsValidPath(path):
    return path[0] == '/' and len(path) <= MAX_PATH_LEN


def LoadVolumes(volumes):
    """Process a "volumes" block of config and return a list of volumes."""

    # TODO(thockin): could be a map of name -> Volume
    all_vol_names = []
    for vol_index, vol in enumerate(volumes):
        # Get the container name.
        if 'name' not in vol:
            Fatal('volumes[%d] has no name' % (vol_index))
        vol_name = vol['name']
        if not IsRfc1035Name(vol_name):
            Fatal('volumes[%d].name is invalid: %s' % (vol_index, vol_name))
        if vol_name in all_vol_names:
            Fatal('volumes[%d].name is not unique: %s' % (vol_index, vol_name))
        all_vol_names.append(vol_name)

    return all_vol_names


# TODO(thockin): We should probably fail on unknown fields in JSON objects.
class Container(object):

    """The accumulated parameters to start a Docker container."""

    # Only allow the supported params.
    __slots__ = ('name', 'image', 'command', 'hostname', 'working_dir',
                 'ports', 'mounts', 'env_vars', 'network_from')

    def __init__(self, name, image):
        self.name = name          # required str
        self.image = image        # required str
        self.command = []         # list[str]
        self.hostname = None      # str
        self.working_dir = None   # str
        self.ports = []           # [(int, int, str)]
        self.mounts = []          # [str]
        self.env_vars = []        # [str]
        self.network_from = None  # str


def LoadInfraContainers(user_containers):
    """Return a list of infrastructural containers required for this group."""

    # Shared network namespace.
    net_ctr = Container('.net', 'busybox')
    net_ctr.command = ['sh', '-c', 'rm -f nap && mkfifo nap && exec cat nap']
    for user_ctr in user_containers:
        # The port flags must be on the shared network container.
        # This seems like a bug in Docker.

        net_ctr.ports.extend(user_ctr.ports)
        user_ctr.ports = []

    return [net_ctr]


def LoadUserContainers(containers, all_volumes):
    """Process a "containers" block of config and return a list of
    containers."""

    # TODO(thockin): could be a dict of name -> Container
    all_ctrs = []
    all_ctr_names = []
    for ctr_index, ctr_spec in enumerate(containers):
        # Verify the container name.
        if 'name' not in ctr_spec:
            Fatal('containers[%d] has no name' % (ctr_index))
        if not IsRfc1035Name(ctr_spec['name']):
            Fatal('containers[%d].name is invalid: %s'
                  % (ctr_index, ctr_spec['name']))
        if ctr_spec['name'] in all_ctr_names:
            Fatal('containers[%d].name is not unique: %s'
                  % (ctr_index, ctr_spec['name']))
        all_ctr_names.append(ctr_spec['name'])

        # Verify the container image.
        if 'image' not in ctr_spec:
            Fatal('containers[%s] has no image' % (ctr_spec['name']))

        # The current accumulation of parameters.
        current_ctr = Container(ctr_spec['name'], ctr_spec['image'])

        # Always set the hostname for user containers.
        current_ctr.hostname = current_ctr.name

        # Get the commandline.
        current_ctr.command = ctr_spec.get('command', [])

        # Get the initial working directory.
        current_ctr.working_dir = ctr_spec.get('workingDir', None)
        if current_ctr.working_dir is not None:
            if not IsValidPath(current_ctr.working_dir):
                Fatal('containers[%s].workingDir is invalid: %s'
                      % (current_ctr.name, current_ctr.working_dir))

        # Get the list of port mappings.
        current_ctr.ports = LoadPorts(
            ctr_spec.get('ports', []), current_ctr.name)

        # Get the list of volumes to mount.
        current_ctr.mounts = LoadVolumeMounts(
            ctr_spec.get('volumeMounts', []), all_volumes, current_ctr.name)

        # Get the list of environment variables.
        current_ctr.env_vars = LoadEnvVars(
            ctr_spec.get('env', []), current_ctr.name)

        # Set the network linkage.
        current_ctr.network_from = 'container:.net'

        all_ctrs.append(current_ctr)

    return all_ctrs


def LoadPorts(ports_spec, ctr_name):
    """Process a "ports" block of config and return a list of ports."""

    # TODO(thockin): could be a dict of name -> Port
    all_ports = []
    all_port_names = []
    all_host_port_nums = []

    for port_index, port_spec in enumerate(ports_spec):
        if 'name' in port_spec:
            port_name = port_spec['name']
            if not IsRfc1035Name(port_name):
                Fatal('containers[%s].ports[%d].name is invalid: %s'
                      % (ctr_name, port_index, port_name))
            if port_name in all_port_names:
                Fatal('containers[%s].ports[%d].name is not unique: %s'
                      % (ctr_name, port_index, port_name))
            all_port_names.append(port_name)
        else:
            port_name = str(port_index)

        if 'containerPort' not in port_spec:
            Fatal('containers[%s].ports[%s] has no containerPort'
                  % (ctr_name, port_name))
        ctr_port = port_spec['containerPort']
        if not IsValidPort(ctr_port):
            Fatal('containers[%s].ports[%s].containerPort is invalid: %d'
                  % (ctr_name, port_name, ctr_port))

        host_port = port_spec.get('hostPort', ctr_port)
        if not IsValidPort(host_port):
            Fatal('containers[%s].ports[%s].hostPort is invalid: %d'
                  % (ctr_name, port_name, host_port))
        if host_port in all_host_port_nums:
            Fatal('containers[%s].ports[%s].hostPort is not unique: %d'
                  % (ctr_name, port_name, host_port))
        all_host_port_nums.append(host_port)

        proto = port_spec.get('protocol', 'TCP')
        if not IsValidProtocol(proto):
            Fatal('containers[%s].ports[%s].protocol is invalid: %s'
                  % (ctr_name, port_name, proto))

        all_ports.append((host_port, ctr_port, ProtocolString(proto)))

    return all_ports


def LoadVolumeMounts(mounts_spec, all_volumes, ctr_name):
    """Process a "volumeMounts" block of config and return a list of mounts."""

    # TODO(thockin): Could be a dict of name -> Mount
    all_mounts = []
    for vol_index, vol_spec in enumerate(mounts_spec):
        if 'name' not in vol_spec:
            Fatal('containers[%s].volumeMounts[%d] has no name'
                  % (ctr_name, vol_index))
        vol_name = vol_spec['name']
        if not IsRfc1035Name(vol_name):
            Fatal('containers[%s].volumeMounts[%d].name'
                  'is invalid: %s'
                  % (ctr_name, vol_index, vol_name))
        if vol_name not in all_volumes:
            Fatal('containers[%s].volumeMounts[%d].name'
                  'is not a known volume: %s'
                  % (ctr_name, vol_index, vol_name))

        if 'path' not in vol_spec:
            Fatal('containers[%s].volumeMounts[%s] has no path'
                  % (ctr_name, vol_name))
        vol_path = vol_spec['path']
        if not IsValidPath(vol_path):
            Fatal('containers[%s].volumeMounts[%s].path is invalid: %s'
                  % (ctr_name, vol_name, vol_path))

        read_mode = 'ro' if vol_spec.get('readOnly', False) else 'rw'

        all_mounts.append(
            '%s/%s:%s:%s' % (VOLUMES_ROOT_DIR, vol_name, vol_path, read_mode))

    return all_mounts


def LoadEnvVars(env_spec, ctr_name):
    """Process an "env" block of config and return a list of env vars."""

    # TODO(thockin): could be a dict of key -> value
    all_env_vars = []
    for env_index, env_spec in enumerate(env_spec):
        if 'key' not in env_spec:
            Fatal('containers[%s].env[%d] has no key' % (ctr_name, env_index))
        env_key = env_spec['key']
        if not IsCToken(env_key):
            Fatal('containers[%s].env[%d].key is invalid: %s'
                  % (ctr_name, env_index, env_key))

        if 'value' not in env_spec:
            Fatal('containers[%s].env[%s] has no value' % (ctr_name, env_key))
        env_val = env_spec['value']

        all_env_vars.append('%s=%s' % (env_key, env_val))

    return all_env_vars


def CheckGroupWideConflicts(containers):
    # TODO(thockin): we could put other uniqueness checks (e.g. name) here.
    # Make sure not two containers have conflicting host or container ports.
    host_ports = set()
    ctr_ports = set()
    for ctr in containers:
        for port in ctr.ports:
            h = '%s%s' % (port[0], port[2])
            if h in host_ports:
                Fatal('host port %s is not unique group-wide' % (h))
            host_ports.add(h)
            c = '%s%s' % (port[1], port[2])
            if c in ctr_ports:
                Fatal('container port %s is not unique group-wide' % (c))
            ctr_ports.add(c)


def FlagList(values, flag):
    """Turns a list of values into a list of flags.

    This takes a list of strings, and produces a new list with an extra string
    ('flag') between each value.

    Args:
      values: a list of strings
      flag: a string

    Returns:
      the expanded list of strings

    Example:
      FlagList(["a", "b", "c"], "-x") => ["-x", "a", "-x", "b", "-x", "c"]

    """

    result = []
    for v in values:
        result.extend([flag, v])
    return result


def FlagOrNothing(value, flag):
    """Turns a value into a flag list iff value is not None."""
    if value is not None:
        return [flag, value]
    return []


def RunContainers(containers):
    # TODO(thockin): This does not remove containers which used to be in the
    # config but are not any more.
    for ctr in containers:
        # Log and run the container, with a keepalive if needed.
        # TODO(thockin): We would have a distinct log file per-group,
        # but we only support one group.
        LogInfo("starting container '%s'" % (ctr.name))

        # Pull the image.  Retry for up to 30 seconds.
        for pulls_left in range(9, -1, -1):
            proc = subprocess.Popen(
                [DOCKER_CMD, 'pull', ctr.image],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT)
            o, _ = proc.communicate()
            if proc.returncode == 0:
                break
            else:
                LogInfo(o)
                if pulls_left == 0:
                    Fatal('failed to pull %s' % (ctr.image))
                LogInfo('could not pull %s, will retry %d more time%s'
                        % (ctr.image, pulls_left, 's'
                           if pulls_left > 1 else ''))
                time.sleep(3)

        # Unilaterally destroy any extant container that is already running
        # with the same name.
        # TODO(thockin): If this was smart, it would actually check the config
        # of the running container and leave it alone if it was correct.
        subprocess.call(
            [DOCKER_CMD, 'kill', ctr.name],
            stdout=open('/dev/null', 'w'),
            stderr=open('/dev/null', 'w'))
        subprocess.call(
            [DOCKER_CMD, 'rm', '-f', ctr.name],
            stdout=open('/dev/null', 'w'),
            stderr=open('/dev/null', 'w'))

        proc = subprocess.Popen(
            [DOCKER_CMD, 'run', '-d'] +
            ['--name', ctr.name] +
            FlagOrNothing(ctr.hostname, '--hostname') +
            FlagOrNothing(ctr.working_dir, '--workdir') +
            FlagOrNothing(ctr.network_from, '--net') +
            FlagList(['%s:%s%s' % (p[0], p[1], p[2])
                      for p in ctr.ports], '-p') +
            FlagList(ctr.mounts, '-v') +
            FlagList(ctr.env_vars, '-e') +
            [ctr.image] +
            ctr.command,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT)
        o, _ = proc.communicate()
        if proc.returncode == 0:
            ctr_id = o.strip()
        else:
            LogInfo(o)
            Fatal("failed to run container '%s'" % (ctr.name))

        os.system(KEEPALIVE_SCRIPT %
                  {'docker': DOCKER_CMD, 'log': LOG_CMD,
                   'name': ctr.name, 'id': ctr_id})


def CheckVersion(config):
    if 'version' not in config:
        Fatal('config has no version field')
    if config['version'] not in SUPPORTED_CONFIG_VERSIONS:
        Fatal("config version '%s' is not supported" % config['version'])


def main():
    if len(sys.argv) > 2:
        Fatal('usage: %s [containers.yaml]' % sys.argv[0])

    if len(sys.argv) == 2:
        with open(sys.argv[1], 'r') as fp:
            config = yaml.load(fp)
    else:
        config = yaml.load(sys.stdin)

    syslog.openlog(PROGNAME)
    LogInfo('processing container manifest')

    CheckVersion(config)

    all_volumes = LoadVolumes(config.get('volumes', []))
    user_containers = LoadUserContainers(config.get('containers', []),
                                         all_volumes)
    CheckGroupWideConflicts(user_containers)

    if user_containers:
        infra_containers = LoadInfraContainers(user_containers)
        RunContainers(infra_containers + user_containers)

if __name__ == '__main__':
    main()
