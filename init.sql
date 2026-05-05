CREATE DATABASE mychef_db;
\c mychef_db;

-- =============================================
-- Family Members
-- =============================================
CREATE TABLE family_members (
    id          SERIAL PRIMARY KEY,
    name        VARCHAR(100) NOT NULL,
    relationship VARCHAR(50) NOT NULL  -- 'self', 'spouse', 'child', 'parent', etc.
);

-- =============================================
-- Dietary Profiles (linked to family members)
-- =============================================
CREATE TABLE dietary_profiles (
    id          SERIAL PRIMARY KEY,
    member_id   INT REFERENCES family_members(id) ON DELETE CASCADE,
    trait_type   VARCHAR(20) NOT NULL CHECK (trait_type IN ('allergy', 'diet', 'dislike', 'favorite')),
    value       VARCHAR(100) NOT NULL
);

-- =============================================
-- Pantry (upgraded with units + expiry tracking)
-- =============================================
CREATE TABLE pantry (
    id              SERIAL PRIMARY KEY,
    item_name       VARCHAR(100) NOT NULL,
    quantity        FLOAT NOT NULL DEFAULT 1,
    unit            VARCHAR(30) NOT NULL DEFAULT 'unit',
    purchase_date   DATE NOT NULL DEFAULT CURRENT_DATE,
    expiry_date     DATE  -- NULL = non-perishable
);

-- =============================================
-- Seed Data
-- =============================================
INSERT INTO family_members (name, relationship) VALUES
    ('User', 'self'),
    ('Priya', 'spouse');

INSERT INTO dietary_profiles (member_id, trait_type, value) VALUES
    (2, 'diet', 'vegetarian'),
    (2, 'allergy', 'peanuts');

INSERT INTO pantry (item_name, quantity, unit, purchase_date, expiry_date) VALUES
    ('chicken breast', 2, 'pieces', CURRENT_DATE - 1, CURRENT_DATE + 2),
    ('garlic', 5, 'cloves', CURRENT_DATE - 7, CURRENT_DATE + 21),
    ('heavy cream', 1, 'carton', CURRENT_DATE - 3, CURRENT_DATE + 4),
    ('rice', 2, 'kg', CURRENT_DATE - 30, CURRENT_DATE + 335),
    ('onion', 4, 'pieces', CURRENT_DATE - 5, CURRENT_DATE + 9);
