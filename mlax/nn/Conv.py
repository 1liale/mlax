import jax
from jax import (
    nn,
    lax
)
from typing import Tuple, Any, Sequence, Union, Optional, NamedTuple

class Hyperparams(NamedTuple):
    window_strides: Any
    padding: Any
    input_dilation: Any
    filter_dilation: Any
    feature_group_count: Any
    batch_group_count: Any
    conv_spec: Tuple[str, str, str]
    precision: Any
    accum_dtype: Any


def init(
    key: Any,
    ndims: int,
    in_channels: int,
    out_channels: int,
    filter_shape: Union[int, Sequence[int]],
    strides: Union[int, Sequence[int]] = 1,
    padding = "VALID",
    input_dilation: Optional[Union[int, Sequence[int]]] = None,
    filter_dilation: Optional[Union[int, Sequence[int]]] = None,
    feature_group_count = 1,
    batch_group_count = 1,
    conv_spec: Tuple[str, str, str] = None,
    precision=None,
    accum_dtype=None,
    kernel_initializer=nn.initializers.glorot_uniform(in_axis=1, out_axis=0),
    dtype=None
) -> Tuple[jax.Array, None, Hyperparams]:
    """Intialize variables for a convolutional transform.

    :param key: PRNG key for weight initialization.
    :param ndims: Number of input spatial dimensions.
    :param in_channels: Number of input feature dimensions/channels.
    :param out_channels: Number of desired output feature dimensions/channels.
    :param filter_shape: An integer or a sequence of ``ndims`` integers,
        specifying the shape of the filters used on input features. A single
        integer specifies the same value for all spatial dimensions.
    :param strides: An integer or a sequence of ``ndims`` integers, specifying
        the strides of the convolution along the spatial dimensions. A single
        integer specifies the same value for all spatial dimensions. Default: 1.
    :param padding: See the ``padding`` parameter of
        `jax.lax.conv_general_dilated`_, which is used internally.
    :param input_dilation: None, an integer, or a sequence of ``ndims``
        integers, specifying the transposed convolution dilation rate in each
        spatial dimension. See the ``lhs_dilation`` parameter of
        `jax.lax.conv_general_dilated`_. Default: None, no input dilation.
    :param filter_dilation: None, an integer, or a sequence of ``ndims``
        integers, specifying the atrous convolution dilation rate. See the
        ``rhs_dilation`` parameter of `jax.lax.conv_general_dilated`_. Default:
        None, no filter dilation.
    :param feature_group_count: See the ``feature_group_count`` parameter of
        `jax.lax.conv_general_dilated`_. Can be used to perform group and
        seperable convolutions. Default: 1.
    :param batch_group_count: See the ``batch_group_count`` parameter of
        `jax.lax.conv_general_dilated`_. Default: 1.
    :param conv_spec: Optional 3-tuple ``(in_spec, kernel_spec, out_spec)``
        specifying the input, kernel, and output layout. The string specifying
        each layout must be ``ndims`` in length. See the ``dimension_numbers``
        parameter of `jax.lax.conv_general_dilated`_. Default: None, equivalent
        to a channel-first ``("NC...", "OI...", "NC...")`` layout.
    :param precision: See the ``precision`` parameter of
        `jax.lax.conv_general_dilated`_. Default: None.
    :param accum_dtype: See the ``preferred_element_type`` parameter of
        `jax.lax.conv_general_dilated`_. Default: None.
    :param kernel_initializer: Kernel initializer as defined by
        ``jax.nn.initalizers <https://jax.readthedocs.io/en/latest/jax.nn.initializers.html>``.
        Default:: glorot uniform.
    :param dtype: Type of initialized kernel weight. Default: None, which means
        the ``kernel_initializer``'s default.

    :returns trainables: Initialized kernel weight.
    :returns non_trainables: None.
    :returns hyperparams: NamedTuple containing the hyperparameters.

    .. note:
        If you override the default ``conv_spec``, also override the default
        ``kernel_initializer`` with one that has the correct ``in_axis`` and
        ``out_axis``.
    
    .. _jax.lax.conv_general_dilated:
        https://jax.readthedocs.io/en/latest/_autosummary/jax.lax.conv_general_dilated.html
    """
    filter_shape = (filter_shape,) * ndims if isinstance(filter_shape, int) else filter_shape
    if conv_spec is None:
        kernel_shape = (out_channels, in_channels, *filter_shape)
    else:
        filter_shape_iter = iter(filter_shape)
        kernel_shape = tuple(
            out_channels if c == "O" else
            in_channels if c == "I" else
            next(filter_shape_iter) for c in conv_spec[1]
        )
    kernel_weight = kernel_initializer(
        key,
        kernel_shape,
        dtype
    )
    
    hyperparams = Hyperparams(
        (strides,) * ndims if isinstance(strides, int) else strides,
        padding,
        (input_dilation,) * ndims if isinstance(input_dilation, int) else input_dilation,
        (filter_dilation,) * ndims if isinstance(filter_dilation, int) else filter_dilation,
        feature_group_count,
        batch_group_count,
        conv_spec,
        precision,
        accum_dtype
    )

    return kernel_weight, None, hyperparams

def fwd(
    x: jax.Array,
    trainables: jax.Array,
    non_trainables: None,
    hyperparams: Hyperparams,
    inference_mode: bool=False
) -> jax.Array:
    """Applies convolutions on input features.

    :param x: Input features to the convolutional transform. Must be compatible
        with the ``in_spec`` of ``conv_spec``.
    :param trainables: Trainable weights for a convolutional transform.
    :param non_trainables: Non-trainable weights for a linear transform, should
        be None. Ignored.
    :param hyperparams: NamedTuple containing the hyperparameters.
    :param inference_mode: Whether in inference or training mode. Ignored.
        Default: False.
 
    :returns y: Convolution on ``x``.
    :returns non_trainables: Unchanged ``non_trainables``.
    """
    return lax.conv_general_dilated(
        x,
        trainables,
        hyperparams.window_strides,
        hyperparams.padding,
        hyperparams.input_dilation,
        hyperparams.filter_dilation,
        hyperparams.conv_spec,
        hyperparams.feature_group_count,
        hyperparams.batch_group_count,
        hyperparams.precision,
        hyperparams.accum_dtype
    ), non_trainables
