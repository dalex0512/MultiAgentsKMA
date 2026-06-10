"""Slide 3 v4 — pixel-aligned layout (1920×1080 coords, y-up)."""
from __future__ import annotations

import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, Polygon
from matplotlib.patches import FancyArrowPatch

W, H = 1920, 1080

fig, ax = plt.subplots(figsize=(19.2, 10.8), dpi=150)
ax.set_xlim(0, W)
ax.set_ylim(0, H)
ax.axis("off")
fig.patch.set_facecolor("white")


def sy(y_svg: float) -> float:
    """SVG y (down) → matplotlib y (up)."""
    return H - y_svg


def rbox(x, y, w, h, title, sub=None, fc="#FFF3E0", ec="#E67E22", fs=22, bold=False):
    y2 = sy(y + h)
    ax.add_patch(FancyBboxPatch(
        (x, y2), w, h, boxstyle="round,pad=0,rounding_size=14",
        facecolor=fc, edgecolor=ec, linewidth=2.5, transform=ax.transData,
    ))
    cy = sy(y + h / 2)
    fw = "bold" if bold else "normal"
    if sub:
        ax.text(x + w / 2, cy + 14, title, ha="center", va="center", fontsize=fs, fontweight=fw)
        ax.text(x + w / 2, cy - 16, sub, ha="center", va="center", fontsize=fs - 6, color="#666")
    else:
        ax.text(x + w / 2, cy, title, ha="center", va="center", fontsize=fs, fontweight=fw)


def dia(cx, cy, hw, hh, lines):
    pts = [(cx, sy(cy - hh)), (cx + hw, sy(cy)), (cx, sy(cy + hh)), (cx - hw, sy(cy))]
    ax.add_patch(Polygon(pts, closed=True, facecolor="#FFF9C4", edgecolor="#F39C12", linewidth=2.5))
    cy_m = sy(cy)
    for i, ln in enumerate(lines):
        ax.text(cx, cy_m + (len(lines) // 2 - i) * 18, ln, ha="center", va="center",
                fontsize=18, fontweight="bold")


def arr(x1, y1, x2, y2, color="#444", dashed=False):
    ax.add_patch(FancyArrowPatch(
        (x1, sy(y1)), (x2, sy(y2)),
        arrowstyle="-|>", mutation_scale=16, color=color, linewidth=2.5,
        linestyle=(0, (10, 6)) if dashed else "solid",
    ))


def lbl(x, y, text, color="#444", fs=16):
    ax.text(x, sy(y), text, ha="center", va="center", fontsize=fs, color=color, fontweight="bold",
            bbox=dict(boxstyle="round,pad=0.15", fc="white", ec="none", alpha=0.95))


# ── title ─────────────────────────────────────────────────────────────────────
ax.text(W / 2, sy(72), "Cơ chế kiểm định relevance và leo thang pipeline",
        ha="center", fontsize=36, fontweight="bold")
ax.text(W / 2, sy(112), "Routing động bổ sung cho routing tĩnh theo Qc  (vùng Hybrid)",
        ha="center", fontsize=20, color="#666", style="italic")

ax.add_patch(FancyBboxPatch(
    (120, sy(192)), 1680, 52, boxstyle="round,pad=0,rounding_size=10",
    facecolor="#EBF5FB", edgecolor="#2E86C1", linewidth=2, linestyle="--",
))
ax.text(W / 2, sy(173), "Tầng 1 — Routing tĩnh:  Router chọn Hybrid  khi  0,50 ≤ Qc < 0,70",
        ha="center", fontsize=20, color="#1B4F72")

# ── center column (x=760, w=400) ──────────────────────────────────────────────
rbox(760, 230, 400, 72, "Retrieve(q)", "Embedding + rerank")
arr(960, 302, 960, 338)

dia(960, 410, 100, 60, ["Bật Grader?", "(0,35 ≤ Qc < 0,65)"])
arr(960, 470, 960, 518)
lbl(990, 495, "Có", color="#27AE60")

# skip path left
arr(868, 410, 520, 410, color="#888")
arr(520, 410, 520, 650, color="#888")
lbl(700, 400, "Không → Generate trực tiếp", color="#888", fs=15)

rbox(760, 518, 400, 72, "Document Grader", "Grade(q, D)  →  YES / NO", bold=True)
lbl(990, 618, "YES", color="#27AE60")
arr(960, 590, 960, 638)

# corrective right
rbox(1280, 518, 380, 72, "Corrective Retrieve", "Requery + Retrieve  (≤ 2 vòng)", ec="#D35400")
arr(1160, 554, 1280, 554, color="#D35400")
lbl(1220, 544, "NO", color="#D35400")
arr(1470, 590, 1470, 660, color="#D35400")
arr(1470, 660, 1060, 660, color="#D35400")
lbl(1280, 648, "sau requery", color="#D35400", fs=14)

dia(960, 698, 95, 60, ["Đủ context?"])
arr(960, 758, 960, 806)
lbl(990, 782, "Có", color="#27AE60")

# NO → agentic
arr(1060, 698, 1320, 698, color="#C0392B", dashed=True)
arr(1320, 698, 1320, 860, color="#C0392B", dashed=True)
lbl(1140, 688, "Không", color="#C0392B")

rbox(760, 806, 400, 68, "Generate", "LLM, temperature = 0", fc="#E8F8F5", ec="#1ABC9C")
rbox(320, 806, 400, 68, "Generate", "LLM, temperature = 0", fc="#E8F8F5", ec="#1ABC9C")

arr(960, 874, 960, 922, color="#27AE60")
arr(520, 874, 520, 930, color="#27AE60")
arr(520, 930, 820, 930, color="#27AE60")

rbox(760, 922, 400, 68, "Kết quả", fc="#D5F5E3", ec="#27AE60", fs=24, bold=True)

# skip fail → agentic
arr(520, 806, 520, 780, color="#C0392B", dashed=True)
arr(520, 780, 1180, 780, color="#C0392B", dashed=True)
arr(1180, 780, 1180, 860, color="#C0392B", dashed=True)
lbl(850, 770, "Trả lời thiếu → leo thang", color="#C0392B", fs=15)

# conditions
ax.add_patch(FancyBboxPatch(
    (120, sy(1010)), 560, 150, boxstyle="round,pad=0,rounding_size=14",
    facecolor="#F4F6F7", edgecolor="#BDC3C7", linewidth=2,
))
ax.text(400, sy(898), "Điều kiện leo thang → Agentic", ha="center", fontsize=20, fontweight="bold")
for i, t in enumerate([
    "①  Grader trả về NO (sau requery)",
    "②  Điểm retrieve thấp  (conf < 0,40)",
    "③  Phản hồi thiếu thông tin",
]):
    ax.text(150, sy(936 + i * 32), t, ha="left", fontsize=17, color="#34495E")

# agentic box
ax.add_patch(FancyBboxPatch(
    (1180, sy(1010)), 620, 150, boxstyle="round,pad=0,rounding_size=14",
    facecolor="#FDEDEC", edgecolor="#C0392B", linewidth=3,
))
ax.text(1490, sy(905), "Leo thang  →  Agentic RAG", ha="center", fontsize=24, fontweight="bold", color="#922B21")
ax.text(1490, sy(945), "Plan  →  Retrieve × N  →  Grade  →  Generate", ha="center", fontsize=19, color="#641E16")
ax.text(1490, sy(982), "Tầng 2 — Routing động (a posteriori)", ha="center", fontsize=16,
        fontweight="bold", color="#922B21")

ax.text(W / 2, sy(1060),
        "Hình X. Cơ chế kiểm định relevance và leo thang pipeline (vùng Hybrid)",
        ha="center", fontsize=16, color="#999", style="italic")

out = r"d:\DATN\kma_rag\demo\assets\slide3_grader_escalation.png"
plt.savefig(out, bbox_inches="tight", pad_inches=0, facecolor="white")
print("Saved:", out)
