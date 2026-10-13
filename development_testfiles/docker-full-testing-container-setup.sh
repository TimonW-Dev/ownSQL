#!/bin/bash
# This script creates a MySQL 8 container with test data and TLS for test_script.py.
# You may have to install docker. Debian example: sudo apt install docker.io
sudo chmod 644 ./testDatabase.sql 
sudo docker build -t ownSQL-testing:v1 .
sudo docker run --restart always -d -p 3306:3306 --name ownSQL-testing ownSQL-testing:v1