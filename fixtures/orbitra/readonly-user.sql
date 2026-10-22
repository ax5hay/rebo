-- The bot's login: can read every table the builder creates (default privileges), nothing else.
CREATE ROLE orbitra_ro LOGIN PASSWORD 'orbitra_ro';
GRANT CONNECT ON DATABASE orbitra TO orbitra_ro;
GRANT USAGE ON SCHEMA public TO orbitra_ro;
ALTER DEFAULT PRIVILEGES FOR ROLE orbitra IN SCHEMA public GRANT SELECT ON TABLES TO orbitra_ro;
ALTER ROLE orbitra_ro SET default_transaction_read_only = on;
