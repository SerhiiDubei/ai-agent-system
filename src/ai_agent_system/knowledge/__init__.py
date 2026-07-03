"""Knowledge Base module — N3.

Public API:
    KnowledgeService  — orchestration facade (search + ingest)
    VaultWatcher      — file-system watcher for live vault sync
    NoteFrontmatter   — Pydantic schema for Obsidian note frontmatter
    AuthorityTier     — Tier 1/2/3 enum
"""

from ai_agent_system.knowledge.models import AuthorityTier, NoteFrontmatter
from ai_agent_system.knowledge.service import KnowledgeService
from ai_agent_system.knowledge.watcher import VaultWatcher

__all__ = [
    "AuthorityTier",
    "KnowledgeService",
    "NoteFrontmatter",
    "VaultWatcher",
]
