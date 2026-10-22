"""Pinned official SOAP semantics with dtype-preserving eigensystem operations.

Upstream: nikhilvyas/SOAP, soap.py blob a6362cc9ed2f50ed299204eb3bf07715e7280757.
The vendored implementation and its MIT license are in third_party/.
Only the preconditioner allocation/decompositions differ: retain the gradient's
dtype/device instead of temporarily casting float64 eigensystems to float32.
Initialisation, update ordering, bias correction, QR refresh and moment sorting
are inherited unchanged.  The legacy pinn1d.SOAP remains available unchanged.
"""
from __future__ import annotations

import torch

from third_party.soap_official import SOAP as OfficialSOAP


class SOAPOfficial64(OfficialSOAP):
    def init_preconditioner(self, grad, state, **kwargs):
        super().init_preconditioner(grad, state, **kwargs)
        state['GG'] = [m.to(dtype=grad.dtype, device=grad.device) if len(m) else m for m in state['GG']]

    def get_orthogonal_matrix(self, matrices):
        result = []
        for m in matrices:
            if not len(m):
                result.append([])
                continue
            eye = torch.eye(m.shape[0], dtype=m.dtype, device=m.device)
            _, q = torch.linalg.eigh(m + 1e-30 * eye)
            result.append(q.flip(-1))
        return result

    def get_orthogonal_matrix_QR(self, state, max_precond_dim=10000, merge_dims=False):
        original_shape = state['exp_avg_sq'].shape
        permuted_shape = None
        if self._data_format == 'channels_last' and len(original_shape) == 4:
            permuted_shape = state['exp_avg_sq'].permute(0, 3, 1, 2).shape
        second = self.merge_dims(state['exp_avg_sq'], max_precond_dim) if merge_dims else state['exp_avg_sq']
        result = []
        for axis, (m, q) in enumerate(zip(state['GG'], state['Q'])):
            if not len(m):
                result.append([])
                continue
            order = torch.argsort(torch.diag(q.T @ m @ q), descending=True)
            second = second.index_select(axis, order)
            q, _ = torch.linalg.qr(m @ q[:, order])
            result.append(q)
        if merge_dims:
            second = second.reshape(permuted_shape).permute(0, 2, 3, 1) if permuted_shape is not None else second.reshape(original_shape)
        state['exp_avg_sq'] = second
        return result
