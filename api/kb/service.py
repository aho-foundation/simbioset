"""Business logic layer for Knowledge Base operations.

Based on conversation tree framework documented in docs/conversation_tree_framework.md.
"""

import time
from typing import Any, Optional

from .models import (
    ConceptNode,
    DeleteResponse,
    ExportResponse,
    ImportResponse,
    NodeCreate,
    NodeUpdate,
    NodeWithContext,
    SearchResponse,
    SearchResult,
    Source,
    StatsResponse,
    TreeResponse,
    TreeStats,
    ConceptNode,
)
from .repository import NodeRepository


class KBService:
    """Knowledge Base service with business logic.

    Implements the ConceptTreeService API from docs/conversation_tree_framework.md lines 66-128.
    """

    def __init__(self, repository: NodeRepository):
        """Initialize service with repository dependency.

        Args:
            repository: NodeRepository instance for data persistence
        """
        self.repository = repository

    def _validate_node_data(self, node_data: dict) -> dict:
        """Validate and fix node data before creating ConceptNode.

        Args:
            node_data: Raw node data from repository

        Returns:
            Validated and fixed node data
        """
        # Ensure content is not empty
        if not node_data.get("content", "").strip():
            node_data["content"] = f"Узел {node_data.get('id', 'без ID')}"

        # Ensure required fields have defaults
        node_data.setdefault("sources", [])
        node_data.setdefault("childrenIds", [])
        node_data.setdefault("type", "message")
        node_data.setdefault("category", "neutral")
        node_data.setdefault("position", {"x": 0.0, "y": 0.0, "z": 0.0})

        return node_data

    def add_concept(
        self,
        parent_id: str | None,
        content: str,
        role: str | None = None,
        node_type: str = "message",
        session_id: str | None = None,
        category: str = "neutral",
        color_code: str = "#6c757d",
        position: dict[str, float] | None = None,
        concept_node_id: str | None = None,
    ) -> ConceptNode:
        """Add a new concept node to the tree.

        Creates a root node if parent_id is None, otherwise adds as child.
        According to docs/conversation_tree_framework.md line 69.

        Args:
            parent_id: ID of parent node, None for root
            content: Text content of the node
            role: Role of the message sender in chat context ('user', 'assistant', 'system')
            node_type: Type of node (default 'message')
            session_id: ID of the chat session (default None)
            category: Category for visualization (default 'neutral')
            color_code: HEX color code for visualization (default '#6c757d')
            position: 3D position coordinates (default None)
            concept_node_id: Reference to original concept node (default None)

        Returns:
            Created ConceptNode

        Raises:
            ValueError: If parent not found or validation fails

        Example:
            >>> service.add_concept(None, "What is climate change?", role="user")
            ConceptNode(id='...', content='What is climate change?', ...)
        """
        if parent_id:
            parent = self.repository.get_by_id(parent_id)
            if not parent:
                raise ValueError(f"Parent node {parent_id} not found")

        node_data: dict[str, Any] = {
            "parentId": parent_id,
            "content": content,
            "role": role,
            "type": node_type,
            "sessionId": session_id,
            "category": category,
            "colorCode": color_code,
            "position": position or {"x": 0.0, "y": 0.0, "z": 0.0},
            "conceptNodeId": concept_node_id,
            "sources": [],
            "childrenIds": [],
            "timestamp": int(time.time() * 1000),
            "expanded": False,
            "selected": False,
        }

        created = self.repository.create(node_data)
        return ConceptNode(**self._validate_node_data(created))

    def get_node_with_context(
        self,
        node_id: str,
        include_parent: bool = True,
        include_children: bool = True,
        include_siblings: bool = True,
        max_depth: int = 1,
    ) -> Optional[NodeWithContext]:
        """
        Get node with surrounding context (parent, children, siblings) (оптимизировано: батчинг).

        Args:
            node_id: Node identifier
            include_parent: Include parent node
            include_children: Include child nodes
            include_siblings: Include sibling nodes
            max_depth: Maximum depth for loading children

        Returns:
            Node with context or None if not found
        """
        # Оптимизация: загружаем все нужные узлы одним запросом
        all_nodes_data = self.repository.get_all()
        nodes_dict = {node.get("id"): node for node in all_nodes_data if node.get("id")}

        node_data = nodes_dict.get(node_id)
        if not node_data:
            return None

        node = ConceptNode(**self._validate_node_data(node_data))
        parent = None
        children = []
        siblings = []

        if include_parent and node.parentId:
            parent_data = nodes_dict.get(node.parentId)
            if parent_data:
                parent = ConceptNode(**self._validate_node_data(parent_data))

        if include_children:
            for child_id in node.childrenIds[:50]:
                child_data = nodes_dict.get(child_id)
                if child_data:
                    children.append(ConceptNode(**self._validate_node_data(child_data)))

        if include_siblings and node.parentId:
            parent_data = nodes_dict.get(node.parentId)
            if parent_data:
                for sibling_id in parent_data.get("childrenIds", []):
                    if sibling_id != node_id:
                        sibling_data = nodes_dict.get(sibling_id)
                        if sibling_data:
                            siblings.append(ConceptNode(**self._validate_node_data(sibling_data)))

        metadata = {
            "childrenCount": len(node.childrenIds),
            "depth": self._calculate_node_depth(node_id),
            "hasMoreChildren": len(node.childrenIds) > len(children),
        }

        return NodeWithContext(node=node, parent=parent, children=children, siblings=siblings, metadata=metadata)

    def get_tree(
        self,
        root_id: Optional[str] = None,
        depth: int = 2,
        limit: int = 50,
        offset: int = 0,
        category: Optional[str] = None,
        node_type: Optional[str] = None,
    ) -> TreeResponse:
        """
        Get tree structure with optional filters.

        Args:
            root_id: Specific root node ID (None for default root)
            depth: Tree depth to load
            limit: Maximum number of nodes
            offset: Pagination offset
            category: Filter by category
            node_type: Filter by type

        Returns:
            Tree response with root and nodes
        """
        all_nodes = self.repository.get_all()

        # Если указан root_id, проверяем его сначала
        if root_id:
            root_data = self.repository.get_by_id(root_id) if all_nodes else None
            if not root_data:
                # Если узел не найден, возвращаем пустое дерево
                # Это нормальная ситуация для новых сессий, которые еще не имеют узлов в KB
                from datetime import datetime

                empty_root = ConceptNode(
                    id=root_id,
                    parentId=None,
                    childrenIds=[],
                    content="Начало сессии",
                    sources=[],
                    timestamp=int(datetime.now().timestamp() * 1000),
                    type="message",
                    category="neutral",
                    embedding=None,
                    expanded=None,
                    selected=None,
                    sessionId=None,
                    role=None,
                    conceptNodeId=None,
                    position={"x": 0.0, "y": 0.0, "z": 0.0},
                )
                return TreeResponse(
                    root=empty_root,
                    nodes=[],
                    stats={"totalNodes": 0, "maxDepth": 0, "rootNodes": 0},
                )
        else:
            # Если root_id не указан, проверяем что база не пустая
            if not all_nodes:
                # Возвращаем пустое дерево вместо исключения
                # Это нормальная ситуация для новой базы знаний
                from datetime import datetime

                empty_root = ConceptNode(
                    id="empty",
                    parentId=None,
                    childrenIds=[],
                    content="База знаний пуста",
                    sources=[],
                    timestamp=int(datetime.now().timestamp() * 1000),
                    type="message",
                    category="neutral",
                    embedding=None,
                    expanded=None,
                    selected=None,
                    sessionId=None,
                    role=None,
                    conceptNodeId=None,
                    position={"x": 0.0, "y": 0.0, "z": 0.0},
                )
                return TreeResponse(
                    root=empty_root,
                    nodes=[],
                    stats={"totalNodes": 0, "maxDepth": 0, "rootNodes": 0},
                )

            # Ищем корневой узел
            root_nodes = [n for n in all_nodes if not n.get("parentId")]
            if not root_nodes:
                # Если нет корневых узлов, возвращаем пустое дерево
                from datetime import datetime

                empty_root = ConceptNode(
                    id="empty",
                    parentId=None,
                    childrenIds=[],
                    content="",
                    sources=[],
                    timestamp=int(datetime.now().timestamp() * 1000),
                    type="message",
                    category="neutral",
                    embedding=None,
                    expanded=None,
                    selected=None,
                    sessionId=None,
                    role=None,
                    conceptNodeId=None,
                    position={"x": 0.0, "y": 0.0, "z": 0.0},
                )
                return TreeResponse(
                    root=empty_root,
                    nodes=[],
                    stats={"totalNodes": 0, "maxDepth": 0, "rootNodes": 0},
                )
            root_data = root_nodes[0]

        root = ConceptNode(**root_data)

        nodes = self._collect_tree_nodes(root.id, depth, category, node_type, limit, offset)

        stats = self._calculate_tree_stats(nodes)

        return TreeResponse(root=root, nodes=nodes, stats=stats)  # type: ignore

    def _collect_tree_nodes(
        self,
        root_id: str,
        depth: int,
        category: Optional[str],
        node_type: Optional[str],
        limit: int,
        offset: int,
    ) -> list[ConceptNode]:
        """Recursively collect tree nodes with filters and limits (оптимизировано: пагинация с ранней остановкой)."""
        # Оптимизация для пагинации: загружаем данные один раз (с кэшем это дешево)
        # Используем индекс byParent для эффективного обхода дерева
        all_nodes_data = self.repository.get_all()
        nodes_dict = {node.get("id"): node for node in all_nodes_data if node.get("id")}

        # Получаем индекс byParent из данных (если доступен через _read_data)
        # Для оптимизации используем childrenIds из узлов напрямую
        nodes: list[ConceptNode] = []
        visited = set()
        target_count = limit + offset  # Останавливаем обход, когда собрано достаточно

        def traverse(node_id: str, current_depth: int):
            """Обходит дерево с ранней остановкой для пагинации."""
            if current_depth > depth or len(nodes) >= target_count:
                return

            if node_id in visited:
                return

            visited.add(node_id)

            node_data = nodes_dict.get(node_id)
            if not node_data:
                return

            # Применяем фильтры
            if category and node_data.get("category") != category:
                return
            if node_type and node_data.get("type") != node_type:
                return

            # Добавляем узел в результат (с валидацией)
            validated_data = self._validate_node_data(node_data)
            nodes.append(ConceptNode(**validated_data))

            # Ранняя остановка: если собрано достаточно узлов, не обходим дальше
            if len(nodes) >= target_count:
                return

            # Обходим дочерние узлы
            for child_id in node_data.get("childrenIds", []):
                traverse(child_id, current_depth + 1)

        # Обходим дерево с ранней остановкой
        traverse(root_id, 0)

        # Сортируем по timestamp для стабильности пагинации
        nodes.sort(key=lambda x: x.timestamp)

        # Применяем пагинацию
        return nodes[offset : offset + limit]

    def _calculate_tree_stats(self, nodes: list[ConceptNode]) -> TreeStats:
        """Calculate statistics for tree nodes.

        Args:
            nodes: List of concept nodes

        Returns:
            TreeStats dictionary with totalNodes, maxDepth, rootNodes
        """
        max_depth = max((self._calculate_node_depth(node.id) for node in nodes), default=0)
        root_nodes = sum(1 for node in nodes if node.parentId is None)

        return TreeStats(totalNodes=len(nodes), maxDepth=max_depth, rootNodes=root_nodes)

    def search_nodes(
        self,
        query: str,
        category: Optional[str] = None,
        node_type: Optional[str] = None,
        limit: int = 20,
        offset: int = 0,
    ) -> SearchResponse:
        """
        Search nodes by content with filters.

        Args:
            query: Search query string
            category: Optional category filter
            node_type: Optional type filter
            limit: Maximum results
            offset: Pagination offset

        Returns:
            Search response with results and metadata
        """
        filters = {"category": category, "type": node_type, "limit": limit, "offset": offset}

        results_data = self.repository.search(query, filters)

        results = [
            SearchResult(
                node=ConceptNode(**item["node"]),
                relevance=item["relevance"],
                matchedFields=["content"] if query.lower() in item["node"].get("content", "").lower() else [],
            )
            for item in results_data
        ]

        all_results = self.repository.search(query, {**filters, "limit": 10000})
        total = len(all_results)

        return SearchResponse(results=results, total=total, query=query, limit=limit, offset=offset)

    def create_node(self, node_data: NodeCreate) -> ConceptNode:
        """Create new node (legacy method, use add_concept instead).

        Args:
            node_data: Node creation data

        Returns:
            Created node

        Raises:
            ValueError: If parent node doesn't exist
        """
        return self.add_concept(node_data.parentId, node_data.content, node_data.role)

    def update_node(self, node_id: str, updates: NodeUpdate) -> Optional[ConceptNode]:
        """
        Update existing node.

        Args:
            node_id: Node identifier
            updates: Partial update data

        Returns:
            Updated node or None if not found
        """
        update_dict = {k: v for k, v in updates.model_dump(exclude_unset=True).items() if v is not None}

        if not update_dict:
            node_data = self.repository.get_by_id(node_id)
            return ConceptNode(**self._validate_node_data(node_data)) if node_data else None

        updated = self.repository.update(node_id, update_dict)
        return ConceptNode(**self._validate_node_data(updated)) if updated else None

    def delete_node(self, node_id: str, cascade: bool = True) -> DeleteResponse:
        """
        Delete node with optional cascade.

        Args:
            node_id: Node identifier
            cascade: Delete children recursively

        Returns:
            Delete response with count

        Raises:
            ValueError: If node not found or has children without cascade
        """
        node_data = self.repository.get_by_id(node_id)
        if not node_data:
            raise ValueError(f"Node {node_id} not found")

        children_count = len(node_data.get("childrenIds", []))
        if children_count > 0 and not cascade:
            raise ValueError(f"Cannot delete node with {children_count} children without cascade=true")

        deleted_count = self.repository.delete(node_id, cascade)

        return DeleteResponse(deleted=True, nodeId=node_id, deletedCount=deleted_count)

    def get_stats(self) -> StatsResponse:
        """
        Get knowledge base statistics.

        Returns:
            Statistics response
        """
        stats = self.repository.get_stats()
        return StatsResponse(**stats)

    def export_tree(self, root_id: Optional[str] = None) -> ExportResponse:
        """
        Export tree to JSON format.

        Args:
            root_id: Optional root node for subtree export

        Returns:
            Export response with nodes
        """
        if root_id:
            tree = self.get_tree(root_id=root_id, depth=100, limit=10000)
            nodes = tree.nodes
        else:
            export_data = self.repository.export_all()
            nodes = [ConceptNode(**n) for n in export_data["nodes"]]

        return ExportResponse(version="1.0.0", exported=len(nodes), nodes=nodes)

    def import_tree(self, nodes: list[ConceptNode], merge: bool = False, overwrite: bool = False) -> ImportResponse:
        """
        Import tree from external data.

        Args:
            nodes: List of nodes to import
            merge: Merge with existing nodes
            overwrite: Overwrite existing nodes

        Returns:
            Import response with results
        """
        nodes_dict = [n.model_dump() for n in nodes]
        result = self.repository.import_nodes(nodes_dict, merge, overwrite)
        return ImportResponse(**result)

    def _calculate_node_depth(self, node_id: str) -> int:
        """Calculate depth of node in tree."""
        depth = 0
        current_id = node_id

        while current_id:
            node_data = self.repository.get_by_id(current_id)
            if not node_data:
                break

            parent_id = node_data.get("parentId")
            if not parent_id:
                break

            depth += 1
            current_id = parent_id

            if depth > 100:
                break

        return depth

    def get_node(self, node_id: str) -> Optional[ConceptNode]:
        """Get node by ID.

        Args:
            node_id: Node identifier

        Returns:
            ConceptNode or None if not found
        """
        node_data = self.repository.get_by_id(node_id)
        if not node_data:
            return None
        return ConceptNode(**self._validate_node_data(node_data))

    def get_root(self) -> ConceptNode | None:
        """Get the root node of the tree.

        According to docs/conversation_tree_framework.md line 77.

        Returns:
            Root ConceptNode or None if no root exists

        Example:
            >>> root = service.get_root()
            >>> root.parentId is None
            True
        """
        nodes = self.repository.get_all()
        for node in nodes:
            if node.get("parentId") is None:
                return ConceptNode(**self._validate_node_data(node))
        return None

    def set_selected(self, node_id: str, selected: bool) -> None:
        """Set selection state of a node.

        According to docs/conversation_tree_framework.md line 87.

        Args:
            node_id: Node identifier
            selected: True to select, False to deselect

        Raises:
            ValueError: If node not found
        """
        node_data = self.repository.get_by_id(node_id)
        if not node_data:
            raise ValueError(f"Node {node_id} not found")

        self.repository.update(node_id, {"selected": selected})

    def toggle_selected(self, node_id: str) -> None:
        """Toggle selection state of a node.

        According to docs/conversation_tree_framework.md line 90.

        Args:
            node_id: Node identifier

        Raises:
            ValueError: If node not found
        """
        node_data = self.repository.get_by_id(node_id)
        if not node_data:
            raise ValueError(f"Node {node_id} not found")

        current_selected = node_data.get("selected", False)
        self.repository.update(node_id, {"selected": not current_selected})

    def get_selected_nodes(self) -> list[ConceptNode]:
        """Get all selected nodes.

        According to docs/conversation_tree_framework.md line 93.

        Returns:
            List of selected ConceptNodes
        """
        all_nodes = self.repository.get_all()
        selected = [ConceptNode(**node) for node in all_nodes if node.get("selected", False)]
        return selected

    def clear_selection(self) -> None:
        """Clear selection from all nodes.

        According to docs/conversation_tree_framework.md line 96.
        """
        all_nodes = self.repository.get_all()
        for node_data in all_nodes:
            node_id = node_data.get("id")
            if not node_id:
                continue
            if node_data.get("selected", False):
                self.repository.update(node_id, {"selected": False})

    def set_expanded(self, node_id: str, expanded: bool) -> None:
        """Set expanded state of a node.

        According to docs/conversation_tree_framework.md line 99.

        Args:
            node_id: Node identifier
            expanded: True to expand, False to collapse

        Raises:
            ValueError: If node not found
        """
        node_data = self.repository.get_by_id(node_id)
        if not node_data:
            raise ValueError(f"Node {node_id} not found")

        self.repository.update(node_id, {"expanded": expanded})

    def toggle_expanded(self, node_id: str) -> None:
        """Toggle expanded state of a node.

        According to docs/conversation_tree_framework.md line 102.

        Args:
            node_id: Node identifier

        Raises:
            ValueError: If node not found
        """
        node_data = self.repository.get_by_id(node_id)
        if not node_data:
            raise ValueError(f"Node {node_id} not found")

        current_expanded = node_data.get("expanded", False)
        self.repository.update(node_id, {"expanded": not current_expanded})

    def get_chat_sessions(self) -> list[ConceptNode]:
        """Get all root nodes that can represent chat sessions.

        Note: ChatSession управляется через ChatSessionService, но корневые узлы
        могут использоваться для представления сессий в дереве знаний.
        ConceptNode не имеет типа 'chat_session' - это атавизм.

        According to docs/conversation_tree_framework.md line 119.

        Returns:
            List of root ConceptNodes (nodes without parent that can represent sessions)
        """
        all_nodes = self.repository.get_all()
        sessions = [ConceptNode(**node) for node in all_nodes if node.get("parentId") is None]
        return sessions

    def get_chat_session_by_id(self, session_id: str) -> ConceptNode | None:
        """Get root node by ID that can represent a chat session.

        Note: ChatSession управляется через ChatSessionService, но корневые узлы
        могут использоваться для представления сессий в дереве знаний.
        ConceptNode не имеет типа 'chat_session' - это атавизм.

        According to docs/conversation_tree_framework.md line 122.

        Args:
            session_id: Root node identifier (used as session identifier)

        Returns:
            Root ConceptNode or None if not found or not a root
        """
        node_data = self.repository.get_by_id(session_id)
        if not node_data:
            return None

        if node_data.get("parentId") is not None:
            return None

        return ConceptNode(**self._validate_node_data(node_data))

    def add_source(self, concept_id: str, source: dict) -> Source:
        """Add a source to a concept node.

        According to docs/conversation_tree_framework.md line 126.

        Args:
            concept_id: Node identifier
            source: Source data (without id and timestamp)

        Returns:
            Created Source object

        Raises:
            ValueError: If node not found or source data invalid
        """
        node_data = self.repository.get_by_id(concept_id)
        if not node_data:
            raise ValueError(f"Node {concept_id} not found")

        import uuid

        source_obj = Source(
            id=str(uuid.uuid4()),
            url=source.get("url", ""),
            title=source.get("title"),
            type=source.get("type", "confirm"),
            tool=source.get("tool"),
            sentiment=source.get("sentiment"),
            userConfirmed=source.get("userConfirmed"),
            reliabilityScore=source.get("reliabilityScore"),
            timestamp=int(time.time() * 1000),
        )

        current_sources = node_data.get("sources", [])
        current_sources.append(source_obj.model_dump())

        self.repository.update(concept_id, {"sources": current_sources})

        return source_obj

    def get_session_messages(self, session_id: str) -> list[dict]:
        """Get all messages for a specific session (оптимизировано: один запрос вместо множественных).

        Args:
            session_id: Session identifier

        Returns:
            List of message dictionaries with content, sender, and timestamp
        """
        # Оптимизация: один запрос get_all() вместо множественных get_by_id()
        all_nodes = self.repository.get_all()
        session_messages = []

        # Filter nodes that belong to the specified session
        for node_data in all_nodes:
            if node_data.get("sessionId") == session_id:
                # Create a message dict from the node
                message = {
                    "id": node_data.get("id"),
                    "content": node_data.get("content", ""),
                    "sender": node_data.get("role", "user"),  # Исправлено: role -> sender для совместимости
                    "timestamp": node_data.get("timestamp", 0),
                    "type": node_data.get("type", "message"),
                }
                session_messages.append(message)

        # Sort messages by timestamp to maintain chronological order
        session_messages.sort(key=lambda x: x["timestamp"])

        return session_messages
