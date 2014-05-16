# Manifest

## Specification

`container-agent` YAML manifest format is specified as follows:

    version: v1beta1
    containers:           // Required.
      - name: string      // Required.
        image: string     // Required.
        command: []
        workingDir: string
        volumeMounts:
          - name: string
            path: string
            readOnly: boolean
        ports:
          - name: string
            containerPort: int
            hostPort: int
            protocol: string
        env:
          - key: string
            value: string
    volumes:
      - name: string


Field name | Value type | Required? | Spec
---------- | ---------- | -------- | ----
`version` | `string` | Required | The version of the manifest.  Must be `v1beta1`.
`containers[]` | `list` | Required | The list of containers to launch.
`containers[].name` | `string` | Required | A symbolic name used to create and track the container.  Must be an RFC1035 compatible value (a single segment of a DNS name). All containers must have unique names.
`containers[].image` | `string` | Required | The container image to run.
`containers[].command[]` | `list of string` |  | The command line to run.  If this is omitted, the container is assumed to have a command embedded in it.
`containers[].workingDir` | `string` |  | The initial working directory for the command.  Default is the container’s embedded working directory or else the Docker default.
`containers[].volumeMounts[]` | `list` |  | Data volumes to expose into the container.
`containers[].volumeMounts[].name` | `string` | | The name of the volume to mount.  This must match the name of a volume defined in volumes[].
`containers[].volumeMounts[].path` | `string` | | The path at which to mount the volume inside the container.  This must be an absolute path and no longer than 512 characters.
`containers[].volumeMounts[].readOnly` | `boolean` |  | Whether this volume should be read-only.  Default is `false` (read-write).
`containers[].ports[]` | `list` |  | Ports to expose from the container. All of these are exposed out through the public interface of the VM.
`containers[].ports[].name` | `string` |  | A symbolic name used to create and track the port. Must be an RFC1035 compatible value (a single segment of a DNS name).
`containers[].ports[].containerPort` | `int` | | The port on which the container is listening.
`containers[].ports[].hostPort` | `int` |  | The port on the host which maps to the `containerPort`. Default is the same as `containerPort`.
`containers[].ports[].protocol` | `string` |  | The protocol for this port. Valid options are `TCP` and `UDP`.  Default is `TCP`.
`containers[].env[]` | `list` | | Environment variables to set before the container runs.
`containers[].env[].key` | `string` | | The name of the environment variable.
`containers[].env[].value` | `string` | | The value of the environment variable.
`volumes[]` | `list` | | A list of volumes to share between containers.
`volumes[].name` | `string` | | The name of the volume.  Must be an RFC1035 compatible value (a single segment of a DNS name).  All volumes must have unique names.  These are referenced by `containers[].volumeMounts[].name`.

### Examples

#### Simple

A simple netcat server.

    version: v1beta1
    containers:
      - name: simple-echo
        image: google/busybox
        command: ['nc', '-p', '8080', '-l', '-l', '-e', 'echo', 'hello world!']
        ports:
          - name: nc-echo
            hostPort: 8080
            containerPort: 8080


#### Private container images

A container group including:
- [`google/docker-registry`](https://index.docker.io/u/google/docker-registry) to pull (and push) private image from a [Google Cloud Storage](https://developers.google.com/storage/) bucket.
- Another container pulled from the registry container running localhost.

        version: v1beta1
        containers:
        - name: registry
          image: google/docker-registry
          env:
            - key: GCS_BUCKET
              value: my-private-repository-bucket
          ports:
            - name: port5000
              containerPort: 5000
        - name: my-private-app
          image: localhost:5000/my/app
          ports:
            - name: port80
              hostPort: 80
              containerPort: 8080


#### Volumes

A container group including:
- A [volume](http://docs.docker.io/use/working_with_volumes/) definition.
- Two containers using the same volume.

        version: v1beta1
        containers:
          - name: data-loader
            image: data-loader
            volumeMounts:
              - name: data
                path: /mnt/data
          - name: server
            image: data-server
            ports:
              - name: www
                containerPort: 80
            volumeMounts:
              - name: data
                path: /mnt/data
        volumes:
          - name: data
