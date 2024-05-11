import json
import threading
import time
import logging
from threading import Thread
from one_inch import OneInchAPI  # Ensure this is correctly implemented
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
        self.trading_dict = {}  # token_id: score_at_purchase
        self.last_pulse = {}
        self.counter = 1
        self.wallet_address = '0x9055192d0673CE6034b302a9921A3E071A220553'


    def configure_logging(self):
        logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s', filename='trading_bot.log', filemode='w')
        console = logging.StreamHandler()
        console.setLevel(logging.INFO)
        formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        console.setFormatter(formatter)
        logging.getLogger('').addHandler(console)
        self.logging = logging

    def chain_handler(self, chain_name, chain_id):
        while True:
            self.logging.info(f"Processing {chain_name} with chain ID {chain_id}")
            self.logging.info(f"Iteration self.counter: {self.counter}")
            self.update_token_scores(chain_name, chain_id)
            self.counter += 1
            if self.counter % 5 == 0:
                self.initialize_tokens(chain_name, chain_id)
                self.manage_trading_dict(chain_name, chain_id)
            time.sleep(self.interval)

    def initialize_tokens(self, chain_name, chain_id):
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
                    market_cap = self.get_market_cap(token_id, chain_id)
                    initial_score = self.calculate_initial_score(market_cap)
                    token = Token((token_id, chain_id), initial_score, current_price)
                    self.tokens_per_chain[chain_name].insert_token(token)  # Insert new token into the tree
                    self.logging.info(f"Inserted new token {token_id} with initial score {initial_score}.")

    def update_token_scores(self, chain_name, chain_id):
        for token_id, token in self.tokens_per_chain[chain_name].tokens_map.items():
            current_price_info = self.one_inch_api.get_swap_rate(token_id, network=chain_id)
            time.sleep(0.5)
            if current_price_info and 'price' in current_price_info:
                current_price = int(current_price_info['price'])
                if not token.last_price:
                    self.logging.error(f"last price was not updated correctly for token {token.id}")
                    continue
                price_difference = current_price - token.last_price
                strikes = token.strikes     
                adjustment_factor = self.calculate_adjustment_factor(price_difference, token.last_price)
                new_score = token.score + adjustment_factor
                self.tokens_per_chain[chain_name].update_token(token.id, new_score, current_price, strikes)
                if not price_difference < 0:
                    strikes += 1
                else:
                    strikes = 0
                if token.id in self.trading_dict and strikes > 2 or token.id in self.trading_dict and token.score < 0:
                    self.trading_dict.pop(token.id)
                elif token.score < 3 and token.id not in self.trading_dict:
                    self.trading_dict[token.id] = token.score
                self.manage_trading_dict()
                self.logging.info(f"Updated token {token_id} with new score {new_score}, price difference {price_difference}.")
                
    def manage_trading_dict(self, chain_name, chain_id):
        last_pulse = self.check_last_pulse(chain_id)
        if len(last_pulse) >= 1:
            if len(self.trading_dict) > 0:
                for address, score in self.trading_dict.items():
                    if address not in self.trading_dict and self.trading_dict:
                        self.swap_native_for_token(address)
                        self.last_pulse[address] = score





    def bridge(self, token_id, amount):
        self.logging.info(f"Dummy swap {token_id} for native currency with amount {amount}")

    def check_last_pulse(self):
        try:
            last_pulse = OneInchAPI.check_wallet_assets(self.wallet_address, self.chains[])
            return last_pulse
        except Exception as e:
            print(e)
        return None


    def swap_token_for_native(self, token_id, amount):
        self.logging.info(f"Dummy swap {token_id} for native currency with amount {amount}")

    def swap_native_for_token(self, token_id, amount):
        self.logging.info(f"Dummy swap native currency for {token_id} with amount {amount}")

    def trade(self, last_pulse):
        pass


    def calculate_adjustment_factor(self, price_difference, last_price):
        """
        Calculates the adjustment factor for a token's score based on the price difference and last price.
        """
        if last_price == 0:
            return 0  # Avoid division by zero if last_price is not initialized.
        adjustment_factor = abs(price_difference / last_price) * 100
        adjustment_factor = adjustment_factor % 10 + int(adjustment_factor / 10)
        bonus = 0
        if price_difference <= 0:
            if price_difference < 0:
                bonus = 1
            return adjustment_factor + bonus
        else:
            return -1 * adjustment_factor

    def main_loop(self):
        for chain_name, chain_id in self.chain_ids.items():
            t = Thread(target=self.chain_handler, args=(chain_name, chain_id))
            t.start()

        trading_dict_thread = Thread(target=self.manage_trading_dict, args=(self.last_pulse))
        trading_dict_thread.start()

    def get_market_cap(self, token_id, chain_id):
        # Your existing implementation
        return 1000000  # Example market cap value

    def calculate_initial_score(self, market_cap):
        # Your existing implementation
        return market_cap / 1000000  # Example calculation

if __name__ == "__main__":
    chain_ids = {
        # "BNB Chain": 56,
        "PoS": 137,
    }
    bot = TradingBot(chain_ids=chain_ids, api_key="QA15qLIBp3OykOei5tLSslzOgjCxBS3t")
    sys.setrecursionlimit(3000)
    bot.main_loop()
