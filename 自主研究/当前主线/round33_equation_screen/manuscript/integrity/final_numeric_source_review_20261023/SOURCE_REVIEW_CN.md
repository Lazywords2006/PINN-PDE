# 只读复算器源码与小规模实测独立审核

结论：**无阻断全206项体/迹数值复算的问题，可运行冻结版本；这不是最终完整性PASS。**

审核源码SHA256：`7cbe64b660606ca66bf63af28f6fc71c4072106a687c8a85a56b3fb7c37b9611`。plan SHA256：`c3ab15b47313c62f5b50aafff2df1e698e4aff5c8a905bc7654485dabbaf8d5b`。

已逐行阅读 `validation/final_numeric_provenance_20261023/recompute_saved_models.py`，并对照实际 `pinn1d.Model` 和 `problems.Reference/ReferenceBS`。检查器固定206个任务、488个输入，真实新建N48/64/96参考解；新实现五时刻的N64/GL200及N96/GL400误差求积，与原始JSON按rtol=1e−5、atol=1e−9逐值比较。输入/代码在前后重新哈希。权重先在meta设备构造后strict+assign加载；完整模型核对元数据、base与full一致性；旧E4删除没有保存的surf，不执行v或依赖该分支的残差。没有训练入口调用，直接封锁pinn1d.train。浮点权重和输出检查有限值与float64，参考积分失败/超容差使进程非零退出。

执行取 `subprocess.run` 的实际OS returncode，不以JSON内 intended_exit_code替代。完整命令、环境、依赖模块文件哈希、stdout、stderr及Python警告列表均保存。临时和运行文件置于D:/CodexRuntime。最终副本逐文件哈希核对。前向函数与PDE参考求解器是冻结的项目实现；独立性限于新进程、权重加载、求积、比较及证据链，不声称独立PDE算法复现。

对8模型+4参考进程probe做了685项独立检查，全部通过：488输入当前哈希一致；所有冻结代码与probe证据文件哈希一致；12个实际returncode均为0，逐进程warning_count=0且stderr为空；保存NPZ的预测/参考数组被本审核者重新计算体/迹误差，与原JSON均满足既有容差。覆盖五种构造、MLP/Pirate、旧/完整权重、旧E4缺surf及Pirate续跑配置。详细记录见 `PROBE_INDEPENDENT_CHECK.json`。

注意：代码中的 `current_numerical_recomputation_pass` 只汇总数值、输入及退出码条件，未将warning_count并入布尔表达式。最终完整性核验仍须单独读取warning_count和stderr，不能直接把该布尔值视为Mode1清除。该脚本不重新生产heldout残差、旧训练损失/计数/成本，也不恢复历史训练日志；这些范围必须分开核查。任何全批失败、警告或原容差不满足应保留原件，不能删除不利任务或放宽容差。
