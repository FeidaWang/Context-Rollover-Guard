"""Bounded overload backoff only for read RPCs and explicitly verified error predicates."""
import time
from .appserver import RpcError
READ_METHODS=frozenset({'thread/read','thread/list','config/read','hooks/list'})

def read_with_backoff(client,method,params,*,retryable=lambda error:False,attempts=3,delay=.1,sleep=time.sleep):
    if method not in READ_METHODS:raise ValueError('Mutation retry is forbidden')
    if type(attempts)is not int or not 1<=attempts<=5 or not 0<=delay<=1:raise ValueError('Invalid bounded retry policy')
    for index in range(attempts):
        try:return client.request(method,params)
        except RpcError as exc:
            if index+1==attempts or not retryable(exc.error):raise
            sleep(min(delay*2**index,2))
