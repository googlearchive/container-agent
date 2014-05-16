#!/usr/bin/python

"""Tests for run_containers."""

import unittest
import yaml
from container_agent import run_containers


class RunContainersTest(unittest.TestCase):

    def testKnownVersion(self):
        yaml_code = """
      version: v1beta1
      """
        run_containers.CheckVersion(yaml.load(yaml_code))

    def testNoVersion(self):
        yaml_code = """
      not_version: not valid
      """
        with self.assertRaises(SystemExit):
            run_containers.CheckVersion(yaml.load(yaml_code))

    def testUnknownVersion(self):
        yaml_code = """
      version: not valid
      """
        with self.assertRaises(SystemExit):
            run_containers.CheckVersion(yaml.load(yaml_code))

    def testRfc1035Name(self):
        self.assertFalse(run_containers.IsRfc1035Name('1'))
        self.assertFalse(run_containers.IsRfc1035Name('123'))
        self.assertFalse(run_containers.IsRfc1035Name('123abc'))
        self.assertFalse(run_containers.IsRfc1035Name('123abc'))
        self.assertFalse(run_containers.IsRfc1035Name('a_b'))
        self.assertFalse(run_containers.IsRfc1035Name('a:b'))
        self.assertFalse(run_containers.IsRfc1035Name('a b'))
        self.assertFalse(run_containers.IsRfc1035Name('A.B'))
        self.assertFalse(run_containers.IsRfc1035Name('ab-'))
        self.assertTrue(run_containers.IsRfc1035Name('a'))
        self.assertTrue(run_containers.IsRfc1035Name('abc'))
        self.assertTrue(run_containers.IsRfc1035Name('abc123'))
        self.assertTrue(run_containers.IsRfc1035Name('abc123def'))
        self.assertTrue(run_containers.IsRfc1035Name('abc-123-def'))

    def testVolumeValid(self):
        yaml_code = """
      - name: abc
      - name: abc-123
      - name: a
      """
        x = run_containers.LoadVolumes(yaml.load(yaml_code))
        self.assertEqual(3, len(x))
        self.assertEqual('abc', x[0])
        self.assertEqual('abc-123', x[1])
        self.assertEqual('a', x[2])

    def testVolumeNoName(self):
        yaml_code = """
      - notname: notgood
      """
        with self.assertRaises(SystemExit):
            run_containers.LoadVolumes(yaml.load(yaml_code))

    def testVolumeInvalidName(self):
        yaml_code = """
      - name: 123abc
      """
        with self.assertRaises(SystemExit):
            run_containers.LoadVolumes(yaml.load(yaml_code))

    def testVolumeDupName(self):
        yaml_code = """
      - name: abc123
      - name: abc123
      """
        with self.assertRaises(SystemExit):
            run_containers.LoadVolumes(yaml.load(yaml_code))

    def testContainerValidMinimal(self):
        yaml_code = """
      - name: abc123
        image: foo/bar
      - name: abc124
        image: foo/bar
      """
        user = run_containers.LoadUserContainers(yaml.load(yaml_code), [])
        self.assertEqual(2, len(user))
        self.assertEqual('abc123', user[0].name)
        self.assertEqual('abc124', user[1].name)

        infra = run_containers.LoadInfraContainers(user)
        self.assertEqual(1, len(infra))
        self.assertEqual('.net', infra[0].name)

    def testContainerValidFull(self):
        yaml_code = """
      - name: abc123
        image: foo/bar
        command:
          - one
          - two
        workingDir: /tmp
        ports:
          - name: port1
            hostPort: 111
            containerPort: 2222
            protocol: UDP
        volumeMounts:
          - name: vol1
            path: /mnt
            readOnly: true
        env:
          - key: KEY
            value: value str
      """
        x = run_containers.LoadUserContainers(yaml.load(yaml_code), ['vol1'])
        self.assertEqual(1, len(x))
        self.assertEqual('abc123', x[0].name)
        self.assertEqual('foo/bar', x[0].image)
        self.assertEqual(['one', 'two'], x[0].command)
        self.assertEqual('/tmp', x[0].working_dir)
        self.assertEqual((111, 2222, '/udp'), x[0].ports[0])
        self.assertEqual('/export/vol1:/mnt:ro', x[0].mounts[0])
        self.assertEqual('KEY=value str', x[0].env_vars[0])

    def testContainerValidFullJson(self):
        """Proves that the same YAML parsing code handles JSON."""
        json_code = """
      [
        {
          "name": "abc123",
          "image": "foo/bar",
          "command": [
            "one",
            "two"
          ],
          "workingDir": "/tmp",
          "ports": [
            {
              "name": "port1",
              "hostPort": 111,
              "containerPort": 2222,
              "protocol": "UDP"
            }
          ],
          "volumeMounts": [
            {
              "name": "vol1",
              "path": "/mnt",
              "readOnly": true
            }
          ],
          "env": [
            {
              "key": "KEY",
              "value": "value str"
            }
          ]
        }
      ]
      """
        x = run_containers.LoadUserContainers(yaml.load(json_code), ['vol1'])
        self.assertEqual(1, len(x))
        self.assertEqual('abc123', x[0].name)
        self.assertEqual('foo/bar', x[0].image)
        self.assertEqual(['one', 'two'], x[0].command)
        self.assertEqual('/tmp', x[0].working_dir)
        self.assertEqual((111, 2222, '/udp'), x[0].ports[0])
        self.assertEqual('/export/vol1:/mnt:ro', x[0].mounts[0])
        self.assertEqual('KEY=value str', x[0].env_vars[0])

    def testContainerNoName(self):
        yaml_code = """
      - notname: notgood
        image: foo/bar
      """
        with self.assertRaises(SystemExit):
            run_containers.LoadUserContainers(yaml.load(yaml_code), [])

    def testContainerInvalidName(self):
        yaml_code = """
      - name: not_good
        image: foo/bar
      """
        with self.assertRaises(SystemExit):
            run_containers.LoadUserContainers(yaml.load(yaml_code), [])

    def testContainerDupName(self):
        yaml_code = """
      - name: abc123
        image: foo/bar
      - name: abc123
        image: foo/bar
      """
        with self.assertRaises(SystemExit):
            run_containers.LoadUserContainers(yaml.load(yaml_code), [])

    def testContainerNoImage(self):
        yaml_code = """
      - name: abc123
        notimage: foo/bar
      """
        with self.assertRaises(SystemExit):
            run_containers.LoadUserContainers(yaml.load(yaml_code), [])

    def testContainerWithoutCommand(self):
        yaml_code = """
      - name: abc123
        image: foo/bar
      """
        x = run_containers.LoadUserContainers(yaml.load(yaml_code), [])
        self.assertEqual(1, len(x))
        self.assertEqual(0, len(x[0].command))

    def testContainerWithCommand(self):
        yaml_code = """
      - name: abc123
        image: foo/bar
        command:
          - first
          - second
          - third fourth
      """
        x = run_containers.LoadUserContainers(yaml.load(yaml_code), [])
        self.assertEqual(1, len(x))
        self.assertEqual(3, len(x[0].command))

    def testContainerWithoutWorkingDir(self):
        yaml_code = """
      - name: abc123
        image: foo/bar
      """
        x = run_containers.LoadUserContainers(yaml.load(yaml_code), [])
        self.assertIsNone(x[0].working_dir)

    def testContainerWithWorkingDir(self):
        yaml_code = """
      - name: abc123
        image: foo/bar
        workingDir: /foo/bar
      """
        x = run_containers.LoadUserContainers(yaml.load(yaml_code), [])
        self.assertEqual('/foo/bar', x[0].working_dir)

    def testContainerWorkingDirNotAbsolute(self):
        yaml_code = """
      - name: abc123
        image: foo/bar
        workingDir: foo/bar
      """
        with self.assertRaises(SystemExit):
            run_containers.LoadUserContainers(yaml.load(yaml_code), [])

    def testContainerWithoutPorts(self):
        yaml_code = """
      - name: abc123
        image: foo/bar
      """
        x = run_containers.LoadUserContainers(yaml.load(yaml_code), [])
        self.assertEqual(0, len(x[0].ports))

    def testPortValidMinimal(self):
        yaml_code = """
      - containerPort: 1
      - containerPort: 65535
      """
        x = run_containers.LoadPorts(yaml.load(yaml_code), 'ctr_name')
        self.assertEqual(2, len(x))
        self.assertEqual((1, 1, ''), x[0])
        self.assertEqual((65535, 65535, ''), x[1])

    def testPortWithName(self):
        yaml_code = """
      - name: abc123
        containerPort: 123
      """
        x = run_containers.LoadPorts(yaml.load(yaml_code), 'ctr_name')
        self.assertEqual(1, len(x))
        self.assertEqual((123, 123, ''), x[0])

    def testPortInvalidName(self):
        yaml_code = """
      - name: 123abc
        containerPort: 123
      """
        with self.assertRaises(SystemExit):
            run_containers.LoadPorts(yaml.load(yaml_code), 'ctr_name')

    def testPortDupName(self):
        yaml_code = """
      - name: abc123
        containerPort: 123
      - name: abc123
        containerPort: 124
      """
        with self.assertRaises(SystemExit):
            run_containers.LoadPorts(yaml.load(yaml_code), 'ctr_name')

    def testPortNoContainerPort(self):
        yaml_code = """
      - name: abc123
      """
        with self.assertRaises(SystemExit):
            run_containers.LoadPorts(yaml.load(yaml_code), 'ctr_name')

    def testPortTooLowContainerPort(self):
        yaml_code = """
      - containerPort: 0
      """
        with self.assertRaises(SystemExit):
            run_containers.LoadPorts(yaml.load(yaml_code), 'ctr_name')

    def testPortTooHighContainerPort(self):
        yaml_code = """
      - containerPort: 65536
      """
        with self.assertRaises(SystemExit):
            run_containers.LoadPorts(yaml.load(yaml_code), 'ctr_name')

    def testPortWithHostPort(self):
        yaml_code = """
      - containerPort: 123
        hostPort: 456
      """
        x = run_containers.LoadPorts(yaml.load(yaml_code), 'ctr_name')
        self.assertEqual(1, len(x))
        self.assertEqual((456, 123, ''), x[0])

    def testPortTooLowHostPort(self):
        yaml_code = """
      - containerPort: 123
        hostPort: 0
      """
        with self.assertRaises(SystemExit):
            run_containers.LoadPorts(yaml.load(yaml_code), 'ctr_name')

    def testPortTooHighHostPort(self):
        yaml_code = """
      - containerPort: 123
        hostPort: 65536
      """
        with self.assertRaises(SystemExit):
            run_containers.LoadPorts(yaml.load(yaml_code), 'ctr_name')

    def testPortDupHostPort(self):
        yaml_code = """
      - containerPort: 123
        hostPort: 123
      - containerPort: 124
        hostPort: 123
      """
        with self.assertRaises(SystemExit):
            run_containers.LoadPorts(yaml.load(yaml_code), 'ctr_name')

    def testPortWithProtocolTcp(self):
        yaml_code = """
      - containerPort: 123
        protocol: TCP
      """
        x = run_containers.LoadPorts(yaml.load(yaml_code), 'ctr_name')
        self.assertEqual(1, len(x))
        self.assertEqual((123, 123, ''), x[0])

    def testPortWithProtocolUdp(self):
        yaml_code = """
      - containerPort: 123
        protocol: UDP
      """
        x = run_containers.LoadPorts(yaml.load(yaml_code), 'ctr_name')
        self.assertEqual(1, len(x))
        self.assertEqual((123, 123, '/udp'), x[0])

    def testPortWithInvalidProtocol(self):
        yaml_code = """
      - containerPort: 123
        protocol: IGMP
      """
        with self.assertRaises(SystemExit):
            run_containers.LoadPorts(yaml.load(yaml_code), 'ctr_name')

    def testContainerWithoutMounts(self):
        yaml_code = """
      - name: abc123
        image: foo/bar
      """
        x = run_containers.LoadUserContainers(yaml.load(yaml_code), [])
        self.assertEqual(0, len(x[0].mounts))

    def testMountValidMinimal(self):
        yaml_code = """
      - name: vol1
        path: /mnt/vol1
      - name: vol2
        path: /mnt/vol2
      """
        x = run_containers.LoadVolumeMounts(
            yaml.load(yaml_code), ['vol1', 'vol2'], 'ctr_name')
        self.assertEqual(2, len(x))
        self.assertEqual('/export/vol1:/mnt/vol1:rw', x[0])
        self.assertEqual('/export/vol2:/mnt/vol2:rw', x[1])

    def testMountNoName(self):
        yaml_code = """
      - path: /mnt/vol1
      """
        with self.assertRaises(SystemExit):
            run_containers.LoadVolumeMounts(
                yaml.load(yaml_code), ['vol1'], 'ctr_name')

    def testMountInvalidName(self):
        yaml_code = """
      - name: 1vol
        path: /mnt/vol1
      """
        with self.assertRaises(SystemExit):
            run_containers.LoadVolumeMounts(
                yaml.load(yaml_code), ['1vol'], 'ctr_name')

    def testMountUnknownName(self):
        yaml_code = """
      - name: vol1
        path: /mnt/vol1
      """
        with self.assertRaises(SystemExit):
            run_containers.LoadVolumeMounts(
                yaml.load(yaml_code), [], 'ctr_name')

    def testMountNoPath(self):
        yaml_code = """
      - name: vol1
      """
        with self.assertRaises(SystemExit):
            run_containers.LoadVolumeMounts(
                yaml.load(yaml_code), ['vol1'], 'ctr_name')

    def testMountInvalidPath(self):
        yaml_code = """
      - name: vol1
        path: mnt/vol1
      """
        with self.assertRaises(SystemExit):
            run_containers.LoadVolumeMounts(
                yaml.load(yaml_code), ['vol1'], 'ctr_name')

    def testContainerWithoutEnv(self):
        yaml_code = """
      - name: abc123
        image: foo/bar
      """
        x = run_containers.LoadUserContainers(yaml.load(yaml_code), [])
        self.assertEqual(0, len(x[0].env_vars))

    def testEnvValidMinimal(self):
        yaml_code = """
      - key: key1
        value: value
      - key: key2
        value: value too
      """
        x = run_containers.LoadEnvVars(yaml.load(yaml_code), 'ctr_name')
        self.assertEqual(2, len(x))
        self.assertEqual('key1=value', x[0])
        self.assertEqual('key2=value too', x[1])

    def testEnvNoKey(self):
        yaml_code = """
      - value: value
      """
        with self.assertRaises(SystemExit):
            run_containers.LoadEnvVars(yaml.load(yaml_code), 'ctr_name')

    def testEnvInvalidKey(self):
        yaml_code = """
      - key: 1value
        value: value
      """
        with self.assertRaises(SystemExit):
            run_containers.LoadEnvVars(yaml.load(yaml_code), 'ctr_name')

    def testEnvNoValue(self):
        yaml_code = """
      - key: key
      """
        with self.assertRaises(SystemExit):
            run_containers.LoadEnvVars(yaml.load(yaml_code), 'ctr_name')

    def testFlagList(self):
        self.assertEqual([], run_containers.FlagList([], '-x'))
        self.assertEqual(['-x', 'a'], run_containers.FlagList(['a'], '-x'))
        self.assertEqual(['-x', 'a', '-x', 'b', '-x', 'c'],
                         run_containers.FlagList(['a', 'b', 'c'], '-x'))

    def testFlagOrNothing(self):
        self.assertEqual([], run_containers.FlagOrNothing(None, '-x'))
        self.assertEqual(['-x', 'a'], run_containers.FlagOrNothing('a', '-x'))

    def testCheckGroupWideConflictsOk(self):
        containers = []
        c = run_containers.Container('name1', 'ubuntu')
        c.ports = [(80, 80, '')]
        containers.append(c)
        c = run_containers.Container('name1', 'ubuntu')
        c.ports = [(81, 81, '')]
        containers.append(c)
        c = run_containers.Container('name2', 'ubuntu')
        c.ports = [(81, 81, '/udp')]
        containers.append(c)

        run_containers.CheckGroupWideConflicts(containers)

    def testCheckGroupWideConflictsDupHostPort(self):
        containers = []
        c = run_containers.Container('name1', 'ubuntu')
        c.ports = [(80, 80, '')]
        containers.append(c)
        c = run_containers.Container('name1', 'ubuntu')
        c.ports = [(80, 81, '')]
        containers.append(c)

        with self.assertRaises(SystemExit):
            run_containers.CheckGroupWideConflicts(containers)

    def testCheckGroupWideConflictsDupContainerPort(self):
        containers = []
        c = run_containers.Container('name1', 'ubuntu')
        c.ports = [(80, 80, '')]
        containers.append(c)
        c = run_containers.Container('name1', 'ubuntu')
        c.ports = [(81, 80, '')]
        containers.append(c)

        with self.assertRaises(SystemExit):
            run_containers.CheckGroupWideConflicts(containers)


if __name__ == '__main__':
    unittest.main()
