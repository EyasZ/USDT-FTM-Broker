import json
import threading
import time
import logging
from threading import Thread
from one_inch import OneInchAPI  # Ensure this is correctly implemented
from objects import Chain, Token, TokenBinaryTree
import sys
from chainlink import ChainlinkDataFetcher
import mpmath

class TradingBot:
    def __init__(self, secrets_json, budget=0, chain_ids=None, interval=30, api_key="YOUR_API_KEY"):
        self.budget = budget
        self.chain_ids = chain_ids if chain_ids is not None else {}
        self.interval = interval
        self.init_interval = interval * 10
        self.logging = None
        self.swapped_to_stable_flag = False
        self.swap_to_stable_order = False
        self.stable_token = None
        mpmath.mp.dps = 50
        self.one_inch_api = OneInchAPI(secrets_json)
        self.chain_link = None
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
        self.manage_dict_flag = False
        self.sleep_count = 1

    def configure_logging(self):
        logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s', filename='history.log', filemode='w')
        console = logging.StreamHandler()
        console.setLevel(logging.INFO)
        formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        console.setFormatter(formatter)
        logging.getLogger('').addHandler(console)
        self.logging = logging
        self.one_inch_api.logging = logging

    def chain_handler(self, chain_name, chain_id):
        while True:
            self.initialize_tokens(chain_name, chain_id)
            self.logging.info("Finished tokens initialization")
            time.sleep(self.init_interval)
            while len(self.trading_dict) < 5 or self.tokens_per_chain[chain_name].find_token(self.native_token).score < 3 * self.sleep_count :
                while len(self.trading_dict) > 6:
                    min_score_token_id = min(self.trading_dict, key=lambda k: self.trading_dict[k].score)
                    # Pop the key-value pair with the minimum score
                    self.trading_dict.pop(min_score_token_id)
                self.logging.info(f"Processing {chain_name} with chain ID {chain_id}")
                self.logging.info(f"Iteration counter: {self.counter}\nSleep Counter: {self.sleep_count-1}")
                self.update_token_scores(chain_name, chain_id)
                self.counter += 1
                time.sleep(self.init_interval)
            self.manage_trading_dict(chain_name, chain_id)
            if self.swapped_to_stable_flag:
                # sleep for 4 hours
                self.trading_dict = {}
                self.sleep_count += 1
                self.manage_dict_flag = False
                self.tokens_per_chain[chain_name].find_token(self.native_token).score = self.sleep_count
                self.tokens_per_chain[chain_name].find_token(self.native_token).strikes = 0
                self.swapped_to_stable_flag = False
                time.sleep(self.init_interval * 48)

    def initialize_tokens(self, chain_name, chain_id):
        if self.one_inch_api.end_point is None:
            self.one_inch_api.end_point = self.secrets['quick_node'][chain_name]["end_point"]
            self.one_inch_api.chain_id = chain_id
            self.stable_token = self.secrets['quick_node'][chain_name]["stable_token"]
            self.one_inch_api.logging = self.logging
        raw_tokens = json.loads(self.one_inch_api.get_chain_pairs())
        time.sleep(1)
        for token_id, token_info in raw_tokens.items():
            token = self.tokens_per_chain[chain_name].find_token(token_id)
            if token is None and token_id != self.native_token:
                current_price_info = self.one_inch_api.get_swap_rate(token_id)
                time.sleep(1)
                if current_price_info and 'price' in current_price_info:
                    current_price = int(current_price_info['price'])  # Ensure float for accurate calculations
                    market_cap = self.get_market_cap(token_id, chain_id)
                    token_name = token_info['name']
                    if "us" in token_name.lower() or "eu" in token_name.lower() or "OX" in token_name.lower():
                        continue
                    token_symbol = token_info['symbol']
                    decimals = token_info['decimals']
                    initial_score = self.calculate_initial_score(market_cap)
                    token = Token((token_id, chain_id, token_name, token_symbol, decimals), initial_score, current_price)
                    self.tokens_per_chain[chain_name].insert_token(token)  # Insert new token into the tree
                    self.logging.info(f"Inserted {token}")
            elif token is None and token_id == self.native_token:
                current_price_info = self.one_inch_api.get_swap_rate(token_id, self.stable_token)
                time.sleep(1)
                if current_price_info and 'price' in current_price_info:
                    current_price = int(current_price_info['price'])  # Ensure float for accurate calculations
                    market_cap = self.get_market_cap(token_id, chain_id)
                    token_name = token_info['name']
                    if "us" in token_name.lower() or "eu" in token_name.lower():
                        continue
                    token_symbol = token_info['symbol']
                    decimals = token_info['decimals']
                    initial_score = self.calculate_initial_score(market_cap)
                    token = Token((token_id, chain_id, token_name, token_symbol, decimals), initial_score,
                                  current_price)
                    self.tokens_per_chain[chain_name].insert_token(token)  # Insert new token into the tree
                    self.logging.info(f"Inserted native {token}")


    def calculate_adjustment_factor(self, price_difference, last_price):
        """
        Calculates the adjustment factor for a token's score based on the price difference and last price.
        The score is more rewarding for positive changes and penalizes negative changes.
        """
        if last_price == 0:
            return 0  # Avoid division by zero if last_price is not initialized.

        # Calculate the percentage change
        percentage_change = mpmath.mpf(mpmath.mpf(price_difference / last_price) * 100)

        # Initialize the adjustment factor
        adjustment_factor = 0

        # Apply game theory principles
        if percentage_change > 0:
            # Reward for positive changes
            multiplier = 1.5  # Increase this value to make positive changes more rewarding
            adjustment_factor = percentage_change * multiplier

            # Add a bonus for significant positive changes
            if percentage_change > 1:
                adjustment_factor += 1  # Add a flat bonus for significant increases

        else:
            # Penalty for negative changes
            penalty_multiplier = 1.2  # Increase this value to make negative changes more penalizing
            adjustment_factor = percentage_change * penalty_multiplier

        # Cap the adjustment factor to avoid excessively high scores
        adjustment_factor = max(min(adjustment_factor, self.sleep_count), -1 * self.sleep_count)

        return adjustment_factor

    def update_token_scores(self, chain_name, chain_id):
        for token_id, token in self.tokens_per_chain[chain_name].tokens_map.items():
            if self.manage_dict_flag:
                flag = False
                for token_address, _ in self.trading_dict.items():
                    if token_address == token_id:
                        flag = True
                        break
                if not flag:
                    continue
            if token_id == self.native_token:
                current_price_info = self.one_inch_api.get_swap_rate(token_id, self.stable_token)
            else:
                current_price_info = self.one_inch_api.get_swap_rate(token_id)
            time.sleep(1)
            if current_price_info and 'price' in current_price_info:
                current_price = int(current_price_info['price'])
                if not token.last_price:
                    self.logging.error(f"last price was not updated correctly for token {token.id}")
                    continue
                price_difference = current_price - token.last_price
                adjustment_factor = self.calculate_adjustment_factor(price_difference * -1, token.last_price)
                new_score = token.score + adjustment_factor
                self.tokens_per_chain[chain_name].update_token(token.id, new_score, current_price, token.strikes)
                if price_difference > 0:
                    token.strikes += 1
                elif price_difference < 0 < token.strikes:
                    token.strikes -= 2
                if token.id in self.trading_dict and token.strikes > 2 or token.id in self.trading_dict and token.score < 0.9:
                    self.trading_dict.pop(token.id)
                elif (token.score > 2 * self.sleep_count and token.id not in self.trading_dict and token.strikes < 4 or token_id == self.native_token
                      and token.id not in self.trading_dict and token.score > 0.5):
                    self.trading_dict[token.id] = token
                    self.logging.info(f"trading dict: {self.trading_dict}")
                self.logging.info(f"Updated token: {token}\n ROI: {(token.initial_price - current_price) / token.initial_price}\n strikes: {token.strikes}.")
                if token_id == self.native_token and new_score < 0:
                    self.logging.warning(f"native token score is low, score = {new_score}")
                    time.sleep(1)
                    self.swap_to_stable_order = True

    def check_last_pulse(self, chain_id):
        try:
            last_pulse = self.one_inch_api.check_wallet_assets()
            return {address: balance for address, balance in last_pulse.items() if int(balance) != 0}
        except Exception as e:
            print(e)
        return None

    def swap_all_to_stable(self, chain_id, chain_name):
        last_pulse = self.check_last_pulse(chain_id)
        time.sleep(1)
        for address, balance in last_pulse.items():
            balance = int(balance)
            if address != self.native_token and address != self.stable_token:
                self.swap_token_for_stable(address, balance)
                time.sleep(1)
            elif address != self.stable_token and address == self.native_token and balance > ((10**18)*100):
                self.swap_token_for_stable(address, int(0.9*balance))
                time.sleep(1)
        self.swapped_to_stable_flag = True
        self.swap_to_stable_order = False
        logging.info("swap all function activated")

    def manage_trading_dict(self, chain_name, chain_id):
        time.sleep(1)
        self.manage_dict_flag = True
        while True:
            last_pulse = self.check_last_pulse(chain_id)
            logging.info(last_pulse)
            time.sleep(1)
            native = self.tokens_per_chain[chain_name].find_token(self.native_token)
            if native.strikes > 4 or native.score < 0.5 or self.native_token not in self.trading_dict:
                self.logging.warning("native token probably wasn't in trading dict(trading_dict_manager)")
                self.swap_all_to_stable(chain_id, chain_name)
                return

            # Create a set of addresses from last_pulse for quick lookup
            if last_pulse:
                pulse_addresses = {address for address, balance in last_pulse.items() if int(balance) > 0}

            # If the wallet contains assets, and there are assets in trading_dict
            if last_pulse and self.trading_dict:
                # Iterate over each asset in the last_pulse
                for address, balance in last_pulse.items():
                    token = self.trading_dict.get(address)
                    if token or address == self.native_token:
                        if address == self.native_token:
                            token.tested = True
                        continue
                    else:
                        # If the address is in last_pulse but not in trading_dict, mark for selling
                        tx_hash = self.swap_token_for_native(token_address=address, amount=balance)
                # Check for tokens in trading_dict that are not in last_pulse (new tokens to buy)
                for address, token in self.trading_dict.items():
                    if address not in pulse_addresses:
                        if not token.tested and token.id != self.native_token:
                            if token.id == self.native_token:
                                self.trading_dict[token.id].tested = True
                                self.trading_dict[token.id].white_listed = True
                            else:
                                self.trading_dict[token.id].tested = True
                                self.trading_dict[token.id].white_listed = self.one_inch_api.whitelist_token(address)
                                logging.info(f"token {address} whitelist status: {token.white_listed}")
                                time.sleep(1)
                        if token.tested and not token.white_listed:
                            continue
                white_listed_tokens = {address: token for address, token in self.trading_dict.items() if (token.tested and token.white_listed)}
                last_pulse = self.check_last_pulse(chain_id)
                time.sleep(1)
                native_balance = int(last_pulse[self.native_token])
                token_budget = str(int((0.7 * native_balance) / len(white_listed_tokens) - 1))
                for address, token in white_listed_tokens.items():
                    if token.id != self.native_token:
                        tx_hash = self.swap_native_for_token(address, token_budget)
                        time.sleep(1)

            self.update_token_scores(chain_name, chain_id)
            if self.swap_to_stable_order:
                self.swap_all_to_stable(chain_id, chain_name)
                return
            time.sleep(self.init_interval * 2)
            if len({address: token for address, token in self.trading_dict.items() if ((token.tested and token.white_listed) or not token.tested)}) == 1:
                break

    def bridge(self, token_id, amount):
        self.logging.info(f"Dummy swap {token_id} for native currency with amount {amount}")

    def swap_token_for_native(self, token_address, amount):
        tx_hash = self.one_inch_api.swap_tokens(self.wallet_address, self.private_key, token_address,
                                                self.native_token, amount)
        self.logging.info(f"swapped {token_address} for native currency - amount: {amount}\n transaction hash = {tx_hash}")
        return tx_hash

    def swap_native_for_token(self, token_address, amount):
        tx_hash = self.one_inch_api.swap_tokens(self.wallet_address,
                                                self.private_key, self.native_token, token_address, amount)
        self.logging.info(f"swapped native currency for {token_address} - amount: {amount}\n"
                          f"transaction hash = {tx_hash}")
        return tx_hash

    def swap_token_for_stable(self, token_address, amount):
        tx_hash = self.one_inch_api.swap_tokens(self.wallet_address, self.private_key,
                                                token_address, self.stable_token, amount)
        self.logging.info(f"swapped {token_address} with stable currency - amount: {amount}\n"
                          f"transaction hash = {tx_hash}")
        return tx_hash

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
