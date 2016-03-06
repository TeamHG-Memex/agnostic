FROM ubuntu:14.04
MAINTAINER mehaase@gmail.com
RUN apt-get update
RUN apt-get install -y curl postgresql python3-psycopg2 supervisor
RUN curl  https://bootstrap.pypa.io/get-pip.py | python3
RUN pip3 install Click nose
COPY supervisor.conf /etc/supervisor/conf.d/agnostic-tests.conf
RUN mkdir -p /var/log/supervisor

# "CREATE DATABASE" is much faster with fsync disabled:
RUN sed --in-place 's:#fsync = on:fsync = off:' \
        /etc/postgresql/9.3/main/postgresql.conf

RUN /etc/init.d/postgresql start && \
    sudo -u postgres psql --command "CREATE USER root WITH SUPERUSER PASSWORD 'root';"

#

# This environment variable allows Click to print to stdout:
ENV LANG=C.UTF-8

VOLUME /opt/agnostic
ENTRYPOINT ["/usr/bin/supervisord"]
