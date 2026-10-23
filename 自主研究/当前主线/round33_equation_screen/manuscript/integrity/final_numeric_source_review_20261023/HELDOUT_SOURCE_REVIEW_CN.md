# 已保存52项独立残差复算器源码审核

结论：**没有阻断运行的问题。可在全206体/迹批次结束后，以最多8个单线程子进程执行；最终接受依赖实际结果，不在此预先PASS。**

已完整阅读 `recompute_heldout.py`，SHA256 `0f95d05c484dddb3be20d8d8de512f0759934234eee278bd0d00505eff7b0433`，并对照冻结 `stage5_support.heldout_residuals` 及 `pinn1d.residuals` 的定义。计划绑定Pirate4、IC18、第6阶段30共52个已有残差记录，各记录四分量都存在；没有新造诊断指标或补入旧E4。

逐项核查结论：

- RNG为NumPy default_rng(330500)，依次生成体x、体t、左t、右t、初值x，长度8192、8192、1024、1024、1024，与原点顺序、范围和原1024体分块相同。
- PDE残差独立写为u_t−D u_xx−R(u)，左为u_x，右为c u_t＋D u_x＋G(u)，初值为u(x,0)−f(x)；自动微分符号、求导变量和两次空间导数正确。统计为sqrt(mean(r²))和max(abs(r))，不是加权训练损失。
- 使用已审strict/assign权重重载，不创建可用随机替代权重；只涉及非E4完整模型，meta参数必须全部被保存参数替换。不会调用训练，参数梯度不累计且模型/输入哈希在前后相同才通过。
- 保存全部固定点与每点残差NPZ；RMS/max_abs按原rtol=1e−5、atol=1e−9比较，n要求精确相同。全部失败保留，未加结果筛选/选参逻辑。
- 每项真实subprocess returncode、命令、环境/导入文件哈希、stdout/stderr/Python警告记录齐备。源码、原报告和parent plan在前后重新核对，输出副本逐文件哈希核对。

`HELDOUT_SOURCE_BINDINGS.json`记录源、计划、三份原报告哈希及52个身份覆盖的独立核对，未发现不匹配。与体/迹脚本相同，代码内 `current_heldout_recomputation_pass`不含零警告条件；最终核验须独立读取warning_count和stderr，不能以单个布尔值替代完整性门。此复算只建立当前预测残差的生产证据，不恢复旧训练损失、训练轨迹、成本或历史生产日志。
