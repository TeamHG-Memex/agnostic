FROM ubuntu:16.04
MAINTAINER mehaase@gmail.com
RUN apt-get update && \
    DEBIAN_FRONTEND=noninteractive apt-get install -y curl mysql-server postgresql supervisor && \
    rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*
RUN curl  https://bootstrap.pypa.io/get-pip.py | python3
RUN pip3 install agnostic[dev,mysql,postgres]
COPY supervisor.conf /etc/supervisor/conf.d/agnostic-tests.conf
RUN mkdir -p /var/log/supervisor

RUN /etc/init.d/mysql start && \
    mysql -u root -e "SET PASSWORD FOR 'root'@'localhost' = PASSWORD('root')"

# "CREATE DATABASE" is much faster with fsync disabled:
RUN sed --in-place 's:#fsync = on:fsync = off:' \
       /etc/postgresql/9.5/main/postgresql.conf

RUN /etc/init.d/postgresql start && \
    su postgres -c "echo CREATE USER root WITH SUPERUSER PASSWORD \\'root\\' | psql"

# This environment variable allows Click to print to stdout:
ENV LANG=C.UTF-8

# Provide default credentials for integration tests.
ENV MYSQL_USER=root
ENV MYSQL_PASSWORD=root
ENV POSTGRES_USER=root
ENV POSTGRES_PASSWORD=root

VOLUME /opt/agnostic
ENTRYPOINT ["/usr/bin/supervisord"]
