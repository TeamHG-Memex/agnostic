# Agnostic Testing

## Overview

Agnostic is just a thin wrapper around various database clients and the file
system. Due to these external dependencies, unit testing has limited value.
Therefore, Agnostic's tests are primarily *integration tests*. These tests will
run as part of the automated test suite if suitable database credentials are
exported in the environment. If database credentials are not exported in the
environment, then the tests that depend on those credentials will be skipped.

If database credentials are exported in the environment, then the corresponding
database server must be running and any required tools (e.g. `pg_dump`) must
also be present. If a test cannot find the database server or a required tool,
then that test will error out.

## Docker Container

The full test suite can be run against all of its dependencies using a [Docker
container](https://www.docker.com/). The container contains all of the database
servers, tools, and libraries needed, pre-configured to be easily accessed by
the test suite. The docker is intended to emulate the Travis CI environment as
closely as possible, so that the full test suite can be run locally before
committing and pushing.

Docker containers are not mutable: they are restored to their original state
when they are stopped and restarted. This is a good thing for integration tests!
It means that the testing environment can quickly be restored to a known state.

To build the docker image, run the following command from the project root:

    docker build -t agnostic-tests tests/docker

This step will take a few minutes the first time you run it because it needs to
download a few hundred megabytes of files. After you build it once, subsequent
builds will be much faster since most build steps are cached. (You only need to
rebuild the image when you update the Agnostic repository.)

Once the image is completed, create and run a container with the following
command:

    docker run --name=agnostic-tests -v $PWD:/opt/agnostic --rm agnostic-tests

Docker will show the various databases starting up and then continue to run in
the foreground, but it does not open a shell. To open a shell, run the following
command in another terminal window:

    docker exec -it agnostic-tests /bin/bash

With this shell, you can run commands inside the container, completely isolated
from the host system. In order to run the test suite, you need to export
environment variables that tell the test suite what credentials to use when
accessing the various databases.

    export LC_ALL=C.UTF-8
    export POSTGRES_USER=root
    export POSTGRES_PASSWORD=root
    cd /opt/agnostic
    nosetests -v tests

The Agnostic source code in the container is mounted from the host system. This
means that you can edit the code on your host system, then immediately re-
execute the tests in the container. You don't need to restart the container or
anything like that.

To run tests with code coverage, use this alternate form:

    nosetests --with-coverage --cover-package agnostic -v tests

When you are done, you can exit from Docker by typing `Ctrl+C` in the shell from
which you ran `docker run`.

## Testing Postgres

The PostgresSQL integration tests support the following environment variables:

* `POSTGRES_USER` username to log in with; must be a super user (required)
* `POSTGRES_PASSWORD` password to log in with (required)
* `POSTGRES_HOST` hostname to connect to (default: "localhost")
* `POSTGRES_PORT` port number to connect to (default: the postgres default
  port)
