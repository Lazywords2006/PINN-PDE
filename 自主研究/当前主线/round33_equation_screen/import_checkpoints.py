"""Inspect pinned historical checkpoints and create identity-bound working copies.

Original .ckptgit bytes and the source ZIP are kept intact outside the repository.
--probe performs only two Adam updates twice per checkpoint, never a full run.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import pathlib
import shutil
import zipfile
from dataclasses import asdict, replace

import torch

from pinn1d import Config, Model
from problems import get_problem
from run_artifacts import sha256, validate_checkpoint

HERE = pathlib.Path(__file__).resolve().parent
SOURCE_COMMIT = 'aec7fcdfc0dae861f46ca594d0771c5669af5ad3'
BLOBS = {'pirate__E1_heat__hardic_layer_s0.ckptgit': '866fb470288b0b3d9cb32aa2afc0fbea21cf75fd',
         'pirate__E1_heat__hardic_layer_s1.ckptgit': '6964584738730d3626f30137995a0b770dda6422',
         'pirate__E1_heat__hardic_s0.ckptgit': 'dd50ecc2e70bf000c4e26ce888988b97ce751372',
         'pirate__E1_heat__hardic_s1.ckptgit': '0f00514b4e9d9425e45ace6e2065654de17a4947'}


def same(a, b):
    if isinstance(a, torch.Tensor):
        return isinstance(b, torch.Tensor) and torch.equal(a, b)
    if isinstance(a, dict):
        return a.keys() == b.keys() and all(same(a[k], b[k]) for k in a)
    if isinstance(a, (list, tuple)):
        return len(a) == len(b) and all(same(x, y) for x, y in zip(a, b))
    return a == b


def probe(source, cfg, method, folder):
    import pinn1d
    records = []
    original = pinn1d.residuals
    for attempt in (1, 2):
        target = folder / f'probe{attempt}' / source.name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
        count = [0]
        def two_calls(*args, **kwargs):
            count[0] += 1
            if count[0] > 2:
                raise KeyboardInterrupt
            return original(*args, **kwargs)
        pinn1d.residuals = two_calls
        try:
            try:
                pinn1d.train(get_problem('E1_heat'), method, cfg, ckpt=str(target), ckpt_every=1)
                raise AssertionError('probe unexpectedly completed training')
            except KeyboardInterrupt:
                pass
        finally:
            pinn1d.residuals = original
        result = torch.load(target, weights_only=False, map_location='cpu')
        assert all(torch.isfinite(v).all() for v in result['model'].values())
        records.append(result)
    assert all(same(records[0][k], records[1][k]) for k in ('model', 'opt', 'sched', 'gen', 'hist'))
    return {'恢复位置': records[0]['hist']['resumed_at'][-1], '验证后Adam步数': records[0]['state']['step'],
            '重复两次模型优化器采样状态逐位相同': True, '仅执行Adam更新次数': 4}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--source', type=pathlib.Path, required=True)
    parser.add_argument('--out', type=pathlib.Path, required=True)
    parser.add_argument('--probe', action='store_true')
    args = parser.parse_args()
    torch.set_num_threads(1)
    if str(torch.__version__).split('+')[0] != '2.14.1':
        raise RuntimeError('use the pinned PyTorch 2.14.1 runtime')
    args.out.mkdir(parents=True, exist_ok=True)
    report = []
    with zipfile.ZipFile(args.source) as archive:
        for filename, expected_blob in BLOBS.items():
            names = [n for n in archive.namelist() if pathlib.PurePosixPath(n).name == filename]
            assert len(names) == 1
            raw = archive.read(names[0])
            blob = hashlib.sha1(f'blob {len(raw)}\0'.encode() + raw).hexdigest()
            assert blob == expected_blob, filename
            original = args.out/'originals'/filename
            original.parent.mkdir(parents=True, exist_ok=True)
            if original.exists():
                assert original.read_bytes() == raw
            else:
                original.write_bytes(raw)
            state = torch.load(io.BytesIO(raw), weights_only=False, map_location='cpu')
            method = 'hardic+layer' if 'hardic_layer' in filename else 'hardic'
            seed = int(filename.split('_s')[-1].split('.')[0])
            old_path = HERE/'runs'/'pirate'/'E1_heat'/f"{method.replace('+','_')}_s2.json"
            old = json.loads(old_path.read_text(encoding='utf-8'))
            cfg = replace(Config(**old['config']), seed=seed)
            step = 16000 if method.endswith('layer') else 16500
            assert state['state']['phase'] == 'adam' and state['state']['step'] == step
            assert state['sched']['last_epoch'] == step
            expected_lr = cfg.lr0 * (cfg.lr1/cfg.lr0)**(step/cfg.adam_steps)
            assert all(abs(g['lr']/expected_lr-1) < 1e-10 for g in state['opt']['param_groups'])
            assert all(int(v['step']) == step for v in state['opt']['state'].values())
            model = Model(get_problem('E1_heat'), method, cfg)
            model.load_state_dict(state['model'], strict=True)
            assert all(v.dtype == torch.float64 and torch.isfinite(v).all() for v in state['model'].values())
            torch.Generator().set_state(state['gen'])
            state['identity'] = {'problem': 'E1_heat', 'method': method, 'config': asdict(cfg)}
            state['environment'] = {'torch': str(torch.__version__)}
            state['legacy_source'] = {'commit': SOURCE_COMMIT, 'file': filename, 'git_blob': blob,
                                      'sha256': hashlib.sha256(raw).hexdigest(), 'recorded_environment': old['env']}
            target = args.out/'checkpoints'/filename.replace('.ckptgit', '.ckpt')
            target.parent.mkdir(parents=True, exist_ok=True)
            if target.exists():
                existing = torch.load(target, weights_only=False, map_location='cpu')
                assert existing.get('legacy_source') == state['legacy_source'], 'do not overwrite another checkpoint'
                assert existing['state']['step'] == step, 'do not overwrite progressed checkpoint'
            else:
                torch.save(state, target)
            validate_checkpoint(target, get_problem('E1_heat'), method, cfg)
            item = {'文件': filename, '原始Git对象核对': True, '源SHA256': sha256(original), '源提交': SOURCE_COMMIT,
                    '方法': method, '种子': seed, 'Adam步数': step, '工作副本': str(target), 'Torch': str(torch.__version__)}
            if args.probe:
                item['本机短续跑核验'] = probe(target, cfg, method, args.out/filename)
                assert item['本机短续跑核验']['验证后Adam步数'] == step+2
            assert hashlib.sha256(original.read_bytes()).hexdigest() == item['源SHA256']
            report.append(item)
            print(json.dumps(item, ensure_ascii=False), flush=True)
    result = {'范围': '恢复可操作性与本机短续跑一致性；不声称跨机器完整训练轨迹逐位相同', 'checkpoint数': 4,
              '本机Torch': str(torch.__version__), '源ZIP_SHA256': sha256(args.source), '检查': report}
    (args.out/'checkpoint_review.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')


if __name__ == '__main__':
    main()
