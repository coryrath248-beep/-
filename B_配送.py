# -*- coding: utf-8 -*-
"""
计算题 B：生鲜冷链配送车辆路径问题（CVRP）

数据：1 个仓库 + 31 个配送站（文档编号 1 为仓库，2~32 为配送站），
单车容量 50 件，可用车辆上限 25 辆。距离采用欧氏距离（单位：km）。

求解思路：
1. 先用“装箱（bin packing）”确定最少车辆数（由总需求 413 件 / 容量 50 得下界 9 辆，
   并用回溯法验证 9 辆可行）；
2. 对每辆车的客户组分别用“最近邻 + 2-opt”构造行驶路线；
3. 用“迭代局部搜索（ILS）”：在保持 9 辆车不变的前提下，通过客户在车辆间
   移动 / 交换、随机扰动与重启动，持续缩短总配送距离。
"""

import math
import random

# 仓库（文档编号 1）
DEPOT = (1, 82.0, 76.0, 0)

# 配送站：文档编号 2~32，坐标为 (x, y)，需求量为件/天
CUSTOMERS = [
    (2, 96, 44, 19), (3, 50, 5, 21), (4, 49, 8, 6), (5, 13, 7, 19),
    (6, 29, 89, 7), (7, 58, 30, 12), (8, 84, 39, 16), (9, 14, 24, 6),
    (10, 2, 39, 16), (11, 3, 82, 8), (12, 5, 10, 14), (13, 98, 52, 21),
    (14, 84, 25, 16), (15, 61, 59, 3), (16, 1, 65, 22), (17, 88, 51, 18),
    (18, 91, 2, 19), (19, 19, 32, 4), (20, 93, 3, 24), (21, 50, 93, 8),
    (22, 98, 14, 12), (23, 5, 42, 4), (24, 42, 9, 8), (25, 61, 62, 24),
    (26, 9, 97, 24), (27, 80, 55, 2), (28, 57, 69, 20), (29, 23, 15, 15),
    (30, 20, 70, 2), (31, 85, 60, 14), (32, 98, 5, 9),
]

CAPACITY = 50
MAX_VEHICLES = 25


def dist(a, b):
    return math.hypot(a[1] - b[1], a[2] - b[2])


def route_length(route, nodes):
    return sum(dist(nodes[route[k]], nodes[route[k + 1]]) for k in range(len(route) - 1))


def route_demand(route, nodes):
    return sum(nodes[i][3] for i in route if i != 0)


def two_opt(route, nodes):
    """对单条路线做 2-opt 局部优化。"""
    improved = True
    while improved:
        improved = False
        best = route_length(route, nodes)
        for a in range(1, len(route) - 2):
            for b in range(a + 1, len(route) - 1):
                new_route = route[:a] + list(reversed(route[a:b + 1])) + route[b + 1:]
                new_len = route_length(new_route, nodes)
                if new_len < best - 1e-9:
                    route, best = new_route, new_len
                    improved = True
                    break
            if improved:
                break
    return route


def pack_into_k(demands, k, capacity):
    """回溯装箱：把 31 个需求装入 k 个容量为 capacity 的箱子。"""
    items = sorted(range(len(demands)), key=lambda i: -demands[i])
    bins = [[] for _ in range(k)]
    loads = [0] * k

    def bt(idx):
        if idx == len(items):
            return True
        it = items[idx]
        d = demands[it]
        for b in range(k):
            if loads[b] + d <= capacity:
                bins[b].append(it)
                loads[b] += d
                if bt(idx + 1):
                    return True
                bins[b].pop()
                loads[b] -= d
        return False

    return bins if bt(0) else None


def route_group(member_ids, nodes):
    """对一组客户（节点编号集合）用最近邻 + 2-opt 构造路线。"""
    unvisited = set(member_ids)
    route = [0]
    cur = 0
    while unvisited:
        nxt = min(unvisited, key=lambda k: dist(nodes[cur], nodes[k]))
        route.append(nxt)
        unvisited.remove(nxt)
        cur = nxt
    route.append(0)
    return two_opt(route, nodes)


def local_search(routes, nodes, capacity):
    """在保持车辆数不变的前提下，用客户移动/交换缩短总里程。"""
    improved = True
    while improved:
        improved = False
        best = None

        # 移动：把 a 路线里的一个客户插入到 b 路线
        for a in range(len(routes)):
            for i in range(1, len(routes[a]) - 1):
                node = routes[a][i]
                if len(routes[a]) <= 3:  # 路线里只有一个客户时不移动，避免车辆数增加
                    continue
                for b in range(len(routes)):
                    if a == b:
                        continue
                    if route_demand(routes[b], nodes) + nodes[node][3] > capacity:
                        continue
                    for pos in range(1, len(routes[b])):
                        new_a = routes[a][:i] + routes[a][i + 1:]
                        new_b = routes[b][:pos] + [node] + routes[b][pos:]
                        delta = (route_length(new_a, nodes) + route_length(new_b, nodes)) - (
                            route_length(routes[a], nodes) + route_length(routes[b], nodes)
                        )
                        if delta < -1e-9 and (best is None or delta < best[0]):
                            best = (delta, "move", a, b, i, pos)

        # 交换：a、b 两条路线各取一个客户互换
        for a in range(len(routes)):
            for b in range(a + 1, len(routes)):
                for i in range(1, len(routes[a]) - 1):
                    for j in range(1, len(routes[b]) - 1):
                        na, nb = routes[a][i], routes[b][j]
                        if route_demand(routes[a], nodes) - nodes[na][3] + nodes[nb][3] > capacity:
                            continue
                        if route_demand(routes[b], nodes) - nodes[nb][3] + nodes[na][3] > capacity:
                            continue
                        new_a = routes[a][:i] + [nb] + routes[a][i + 1:]
                        new_b = routes[b][:j] + [na] + routes[b][j + 1:]
                        delta = (route_length(new_a, nodes) + route_length(new_b, nodes)) - (
                            route_length(routes[a], nodes) + route_length(routes[b], nodes)
                        )
                        if delta < -1e-9 and (best is None or delta < best[0]):
                            best = (delta, "swap", a, b, i, j)

        if best is None:
            break
        delta, kind, a, b, i, j = best
        if kind == "move":
            node = routes[a][i]
            routes[a] = routes[a][:i] + routes[a][i + 1:]
            routes[b] = routes[b][:j] + [node] + routes[b][j:]
        else:
            na, nb = routes[a][i], routes[b][j]
            routes[a] = routes[a][:i] + [nb] + routes[a][i + 1:]
            routes[b] = routes[b][:j] + [na] + routes[b][j + 1:]
        routes[a] = two_opt(routes[a], nodes)
        routes[b] = two_opt(routes[b], nodes)
        improved = True

    return routes


def iterated_local_search(groups0, nodes, capacity, iters=600, seed=7):
    """迭代局部搜索：在固定车辆数下尽量缩短总里程。"""
    demands = [nodes[i][3] for i in range(1, len(nodes))]
    rng = random.Random(seed)
    groups = [list(g) for g in groups0]
    best = None

    def make(g):
        return [route_group([i + 1 for i in gg], nodes) for gg in g if gg]

    def total(routes):
        return sum(route_length(r, nodes) for r in routes)

    for _ in range(iters):
        routes = local_search(make(groups), nodes, capacity)
        d = total(routes)
        if best is None or d < best[0]:
            best = (d, routes, [list(g) for g in groups])

        gs = [list(g) for g in (best[2] if rng.random() < 0.4 else groups)]
        for _ in range(4):
            a, b = rng.sample(range(len(gs)), 2)
            if not gs[a] or not gs[b]:
                continue
            x = rng.choice(gs[a])
            y = rng.choice(gs[b])
            da = sum(demands[i] for i in gs[a])
            db = sum(demands[i] for i in gs[b])
            if da - demands[x] + demands[y] <= capacity and db - demands[y] + demands[x] <= capacity:
                gs[a].remove(x)
                gs[a].append(y)
                gs[b].remove(y)
                gs[b].append(x)
        groups = gs

    return best[1]


def plot_routes(routes, nodes, out="B_路线图.png"):
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        from matplotlib import font_manager

        # 尽量使用中文字体，避免中文显示成方框
        for fname in ["Microsoft YaHei", "SimHei", "SimSun"]:
            try:
                font_manager.findfont(fname, fallback_to_default=False)
                plt.rcParams["font.sans-serif"] = [fname]
                break
            except Exception:
                continue
        plt.rcParams["axes.unicode_minus"] = False

        total = sum(route_length(r, nodes) for r in routes)
        fig, ax = plt.subplots(figsize=(8.5, 8.5))
        colors = plt.cm.tab10.colors
        ax.scatter([DEPOT[1]], [DEPOT[2]], c="red", marker="s", s=130, zorder=5, label="仓库")
        for k, r in enumerate(routes):
            xs = [nodes[i][1] for i in r]
            ys = [nodes[i][2] for i in r]
            ax.plot(xs, ys, marker="o", markersize=5, linewidth=1.6,
                    color=colors[k % 10], label=f"车辆 {k + 1}")
        for c in CUSTOMERS:
            ax.annotate(str(c[0]), (c[1], c[2]), fontsize=8, ha="center", va="center")
        ax.set_title(f"冷链配送车辆路径方案（{len(routes)} 辆车，总里程约 {total:.0f} km）", fontsize=13)
        ax.set_xlabel("x 坐标 (km)")
        ax.set_ylabel("y 坐标 (km)")
        ax.legend(fontsize=8, ncol=2, loc="best")
        ax.grid(True, alpha=0.3)
        fig.tight_layout()
        fig.savefig(out, dpi=150)
        plt.close(fig)
    except Exception as e:  # 绘图失败不影响主流程
        print(f"(绘图跳过：{e})")


def main():
    nodes = [DEPOT] + CUSTOMERS
    demands = [c[3] for c in CUSTOMERS]
    total_demand = sum(demands)
    lower = math.ceil(total_demand / CAPACITY)

    # 1. 确定最少车辆数
    groups = None
    for k in range(lower, MAX_VEHICLES + 1):
        g = pack_into_k(demands, k, CAPACITY)
        if g is not None:
            groups = g
            break

    # 2. 用迭代局部搜索在最少车辆数下优化路线与总里程
    routes = iterated_local_search(groups, nodes, CAPACITY)

    total_distance = sum(route_length(r, nodes) for r in routes)

    print("=" * 72)
    print("计算题 B 求解结果（装箱定车辆数 + 最近邻/2-opt + 迭代局部搜索）")
    print("=" * 72)
    print(f"配送站总数：{len(CUSTOMERS)}，总需求量：{total_demand} 件")
    print(f"车辆容量：{CAPACITY} 件，车辆数下界：{lower} 辆")
    print(f"本方案使用车辆数：{len(routes)} 辆（上限 {MAX_VEHICLES} 辆）")
    print(f"总配送距离：{total_distance:.2f} km")
    print()
    for idx, r in enumerate(routes, 1):
        demand = route_demand(r, nodes)
        length = route_length(r, nodes)
        seq = " -> ".join(str(nodes[i][0]) for i in r)
        print(f"车辆 {idx:2d} | 载货 {demand:2d} 件 | 里程 {length:6.2f} km | 路线：{seq}")

    plot_routes(routes, nodes)
    return routes, nodes


if __name__ == "__main__":
    main()
