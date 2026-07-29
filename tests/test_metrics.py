import torch

from block_kyfan_pinn.metrics import orthogonality_error, principal_angle_degrees, projector_sine_error
from block_kyfan_pinn.physics import periodic_mgs


def test_projector_sine_error_is_basis_rotation_invariant() -> None:
    torch.manual_seed(9)
    basis = periodic_mgs(torch.randn(1, 40, 2, 2))
    rotation = torch.tensor([[0.6, -0.8], [0.8, 0.6]])
    rotated_real = torch.einsum("bnir,ij->bnjr", basis, rotation)
    assert projector_sine_error(basis, rotated_real) < 1e-5
    mean_angle, max_angle = principal_angle_degrees(basis, rotated_real)
    assert mean_angle < 1e-5
    assert max_angle < 1e-5
    assert orthogonality_error(basis) < 1e-5
