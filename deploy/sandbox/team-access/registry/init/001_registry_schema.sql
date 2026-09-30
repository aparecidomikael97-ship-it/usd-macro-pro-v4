BEGIN;

CREATE TABLE IF NOT EXISTS registry_revisions (
    revision BIGINT PRIMARY KEY CHECK (revision > 0),
    previous_revision_digest CHAR(64) NOT NULL
        CHECK (previous_revision_digest ~ '^[0-9a-f]{64}$'),
    registry_digest CHAR(64) NOT NULL
        CHECK (registry_digest ~ '^[0-9a-f]{64}$'),
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS team_memberships (
    revision BIGINT NOT NULL REFERENCES registry_revisions(revision) ON DELETE RESTRICT,
    username TEXT NOT NULL,
    profile TEXT NOT NULL,
    tenant_ids JSONB NOT NULL DEFAULT '[]'::jsonb,
    active BOOLEAN NOT NULL,
    strong_auth_required BOOLEAN NOT NULL,
    membership_digest CHAR(64) NOT NULL
        CHECK (membership_digest ~ '^[0-9a-f]{64}$'),
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (revision, username)
);

CREATE INDEX IF NOT EXISTS idx_team_memberships_username
    ON team_memberships(username);

CREATE INDEX IF NOT EXISTS idx_team_memberships_active
    ON team_memberships(active);

COMMIT;
