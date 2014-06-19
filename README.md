container-agent
===============

PLEASE NOTE: This code is deprecated in favor of [Kubernetes](https://github.com/GoogleCloudPlatform/kubernetes) and [Kubelet](https://github.com/GoogleCloudPlatform/kubernetes/tree/master/pkg/kubelet).

container-agent is a small python agent designed to manage a [group](#container-group) of [Docker](https://docker.io) containers according to a YAML [manifest](#manifest).

[![Build Status](https://travis-ci.org/GoogleCloudPlatform/container-agent.svg?branch=master)](https://travis-ci.org/GoogleCloudPlatform/container-agent)

## Usage

### Locally

```
virtualenv env
env/bin/pip install git+http://github.com/GoogleCloudPlatform/container-agent.git
env/bin/container-agent <path/to/manifest.yaml>
```

### Google Cloud Platform

Container-optimized images including `container-agent` are available for Google Compute Engine.

You can list available versions using:
```
gcloud compute images list --project google-containers
```

You can launch a new instance running `container-agent`. It will try to read the [manifest](#manifest) from `google-container-manifest` metadata on startup:
```
gcloud compute instances create my-container-vm \
    --image projects/google-containers/global/images/container-vm-v20140522 \
    --metadata-from-file google-container-manifest=/path/to/containers.yaml \
    --zone us-central1-a \
    --machine-type f1-micro
```

[Read more about Containers on the Google Cloud Platform](https://developers.google.com/compute/docs/containers)

## Container Group

The agent setup the container group defined by the manifest to share:
- Network Namespaces
- Volumes

This creates a runtime environment where:
- Containers can connect to a service running in other containers of the same group using `localhost` and a fixed port.
- Containers of the same group can't run services on the same ports.
- Containers of the same group can mount shared volumes defined in the manifest.

## Manifest

A simple netcat server.
```
version: v1beta1
containers:
  - name: simple-echo
    image: busybox
    command: ['nc', '-p', '8080', '-l', '-l', '-e', 'echo', 'hello world!']
    ports:
      - name: nc-echo
        hostPort: 8080
        containerPort: 8080
```

[Read the Manifest format specification, and browse examples](manifests/)

## Community

- Give early feedback and talk with the community (including the developer team) on the [mailing-list](https://groups.google.com/forum/#!forum/google-containers)
- Ask development and best practices questions on [Stack Overflow](http://stackoverflow.com/questions/tagged/google-compute-engine+docker)
- Chat with the community on [IRC](irc://irc.freenode.net/#google-containers)
- [Submit](https://github.com/GoogleCloudPlatform/container-agent/issues) Issues & Feature requests to the GitHub issue tracker
- [Fork](https://github.com/GoogleCloudPlatform/container-agent/fork) the repository and start [contributing](CONTRIB.md)

## License

[Apache License, Version 2.0](tree/master/COPYING.md)
