from mlax.nn import Conv
import jax.numpy as jnp
from jax import (
    random,
    lax,
    nn,
    jit
)

key1, key2 = random.split(random.PRNGKey(0))
in_dtype = jnp.float16
out_dtype = jnp.float32
inputs1 = jnp.ones((4, 3, 32, 32), dtype=in_dtype)
inputs2 = jnp.ones((4, 32, 32, 3), dtype=in_dtype)
trainables1, non_trainables1, hyperparams1 = Conv.init(
    key1,
    ndims=2,
    in_channels=3,
    out_channels=16,
    filter_shape=(5, 5),
    input_dilation=1,
    filter_dilation=1,
    conv_spec=None,
    accum_dtype=out_dtype,
    kernel_initializer=nn.initializers.constant(1, dtype=out_dtype),
    dtype=in_dtype
)
trainables2, non_trainables2, hyperparams2 = Conv.init(
    key2,
    ndims=2,
    in_channels=3,
    out_channels=16,
    filter_shape=5,
    strides=(1, 1),
    input_dilation=(1, 1),
    filter_dilation=(1, 1),
    conv_spec=("NHWC", "OHWI", "NHWC"),
    accum_dtype=out_dtype,
    kernel_initializer=nn.initializers.constant(1, dtype=out_dtype),
    dtype=in_dtype
)

def test_init(): 
    assert lax.eq(
        trainables1,
        jnp.ones((16, 3, 5, 5), dtype=in_dtype)
    ).all()
    assert non_trainables1 is None

    assert lax.eq(
        trainables2,
        jnp.ones((16, 5, 5, 3), dtype=in_dtype)
    ).all()
    assert non_trainables2 is None

def test_fwd():
    activations, new_ntr = jit(Conv.fwd, static_argnames="hyperparams")(
        inputs1,
        trainables1,
        non_trainables1,
        hyperparams1
    )
    assert lax.eq(
        activations,
        jnp.full((4, 16, 28, 28), 75, dtype=out_dtype)
    ).all()
    assert new_ntr == non_trainables1

    activations, new_ntr = Conv.fwd(
        inputs2,
        trainables2,
        non_trainables2,
        hyperparams2

    )
    assert lax.eq(
        activations,
        jnp.full((4, 28, 28, 16), 75, dtype=out_dtype)
    ).all()
    assert new_ntr == non_trainables2
