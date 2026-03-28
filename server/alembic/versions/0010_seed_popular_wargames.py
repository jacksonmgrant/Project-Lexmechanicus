"""seed additional popular wargames

Revision ID: 0010_seed_popular_wargames
Revises: 0009_cleanup_typoed_game_systems
Create Date: 2026-03-26 02:00:00.000000
"""

from __future__ import annotations

import re

from alembic import op
import sqlalchemy as sa


revision = "0010_seed_popular_wargames"
down_revision = "0009_cleanup_typoed_game_systems"
branch_labels = None
depends_on = None


WARGAMES: list[tuple[str, list[str]]] = [
    ("Warhammer: The Horus Heresy", ["Horus Heresy", "The Horus Heresy", "30k"]),
    ("Warhammer: The Old World", ["The Old World", "TOW"]),
    ("Middle-earth Strategy Battle Game", ["MESBG", "Middle Earth SBG", "Lord of the Rings Strategy Battle Game"]),
    ("Warcry", ["Warhammer Warcry"]),
    ("Warhammer Underworlds", ["Underworlds"]),
    ("Blood Bowl", ["Blood Bowl Third Season", "Blood Bowl 2020"]),
    ("Legions Imperialis", ["Warhammer Legions Imperialis"]),
    ("Adeptus Titanicus", ["Titanicus"]),
    ("Aeronautica Imperialis", ["Aeronautica"]),
    ("Bolt Action Third Edition", ["Bolt Action 3rd Edition", "Bolt Action 3e"]),
    ("Flames of War", ["FoW"]),
    ("Team Yankee", ["TY"]),
    ("Infinity N5", ["Infinity", "Infinity the Game", "Infinity N4", "Infinity N5"]),
    ("BattleTech", ["Battletech Classic", "Classic BattleTech"]),
    ("BattleTech Alpha Strike", ["Alpha Strike"]),
    ("Warmachine MkIV", ["Warmachine", "Warmachine MK4", "Warmachine 4"]),
    ("Malifaux Third Edition", ["Malifaux 3E", "Malifaux 3rd Edition"]),
    ("Conquest: The Last Argument of Kings", ["Conquest TLAOK", "TLAOK"]),
    ("Conquest: First Blood Second Edition", ["Conquest First Blood", "First Blood 2e"]),
    ("Kings of War Third Edition", ["Kings of War", "KoW 3e"]),
    ("A Song of Ice and Fire Tabletop Miniatures Game", ["ASOIAF TMG", "ASOIAF Miniatures", "A Song of Ice and Fire Miniatures Game"]),
    ("Star Wars: Legion", ["Legion"]),
    ("Star Wars: Shatterpoint", ["Shatterpoint"]),
    ("Star Wars: Armada", ["Armada"]),
    ("Star Wars: X-Wing Second Edition", ["X-Wing", "X-Wing 2.5", "X-Wing 2nd Edition"]),
    ("Marvel: Crisis Protocol", ["Marvel Crisis Protocol", "MCP"]),
    ("Deadzone Third Edition", ["Deadzone", "Deadzone 3e"]),
    ("Firefight Second Edition", ["Mantic Firefight", "Firefight 2e"]),
    ("Frostgrave Second Edition", ["Frostgrave", "Frostgrave 2e"]),
    ("The Silver Bayonet", ["Silver Bayonet"]),
    ("One Page Rules Grimdark Future", ["Grimdark Future", "OPR Grimdark Future"]),
    ("One Page Rules Age of Fantasy", ["Age of Fantasy", "OPR Age of Fantasy"]),
    ("Saga Second Edition", ["Saga 2e", "SAGA"]),
    ("Gaslands Refuelled", ["Gaslands", "Gaslands Refueled"]),
    ("Black Powder Second Edition", ["Black Powder", "Black Powder 2e"]),
    ("Pike & Shotte", ["Pike and Shotte"]),
    ("Hail Caesar", ["Hail Caesar Second Edition", "Hail Caesar 2e"]),
    ("Dropzone Commander Fourth Edition", ["Dropzone Commander", "DZC 4e"]),
    ("Dropfleet Commander", ["DFC"]),
    ("Bushido Risen Sun", ["Bushido"]),
]


def _normalize(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip()).lower()[:160]


def _slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.strip().lower()).strip("-")
    return slug[:160]


def upgrade() -> None:
    connection = op.get_bind()

    for name, aliases in WARGAMES:
        normalized_name = _normalize(name)
        slug_base = _slugify(name)
        slug = slug_base
        suffix = 2

        while connection.execute(sa.text("SELECT 1 FROM rulesets WHERE slug = :slug"), {"slug": slug}).scalar():
            existing_normalized = connection.execute(
                sa.text("SELECT normalized_name FROM rulesets WHERE slug = :slug"),
                {"slug": slug},
            ).scalar()
            if existing_normalized == normalized_name:
                break
            slug = f"{slug_base}-{suffix}"
            suffix += 1

        connection.execute(
            sa.text(
                """
                INSERT INTO rulesets (name, normalized_name, slug, kind, parent_id, edition_label)
                VALUES (:name, :normalized_name, :slug, 'general', NULL, NULL)
                ON CONFLICT (normalized_name) DO NOTHING
                """
            ),
            {
                "name": name,
                "normalized_name": normalized_name,
                "slug": slug,
            },
        )

        ruleset_id = connection.execute(
            sa.text("SELECT id FROM rulesets WHERE normalized_name = :normalized_name"),
            {"normalized_name": normalized_name},
        ).scalar()
        if ruleset_id is None:
            continue

        for alias in [name, *aliases]:
            cleaned_alias = re.sub(r"\s+", " ", alias.strip())[:160]
            if not cleaned_alias:
                continue
            connection.execute(
                sa.text(
                    """
                    INSERT INTO ruleset_aliases (ruleset_id, alias, normalized_alias)
                    VALUES (:ruleset_id, :alias, :normalized_alias)
                    ON CONFLICT (normalized_alias) DO NOTHING
                    """
                ),
                {
                    "ruleset_id": ruleset_id,
                    "alias": cleaned_alias,
                    "normalized_alias": _normalize(cleaned_alias),
                },
            )


def downgrade() -> None:
    connection = op.get_bind()

    for name, aliases in reversed(WARGAMES):
        normalized_name = _normalize(name)
        ruleset_id = connection.execute(
            sa.text("SELECT id FROM rulesets WHERE normalized_name = :normalized_name"),
            {"normalized_name": normalized_name},
        ).scalar()
        if ruleset_id is None:
            continue

        for alias in [name, *aliases]:
            cleaned_alias = re.sub(r"\s+", " ", alias.strip())[:160]
            if not cleaned_alias:
                continue
            connection.execute(
                sa.text(
                    """
                    DELETE FROM ruleset_aliases
                    WHERE ruleset_id = :ruleset_id AND normalized_alias = :normalized_alias
                    """
                ),
                {
                    "ruleset_id": ruleset_id,
                    "normalized_alias": _normalize(cleaned_alias),
                },
            )

        connection.execute(sa.text("DELETE FROM rulesets WHERE id = :ruleset_id"), {"ruleset_id": ruleset_id})
