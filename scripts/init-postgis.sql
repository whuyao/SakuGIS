-- Normalized OSM feature table used by SakuGIS GIS verification.
-- Load OSM-derived features into this table with your preferred ETL pipeline.

CREATE EXTENSION IF NOT EXISTS postgis;

CREATE TABLE IF NOT EXISTS public.sakugis_osm_features (
    feature_id bigserial PRIMARY KEY,
    osm_type text NOT NULL,
    osm_id bigint NOT NULL,
    name text,
    tags jsonb NOT NULL DEFAULT '{}'::jsonb,
    geom geometry(Geometry, 4326) NOT NULL,
    UNIQUE (osm_type, osm_id)
);

CREATE INDEX IF NOT EXISTS sakugis_osm_features_geom_gix
    ON public.sakugis_osm_features
    USING gist (geom);

CREATE INDEX IF NOT EXISTS sakugis_osm_features_tags_gin
    ON public.sakugis_osm_features
    USING gin (tags);

ANALYZE public.sakugis_osm_features;
