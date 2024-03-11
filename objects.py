import logging
from typing import Tuple, Dict

class TradeSignal:
    """Represents a trading signal with associated data."""
    def __init__(self, data: Tuple):
        if not data:
            raise ValueError("Initialization data cannot be empty")
        self.data = data

    def __str__(self) -> str:
        return f"TradeSignal(data={self.data})"

class Chain:
    """Represents a blockchain chain with id, address, oracle address, and name."""
    def __init__(self, data: Tuple[int, str, str, str]):
        if not data:
            raise ValueError("Initialization data cannot be empty")
        self.id, self.address, self.oracle_address, self.name = data

    def __str__(self) -> str:
        return f"Chain(id={self.id}, address={self.address}, oracle_address={self.oracle_address}, name={self.name})"

class Token:
    """Represents a token with id, chain id, score, and tracks performance history."""
    def __init__(self, data: Tuple[str, int], score: float = 0.0, last_price: float = None):
        if not data:
            raise ValueError("Initialization data cannot be empty")
        self.id, self.chain_id = data
        self.score = score
        self.last_price = last_price  # Now accepts last_price during initialization

    def __str__(self) -> str:
        return f"Token(id={self.id}, chain_id={self.chain_id}, score={self.score}, last_price={self.last_price})"

class BinaryTreeNode:
    """Node in the binary tree, containing a token."""
    def __init__(self, token: Token):
        self.token = token
        self.left = None
        self.right = None

class TokenBinaryTree:
    """Binary tree structure for storing and managing tokens based on their score."""
    def __init__(self):
        self.root = None
        self.tokens_map = {}  # Hash map for ID-based lookup to ensure O(1) access time.

    def insert_token(self, token: Token):
        """Inserts a token into both the binary tree and the hash map, ensuring it's accessible by ID and ordered by score."""
        self.root = self._insert(self.root, token)
        self.tokens_map[token.id] = token

    def _insert(self, node, token: Token):
        """Helper method for inserting a token into the binary tree based on its score."""
        if node is None:
            return BinaryTreeNode(token)
        if token.score <= node.token.score:
            node.left = self._insert(node.left, token)
        else:
            node.right = self._insert(node.right, token)
        return node

    def update_token(self, token_id, new_score, current_price):
        """Updates a token's score and repositions it in the binary tree to reflect the new score."""
        token = self.find_token(token_id)
        if token:
            self.root = self._remove(self.root, token)  # Remove the token from its current position.
            token.score = new_score  # Update the score.
            token.last_price = current_price  # Update the last known price.
            self.root = self._insert(self.root, token)  # Re-insert the token in its new position.
        else:
            logging.warning(f"Token ID {token_id} not found for update.")

    def find_token(self, token_id):
        """Retrieves a token by its ID using the hash map."""
        return self.tokens_map.get(token_id)

    def _remove(self, node, token):
        """Recursively removes a token from the binary tree."""
        if node is None:
            return None
        # Comparison based on score and token ID to locate the exact token.
        if token.score < node.token.score or (token.score == node.token.score and token.id != node.token.id):
            node.left = self._remove(node.left, token)
        elif token.score > node.token.score or (token.score == node.token.score and token.id != node.token.id):
            node.right = self._remove(node.right, token)
        else:
            # Node with only one child or no child.
            if node.left is None:
                temp = node.right
                node = None
                return temp
            elif node.right is None:
                temp = node.left
                node = None
                return temp
            # Node with two children: Get the inorder successor.
            temp = self._find_min(node.right)
            node.token = temp.token
            node.right = self._remove(node.right, temp.token)
        return node

    def _find_min(self, node):
        """Finds the minimum valued node in the given subtree."""
        current = node
        while current.left is not None:
            current = current.left
        return current

    def in_order_traversal(self, node, tokens):
        """Performs an in-order traversal of the binary tree, collecting tokens in ascending score order."""
        if node:
            self.in_order_traversal(node.left, tokens)
            tokens.append(node.token)
            self.in_order_traversal(node.right, tokens)

    def get_sorted_tokens(self):
        """Returns a list of tokens sorted by their score using an in-order traversal."""
        sorted_tokens = []
        self.in_order_traversal(self.root, sorted_tokens)
        return sorted_tokens

    def log_tree(self):
        """Logs the current state of the binary tree, listing tokens by their ID and score."""
        sorted_tokens = self.get_sorted_tokens()
        tokens_info = [(token.id, token.score) for token in sorted_tokens]
        logging.info("Current state of the tree (Token ID, Score): {}".format(tokens_info))
