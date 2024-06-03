import time
from decimal import Decimal
import requests
from quick_node import Web3Instance


class OneInchAPI:

    def __init__(self, secrets):
        """
        Initializes the OneInchAPI with a given API key.

        :param api_key: Your 1inch API key.
        """
        self.wallet_address = secrets['one_inch']['wallet_address']
        self.api_key = secrets['one_inch']['api_key']
        self.end_point = None
        self.logging = None
        self.chain_id = None
        self.native_token = '0xeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee'
        self.private_key = secrets['one_inch']['wallet_pk']

    def whitelist_token(self, address):
        web3_instance = Web3Instance.get_instance(self.end_point).web3
        amount = web3_instance.toWei(1, 'ether')
        try:
            buy_hash = self.swap_tokens(self.wallet_address, self.private_key, self.native_token, address, amount)
            if buy_hash:
                buy_receipt = web3_instance.eth.wait_for_transaction_receipt(buy_hash)
                if buy_receipt.status == 1:
                    sell_hash = self.swap_tokens(self.wallet_address, self.private_key, self.native_token, address, amount)
                    if sell_hash:
                        sell_receipt = web3_instance.eth.wait_for_transaction_receipt(sell_hash)
                        if sell_receipt.status == 1:
                            return True
                        else:
                            return False
                    else:
                        return False
                else:
                    return False
            else:
                return False
        except Exception as e:
            print(f"An error occurred: {e}")
            return False

    def check_wallet_assets(self):
        """Fetches assets for a given wallet address using the 1inch API.

        Args:
            wallet_address (str): The wallet address to check.
            chain_id (str): The chain ID. Defaults to '1' (Ethereum).

        Returns:
            dict: A dictionary containing the assets in the wallet.
        """
        method = "get"
        apiUrl = f"https://api.1inch.dev/balance/v1.2/{self.chain_id}/balances/{self.wallet_address}"
        requestOptions = {
            "headers": {
                "Authorization": f"Bearer {self.api_key}"
            },
            "body": {},
            "params": {}
        }

        # Prepare request components
        headers = requestOptions.get("headers", {})
        body = requestOptions.get("body", {})
        params = requestOptions.get("params", {})

        response = requests.get(apiUrl, headers=headers, params=params)
        if response.status_code == 200:
            return response.json()
        else:
            raise Exception(f"Failed to fetch wallet assets: {response.text}")

    def __str__(self) -> str:
        return f"OneInchAPI(api_key={self.api_key})"

    def get_swap_rate(self, to_token_address: str,
                      from_token_address: str = '0xeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee',
                      amount: int = 10 ** 18) -> dict:
        """
        Retrieves the swap rate for a given pair of tokens.

        :param from_token_address: Address of the source token.
        :param to_token_address: Address of the destination token.
        :param amount: Amount of the source token to swap.
        :return: Dictionary with price and gas amount or None if request fails.
        """
        headers = {"Authorization": f"Bearer {self.api_key}", "accept": "application/json"}
        params = {
            "src": from_token_address,
            "dst": to_token_address,
            "amount": amount,
            "includeTokensInfo": "true",
            "includeProtocols": "false",
            "includeGas": "true"
        }
        api_url = f"https://api.1inch.dev/swap/v6.0/{self.chain_id}/quote"

        try:
            response = requests.get(api_url, headers=headers, params=params)
            if response.status_code == 200:
                data = response.json()
                price = data['dstAmount']
                return {"price": price, "gas": Decimal(data.get("gas", 0)), "name": data.get("name")}
            else:
                return None
        except Exception as e:
            return None

    def get_chain_pairs_prices(self) -> str:
        """
        Retrieves available token pairs for a given chain.

        :param chain_id: Network ID (Chain ID) for which to retrieve token pairs.
        :return: Response text containing token pairs or error message.
        """
        chain_id = self.chain_id
        headers = {"Authorization": f"Bearer {self.api_key}", "accept": "application/json"}
        params = {"chain": chain_id, "currency": "USD"}
        api_url = f"https://api.1inch.dev/price/v1.1/{chain_id}"

        try:
            response = requests.get(api_url, headers=headers, params=params)
            return response.text
        except Exception:
            return "Error fetching chain pairs"

    def get_chain_pairs(self) -> str:
        chain_id = self.chain_id
        method = "get"
        api_url = f"https://api.1inch.dev/token/v1.2/{chain_id}"
        requestOptions = {
            "headers": {
                "Authorization": "Bearer " + str(self.api_key)
            },
            "body": {},
            "params": {"chain_id": chain_id}
        }

        # Prepare request components
        headers = requestOptions.get("headers", {})
        params = requestOptions.get("params", {})

        try:
            response = requests.get(api_url, headers=headers, params=params)
            # input(response.text)
            return response.text
        except Exception:
            return "Error fetching chain pairs"

    def swap_tokens(self, from_address, private_key, from_token_address, to_token_address, amount):
        web3_instance = Web3Instance.get_instance(self.end_point).web3

        # Normalize addresses to checksum addresses
        from_address = web3_instance.to_checksum_address(from_address)
        to_token_address = web3_instance.to_checksum_address(to_token_address)

        # 1inch API endpoint for swap
        api_url = f"https://api.1inch.dev/swap/v6.0/{self.chain_id}/swap"

        headers = {
            'Authorization': "Bearer " + self.api_key
        }

        # Prepare swap request
        params = {
            'src': from_token_address,
            'dst': to_token_address,
            'amount': amount,
            'from': from_address,
            'slippage': 1,
        }

        response = requests.get(api_url, headers=headers, params=params)
        input(response)

        if response.status_code != 200:
            raise Exception(f"Error: Received status code {response.status_code} from API. Response: {response.text}")

        try:
            response_json = response.json()
        except ValueError:
            raise Exception(f"Error: Could not parse response as JSON. Response: {response.text}")

        # Extracting transaction data
        if 'tx' not in response_json:
            raise Exception(f"Error: 'tx' field not found in response. Response: {response_json}")

        tx = response_json['tx']

        # Ensure the 'from' and 'to' fields in the transaction data are checksummed
        tx['from'] = from_address
        tx['to'] = web3_instance.to_checksum_address(tx['to'])

        # Fetch the current nonce for the from_address
        nonce = web3_instance.eth.get_transaction_count(from_address)
        tx['nonce'] = nonce

        # Convert necessary fields to appropriate types
        tx['value'] = int(tx['value'])
        tx['gasPrice'] = int(tx['gasPrice'])

        # Include the chainId for EIP-155 replay protection
        tx['chainId'] = web3_instance.eth.chain_id

        # Sign and send the transaction
        signed_tx = web3_instance.eth.account.sign_transaction(tx, private_key=private_key)
        tx_hash = web3_instance.eth.send_raw_transaction(signed_tx.rawTransaction)
        time.sleep(5)
        return tx_hash.hex()
