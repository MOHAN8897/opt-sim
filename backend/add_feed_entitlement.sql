-- Migration: Add feed_entitlement column to upstox_accounts table
-- Date: 2026-01-20
-- Purpose: Separate WebSocket feed permission tracking from REST token validity

USE `option_simulator`;

-- Add the new column with safe default
ALTER TABLE upstox_accounts
ADD COLUMN feed_entitlement TINYINT(1) NOT NULL DEFAULT 0
COMMENT 'WebSocket feed entitlement: 0=unavailable/unverified, 1=verified and available';

-- Verify the change
DESCRIBE upstox_accounts;
