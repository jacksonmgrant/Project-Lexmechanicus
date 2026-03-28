"""seed common tabletop game systems

Revision ID: 0008_seed_common_game_systems
Revises: 0007_flatten_game_systems
Create Date: 2026-03-26 01:00:00.000000
"""

from __future__ import annotations

import re

from alembic import op
import sqlalchemy as sa


revision = "0008_seed_common_game_systems"
down_revision = "0007_flatten_game_systems"
branch_labels = None
depends_on = None


GAME_SYSTEMS: list[tuple[str, list[str]]] = [
    ("Dungeons & Dragons 5th Edition", ["D&D 5e", "DnD 5e", "5e"]),
    ("Dungeons & Dragons 2024", ["D&D 2024", "DnD 2024", "One D&D", "One DnD"]),
    ("Pathfinder First Edition", ["Pathfinder 1e", "PF1e", "PF1"]),
    ("Pathfinder Second Edition", ["Pathfinder 2e", "PF2e", "PF2"]),
    ("Pathfinder Second Edition Remastered", ["Pathfinder 2e Remastered", "PF2e Remastered", "Pathfinder Remastered"]),
    ("Starfinder First Edition", ["Starfinder", "SF1e"]),
    ("Call of Cthulhu 7th Edition", ["Call of Cthulhu", "CoC 7e", "CoC7e"]),
    ("Warhammer 40,000 10th Edition", ["Warhammer 40k 10th Edition", "Warhammer 40K 10th", "40k 10th Edition", "40k 10th"]),
    ("Warhammer Age of Sigmar 4th Edition", ["Age of Sigmar 4th Edition", "AoS 4th Edition", "AoS 4e"]),
    ("Warhammer Fantasy Roleplay 4th Edition", ["WFRP 4e", "Warhammer Fantasy RPG 4e"]),
    ("Kill Team 2024", ["Warhammer 40,000 Kill Team 2024", "Kill Team"]),
    ("Necromunda", ["Necromunda Underhive"]),
    ("Shadowrun Sixth World", ["Shadowrun 6e", "Shadowrun Sixth Edition"]),
    ("Cyberpunk RED", ["Cyberpunk Red"]),
    ("Traveller 2nd Edition", ["Mongoose Traveller 2e", "Traveller 2e"]),
    ("Savage Worlds Adventure Edition", ["SWADE", "Savage Worlds"]),
    ("Vampire: The Masquerade 5th Edition", ["V5", "Vampire 5th Edition"]),
    ("Blades in the Dark", ["BitD"]),
    ("Lancer", ["LANCER"]),
    ("Mork Borg", ["MORK BORG", "Mörk Borg"]),
    ("Dragonbane", ["Drakar och Demoner"]),
    ("Forbidden Lands", ["Forbidden Lands RPG"]),
    ("Alien RPG", ["ALIEN RPG"]),
    ("Delta Green", ["Delta Green RPG"]),
    ("Mutant: Year Zero", ["Mutant Year Zero", "MYZ"]),
    ("Star Wars: Edge of the Empire", ["Edge of the Empire", "EotE"]),
    ("Star Wars: Age of Rebellion", ["Age of Rebellion", "AoR"]),
    ("Star Wars: Force and Destiny", ["Force and Destiny", "FaD"]),
    ("The One Ring Second Edition", ["The One Ring 2e", "TOR 2e"]),
    ("Pendragon 6th Edition", ["Pendragon 6e"]),
    ("Dungeon Crawl Classics", ["DCC RPG", "DCC"]),
    ("Old-School Essentials", ["OSE"]),
]


def _normalize(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip()).lower()[:160]


def _slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.strip().lower()).strip("-")
    return slug[:160]


def upgrade() -> None:
    connection = op.get_bind()

    for name, aliases in GAME_SYSTEMS:
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

    for name, aliases in reversed(GAME_SYSTEMS):
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

        connection.execute(
            sa.text("DELETE FROM rulesets WHERE id = :ruleset_id"),
            {"ruleset_id": ruleset_id},
        )
