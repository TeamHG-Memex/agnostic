FROM ubuntu:16.04
MAINTAINER mehaase@gmail.com
RUN apt-get update && \
    DEBIAN_FRONTEND=noninteractive apt-get install -y curl make mysql-server \
        postgresql sqlite3 supervisor && \
    rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*
RUN curl  https://bootstrap.pypa.io/get-pip.py | python3
RUN pip3 install 'Click>=7.0,<8.0' 'sqlparse>=0.2.4,<0.3.0' 'nose>=1.3.7,<1.4.0' \
    'PyMySQL>=0.9.2,<0.10.0' 'pg8000>=1.12.3,<1.13.0'
RUN pip3 install coveralls sphinx sphinx_rtd_theme
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

# Work around weird MySQL-in-Docker error: https://serverfault.com/questions/870568/fatal-error-cant-open-and-lock-privilege-tables-table-storage-engine-for-use
VOLUME /var/lib/mysql

VOLUME /opt/agnostic
ENTRYPOINT ["/usr/bin/supervisord"]
