"""
Binary Search Tree (BST) for ranking stocks by score/trend.
Stores (symbol, trend, short_avg, long_avg, latest_price) ordered by trend.
Higher trend = higher rank. Retrieval returns symbols from best to worst.
"""

from dataclasses import dataclass
from typing import Any, List, Optional, Tuple


@dataclass
class BSTNode:
    """Node in the BST. Key = trend (score); value = full stock data tuple."""

    key: float
    value: Any
    left: Optional["BSTNode"] = None
    right: Optional["BSTNode"] = None


class BST:
    """
    Binary Search Tree ordered by score (trend).
    Used to quickly retrieve top-ranked stocks without sorting the full list.
    """

    def __init__(self) -> None:
        self._root: Optional[BSTNode] = None

    def insert(self, key: float, value: Any) -> None:
        """Insert a node with the given key (trend) and value (stock data)."""
        self._root = self._insert_rec(self._root, key, value)

    def _insert_rec(
        self, node: Optional[BSTNode], key: float, value: Any
    ) -> BSTNode:
        if node is None:
            return BSTNode(key=key, value=value)
        if key > node.key:
            node.right = self._insert_rec(node.right, key, value)
        else:
            node.left = self._insert_rec(node.left, key, value)
        return node

    def get_ranked_descending(
        self,
    ) -> List[Tuple[str, float, float, float, float]]:
        """
        Reverse inorder traversal: right -> root -> left.
        Returns list of (symbol, trend, short_avg, long_avg, latest) best first.
        """
        result: List[Tuple[str, float, float, float, float]] = []
        self._reverse_inorder(self._root, result)
        return result

    def _reverse_inorder(
        self,
        node: Optional[BSTNode],
        result: List[Tuple[str, float, float, float, float]],
    ) -> None:
        if node is None:
            return
        self._reverse_inorder(node.right, result)
        result.append(node.value)
        self._reverse_inorder(node.left, result)

    def count_less_than(self, threshold: float) -> int:
        """Count nodes with key (trend) less than threshold."""
        return self._count_less_rec(self._root, threshold)

    def _count_less_rec(self, node: Optional[BSTNode], threshold: float) -> int:
        if node is None:
            return 0
        count = 1 if node.key < threshold else 0
        count += self._count_less_rec(node.left, threshold)
        count += self._count_less_rec(node.right, threshold)
        return count

    def get_max(self) -> Optional[Tuple[float, Any]]:
        """Get the highest-scoring stock (rightmost node)."""
        if self._root is None:
            return None
        node = self._root
        while node.right is not None:
            node = node.right
        return (node.key, node.value)
