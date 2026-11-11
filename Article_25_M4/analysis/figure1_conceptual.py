# Figure 1 of the article (conceptual diagram). Run: python figure1_conceptual.py -> image1_new.png
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch

plt.rcParams["font.family"] = "DejaVu Serif"
fig = plt.figure(figsize=(12.4, 5.94), dpi=100)
ax = fig.add_axes([0, 0, 1, 1])
ax.set_xlim(0, 1240); ax.set_ylim(0, 594); ax.axis("off")

W, H = 473, 0  # ancho de caja
xl, xr = 40, 727          # x izquierda de cada columna (hueco de 214 px)
rows = [(417, 126), (229, 115), (40, 115)]  # (y inferior, alto) de arriba a abajo
edge = "#444444"

def box(x, y, h, color, text, bold=False, size=16):
    ax.add_patch(FancyBboxPatch((x, y), W, h, boxstyle="round,pad=0,rounding_size=8",
                                fc=color, ec=edge, lw=2))
    ax.text(x + W/2, y + h/2, text, ha="center", va="center", fontsize=size,
            fontweight="bold" if bold else "normal", linespacing=1.15)

def arrow(x0, y0, x1, y1, color="#333333"):
    ax.annotate("", xy=(x1, y1), xytext=(x0, y0),
                arrowprops=dict(arrowstyle="-|>", lw=2.2, color=color, mutation_scale=22))

# columna izquierda
box(xl, *rows[0], "#dce6f2", "NETWORK EXPANSION\nGrowth in active distributors\nand sponsor–downline links", bold=True, size=15)
box(xl, *rows[1], "#eef1f6", "Recruitment: enrollment,\nentry purchases, more sellers", size=16)
box(xl, *rows[2], "#eef1f6", "More selling and service\ncapacity (also more contact overlap)", size=16)
# columna derecha
box(xr, *rows[0], "#f7e2e1", "MARKET EXPANSION\nGrowth in nonparticipant\ncustomers and recurring purchases", bold=True, size=15)
box(xr, *rows[1], "#eef1f6", "Retail acquisition and repurchase\nby external customers", size=16)
box(xr, *rows[2], "#eef1f6", "External retail volume\n(excludes participant purchases)", size=16)

# flechas verticales
for x in (xl + W/2, xr + W/2):
    arrow(x, rows[0][0] - 2, x, rows[1][0] + rows[1][1] + 4)
    arrow(x, rows[1][0] - 2, x, rows[2][0] + rows[2][1] + 4)

# "not the same thing": centrado en el hueco, sin tocar las cajas
gx = (xl + W + xr) / 2
ax.text(gx, rows[0][0] + rows[0][1]/2, "not the\nsame thing", ha="center", va="center",
        fontsize=15, style="italic", color="#777777", linespacing=1.2)

# "supports": flecha horizontal en la fila inferior
yb = rows[2][0] + rows[2][1]/2
arrow(xl + W + 2, yb, xr - 4, yb, color="#555555")
ax.text(gx, yb + 20, "supports", ha="center", va="center", fontsize=15, style="italic", color="#555555")

fig.savefig("image1_new.png", dpi=200, facecolor="white")
