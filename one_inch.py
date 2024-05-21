from decimal import Decimal
import requests
from quick_node import Web3Instance


class OneInchAPI:

    def __init__(self, api_key: str):
        """
        Initializes the OneInchAPI with a given API key.

        :param api_key: Your 1inch API key.
        """
        self.wallet_address = "0x9055192d0673CE6034b302a9921A3E071A220553"
        self.api_key = api_key
        self.logging = None
        self.native_token = '0xeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee'

    def whitelist_token(self, token_address):
        small_amount = 0.01  # Adjust this value as necessary
        try:
            # Example 1inch API endpoints, adjust as necessary
            sell_url = f"https://api.1inch.exchange/v3.0/1/swap?fromTokenAddress={token_address}&toTokenAddress={self.native_token}&amount={small_amount}&fromAddress=YOUR_WALLET_ADDRESS&slippage=1"
            buy_url = f"https://api.1inch.exchange/v3.0/1/swap?fromTokenAddress={self.native_token}&toTokenAddress={token_address}&amount={small_amount}&fromAddress=YOUR_WALLET_ADDRESS&slippage=1"

            buy_response = requests.get(buy_url)
            sell_response = requests.get(sell_url)

            if buy_response.status_code == 200 and sell_response.status_code == 200:
                return True
            else:
                return False
        except Exception as e:
            print(f"Error testing token {token_address}: {e}")
            return False

    def get_token_info(self, address, chain_id):

        method = "get"
        apiUrl = f"https://api.1inch.dev/token/v1.2/{chain_id}/search"
        requestOptions = {
            "headers": {
                "Authorization": f"Bearer {self.api_key}"
            },
            "body": {},
            "params": {
                "query": address,
                "ignore_listed": "false",
                "only_positive_rating": "false"
            }
        }

        # Prepare request components
        headers = requestOptions.get("headers", {})
        body = requestOptions.get("body", {})
        params = requestOptions.get("params", {})

        response = requests.get(apiUrl, headers=headers, params=params)
        return response.json()


    def check_wallet_assets(self, wallet_address, chain_id='1'):
        """Fetches assets for a given wallet address using the 1inch API.

        Args:
            wallet_address (str): The wallet address to check.
            chain_id (str): The chain ID. Defaults to '1' (Ethereum).

        Returns:
            dict: A dictionary containing the assets in the wallet.
        """
        method = "get"
        apiUrl = f"https://api.1inch.dev/balance/v1.2/{chain_id}/balances/{wallet_address}"
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
                      amount: int = 10 ** 12, network: int = 250) -> dict:
        """
        Retrieves the swap rate for a given pair of tokens.

        :param from_token_address: Address of the source token.
        :param to_token_address: Address of the destination token.
        :param amount: Amount of the source token to swap.
        :param network: Network ID (Chain ID).
        :return: Dictionary with price and gas amount or None if request fails.
        """
        headers = {"Authorization": f"Bearer {self.api_key}", "accept": "application/json"}
        params = {
            "chain": network,
            "src": from_token_address,
            "dst": to_token_address,
            "amount": amount,
            "includeTokensInfo": "true",
            "includeGas": "true",
        }
        api_url = f"https://api.1inch.dev/swap/v5.2/{network}/quote"

        try:
            response = requests.get(api_url, headers=headers, params=params)
            if response.status_code == 200:
                data = response.json()
                price = data['toAmount']
                return {"price": price, "gas": Decimal(data.get("gas", 0)), "name": data.get("name")}
            else:
                return None
        except Exception:
            return None

    def get_chain_pairs_prices(self, chain_id: int) -> str:
        """
        Retrieves available token pairs for a given chain.

        :param chain_id: Network ID (Chain ID) for which to retrieve token pairs.
        :return: Response text containing token pairs or error message.
        """
        headers = {"Authorization": f"Bearer {self.api_key}", "accept": "application/json"}
        params = {"chain": chain_id, "currency": "USD"}
        api_url = f"https://api.1inch.dev/price/v1.1/{chain_id}"

        try:
            response = requests.get(api_url, headers=headers, params=params)
            return response.text
        except Exception:
            return "Error fetching chain pairs"

    def get_chain_pairs(self, chain_id: int) -> str:
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

    def swap_tokens(self, from_address, private_key, from_token_address, to_token_address, amount, end_point):
        web3_instance = Web3Instance.get_instance(end_point).web3

        # Normalize the from_address to checksum address
        from_address = web3_instance.to_checksum_address(from_address)

        # 1inch API endpoint for swap
        api_url = f"https://api.1inch.dev/swap/v6.0/137/swap"

        headers = {
            'Authorization': "Bearer " + self.api_key
        }

        # Prepare swap request
        params = {
            'fromTokenAddress': from_token_address,
            'toTokenAddress': to_token_address,
            'amount': amount,
            'fromAddress': from_address,
            'slippage': 1,
        }

        response = requests.get(api_url, headers=headers, params=params)

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

        # Ensure the 'from' field in the transaction data matches the normalized from_address
        tx['from'] = from_address
        tx['to'] = web3_instance.to_checksum_address(tx['to'])

        # Fetch the current nonce for the from_address
        nonce = web3_instance.eth.get_transaction_count(from_address)
        tx['nonce'] = nonce

        # Convert necessary fields to appropriate types
        tx['value'] = int(tx['value'])
        tx['gasPrice'] = int(tx['gasPrice'])
        tx['chainId'] = web3_instance.eth.chain_id

        # Sign and send the transaction
        signed_tx = web3_instance.eth.account.sign_transaction(tx, private_key=private_key)
        tx_hash = web3_instance.eth.send_raw_transaction(signed_tx.rawTransaction)
        return tx_hash.hex()
        # Sign and send the transaction
        signed_tx = web3_instance.eth.account.sign_transaction(tx, private_key=private_key)
        tx_hash = web3_instance.eth.send_raw_transaction(signed_tx.rawTransaction)
        return tx_hash.hex()

