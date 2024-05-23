import json
import threading
import time
import logging
from threading import Thread
from one_inch import OneInchAPI  # Ensure this is correctly implemented
from objects import Chain, Token, TokenBinaryTree
import sys


class TradingBot:
    def __init__(self, secrets_json, budget=0, chain_ids=None, interval=30, api_key="YOUR_API_KEY"):
        self.budget = budget
        self.chain_ids = chain_ids if chain_ids is not None else {}
        self.interval = interval
        self.logging = None
        self.one_inch_api = OneInchAPI(secrets_json)
        self.configure_logging()
        self.chains = {name: Chain((chain_id, '0xeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee', 'ORACLE_ADDRESS', name, end_point))
                       for name, (chain_id, end_point) in self.chain_ids.items()}
        self.tokens_per_chain = {name: TokenBinaryTree() for name in self.chain_ids}
        self.trading_dict = {}  # token_id: score_at_purchase
        self.last_pulse = {}
        self.counter = 1
        self.native_token = '0xeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee'
        self.secrets = secrets_json
        self.wallet_address = secrets_json['one_inch']['wallet_address']
        self.private_key = secrets_json['one_inch']['wallet_pk']

    def configure_logging(self):
        logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s', filename='trading_bot.log', filemode='w')
        console = logging.StreamHandler()
        console.setLevel(logging.INFO)
        formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        console.setFormatter(formatter)
        logging.getLogger('').addHandler(console)
        self.logging = logging
        OneInchAPI.logging = logging

    def chain_handler(self, chain_name, chain_id):
        self.initialize_tokens(chain_name, chain_id)
        while True:
            self.logging.info(f"Processing {chain_name} with chain ID {chain_id}")
            self.logging.info(f"Iteration self.counter: {self.counter}")
            self.update_token_scores(chain_name, chain_id)
            self.counter += 1
            if self.counter != 0 and self.counter % 5 == 0:
                self.manage_trading_dict(chain_name, chain_id)
            time.sleep(self.interval)

    def initialize_tokens(self, chain_name, chain_id):
        if self.one_inch_api.end_point is None:
            self.one_inch_api.end_point = self.secrets['quick_node'][chain_name]
            self.one_inch_api.chain_id = chain_id
            self.one_inch_api.logging = self.logging
        raw_tokens = json.loads(self.one_inch_api.get_chain_pairs())
        time.sleep(1)
        for token_id, token_info in raw_tokens.items():
            if token_id == '0xeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee':  # Skip native currency
                continue

            token = self.tokens_per_chain[chain_name].find_token(token_id)
            if token is None:
                current_price_info = self.one_inch_api.get_swap_rate(token_id)
                time.sleep(1)
                if current_price_info and 'price' in current_price_info:
                    current_price = int(current_price_info['price'])  # Ensure float for accurate calculations
                    market_cap = self.get_market_cap(token_id, chain_id)
                    token_name = token_info['name']
                    token_symbol = token_info['symbol']
                    decimals = token_info['decimals']
                    initial_score = self.calculate_initial_score(market_cap)
                    token = Token((token_id, chain_id, token_name, token_symbol, decimals), initial_score, current_price)
                    self.tokens_per_chain[chain_name].insert_token(token)  # Insert new token into the tree
                    self.logging.info(f"Inserted {token}")

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

    def update_token_scores(self, chain_name, chain_id):
        for token_id, token in self.tokens_per_chain[chain_name].tokens_map.items():
            current_price_info = self.one_inch_api.get_swap_rate(token_id)
            time.sleep(1)
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
                elif price_difference < 0 < strikes:
                    strikes = 0
                if token.id in self.trading_dict and strikes > 2 or token.id in self.trading_dict and token.score < 0:
                    if token.id != self.native_token:
                        self.trading_dict.pop(token.id)
                    '''elif token.id == self.native_token and strikes > 7:
                        self.sell_all'''
                elif token.score < 3 and token.id not in self.trading_dict:
                    self.trading_dict[token.id] = token
                self.logging.info(f"Updated token: {token}\n ROI: {-1 * price_difference / token.initial_price}.")

    def check_last_pulse(self, chain_id):
        try:
            last_pulse = self.one_inch_api.check_wallet_assets()
            return {address: balance for address, balance in last_pulse.items() if int(balance) != 0}
        except Exception as e:
            print(e)
        return None

    def manage_trading_dict(self, chain_name, chain_id):
        last_pulse = self.check_last_pulse(chain_id)
        to_buy = []
        to_sell = []

        # Create a set of addresses from last_pulse for quick lookup
        pulse_addresses = {address for address, balance in last_pulse.items() if int(balance) > 0}

        # If the wallet contains assets, and there are assets in trading_dict
        if last_pulse and self.trading_dict:
            # Check for tokens in trading_dict that are not in last_pulse (new tokens to buy)
            for address, token in self.trading_dict.items():
                if address not in pulse_addresses:
                    if not token.tested:
                        token.tested = True
                        token.white_listed = self.one_inch_api.whitelist_token(address)
                    if token.white_listed:
                        to_buy.append(address)

            # Iterate over each asset in the last_pulse
            for address, balance in last_pulse.items():
                token = self.trading_dict.get(address)
                if token:
                    continue
                else:
                    # If the address is in last_pulse but not in trading_dict, mark for selling
                    to_sell.append((address, balance))

        self.logging.info(f"to sell: {to_sell}\n to buy: {to_buy}")

        return to_buy, to_sell

    def bridge(self, token_id, amount):
        self.logging.info(f"Dummy swap {token_id} for native currency with amount {amount}")

    def swap_token_for_native(self, token, amount):
        tx_hash = self.one_inch_api.swap_tokens(self.wallet_address, token.id,
                                                self.native_token, amount)
        self.logging.info(f"swapped {token.id} for native currency with amount {amount}\n transaction hash = {tx_hash}")

    def swap_native_for_token(self, token, amount):
        tx_hash = self.one_inch_api.swap_tokens(self.wallet_address,
                                                self.native_token, token.id, amount)
        self.logging.info(f"Dummy swap native currency for {token.id} with amount {amount}\n"
                          f"transaction hash = {tx_hash}")

    def trade(self, last_pulse):
        pass

    def main_loop(self):
        for chain_name, (chain_id, _) in self.chain_ids.items():
            t = Thread(target=self.chain_handler, args=(chain_name, chain_id))
            t.start()

    def get_market_cap(self, token_id, chain_id):
        # Your existing implementation
        return 1000000  # Example market cap value

    def calculate_initial_score(self, market_cap):
        # Your existing implementation
        return market_cap / 1000000  # Example calculation


if __name__ == "__main__":
    with open('secrets.json', 'r') as file:
        secrets = json.load(file)
    chain_ids = {
        # "BNB Chain": 56,
        "PoS": (137, secrets['quick_node']['PoS']),
    }
    bot = TradingBot(secrets, chain_ids=chain_ids, api_key=secrets['one_inch']['api_key'])
    sys.setrecursionlimit(3000)
    bot.main_loop()
