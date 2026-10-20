-- The bot connects with this user. SELECT only: the database itself refuses any write.
CREATE USER IF NOT EXISTS 'reports_ro'@'%' IDENTIFIED BY 'reports_ro';
GRANT SELECT, SHOW VIEW ON jms.* TO 'reports_ro'@'%';
FLUSH PRIVILEGES;
