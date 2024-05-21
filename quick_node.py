from web3 import Web3
from web3.middleware import geth_poa_middleware


class Web3Instance:
    instance = None
    my_dict = dict(ether='https://wild-orbital-silence.quiknode.pro/23903db017357bd96f85c262bd5db5ea4d0d671b/',
                   bnb='https://morning-spring-moon.bsc.quiknode.pro'
                       '/863294101c01617971b80955d60e41ec6d4e2cef/',
                   poly='https://holy-lively-cloud.matic.'
                        'quiknode.pro/90fbb47b854814898a599'
                        'c52606feb3a9ed3aeaf/')

    @staticmethod
    def get_instance(endpoint):

        if Web3Instance.instance is None:
            Web3Instance(endpoint)
        return Web3Instance.instance

    def __init__(self, endpoint):
        if Web3Instance.instance is not None:
            raise Exception("This class is a singleton!")
        else:
            self.web3 = Web3(Web3.HTTPProvider(endpoint))
            self.web3.middleware_onion.inject(geth_poa_middleware, layer=0)
            Web3Instance.instance = self
