FROM mysql:latest

# Set environment variables
ENV MYSQL_ROOT_PASSWORD=123456
ENV MYSQL_DATABASE=ownSQL_test

# Initialize the test schema on first container startup.
COPY testDatabase.sql /docker-entrypoint-initdb.d/

EXPOSE 3306

# MySQL 8 generates TLS certificates automatically when none are supplied.
CMD ["mysqld"]
