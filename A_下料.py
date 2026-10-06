# -*- coding: utf-8 -*-
"""
计算题 A：两种原料（8 米、12 米）铝合金线材下料优化

需求（与题目表格一致）：
    长度  6.20  3.60  2.80  1.85  0.75  0.55（米）
    数量    90   120   136   310   215   320（根）

方法：枚举 8 米、12 米的全部可行“切割模式”，
用整数规划（PuLP + CBC）最小化购买总长度（等价于最小化浪费），
并输出各模式用量、总共需要的 8m/12m 根数、切割方案与线材利用率。
"""

import pulp

# 需求
lengths = [6.20, 3.60, 2.80, 1.85, 0.75, 0.55]
demands = [90, 120, 136, 310, 215, 320]

# 换算成毫米，避免浮点误差
mm = [int(round(l * 1000)) for l in lengths]

# 原料：名称 -> 长度（毫米）
stock_specs = {"8m": 8000, "12m": 12000}


def enumerate_patterns(stock_mm):
    """枚举单根原料上所有可行的切割模式。

    模式用元组 (a1, a2, ..., a6) 表示，ai 为该模式切出第 i 种长度的根数。
    """
    n = len(mm)
    out = []

    def dfs(i, rem, vec):
        if i == n:
            out.append(tuple(vec))
            return
        max_k = min(stock_mm // mm[i], rem // mm[i])
        for k in range(max_k + 1):
            dfs(i + 1, rem - k * mm[i], vec + [k])

    dfs(0, stock_mm, [])
    return out


def main():
    pattern_sets = {name: enumerate_patterns(smm) for name, smm in stock_specs.items()}

    prob = pulp.LpProblem("cutting_stock_A", pulp.LpMinimize)

    # 决策变量：x[name][j] = 第 name 种原料按第 j 个模式切割的根数
    x = {
        name: [
            pulp.LpVariable(f"x_{name}_{j}", lowBound=0, cat=pulp.LpInteger)
            for j in range(len(ps))
        ]
        for name, ps in pattern_sets.items()
    }

    # 目标：最小化购买总长度（毫米）；总需求长度固定，等价于最小化浪费
    prob += pulp.lpSum(
        stock_specs[name] * x[name][j]
        for name in pattern_sets
        for j in range(len(pattern_sets[name]))
    )

    # 约束：每种长度的产出根数不少于需求量
    for i in range(len(mm)):
        prob += (
            pulp.lpSum(
                pattern_sets[name][j][i] * x[name][j]
                for name in pattern_sets
                for j in range(len(pattern_sets[name]))
            )
            >= demands[i],
            f"demand_{i}",
        )

    prob.solve(pulp.PULP_CBC_CMD(msg=0))
    assert pulp.LpStatus[prob.status] == "Optimal", f"未找到最优解: {pulp.LpStatus[prob.status]}"

    used = {name: {} for name in pattern_sets}
    for name in pattern_sets:
        for j, ps in enumerate(pattern_sets[name]):
            v = int(round(x[name][j].value()))
            if v > 0:
                used[name][ps] = v

    n8 = sum(used["8m"].values())
    n12 = sum(used["12m"].values())
    purchased_mm = stock_specs["8m"] * n8 + stock_specs["12m"] * n12
    total_demand_mm = sum(mm[i] * demands[i] for i in range(len(mm)))
    waste_mm = purchased_mm - total_demand_mm

    print("=" * 70)
    print("计算题 A 求解结果")
    print("=" * 70)
    print(f"需要 8 米原料：{n8} 根")
    print(f"需要 12 米原料：{n12} 根")
    print(f"购买总长度：{purchased_mm / 1000:.2f} 米")
    print(f"需求总长度：{total_demand_mm / 1000:.2f} 米")
    print(f"总浪费：{waste_mm / 1000:.2f} 米")
    print(f"线材利用率：{total_demand_mm / purchased_mm * 100:.4f}%")
    print()

    print("切割方案（模式 -> 使用根数）：")
    for name in ["8m", "12m"]:
        print(f"\n[{name} 原料]")
        for ps, cnt in sorted(used[name].items(), key=lambda kv: -kv[1]):
            pieces = [f"{lengths[i]}×{ps[i]}" for i in range(len(mm)) if ps[i] > 0]
            used_len = sum(mm[i] * ps[i] for i in range(len(mm)))
            print(f"  切 {cnt:3d} 根 | {' + '.join(pieces):40s} 用料 {used_len/1000:.2f}m")


if __name__ == "__main__":
    main()
