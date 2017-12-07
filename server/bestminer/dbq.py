from bestminer.models import Currency, MinerProgram


def list_supported_currencies():
    """
    filter from all currencies only thos which can be mined.
    :return:
    """
    supported_algos = set()
    for miner in MinerProgram.objects(is_enabled=True):
        for algo in miner.algos:
            algorithms = algo.split('+')
            for algorithm in algorithms:
                supported_algos.add(algorithm)
    currencies = Currency.objects(algo__in=supported_algos)
    return currencies

