"""Repository layer for Knowledge Base storage operations."""

import json
import fcntl
import uuid
import time
from pathlib import Path
from typing import Any, Optional, cast
from datetime import datetime
from abc import ABC, abstractmethod

from .constants import MAX_TREE_DEPTH, MAX_TOTAL_NODES, MAX_CHILDREN_PER_NODE
from .models import DataDict


class NodeRepository(ABC):
    """Abstract repository interface for node storage operations."""

    @abstractmethod
    def get_by_id(self, node_id: str) -> Optional[dict]:
        """Get node by ID."""
        pass

    @abstractmethod
    def get_all(self) -> list[dict]:
        """Get all nodes."""
        pass

    @abstractmethod
    def create(self, node: dict) -> dict:
        """Create new node."""
        pass

    @abstractmethod
    def update(self, node_id: str, updates: dict) -> Optional[dict]:
        """Update existing node."""
        pass

    @abstractmethod
    def delete(self, node_id: str, cascade: bool = False) -> int:
        """Delete node and optionally its children. Returns count of deleted nodes."""
        pass

    @abstractmethod
    def search(self, query: str, filters: dict) -> list[dict]:
        """Search nodes by query and filters."""
        pass

    @abstractmethod
    def get_stats(self) -> dict:
        """Get statistics about the knowledge base."""
        pass

    @abstractmethod
    def export_all(self) -> dict:
        """Export all data."""
        pass

    @abstractmethod
    def import_nodes(self, nodes: list[dict], merge: bool, overwrite: bool) -> dict:
        """Import nodes with merge/overwrite options."""
        pass

    @abstractmethod
    def get_selected(self) -> list[dict]:
        """Get all nodes that are currently selected."""
        pass

    @abstractmethod
    def clear_selection(self) -> int:
        """Clear selection state for all nodes. Returns count of cleared nodes."""
        pass


class JSONNodeRepository(NodeRepository):
    """JSON file-based repository with file locking for thread safety and simple caching."""

    def __init__(self, file_path: str = "data/knowledge_base.json"):
        """Initialize repository with storage file path."""
        self.file_path = Path(file_path)
        self.file_path.parent.mkdir(parents=True, exist_ok=True)
        self._ensure_storage()
        # Простое in-memory кэширование для частых операций
        self._cache: Optional[DataDict] = None
        self._cache_timestamp: float = 0.0
        self._cache_ttl: float = (
            5.0  # TTL кэша в секундах (5 сек для баланса между производительностью и актуальностью)
        )

    def _ensure_storage(self) -> None:
        """Create storage file with initial structure if it doesn't exist."""
        if not self.file_path.exists():
            initial_data: DataDict = {
                "version": "1.0.0",
                "rootId": None,
                "metadata": {
                    "created": int(datetime.now().timestamp() * 1000),
                    "updated": int(datetime.now().timestamp() * 1000),
                    "totalNodes": 0,
                    "maxDepth": 0,
                },
                "nodes": {},
                "index": {"byCategory": {}, "byType": {}, "byParent": {}},
            }
            self._write_data(initial_data)

    def _read_data(self, use_cache: bool = True) -> DataDict:
        """Read data from JSON file with shared lock (multiple readers allowed) with optional caching.

        Lock is acquired immediately after opening to prevent race conditions.
        Uses simple in-memory cache to reduce file I/O for frequent reads.

        Args:
            use_cache: Whether to use cache (default True)

        Returns:
            Tree data dictionary with nodes and metadata

        Raises:
            json.JSONDecodeError: If file contains invalid JSON
        """
        # Проверяем кэш
        if use_cache and self._cache is not None:
            current_time = time.time()
            if current_time - self._cache_timestamp < self._cache_ttl:
                return self._cache

        with open(self.file_path, "r", encoding="utf-8") as f:
            # CRITICAL: Lock must be acquired immediately after open to prevent race condition
            fcntl.flock(f.fileno(), fcntl.LOCK_SH)
            try:
                data = cast(DataDict, json.load(f))
                # Обновляем кэш
                if use_cache:
                    self._cache = data
                    self._cache_timestamp = time.time()
                return data
            finally:
                fcntl.flock(f.fileno(), fcntl.LOCK_UN)

    def _write_data(self, data: DataDict) -> None:
        """Write data to JSON file with exclusive lock (single writer).

        Lock is acquired immediately after opening to prevent race conditions.
        Invalidates cache after write to ensure consistency.

        Args:
            data: Tree data dictionary to write

        Raises:
            OSError: If file write fails
        """
        with open(self.file_path, "w", encoding="utf-8") as f:
            # CRITICAL: Lock must be acquired immediately after open to prevent race condition
            fcntl.flock(f.fileno(), fcntl.LOCK_EX)
            try:
                json.dump(data, f, indent=2, ensure_ascii=False)
                # Инвалидируем кэш после записи
                self._cache = None
                self._cache_timestamp = 0.0
            finally:
                fcntl.flock(f.fileno(), fcntl.LOCK_UN)

    def _check_circular_dependency(self, data: DataDict, node_id: str, parent_id: str) -> bool:
        """Check if adding parent_id would create a cycle in the tree.

        Traverses up the tree from parent_id to detect if node_id appears in the ancestry.
        This prevents infinite loops and ensures tree integrity.

        Args:
            data: Tree data dictionary
            node_id: ID of the node being added/updated
            parent_id: ID of the proposed parent

        Returns:
            False if no cycle detected

        Raises:
            ValueError: If cycle would be created

        Example:
            >>> repo._check_circular_dependency(data, "child", "parent")
            False
            >>> repo._check_circular_dependency(data, "parent", "child")  # Would create cycle
            ValueError: Circular dependency detected
        """
        current = parent_id
        visited = {node_id}

        while current:
            if current in visited:
                raise ValueError(f"Circular dependency detected: {node_id} -> {parent_id}")
            visited.add(current)
            node = data["nodes"].get(current)
            if not node:
                break
            current = node.get("parentId")  # type: ignore

        return False

    def get_by_id(self, node_id: str) -> Optional[dict[str, Any]]:
        """Get node by ID."""
        data = self._read_data()
        return data["nodes"].get(node_id)  # type: ignore

    def get_all(self) -> list[dict[str, Any]]:
        """Get all nodes."""
        data = self._read_data()
        return list(data["nodes"].values())  # type: ignore

    def create(self, node: dict[str, Any]) -> dict[str, Any]:
        """Create new node with auto-generated ID if not provided.

        Args:
            node: Node data dictionary

        Returns:
            Created node data

        Raises:
            ValueError: If node ID already exists, parent doesn't exist,
                       circular dependency detected, or limits exceeded
        """
        data = self._read_data()

        # Check total nodes limit
        if len(data["nodes"]) >= MAX_TOTAL_NODES:
            raise ValueError(f"Maximum number of nodes ({MAX_TOTAL_NODES}) exceeded")

        if "id" not in node or not node["id"]:
            node["id"] = str(uuid.uuid4())

        node_id = node["id"]

        # Check ID uniqueness
        if node_id in data["nodes"]:
            raise ValueError(f"Node with ID {node_id} already exists")

        if "timestamp" not in node:
            node["timestamp"] = int(datetime.now().timestamp() * 1000)

        if "childrenIds" not in node:
            node["childrenIds"] = []

        if "sources" not in node:
            node["sources"] = []

        parent_id = node.get("parentId")
        if parent_id:
            # Check parent exists
            if parent_id not in data["nodes"]:
                raise ValueError(f"Parent node {parent_id} does not exist")

            # Check circular dependency
            self._check_circular_dependency(data, node_id, parent_id)

            # Check children limit
            parent_node = data["nodes"][parent_id]
            if len(parent_node.get("childrenIds", [])) >= MAX_CHILDREN_PER_NODE:
                raise ValueError(f"Parent node {parent_id} has reached maximum children ({MAX_CHILDREN_PER_NODE})")

            # Check depth limit
            parent_depth = self._calculate_depth(data, parent_id)
            if parent_depth + 1 >= MAX_TREE_DEPTH:
                raise ValueError(f"Adding node would exceed maximum tree depth ({MAX_TREE_DEPTH})")

        data["nodes"][node_id] = node  # type: ignore

        if parent_id and parent_id in data["nodes"]:
            if node_id not in data["nodes"][parent_id]["childrenIds"]:
                data["nodes"][parent_id]["childrenIds"].append(node_id)

        self._update_indices(data, node)

        if data["rootId"] is None and not parent_id:
            data["rootId"] = node_id

        data["metadata"]["totalNodes"] = len(data["nodes"])
        data["metadata"]["updated"] = int(datetime.now().timestamp() * 1000)

        self._write_data(data)
        return node

    def update(self, node_id: str, updates: dict) -> Optional[dict]:
        """Update existing node with partial updates."""
        data = self._read_data()

        if node_id not in data["nodes"]:
            return None

        node = data["nodes"][node_id]
        node.update(updates)  # type: ignore
        node["timestamp"] = int(datetime.now().timestamp() * 1000)

        self._rebuild_indices(data)

        data["metadata"]["updated"] = int(datetime.now().timestamp() * 1000)

        self._write_data(data)
        return node  # type: ignore

    def delete(self, node_id: str, cascade: bool = False) -> int:
        """Delete node and optionally all its descendants."""
        data = self._read_data()

        if node_id not in data["nodes"]:
            return 0

        deleted_count = 0

        if cascade:
            children_ids = data["nodes"][node_id].get("childrenIds", [])
            for child_id in children_ids:
                deleted_count += self._delete_recursive(data, child_id)

        parent_id = data["nodes"][node_id].get("parentId")
        if parent_id and parent_id in data["nodes"]:
            if node_id in data["nodes"][parent_id]["childrenIds"]:
                data["nodes"][parent_id]["childrenIds"].remove(node_id)

        del data["nodes"][node_id]
        deleted_count += 1

        if data["rootId"] == node_id:
            data["rootId"] = None

        self._rebuild_indices(data)

        data["metadata"]["totalNodes"] = len(data["nodes"])
        data["metadata"]["updated"] = int(datetime.now().timestamp() * 1000)

        self._write_data(data)
        return deleted_count

    def _delete_recursive(self, data: DataDict, node_id: str) -> int:
        """Recursively delete node and all its children without writing.

        This is a helper method for cascade deletion that modifies the data
        dictionary in-place without writing to disk.

        Args:
            data: Tree data dictionary
            node_id: ID of the node to delete

        Returns:
            Number of nodes deleted (including the node itself and all descendants)
        """
        if node_id not in data["nodes"]:
            return 0

        deleted_count = 0
        children_ids = data["nodes"][node_id].get("childrenIds", [])

        for child_id in children_ids:
            deleted_count += self._delete_recursive(data, child_id)

        del data["nodes"][node_id]
        deleted_count += 1

        return deleted_count

    def search(self, query: str, filters: dict) -> list[dict]:
        """Search nodes by content with optional filters."""
        data = self._read_data()
        results = []
        query_lower = query.lower()

        for node in data["nodes"].values():
            if filters.get("category") and node.get("category") != filters["category"]:
                continue

            if filters.get("type") and node.get("type") != filters["type"]:
                continue

            content = node.get("content", "").lower()
            if query_lower in content:
                relevance = content.count(query_lower) / max(len(content.split()), 1)
                results.append({"node": node, "relevance": min(relevance, 1.0)})

        results.sort(key=lambda x: x["relevance"], reverse=True)  # type: ignore

        limit = filters.get("limit", 20)
        offset = filters.get("offset", 0)

        return results[offset : offset + limit]

    def get_stats(self) -> dict:
        """Calculate and return knowledge base statistics."""
        data = self._read_data()

        categories: dict[str, int] = {}
        types: dict[str, int] = {}
        depths = []

        for node in data["nodes"].values():
            category = node.get("category", "neutral")
            categories[category] = categories.get(category, 0) + 1  # type: ignore

            node_type = node.get("type", "message")
            types[node_type] = types.get(node_type, 0) + 1  # type: ignore

            depth = self._calculate_depth(data, node["id"])
            depths.append(depth)

        root_nodes = [n for n in data["nodes"].values() if not n.get("parentId")]

        return {
            "totalNodes": len(data["nodes"]),
            "rootNodes": len(root_nodes),
            "maxDepth": max(depths) if depths else 0,
            "avgDepth": sum(depths) / len(depths) if depths else 0,
            "categories": categories,
            "types": types,
            "lastUpdated": data["metadata"]["updated"],
        }

    def export_all(self) -> dict:
        """Export complete knowledge base data."""
        data = self._read_data()
        return {
            "version": data["version"],
            "exported": int(datetime.now().timestamp() * 1000),
            "nodes": list(data["nodes"].values()),
        }

    def import_nodes(self, nodes: list[dict], merge: bool, overwrite: bool) -> dict:
        """Import nodes with conflict resolution."""
        data = self._read_data()
        conflicts = []
        warnings = []
        imported_count = 0

        for node in nodes:
            node_id = node.get("id")
            if not node_id:
                warnings.append(f"Skipped node without ID: {node.get('content', 'unknown')[:50]}")
                continue

            if node_id in data["nodes"]:
                if overwrite:
                    data["nodes"][node_id] = node  # type: ignore
                    imported_count += 1
                elif merge:
                    data["nodes"][node_id].update(node)  # type: ignore
                    imported_count += 1
                else:
                    conflicts.append(node_id)
            else:
                data["nodes"][node_id] = node  # type: ignore
                imported_count += 1

        self._rebuild_indices(data)

        data["metadata"]["totalNodes"] = len(data["nodes"])
        data["metadata"]["updated"] = int(datetime.now().timestamp() * 1000)

        self._write_data(data)

        return {
            "imported": True,
            "nodesCount": imported_count,
            "conflicts": conflicts,
            "warnings": warnings,
        }

    def _update_indices(self, data: DataDict, node: dict[str, Any]) -> None:
        """Update indices for a single node.

        Maintains lookup indices for fast filtering by category, type, and parent.
        Ensures node ID is present in appropriate index lists.

        Args:
            data: Tree data dictionary
            node: Node data to index
        """
        node_id = node["id"]
        category = node.get("category", "neutral")
        node_type = node.get("type", "message")
        parent_id = node.get("parentId")

        if category not in data["index"]["byCategory"]:
            data["index"]["byCategory"][category] = []
        if node_id not in data["index"]["byCategory"][category]:
            data["index"]["byCategory"][category].append(node_id)

        if node_type not in data["index"]["byType"]:
            data["index"]["byType"][node_type] = []
        if node_id not in data["index"]["byType"][node_type]:
            data["index"]["byType"][node_type].append(node_id)

        if parent_id:
            if parent_id not in data["index"]["byParent"]:
                data["index"]["byParent"][parent_id] = []
            if node_id not in data["index"]["byParent"][parent_id]:
                data["index"]["byParent"][parent_id].append(node_id)

    def _rebuild_indices(self, data: DataDict) -> None:
        """Rebuild all indices from scratch.

        Called after updates to ensure index consistency with actual node data.

        Args:
            data: Tree data dictionary
        """
        data["index"] = {"byCategory": {}, "byType": {}, "byParent": {}}

        for node in data["nodes"].values():
            self._update_indices(data, node)  # type: ignore

    def _calculate_depth(self, data: DataDict, node_id: str, depth: int = 0) -> int:
        """Calculate depth of node in tree (0 for root nodes).

        Recursively traverses up the tree to count the depth.

        Args:
            data: Tree data dictionary
            node_id: ID of the node to calculate depth for
            depth: Current recursion depth (internal parameter)

        Returns:
            Depth of the node (0 for root nodes, 1 for direct children, etc.)
        """
        node = data["nodes"].get(node_id)
        if not node:
            return depth

        parent_id = node.get("parentId")
        if not parent_id:
            return depth

        return self._calculate_depth(data, parent_id, depth + 1)

    def get_selected(self) -> list[dict]:
        """Get all nodes that are currently selected.

        Returns:
            List of selected node dictionaries
        """
        data = self._read_data()
        selected_nodes = []
        for _node_id, node_data in data["nodes"].items():
            if node_data.get("selected", False):
                selected_nodes.append(cast(dict, node_data))
        return selected_nodes

    def clear_selection(self) -> int:
        """Clear selection state for all nodes.

        Returns:
            Number of nodes that had their selection cleared
        """
        data = self._read_data()
        cleared_count = 0

        # Clear selection for all nodes
        for node_id, node_data in data["nodes"].items():
            if node_data.get("selected", False):
                node_data["selected"] = False
                cleared_count += 1

        if cleared_count > 0:
            self._write_data(data)

        return cleared_count
