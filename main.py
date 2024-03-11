import json
import time
import logging
from threading import Thread
from one_inch import OneInchAPI  # Assuming this is correctly implemented elsewhere
from objects import Chain, Token, TokenBinaryTree
import sys

class TradingBot:
    def __init__(self, budget=10000, chain_ids=None, interval=30, api_key="YOUR_API_KEY"):
        self.budget = budget
        self.chain_ids = chain_ids if chain_ids is not None else {}
        self.interval = interval
        self.logging = None
        self.one_inch_api = OneInchAPI(api_key)
        self.configure_logging()
        self.chains = {name: Chain((chain_id, '0xeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee', 'ORACLE_ADDRESS', name)) for name, chain_id in self.chain_ids.items()}
        self.tokens_per_chain = {name: TokenBinaryTree() for name in self.chain_ids}

    def configure_logging(self):
        logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s', filename='trading_bot.log', filemode='w')
        console = logging.StreamHandler()
        console.setLevel(logging.INFO)
        formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        console.setFormatter(formatter)
        logging.getLogger('').addHandler(console)
        self.logging = logging

    def chain_handler(self, chain_name, chain_id):
        counter = 1
        while True:
            self.logging.info(f"Processing {chain_name} with chain ID {chain_id}")
            logging.info(f"Iteration counter: {counter}")
            self.evaluate_tokens(chain_name, chain_id)
            counter += 1
            self.tokens_per_chain[chain_name].log_tree()  # Log the current state of the tree
            time.sleep(self.interval)

    def calculate_adjustment_factor(self, price_difference, last_price):
        """
        Calculates the adjustment factor for a token's score based on the price difference and last price.

        :param price_difference: The difference between the current price and the last recorded price.
        :param last_price: The last recorded price of the token.
        :return: A calculated adjustment factor.
        """
        if last_price == 0:
            return 0  # Avoid division by zero if last_price is not initialized.
        # Example calculation: adjust score based on percentage change, magnified by a factor (e.g., 10).
        adjustment_factor = abs(price_difference / last_price) * 100
        bonus = 0
        if price_difference <= 0:
            if price_difference < 0:
                bonus = 1
            return adjustment_factor + bonus
        else:
            return -1 * adjustment_factor

    def evaluate_tokens(self, chain_name, chain_id):
        raw_tokens = json.loads(self.one_inch_api.get_chain_pairs(chain_id))
        for token_id, token_info in raw_tokens.items():
            if token_id == '0xeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee':  # Skip native currency
                continue

            token = self.tokens_per_chain[chain_name].find_token(token_id)
            if token is None:
                current_price_info = self.one_inch_api.get_swap_rate(token_id, network=chain_id)
                time.sleep(0.5)
                if current_price_info and 'price' in current_price_info:
                    current_price = int(current_price_info['price'])  # Ensure float for accurate calculations
                    # Fetch and calculate the initial score based on market cap for new tokens
                    market_cap = self.get_market_cap(token_id, chain_id)
                    initial_score = self.calculate_initial_score(market_cap)
                    # Initialize a new token with the current price as its last price
                    token = Token((token_id, chain_id), initial_score, current_price)
                    self.tokens_per_chain[chain_name].insert_token(token)  # Insert new token into the tree
                    self.logging.info(f"Inserted new token {token_id} with initial score {initial_score}.")
                else:
                    continue
            else:
                # Calculate price difference and adjust token score
                current_price_info = self.one_inch_api.get_swap_rate(token_id, network=chain_id)
                time.sleep(0.5)
                if current_price_info and 'price' in current_price_info:
                    current_price = int(current_price_info['price'])
                else:
                    continue
                if not token.last_price or token.last_price == 0:
                    logging.error(f"last price was not updated correctly for token {token.id}")
                price_difference = current_price - token.last_price
                adjustment_factor = self.calculate_adjustment_factor(price_difference, token.last_price)
                new_score = token.score + adjustment_factor  # Ensure score doesn't go below 0
                self.tokens_per_chain[chain_name].update_token(token.id, new_score,
                                                               current_price)  # Update token in the tree
                self.logging.info(
                    f"Updated token {token_id} with new score {new_score}, price difference {price_difference}.")

    def main_loop(self):
        for chain_name, chain_id in self.chain_ids.items():
            t = Thread(target=self.chain_handler, args=(chain_name, chain_id))
            t.start()
        # Threads are deliberately not joined to keep the script running indefinitely.

        # Placeholder methods for market cap retrieval and initial score calculation

    def get_market_cap(self, token_id, chain_id):
        # Implement the logic to retrieve market cap information for the token
        return 1000000  # Example market cap value

    def calculate_initial_score(self, market_cap):
        # Implement the logic to calculate the initial score based on market cap
        return market_cap / 1000000  # Example calculation

if __name__ == "__main__":
    chain_ids = {
        # "Ethereum": 1,
        # "BNB Chain": 56,
        # "Polygon": 137,
        "Fantom": 250
    }
    bot = TradingBot(chain_ids=chain_ids, api_key="QA15qLIBp3OykOei5tLSslzOgjCxBS3t")
    sys.setrecursionlimit(3000)  # Adjusting recursion limit if necessary for deep tree operations
    bot.main_loop()



