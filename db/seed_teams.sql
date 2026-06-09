-- Seed the known team-name mismatches across data sources.
-- Run AFTER schema.sql. The Kaggle loader will INSERT any teams not listed
-- here; this file pre-loads the ones where source spellings diverge so the
-- joins line up. fifa_code is the canonical key.
--
-- Columns: fifa_code, name, confederation, martj42_name, elo_name, fbref_name, fifa_name
-- A NULL alias means that source spells it the same as `name`.

INSERT INTO teams (fifa_code, name, confederation, martj42_name, elo_name, fbref_name, fifa_name) VALUES
    ('USA', 'United States',        'CONCACAF', 'United States',        'United States',  'United States',        'USA'),
    ('KOR', 'South Korea',          'AFC',      'South Korea',          'South Korea',    'South Korea',          'Korea Republic'),
    ('IRN', 'Iran',                 'AFC',      'Iran',                 'Iran',           'Iran',                 'IR Iran'),
    ('CIV', 'Ivory Coast',          'CAF',      'Cote d''Ivoire',       'Ivory Coast',    'Ivory Coast',          'Côte d''Ivoire'),
    ('CZE', 'Czechia',              'UEFA',     'Czech Republic',       'Czech Republic', 'Czech Republic',       'Czechia'),
    ('MKD', 'North Macedonia',      'UEFA',     'North Macedonia',      'North Macedonia','North Macedonia',      'North Macedonia'),
    ('COD', 'DR Congo',             'CAF',      'DR Congo',             'Congo DR',       'Congo DR',             'DR Congo'),
    ('BIH', 'Bosnia and Herzegovina','UEFA',    'Bosnia and Herzegovina','Bosnia-Herzegovina','Bosnia-Herzegovina','Bosnia and Herzegovina'),
    ('TRI', 'Trinidad and Tobago',  'CONCACAF', 'Trinidad and Tobago',  'Trinidad & Tobago','Trinidad and Tobago','Trinidad and Tobago'),
    ('CPV', 'Cape Verde',           'CAF',      'Cape Verde',           'Cape Verde',     'Cape Verde',           'Cabo Verde')
ON CONFLICT (fifa_code) DO UPDATE SET
    martj42_name = EXCLUDED.martj42_name,
    elo_name     = EXCLUDED.elo_name,
    fbref_name   = EXCLUDED.fbref_name,
    fifa_name    = EXCLUDED.fifa_name;
