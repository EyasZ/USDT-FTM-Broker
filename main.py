import json
import time
import logging
from threading import Thread
from one_inch import OneInchAPI
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
        self.chains = {name: Chain((chain_id, '0xeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee', 'ORACLE_ADDRESS', name)) for
                       name, chain_id in self.chain_ids.items()}
        self.tokens_per_chain = {name: TokenBinaryTree() for name in self.chain_ids}

    def configure_logging(self):
        logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s',
                            filename='trading_bot.log', filemode='w')
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
            self.tokens_per_chain[chain_name].log_tree()
            time.sleep(self.interval)

    def evaluate_tokens(self, chain_name, chain_id):
        raw_tokens = json.loads(self.one_inch_api.get_chain_pairs(chain_id))
        for token_id, token_info in raw_tokens.items():
            if token_id == '0xeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee':  # Skip native currency
                continue

            token = self.tokens_per_chain[chain_name].find_token(token_id)
            if token is None:
                current_price_info = self.one_inch_api.get_swap_rate(token_id, network=chain_id)
                if current_price_info and 'price' in current_price_info:
                    current_price = int(current_price_info['price'])
                    market_cap = self.get_market_cap(token_id, chain_id)
                    initial_score = self.calculate_initial_score(market_cap)
                    token = Token((token_id, chain_id), initial_score)
                    token.last_price = current_price  # Initialize last_price for new tokens
                    self.tokens_per_chain[chain_name].insert_token(token)
                    self.logging.info(f"Inserted new token {token_id} with initial score {initial_score}.")
            else:
                current_price_info = self.one_inch_api.get_swap_rate(token_id, network=chain_id)
                if current_price_info and 'price' in current_price_info:
                    current_price = int(current_price_info['price'])
                    logging.info(f"last price: {token.last_price}, current price:{current_price}")
                    price_difference = current_price - token.last_price
                    adjustment_factor = (abs(float(price_difference)) / float(token.last_price)) * 10.0
                    bonus = 2 if price_difference < 0 else 0
                    new_score = token.score + adjustment_factor + bonus if price_difference <= 0 else token.score - adjustment_factor
                    self.tokens_per_chain[chain_name].update_token(token_id, new_score, current_price)
                    token.last_price = current_price  # Update last_price for the next evaluation AFTER the score update
                    self.logging.info(
                        f"Updated token {token_id} with new score {new_score}, price difference {price_difference}.")

    def main_loop(self):
        for chain_name, chain_id in self.chain_ids.items():
            t = Thread(target=self.chain_handler, args=(chain_name, chain_id))
            t.start()
        # Threads are deliberately not joined to allow infinite execution

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
    sys.setrecursionlimit(3000)
    bot.main_loop()
