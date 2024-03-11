from web3 import Web3

class ChainlinkDataFetcher:
    def __init__(self, logging, quicknode_url):
        self.logging = logging
        self.quicknode_url = quicknode_url
        self.w3 = self.connect_to_blockchain()
        self.chainlink_feed_abi = self.get_chainlink_feed_abi()

    def connect_to_blockchain(self):
        # Connect to the blockchain using the provided QuickNode URL
        w3 = Web3(Web3.HTTPProvider(self.quicknode_url))
        if not w3.is_connected():
            self.logging.error("Failed to connect to the network.")
            return None
        return w3

    @staticmethod
    def get_chainlink_feed_abi():
        # Define the ABI for Chainlink Price Feed contracts
        # Note: In a real scenario, this should be loaded from a secure source or file
        return [
            {
                "inputs": [],
                "name": "latestRoundData",
                "outputs": [
                    {"internalType": "uint80", "name": "roundId", "type": "uint80"},
                    {"internalType": "int256", "name": "answer", "type": "int256"},
                    {"internalType": "uint256", "name": "startedAt", "type": "uint256"},
                    {"internalType": "uint256", "name": "updatedAt", "type": "uint256"},
                    {"internalType": "uint80", "name": "answeredInRound", "type": "uint80"}
                ],
                "stateMutability": "view",
                "type": "function"
            }
        ]

    def get_rates(self, contract_addresses):
        # Fetch latest price data for specified contract addresses
        rates = {}
        for symbol, address in contract_addresses.items():
            try:
                contract = self.w3.eth.contract(address=address, abi=self.chainlink_feed_abi)
                price = contract.functions.latestRoundData().call()[1]
                if price <= 0:
                    self.logging.error(f"Invalid price data for {symbol}.")
                    continue
                rates[symbol] = price / 10 ** 8
            except Exception as e:
                self.logging.error(f"Error fetching rate for {symbol}: {e}")
        return rates
