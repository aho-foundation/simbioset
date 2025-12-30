"""Database repository implementation for knowledge nodes.

Works with both SQLite and PostgreSQL through DatabaseManager.
"""

import json
import uuid
from typing import Any, Dict, List, Optional
from datetime import datetime

from api.storage.db import DatabaseManagerBase
from api.kb.repository import NodeRepository
from api.logger import root_logger

log = root_logger.debug


class DatabaseNodeRepository(NodeRepository):
    """Database-based repository for knowledge nodes.

    Works with both SQLite and PostgreSQL through DatabaseManagerBase.
    Implements Repository pattern for node storage operations.
    """

    def __init__(self, db_manager: DatabaseManagerBase):
        """Initialize repository with database manager.

        Args:
            db_manager: DatabaseManagerBase instance (DatabaseManager or PostgreSQLManager)
        """
        self.db_manager = db_manager
        if not self.db_manager.connection:
            self.db_manager.connect()
        self._ensure_tables()

    def _ensure_tables(self) -> None:
        """Ensure tables exist by loading schema."""
        from pathlib import Path

        # Try multiple possible paths for schema.sql
        possible_paths = [
            self.db_manager.db_path.parent / "api" / "storage" / "schema.sql",
            Path(__file__).parent.parent / "storage" / "schema.sql",
            Path("api/storage/schema.sql"),
        ]

        for schema_path in possible_paths:
            if schema_path.exists():
                with open(schema_path, "r", encoding="utf-8") as f:
                    schema_sql = f.read()
                if self.db_manager.connection:
                    self.db_manager.connection.executescript(schema_sql)
                    self.db_manager.connection.commit()
                break

    def _dict_to_node(self, row: Dict[str, Any]) -> Dict[str, Any]:
        """Convert database row to node dictionary.

        Args:
            row: Database row as dictionary

        Returns:
            Node dictionary
        """
        node = {
            "id": row["id"],
            "parentId": row.get("parent_id"),
            "childrenIds": [],  # Will be loaded separately
            "content": row["content"],
            "type": row["type"],
            "category": row["category"],
            "role": row.get("role"),
            "sessionId": row.get("session_id"),
            "conceptNodeId": row.get("concept_node_id"),
            "timestamp": row["timestamp"],
            "position": {
                "x": row.get("position_x", 0.0),
                "y": row.get("position_y", 0.0),
                "z": row.get("position_z", 0.0),
            },
            "expanded": bool(row.get("expanded", False)),
            "selected": bool(row.get("selected", False)),
            "sources": json.loads(row["sources"]) if row.get("sources") else [],
            "metadata": json.loads(row["metadata"]) if row.get("metadata") else {},
        }
        return node

    def _node_to_dict(self, node: Dict[str, Any]) -> Dict[str, Any]:
        """Convert node dictionary to database row.

        Args:
            node: Node dictionary

        Returns:
            Database row dictionary
        """
        return {
            "id": node.get("id"),
            "parent_id": node.get("parentId"),
            "content": node.get("content", ""),
            "type": node.get("type", "message"),
            "category": node.get("category", "neutral"),
            "role": node.get("role"),
            "session_id": node.get("sessionId"),
            "concept_node_id": node.get("conceptNodeId"),
            "timestamp": node.get("timestamp", int(datetime.now().timestamp() * 1000)),
            "position_x": node.get("position", {}).get("x", 0.0),
            "position_y": node.get("position", {}).get("y", 0.0),
            "position_z": node.get("position", {}).get("z", 0.0),
            "expanded": node.get("expanded", False),
            "selected": node.get("selected", False),
            "sources": json.dumps(node.get("sources", [])),
            "metadata": json.dumps(node.get("metadata", {})),
        }

    def _load_children_ids(self, node_id: str) -> List[str]:
        """Load children IDs for a node.

        Args:
            node_id: Node ID

        Returns:
            List of child IDs
        """
        cursor = self.db_manager.connection.cursor()
        cursor.execute(
            "SELECT child_id FROM node_children WHERE parent_id = ? ORDER BY child_order",
            (node_id,),
        )
        rows = cursor.fetchall()
        return [row[0] for row in rows]

    def get_by_id(self, node_id: str) -> Optional[dict]:
        """Get node by ID.

        Args:
            node_id: Node ID

        Returns:
            Node dictionary or None
        """
        cursor = self.db_manager.connection.cursor()
        cursor.execute("SELECT * FROM knowledge_nodes WHERE id = ?", (node_id,))
        row = cursor.fetchone()

        if not row:
            return None

        node = self._dict_to_node(dict(row))
        node["childrenIds"] = self._load_children_ids(node_id)
        return node

    def get_all(self) -> list[dict]:
        """Get all nodes.

        Returns:
            List of node dictionaries
        """
        cursor = self.db_manager.connection.cursor()
        cursor.execute("SELECT * FROM knowledge_nodes")
        rows = cursor.fetchall()

        nodes = []
        for row in rows:
            node = self._dict_to_node(dict(row))
            node["childrenIds"] = self._load_children_ids(node["id"])
            nodes.append(node)

        return nodes

    def create(self, node: dict) -> dict:
        """Create new node.

        Args:
            node: Node dictionary

        Returns:
            Created node dictionary
        """
        if "id" not in node:
            node["id"] = str(uuid.uuid4())

        node_data = self._node_to_dict(node)
        children_ids = node.get("childrenIds", [])

        cursor = self.db_manager.connection.cursor()

        # Insert node
        cursor.execute(
            """
            INSERT INTO knowledge_nodes 
            (id, parent_id, content, type, category, role, session_id, 
             concept_node_id, timestamp, position_x, position_y, position_z, 
             expanded, selected, sources, metadata)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                node_data["id"],
                node_data["parent_id"],
                node_data["content"],
                node_data["type"],
                node_data["category"],
                node_data["role"],
                node_data["session_id"],
                node_data["concept_node_id"],
                node_data["timestamp"],
                node_data["position_x"],
                node_data["position_y"],
                node_data["position_z"],
                node_data["expanded"],
                node_data["selected"],
                node_data["sources"],
                node_data["metadata"],
            ),
        )

        # Insert children relationships
        for order, child_id in enumerate(children_ids):
            cursor.execute(
                """
                INSERT INTO node_children (parent_id, child_id, child_order)
                VALUES (?, ?, ?)
                ON CONFLICT(parent_id, child_id) DO UPDATE SET child_order = ?
                """,
                (node_data["id"], child_id, order, order),
            )

        self.db_manager.connection.commit()

        # Return created node with children
        created = self.get_by_id(node_data["id"])
        return created or node

    def update(self, node_id: str, updates: dict) -> Optional[dict]:
        """Update existing node.

        Args:
            node_id: Node ID
            updates: Dictionary with fields to update

        Returns:
            Updated node dictionary or None
        """
        node = self.get_by_id(node_id)
        if not node:
            return None

        # Merge updates
        node.update(updates)

        node_data = self._node_to_dict(node)
        children_ids = updates.get("childrenIds", node.get("childrenIds", []))

        cursor = self.db_manager.connection.cursor()

        # Update node
        cursor.execute(
            """
            UPDATE knowledge_nodes SET
                parent_id = ?, content = ?, type = ?, category = ?, role = ?,
                session_id = ?, concept_node_id = ?, timestamp = ?,
                position_x = ?, position_y = ?, position_z = ?,
                expanded = ?, selected = ?, sources = ?, metadata = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (
                node_data["parent_id"],
                node_data["content"],
                node_data["type"],
                node_data["category"],
                node_data["role"],
                node_data["session_id"],
                node_data["concept_node_id"],
                node_data["timestamp"],
                node_data["position_x"],
                node_data["position_y"],
                node_data["position_z"],
                node_data["expanded"],
                node_data["selected"],
                node_data["sources"],
                node_data["metadata"],
                node_id,
            ),
        )

        # Update children relationships
        cursor.execute("DELETE FROM node_children WHERE parent_id = ?", (node_id,))
        for order, child_id in enumerate(children_ids):
            cursor.execute(
                """
                INSERT INTO node_children (parent_id, child_id, child_order)
                VALUES (?, ?, ?)
                """,
                (node_id, child_id, order),
            )

        self.db_manager.connection.commit()

        return self.get_by_id(node_id)

    def delete(self, node_id: str, cascade: bool = False) -> int:
        """Delete node and optionally its children.

        Args:
            node_id: Node ID
            cascade: If True, delete children recursively

        Returns:
            Count of deleted nodes
        """
        if cascade:
            # CASCADE DELETE will handle children automatically via FOREIGN KEY
            cursor = self.db_manager.connection.cursor()
            cursor.execute("DELETE FROM knowledge_nodes WHERE id = ?", (node_id,))
            deleted_count = cursor.rowcount
            self.db_manager.connection.commit()
            return deleted_count
        else:
            # Check if node has children
            children = self._load_children_ids(node_id)
            if children:
                raise ValueError(f"Node {node_id} has children. Use cascade=True to delete.")

            cursor = self.db_manager.connection.cursor()
            cursor.execute("DELETE FROM knowledge_nodes WHERE id = ?", (node_id,))
            deleted_count = cursor.rowcount
            self.db_manager.connection.commit()
            return deleted_count

    def search(self, query: str, filters: dict) -> list[dict]:
        """Search nodes by query and filters.

        Args:
            query: Search query
            filters: Filter dictionary (type, category, session_id, etc.)

        Returns:
            List of matching node dictionaries
        """
        cursor = self.db_manager.connection.cursor()

        # Build WHERE clause
        conditions = []
        params = []

        if query:
            conditions.append("content LIKE ?")
            params.append(f"%{query}%")

        if filters.get("type"):
            conditions.append("type = ?")
            params.append(filters["type"])

        if filters.get("category"):
            conditions.append("category = ?")
            params.append(filters["category"])

        if filters.get("session_id"):
            conditions.append("session_id = ?")
            params.append(filters["session_id"])

        where_clause = " AND ".join(conditions) if conditions else "1=1"

        # Execute query
        sql = f"SELECT * FROM knowledge_nodes WHERE {where_clause}"
        limit = filters.get("limit", 100)
        offset = filters.get("offset", 0)

        if limit:
            sql += f" LIMIT {limit}"
        if offset:
            sql += f" OFFSET {offset}"

        cursor.execute(sql, params)
        rows = cursor.fetchall()

        nodes = []
        for row in rows:
            node = self._dict_to_node(dict(row))
            node["childrenIds"] = self._load_children_ids(node["id"])
            nodes.append(node)

        return nodes

    def get_stats(self) -> dict:
        """Get statistics about the knowledge base.

        Returns:
            Statistics dictionary
        """
        cursor = self.db_manager.connection.cursor()

        # Total nodes
        cursor.execute("SELECT COUNT(*) FROM knowledge_nodes")
        total_nodes = cursor.fetchone()[0]

        # Nodes by type
        cursor.execute("SELECT type, COUNT(*) FROM knowledge_nodes GROUP BY type")
        by_type = {row[0]: row[1] for row in cursor.fetchall()}

        # Nodes by category
        cursor.execute("SELECT category, COUNT(*) FROM knowledge_nodes GROUP BY category")
        by_category = {row[0]: row[1] for row in cursor.fetchall()}

        # Root nodes
        cursor.execute("SELECT COUNT(*) FROM knowledge_nodes WHERE parent_id IS NULL")
        root_nodes = cursor.fetchone()[0]

        return {
            "totalNodes": total_nodes,
            "rootNodes": root_nodes,
            "byType": by_type,
            "byCategory": by_category,
        }

    def export_all(self) -> dict:
        """Export all data.

        Returns:
            Dictionary with all nodes
        """
        nodes = self.get_all()
        return {
            "version": "1.0.0",
            "nodes": {node["id"]: node for node in nodes},
            "metadata": self.get_stats(),
        }

    def import_nodes(self, nodes: list[dict], merge: bool, overwrite: bool) -> dict:
        """Import nodes with merge/overwrite options.

        Args:
            nodes: List of node dictionaries
            merge: If True, merge with existing nodes
            overwrite: If True, overwrite existing nodes

        Returns:
            Import result dictionary
        """
        imported = 0
        updated = 0
        skipped = 0

        for node in nodes:
            existing = self.get_by_id(node.get("id", ""))
            if existing:
                if overwrite:
                    self.update(node["id"], node)
                    updated += 1
                elif merge:
                    merged = {**existing, **node}
                    self.update(node["id"], merged)
                    updated += 1
                else:
                    skipped += 1
            else:
                self.create(node)
                imported += 1

        return {
            "imported": imported,
            "updated": updated,
            "skipped": skipped,
            "total": len(nodes),
        }
