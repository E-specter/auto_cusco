-- Inicializacion de la base de datos de auto_cusco.
--
-- Ejecutar UNA VEZ como superusuario de PostgreSQL (normalmente el rol
-- "postgres"), desde una terminal propia para que psql te pida la
-- contrasena de forma interactiva (nunca la pegues en un chat ni la
-- pases por variables de entorno compartidas):
--
--   psql -U postgres -h localhost -f backend/scripts/init_db.sql
--
-- Crea un rol de aplicacion dedicado (no el superusuario) y la base de
-- datos del proyecto, si todavia no existen. Cambia la contrasena por
-- defecto antes o despues de ejecutar este script, y reflejala en tu
-- .env local (nunca versionado) en la variable DB_PASSWORD.

DO
$$
BEGIN
   IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = 'auto_cusco_app') THEN
      CREATE ROLE auto_cusco_app WITH LOGIN PASSWORD 'changeme';
   END IF;
END
$$;

SELECT 'CREATE DATABASE auto_cusco OWNER auto_cusco_app'
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'auto_cusco')
\gexec
