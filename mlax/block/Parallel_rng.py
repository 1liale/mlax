from jax import (
    tree_util,
    random
)
from typing import Tuple, Any, NamedTuple
from mlax._utils import _get_fwd, _needs_key, _block_hyperparams

@_block_hyperparams
class ParallelRngHp:
    layers: Tuple

def init(
    *layers
) -> Tuple[Tuple, Tuple, ParallelRngHp]:
    """Initialize parameters and hyperparameters for a layer that combines
    sub-layers that may require PRNGKeys in parallel.

    :param layers: Initialized parameters and hyperparameters from each of the
        sub-layers.

    :returns trainables: Tuple of trainable weights from each of the sub-layers.
    :returns non_trainables: Tuple of non-trainable weights from each of the 
        sub-layers.
    :returns hyperparams: ParallelRngHp instance.
    """
    trainables, non_trainables, hyperparams = zip(*layers)
    return trainables, non_trainables, ParallelRngHp(hyperparams)

def fwd(
    x: Any,
    trainables: Tuple,
    non_trainables: Tuple,
    key: Any,
    hyperparams: ParallelRngHp,
    inference_mode: bool=False
)  -> Tuple[Any, Tuple]:
    """Apply layers that may require PRNG keys in parallel.

    :param x: PyTree of input features for each of the layers.
    :param trainables: Tuple of trainable weights from each of the layers.
    :param non_trainables: Tuple of non-trainable weights from each of the
        layers.
    :param key: PRNG key.
    :param hyperparams: ParallelRngHp instance.
    :param inference_mode: Whether in inference or training mode. Default:
        False, training mode.

    :returns y: PyTree of ``x`` with layers applied.
    :returns non_trainables: Updated ``non_trainables`` from each of the layers.
    """
    x, treedef = tree_util.tree_flatten(x)

    fwds = tuple(map(_get_fwd, hyperparams.layers))
    needs_keys = tuple(map(_needs_key, fwds))
    n_keys = sum(needs_keys)
    if n_keys > 1:
        keys_iter = iter(random.split(key, n_keys))
    else:
        keys_iter = iter((key,))

    def map_fn(param):
        x, tr, ntr, hp, fwd, needs_key = param
        if needs_key:
            return fwd(
                x, tr, ntr, next(keys_iter), hp, inference_mode
            )
        else:
            return fwd(
                x, tr, ntr, hp, inference_mode
            )

    x, non_trainables = zip(*map(
        map_fn,
        zip(
            x, trainables, non_trainables, hyperparams.layers, fwds, needs_keys
        )
    ))

    return tree_util.tree_unflatten(treedef, x), non_trainables
