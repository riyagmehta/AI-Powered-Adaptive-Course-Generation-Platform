from arq.connections import ArqRedis
from fastapi import Request


def get_arq_pool(request: Request) -> ArqRedis:
    return request.app.state.arq_pool
