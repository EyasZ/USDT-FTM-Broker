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
    def __init__(self, data: Tuple[str, int], score: float = 0):
        if not data:
            raise ValueError("Initialization data cannot be empty")
        self.id, self.chain_id = data
        self.score = score
        self.name = ''  # Placeholder for the token's name
        self.last_price = None

    def __str__(self) -> str:
        return f"Token(id={self.id}, chain_id={self.chain_id}, score={self.score})"

class BinaryTreeNode:
    def __init__(self, token: Token):
        self.token = token
        self.left = None
        self.right = None


class TokenBinaryTree:
    def __init__(self):
        self.root = None
        self.tokens_map = {}  # Hash map for ID-based lookup

    def update_token(self, token_id, new_score, current_price):
        """Updates a token's score and repositions it in the binary tree."""
        if token_id in self.tokens_map:
            # Update the token's score in the hash map
            token = self.tokens_map[token_id]
            # Remove and re-insert the token in the binary tree to reflect its new score
            self.root = self._remove(self.root, token)
            token.score = new_score
            token.last_price = current_price
            self.root = self._insert(self.root, token)
        else:
            logging.info(f"Token ID {token_id} not found in the tree.")

    def insert_token(self, token: Token):
        """Inserts a token into both the binary tree and the hash map."""
        self.root = self._insert(self.root, token)
        self.tokens_map[token.id] = token  # Add to hash map for fast lookup

    def _insert(self, node, token: Token):
        if node is None:
            return BinaryTreeNode(token)
        if token.score <= node.token.score:
            node.left = self._insert(node.left, token)
        else:
            node.right = self._insert(node.right, token)
        return node

    def find_token(self, token_id):
        """Finds a token by ID using the hash map for fast lookup."""
        return self.tokens_map.get(token_id)

    def remove_token(self, token_id):
        """Removes a token from both the binary tree and the hash map."""
        token = self.find_token(token_id)
        if token:
            self.root = self._remove(self.root, token)
            del self.tokens_map[token_id]  # Remove from hash map

    def _remove(self, node, token):
        if node is None:
            return None

        # Step 1: Find the node to be removed
        if token.score < node.token.score:
            node.left = self._remove(node.left, token)
        elif token.score > node.token.score:
            node.right = self._remove(node.right, token)
        else:
            # This is the node to be removed
            if node.token.id != token.id:
                # If the scores are equal but the IDs are not, continue searching
                # This handles the case of duplicate scores
                node.right = self._remove(node.right, token)
            else:
                # Node has no child or one child
                if node.left is None:
                    return node.right
                if node.right is None:
                    return node.left

                # Node has two children, find the in-order successor
                temp = self._find_min(node.right)
                node.token = temp.token  # Replace node's token with its in-order successor's token
                node.right = self._remove(node.right, temp.token)  # Remove the in-order successor

        return node

    def _find_min(self, node):
        """Find the node with the smallest score in the given subtree."""
        current = node
        while current.left is not None:
            current = current.left
        return current

    def in_order_traversal(self, node, tokens):
        """Collects tokens in an in-order manner for logging or inspection."""
        if node:
            self.in_order_traversal(node.left, tokens)
            tokens.append(node.token)
            self.in_order_traversal(node.right, tokens)

    def get_sorted_tokens(self):
        """Returns tokens sorted by their score."""
        sorted_tokens = []
        self.in_order_traversal(self.root, sorted_tokens)
        return sorted_tokens

    def log_tree(self):
        """Logs the current state of the binary tree."""
        sorted_tokens = self.get_sorted_tokens()
        tokens_info = [(token.id, token.score) for token in sorted_tokens]
        logging.info("Current state of the tree (Token ID, Score): {}".format(tokens_info))
