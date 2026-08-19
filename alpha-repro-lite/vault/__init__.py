"""
Vault Package: Storage, Raw Archival, Structured Indexing, Semantic Analysis, and Multi-Format Export
"""
from .raw_archive_manager import RawArchiveManager
from .structured_formatter import StructuredFormatter
from .unified_vault_db import UnifiedVaultDB

try:
    from .entry_exporter import EntryExporter
except ImportError:
    EntryExporter = None

try:
    from .text_analyzer import TextAnalyzer
except ImportError:
    TextAnalyzer = None

__all__ = ["RawArchiveManager", "StructuredFormatter", "UnifiedVaultDB", "EntryExporter", "TextAnalyzer"]
