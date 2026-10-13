#!/bin/bash
# This script creates a MySQL 8 container for the examples.
# You may have to install docker. Debian example: sudo apt install docker.io
sudo docker run --restart always -d -p 3306:3306 --name ownSQL-testing -e MYSQL_ROOT_PASSWORD=123456 mysql:8.4