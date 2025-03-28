from typing import List
import torch
import math
import torch.nn as nn
from torch.nn.init import _calculate_correct_fan


def siren_uniform_(tensor: torch.Tensor, mode: str = 'fan_in', c: float = 6):
    r"""Fills the input `Tensor` with values according to the method
    described in ` Implicit Neural Representations with Periodic Activation
    Functions.` - Sitzmann, Martel et al. (2020), using a
    uniform distribution. The resulting tensor will have values sampled from
    :math:`\mathcal{U}(-\text{bound}, \text{bound})` where
    .. math::
        \text{bound} = \sqrt{\frac{6}{\text{fan\_mode}}}
    Also known as Siren initialization.

    Examples:
        >>> w = torch.empty(3, 5)
        >>> siren.init.siren_uniform_(w, mode='fan_in', c=6)

    :param tensor: an n-dimensional `torch.Tensor`
    :type tensor: torch.Tensor
    :param mode: either ``'fan_in'`` (default) or ``'fan_out'``. Choosing
        ``'fan_in'`` preserves the magnitude of the variance of the weights in
        the forward pass. Choosing ``'fan_out'`` preserves the magnitudes in
        the backwards pass.s
    :type mode: str, optional
    :param c: value used to compute the bound. defaults to 6
    :type c: float, optional
    """
    fan = _calculate_correct_fan(tensor, mode)
    std = 1 / math.sqrt(fan)
    bound = math.sqrt(c) * std  # Calculate uniform bounds from standard deviation
    with torch.no_grad():
        return tensor.uniform_(-bound, bound)


class Sine(nn.Module):
    def __init__(self, w0: float = 1.0):
        """Sine activation function with w0 scaling support.

        Example:
            >>> w = torch.tensor([3.14, 1.57])
            >>> Sine(w0=1)(w)
            torch.Tensor([0, 1])

        :param w0: w0 in the activation step `act(x; w0) = sin(w0 * x)`.
            defaults to 1.0
        :type w0: float, optional
        """
        super(Sine, self).__init__()
        self.w0 = w0

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        self._check_input(x)
        return torch.sin(self.w0 * x)

    @staticmethod
    def _check_input(x):
        if not isinstance(x, torch.Tensor):
            raise TypeError(
                'input to forward() must be torch.xTensor')


class SIREN(nn.Module):
    def __init__(self, layers: List[int], in_features: int,
                 out_features: int,
                 w0_initial: float, # = 30.0,
                 w0: float = 1.0,
                 bias: bool = True,
                 initializer: str = 'siren',
                 c: float = 6):
        """
        SIREN model from the paper [Implicit Neural Representations with
        Periodic Activation Functions](https://arxiv.org/abs/2006.09661).
        Implementation modified from : https://github.com/dalmia/siren/tree/master/siren

        :param layers: list of number of neurons in each hidden layer
        :type layers: List[int]
        :param in_features: number of input features
        :type in_features: int
        :param out_features: number of final output features
        :type out_features: int
        :param w0: w0 in the activation step `act(x; w0) = sin(w0 * x)`.
            defaults to 1.0
        :type w0: float, optional
        :param w0_initial: `w0` of first layer. defaults to 30 (as used in the
            paper)
        :type w0_initial: float, optional
        :param bias: whether to use bias or not. defaults to
            True
        :type bias: bool, optional
        :param initializer: specifies which initializer to use. defaults to
            'siren'
        :type initializer: str, optional
        :param c: value used to compute the bound in the siren intializer.
            defaults to 6
        :type c: float, optional

        # References:
            -   [Implicit Neural Representations with Periodic Activation
                 Functions](https://arxiv.org/abs/2006.09661)
        """
        super(SIREN, self).__init__()
        self.layers = layers
        self.w0 = w0
        self.w0_initial = w0_initial
        
        
        self._check_params(layers)
        self.nn_layers = [nn.Linear(in_features, layers[0], bias=bias), Sine(
            w0=w0_initial)]

        for index in range(len(layers) - 1):
            self.nn_layers.extend([
                nn.Linear(layers[index], layers[index + 1], bias=bias),
                Sine(w0=w0)
            ])

        self.nn_layers.append(nn.Linear(layers[-1], out_features, bias=bias))
        self.network = nn.Sequential(*self.nn_layers)

        if initializer is not None and initializer == 'siren':
            for m in self.network.modules():
                if isinstance(m, nn.Linear):
                    siren_uniform_(m.weight, mode='fan_in', c=c)

    @staticmethod
    def _check_params(layers):
        assert isinstance(layers, list), 'layers should be a list of ints'
        assert len(layers) >= 1, 'layers should not be empty'

    def forward(self, X):
        return self.network(X)
    
    
class ConditionalSIREN(nn.Module):
    def __init__(self, 
                 layers: List[int],
                 return_density,
                 w0_initial: float, # = 30.0,
                 w0: float = 1.0,
                 **kwargs):
        """
        SIREN model from the paper [Implicit Neural Representations with
        Periodic Activation Functions](https://arxiv.org/abs/2006.09661).
        Implementation modified from : https://github.com/dalmia/siren/tree/master/siren

        :param layers: list of number of neurons in each layer, including the
            input and output layers; e.g. [2, 3, 1] means 2 input, 1 output
        :type layers: List[int]
        :param w0: w0 in the activation step `act(x; w0) = sin(w0 * x)`.
            defaults to 1.0
        :type w0: float, optional
        :param w0_initial: `w0` of first layer. defaults to 30 (as used in the
            paper)
        :type w0_initial: float, optional
        :param bias: whether to use bias or not. defaults to
            True
        :type bias: bool, optional
        :param initializer: specifies which initializer to use. defaults to
            'siren'
        :type initializer: str, optional
        :param c: value used to compute the bound in the siren intializer.
            defaults to 6
        :type c: float, optional

        # References:
            -   [Implicit Neural Representations with Periodic Activation
                 Functions](https://arxiv.org/abs/2006.09661)
        """
        super(ConditionalSIREN, self).__init__()
        
        self.layers = layers
        self.return_density = return_density
        self.w0_initial = w0_initial
        self.w0 = w0
        
        bias = True
        initializer = 'siren'
        c = 6
        
        self._check_params(layers)
        self.nn_layers = [nn.Linear(layers[0], layers[1], bias=bias), Sine(
            w0=w0_initial)]

        for index in range(1, len(layers) - 2):
            self.nn_layers.extend([
                nn.Linear(layers[index], layers[index + 1], bias=bias),
                Sine(w0=w0)
            ])


        self.nn_layers.append(nn.Linear(layers[-2], layers[-1], bias=bias))
        
        if return_density:
            self.nn_layers.append(nn.Sigmoid())

        self.network = nn.Sequential(*self.nn_layers)

        if initializer is not None and initializer == 'siren':
            for m in self.network.modules():
                if isinstance(m, nn.Linear):
                    siren_uniform_(m.weight, mode='fan_in', c=c)
        
        self.network

    @staticmethod
    def _check_params(layers):
        assert isinstance(layers, list), 'layers should be a list of ints'
        assert len(layers) >= 1, 'layers should not be empty'

    def forward(self, x, z):
        xz = torch.cat([x, z], dim=-1)
        res = self.network(xz)
        return res
    
class LatentModulatedSiren(nn.Module):
    def __init__(self, 
                 layers: List[int],
                 w0: float = 1.0,
                 w0_initial: float = 30.0,
                 bias: bool = True,
                 initializer: str = 'siren',
                 c: float = 6,
                 latent_dim: int = 1):
        """
        SIREN model from the paper [Implicit Neural Representations with
        Periodic Activation Functions](https://arxiv.org/abs/2006.09661).

        :param layers: list of number of neurons in each layer, including the
            input and output layers; e.g. [2, 256, 256, 256, 1] means 2 input, 1 output and 3 hidden layers with 256 neurons each
        :type layers: List[int]
        :param w0: w0 in the activation step `act(x; w0) = sin(w0 * x)`.
            defaults to 1.0
        :type w0: float, optional
        :param w0_initial: `w0` of first layer. defaults to 30 (as used in the
            paper)
        :type w0_initial: float, optional
        :param bias: whether to use bias or not. defaults to
            True
        :type bias: bool, optional
        :param initializer: specifies which initializer to use. defaults to
            'siren'
        :type initializer: str, optional
        :param c: value used to compute the bound in the siren intializer.
            defaults to 6
        :type c: float, optional

        # References:
            -   [From data to functa](https://arxiv.org/abs/2201.12204)
        """
        super(LatentModulatedSiren, self).__init__()
        self.layers = nn.ModuleList()
        self.mod_layer = nn.Linear(latent_dim, sum(layers[1:-1]), bias=True)  # Modulation layer for all hidden layers

        self.layers.append(nn.Linear(layers[0], layers[1], bias=bias))
        self.layers.append(Sine(w0=w0_initial))

        for index in range(1, len(layers) - 1):
            self.layers.append(nn.Linear(layers[index], layers[index + 1], bias=bias))
            if index < len(layers) - 2:
                self.layers.append(Sine(w0=w0))

        self.network = nn.Sequential(*self.layers)

        if initializer == 'siren':
            for m in self.network.modules():
                if isinstance(m, nn.Linear):
                    siren_uniform_(m.weight, mode='fan_in', c=c)


    def forward(self, x, z):
        modulation = self.mod_layer(z)
        idx = 0  # Index to keep track of cumulative layer sizes for shift slicing

        out = x
        for i, layer in enumerate(self.layers):
            if isinstance(layer, nn.Linear) and i != len(self.layers) - 1:
                shift = modulation[..., idx:idx + layer.out_features]  # the ... indexiation is to allow for batching and vmap
                out = layer(out)
                out = out + shift
                idx += layer.out_features
            else:
                out = layer(out)

        return out
    
