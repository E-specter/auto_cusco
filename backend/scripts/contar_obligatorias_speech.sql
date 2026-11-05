-- T-HI-B7, parte 2: SOLO LECTURA. Cuenta lo que la migracion d3a9c5e1b742 va a cambiar, antes de
-- aplicarla en auto_cusco (aplicarla alli es decision del usuario). Se puede correr tal cual en
-- cualquier base: no escribe nada.
--   psql -d auto_cusco_test -f backend/scripts/contar_obligatorias_speech.sql
--
-- nodos_de_adicionales: nodos `variable` cuyo nombre es un campo adicional (archivados incluidos),
--                       en TODAS las versiones del speech.
-- ya_marcados:          los que YA traen obligatoria = true. Debe ser 0: si no, la migracion se
--                       detiene (el downgrade no sabria cuales marco ella).
-- a_marcar:             los que la migracion va a cambiar.
WITH nodos AS (
    SELECT v.id AS version_id, n AS nodo
    FROM mowa_mes_speech_version v
    CROSS JOIN LATERAL jsonb_array_elements(COALESCE(v.expresiones, '[]'::jsonb)) AS e
    CROSS JOIN LATERAL jsonb_array_elements(COALESCE(e -> 'expresion' -> 'nodos', '[]'::jsonb)) AS n
    WHERE n ->> 'tipo' = 'variable'
      AND n ->> 'nombre' IN (SELECT nombre FROM campo_adicional)
)
SELECT
    count(*) AS nodos_de_adicionales,
    count(*) FILTER (WHERE nodo ->> 'obligatoria' = 'true') AS ya_marcados,
    count(*) FILTER (WHERE COALESCE(nodo ->> 'obligatoria', 'false') <> 'true') AS a_marcar,
    count(DISTINCT version_id) AS versiones_con_adicionales
FROM nodos;
