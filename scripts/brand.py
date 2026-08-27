"""채널 브랜딩 이미지 — 프로필(800) + 배너(2560x1440) 시안.

배너는 전 기기 안전영역(1235x338) 안에 텍스트·배지를 모두 넣는다.
그 밖은 글로우만 흐르게 두어 TV/데스크톱에서 잘려도 손실이 없다.
"""
from PIL import Image, ImageDraw, ImageFont, ImageFilter

SANS = "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc"
SERIF = "/usr/share/fonts/opentype/noto/NotoSerifCJK-Bold.ttc"

INK, INK_HI = (26, 20, 36), (48, 34, 66)
LAV, LAV_DIM = (201, 168, 232), (139, 107, 177)
PAPER, MUTED = (242, 237, 247), (163, 149, 181)

FACE = (0, 8, 260, 268)   # ref_chibi에서 얼굴이 중앙에 오는 정사각 크롭


def font(p, s):
    return ImageFont.truetype(p, s)


def circle(img, size, ring=None):
    img = img.resize((size, size), Image.LANCZOS).convert("RGBA")
    m = Image.new("L", (size * 4, size * 4), 0)
    ImageDraw.Draw(m).ellipse((0, 0, size * 4, size * 4), fill=255)
    img.putalpha(m.resize((size, size), Image.LANCZOS))
    if ring:
        pad = 10
        out = Image.new("RGBA", (size + pad * 2, size + pad * 2), (0, 0, 0, 0))
        out.paste(img, (pad, pad), img)
        ImageDraw.Draw(out).ellipse((pad - 5, pad - 5, size + pad + 4, size + pad + 4),
                                    outline=ring, width=5)
        return out
    return img


def glow(w, h, rx, ry, blur):
    g = Image.new("RGB", (w, h), INK)
    d = ImageDraw.Draw(g)
    for i in range(60, 0, -1):
        gw, gh, t = int(w * rx * i / 60), int(h * ry * i / 60), i / 60
        d.ellipse((w // 2 - gw, h // 2 - gh, w // 2 + gw, h // 2 + gh),
                  fill=tuple(int(a + (b - a) * (1 - t)) for a, b in zip(INK, INK_HI)))
    return g.filter(ImageFilter.GaussianBlur(blur))


def profile(out="assets/channel/profile.png"):
    src = Image.open("assets/serin/ref_chibi.png").convert("RGB").crop(FACE)
    S = 800
    base = glow(S, S, 0.62, 0.62, 30)
    ch = circle(src, int(S * 0.90))
    base.paste(ch, ((S - ch.width) // 2, (S - ch.height) // 2), ch)
    base.save(out)
    return out


W, H = 2560, 1440
SAFE_W, SAFE_H = 1235, 338


def banner(lines, tagline, out, serif=True):
    """lines: 타이틀 1~2줄. 배지 3칸(세린 + 예정 2)과 함께 안전영역 안에 중앙 정렬."""
    base = glow(W, H, 0.55, 0.75, 90)
    d = ImageDraw.Draw(base)
    cx, cy = W // 2, H // 2

    D, GAP = 200, 28
    badges_w = D * 3 + GAP * 2

    size = 96 if max(len(x) for x in lines) <= 5 else 78
    f_title, f_tag = font(SERIF if serif else SANS, size), font(SANS, 40)
    text_w = max(d.textlength(x, font=f_title) for x in lines)

    total = badges_w + 60 + text_w
    x0 = int(cx - total / 2)
    assert total <= SAFE_W, f"\uc548\uc804\uc601\uc5ed \ucd08\uacfc: {total:.0f} > {SAFE_W}"

    src = Image.open("assets/serin/ref_chibi.png").convert("RGB").crop(FACE)
    by = cy - D // 2 - 26
    ch = circle(src, D, ring=LAV)
    base.paste(ch, (x0 - 10, by - 10), ch)
    f_slot = font(SANS, 64)
    for n in (1, 2):
        x = x0 + n * (D + GAP)
        d.ellipse((x, by, x + D, by + D), fill=(38, 29, 52), outline=LAV_DIM, width=4)
        d.text((x + D // 2, by + D // 2), "?", font=f_slot, fill=LAV_DIM, anchor="mm")

    tx = x0 + badges_w + 60
    lead = int(size * 1.18)
    ty = by + D // 2 - (lead * len(lines)) // 2
    for i, x in enumerate(lines):
        d.text((tx, ty + lead * i), x, font=f_title, fill=PAPER)

    # \ud0dc\uae00\ub77c\uc778\uc740 \ud589 \uc544\ub798 \uc911\uc559 \uc815\ub82c
    d.text((cx, by + D + 46), tagline, font=f_tag, fill=MUTED, anchor="ma")

    base.save(out)
    return out


if __name__ == "__main__":
    TAG = "살림 못 하는 집에 요정이 하나씩 붙습니다"
    print(profile())
    print(banner(["우리집엔", "요정이 산다"], TAG, "assets/channel/banner_A.png", serif=True))
    print(banner(["어서 와,", "우리집"], TAG, "assets/channel/banner_B.png", serif=False))
