# Agnostic Testing

## Overview

Agnostic is just a thin wrapper around various database clients and the file system. Due
to these external dependencies, unit testing has limited value. Therefore, Agnostic's
tests are primarily *integration tests*. These tests will run as part of the automated
test suite if suitable database credentials are exported in the environment. If database
credentials are not exported in the environment, then the tests that depend on those
credentials will be skipped.

If database credentials are exported in the environment, then the corresponding database
server must be running and any required tools (e.g. `pg_dump`) must also be present. If
a test cannot find the database server or a required tool, then that test will error
out.

## Docker Container

The full test suite can be run against all of its dependencies using a [Docker
container](https://www.docker.com/). The container contains all of the database servers,
tools, and libraries needed, pre-configured to be easily accessed by the test suite. The
same docker image is also used in the Travis CI environment, so that we can run the
exact same tests locally before committing and pushing.

A docker image is immutable: if you start running an image and make some changes, those
changes do not affect the image itself. If you delete your container and run the image
again, you'll find that all of your changes are gone. This is an ideal quality to have
for unit tests: tests are always executed against the same, pristine state.

To run the integration tests:

    export DOCKER_ACCOUNT=mehaase
    make integration-tests

This will download a Docker image from hub.docker.com/mehaase. If you prefer to build
your own container, you can do it as follows. Pick a different Docker account name (it
doesn't even need to be a valid Docker account, unless you plan to push it to Docker
Hub.)

    export DOCKER_ACCOUNT=your_name_here
    make build-container

This step will take a few minutes the first time you run it because it needs to download
a few hundred megabytes of files. After you build it once, subsequent builds will be
much faster since most build steps are cached. Now you can run the `integration-tests`
target again using the same `DOCKER_ACCOUNT` and it will use your image.

If you want to run the container and execute tests manually (e.g. for interactive
debugging):

    make start-container

Docker will show the various databases starting up and then continue to run in the
foreground, but it does not open a shell. To open a shell, run the following command in
another terminal window:

    make container-shell

With this shell, you can run commands inside the container, completely isolated from the
host system.

    pytest tests/

The Agnostic source code in the container is mounted from the host system. This means
that you can edit the code on your host system, then immediately re- execute the tests
in the container. You don't need to restart the container or anything like that.

If you want to debug a single test, you can run it directly using the following form:

    pytest tests/test_cli.py::TestCli::test_invalid_options

To run tests with code coverage, use this alternate form:

    pytest --cov=agnostic tests/

When you are done, you can exit from Docker by running `make stop-container`.

## Documentation

Documentation can also be built inside the Docker container. Go into the `/docs`
directory and run `make html`. The documentation is written to `/docs/_build`.

## Travis CI && Coveralls

Tests for this project run automatically on [GitHub
Actions](https://github.com/mehaase/agnostic/actions/new) and code coverage is computed
by [Coveralls](https://coveralls.io/github/mehaase/agnostic) after each push to GitHub.
The GitHub Action depends on being able to pull the Docker container described in the
previous section. Any time you modify the `agnostic-tests` Docker image, you should tag
and push it to Docker Hub so that Travis CI will be able to find it.

    export DOCKER_ACCOUNT=mehaase
    make push-container

Even though the `:latest` tag is usually a bad idea, it should be fine for this
extremely simple image that will not change very often.

## Testing MySQL

The MySQL integration tests support the following environment variables:

* `MYSQL_USER` username to log in with; must be an "ALL PRIVILEGES" user
  (required)
* `MYSQL_PASSWORD` password to log in with (required)
* `MYSQL_HOST` hostname to connect to (default: "localhost")
* `MYSQL_PORT` port number to connect to (default: the MySQL default port)
* `MYSQL_TEST_DB` the name of the test database; this database will be dropped
  and recreated frequently while running tests, so make sure that it is not a
  production database (default: "testdb")

## Testing Postgres

The PostgresSQL integration tests support the following environment variables:

* `POSTGRES_USER` username to log in with; must be a super user (required)
* `POSTGRES_PASSWORD` password to log in with (required)
* `POSTGRES_HOST` hostname to connect to (default: "localhost")
* `POSTGRES_PORT` port number to connect to (default: the PostgreSQL default
  port)
* `POSTGRES_TEST_DB` the name of the test database; this database will be
  dropped and recreated frequently while running tests, so make sure that it is
  not a production database (default: "testdb")
