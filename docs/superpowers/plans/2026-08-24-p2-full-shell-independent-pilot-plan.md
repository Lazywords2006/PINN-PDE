# P2 Full-Shell Independent Pilot Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Run one independent, evidence-bound pilot of the full-shell neural-augmented Ritz solver.

**Architecture:** Generate a disjoint 96-point suite and cutoff-24 reference cache, then evaluate fixed P5 checkpoints, two neural-Galerkin refinements, and an equal-rank Fourier-only control.  Aggregate accuracy, pairwise wins, orthogonality, 10/100 production latency, direct PWE timing, and a frozen GO/STOP gate.

**Tech Stack:** Python 3.12, PyTorch 2.8, CUDA 12.8, RTX 5090 D, pytest, JSON/CSV/tar SHA evidence.

---

## Tasks

- [ ] Add deterministic P2 suite generator, exact counts, overlap rejection,
  reference-cache CLI, committed suite, and protocol tests.
- [ ] Add P2 pilot gate GO/STOP fixtures for every frozen threshold.
- [ ] Add runner with exact P5 inventory, six methods, 1728-row identity checks,
  family/seed paired wins, 10/100 P2 timing, direct PWE timing, units and sidecars.
- [ ] Add source/checkpoint/environment/probe-evidence provenance and a
  self-contained bundle that is reopened and audited before status output.
- [ ] Run full tests and CUDA preflight on clean Git commit.
- [ ] Generate cutoff-24 P2 references, run pilot once, return evidence locally,
  and preserve either GO or STOP without touching frozen final.
