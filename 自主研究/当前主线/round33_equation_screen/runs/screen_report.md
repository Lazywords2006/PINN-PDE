
### E1_heat  (delta = -9.167)

| method | runs | max-vol per seed | median | max-trace median | wall median (s) |
|---|---|---|---|---|---|
| vanilla | 2 | 2.4e-01, 1.9e-01 | 2.16e-01 | 7.39e-01 | 385 |
| hardic | 2 | 3.8e-02, 2.2e-02 | 3.00e-02 | 1.18e-01 | 370 |
| rba | 2 | 7.6e-02, 6.2e-02 | 6.88e-02 | 2.52e-01 | 336 |
| layer | 2 | 2.5e-02, 5.5e-02 | 3.97e-02 | 1.43e-01 | 433 |
| hardic+layer | 2 | 1.1e-02, 9.4e-03 | 1.04e-02 | 1.78e-02 | 422 |

criterion 2 (vanilla > 1e-2): True; criterion 3 (best of ours 1.04e-02 vs best of hardic/rba 3.00e-02, ratio 2.89 >= 3): False

### E2_allen_cahn  (delta = +1.992)

| method | runs | max-vol per seed | median | max-trace median | wall median (s) |
|---|---|---|---|---|---|
| vanilla | 2 | 1.5e-02, 1.3e-02 | 1.39e-02 | 9.05e-02 | 378 |
| hardic | 2 | 1.9e-03, 2.1e-03 | 1.98e-03 | 1.45e-03 | 375 |
| rba | 2 | 8.3e-03, 5.8e-03 | 7.03e-03 | 3.00e-02 | 325 |
| layer | 2 | 2.4e-03, 3.8e-03 | 3.09e-03 | 1.28e-02 | 427 |
| hardic+layer | 2 | 1.9e-03, 1.0e-03 | 1.49e-03 | 2.26e-03 | 435 |

criterion 2 (vanilla > 1e-2): True; criterion 3 (best of ours 1.49e-03 vs best of hardic/rba 1.98e-03, ratio 1.33 >= 3): False

### E3_fisher  (delta = +3.420)

| method | runs | max-vol per seed | median | max-trace median | wall median (s) |
|---|---|---|---|---|---|
| vanilla | 2 | 1.5e-01, 6.1e-02 | 1.07e-01 | 2.67e-01 | 386 |
| hardic | 2 | 4.8e-03, 7.5e-03 | 6.16e-03 | 1.26e-02 | 371 |
| rba | 2 | 6.6e-02, 4.2e-02 | 5.41e-02 | 9.27e-02 | 334 |
| layer | 2 | 6.2e-02, 5.2e-03 | 3.37e-02 | 3.80e-02 | 431 |
| hardic+layer | 2 | 1.7e-03, 2.0e-03 | 1.88e-03 | 1.52e-03 | 425 |

criterion 2 (vanilla > 1e-2): True; criterion 3 (best of ours 1.88e-03 vs best of hardic/rba 6.16e-03, ratio 3.28 >= 3): True
