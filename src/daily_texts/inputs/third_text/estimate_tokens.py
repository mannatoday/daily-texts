#!/usr/bin/env python3
"""Estimate per-day and yearly token usage for third-text (今日禱文) *selection*.

Method = db_select: the LLM reads the day's two verses plus a compact keyword
index of the source library, and returns {third_text_id, match_keyword, note}.
It does NOT compose text, so per-day output is tiny; the real cost is the
one-time curation of the source library.

Counts input/output tokens with tiktoken (o200k_base, the GPT-4o/5 family
encoding; Claude token counts are within ~10%). Falls back to a CJK-aware
heuristic if tiktoken is unavailable.

Run: python3 estimate_tokens.py
"""
from __future__ import annotations

import csv
import json
from pathlib import Path

HERE = Path(__file__).parent

# --- tokenizer ---------------------------------------------------------------
try:
    import tiktoken

    _ENC = tiktoken.get_encoding("o200k_base")

    def ntok(s: str) -> int:
        return len(_ENC.encode(s))

    TOKENIZER = "tiktoken o200k_base"
except Exception:  # pragma: no cover - fallback path
    def ntok(s: str) -> int:
        # CJK chars ~1 token each; other chars ~4 per token.
        cjk = sum(1 for c in s if "\u4e00" <= c <= "\u9fff")
        other = len(s) - cjk
        return cjk + (other + 3) // 4

    TOKENIZER = "heuristic (tiktoken not installed)"

# --- fixed selection prompt --------------------------------------------------
SYSTEM = (
    "你是華語《摩拉維亞每日箴言》的第三段編者。每天會給你當天的舊約箴言與新約經文，"
    "以及一份『來源庫關鍵詞索引』（每行是 id 加上該聖詩/禱文自己會說出的詞）。"
    "請先從舊約、新約各抽出一組詞或畫面（兩組），再從索引中挑一筆『兩組都已有、或能同時接住』的來源作第三段；"
    "不要只碰一節、漏掉另一節，也不要挑神學總論。"
    "只輸出 JSON：{\"third_text_id\":..., \"match_keyword\":..., \"note\":...}；"
    "match_keyword 格式為『舊約詞組｜新約詞組』；note 用一句話說明怎麼把兩組帶向今天的禱告，不再解經。"
)

# Chinese verse text for the trial days (RCUV/通用，用於估算長度).
VERSES = {
    "2026-10-01": (
        "詩篇 71:20　你是叫我們多經歷重大急難的，必使我們復活，從地的深處救上來。",
        "彼得後書 2:9　主知道搭救敬虔的人脫離試探。",
    ),
    "2026-10-02": (
        "撒母耳記上 3:9　耶和華啊，請說，僕人敬聽。",
        "馬太福音 7:24　凡聽見我這話就去行的，好比一個聰明人，把房子蓋在磐石上。",
    ),
    "2026-10-03": (
        "以賽亞書 29:13　這百姓用嘴唇尊敬我，心卻遠離我。",
        "馬太福音 15:11　入口的不能污穢人，出口的乃能污穢人。",
    ),
    "2026-10-04": (
        "尼希米記 9:5　你們要站起來稱頌耶和華你們的神，從亙古直到永遠。稱頌你榮耀之名，這名超乎一切稱頌和讚美。",
        "哥林多前書 10:31　所以你們或吃或喝，無論做甚麼，都要為榮耀神而行。",
    ),
    "2026-10-05": (
        "創世記 18:27　我雖是灰塵，還敢對主說話。",
        "馬太福音 15:27-28　婦人說：主啊，不錯；但是狗也吃牠主人桌上掉下來的碎渣。耶穌說：婦人，你的信心是大的！照你所要的成全你吧。",
    ),
    "2026-10-06": (
        "詩篇 25:20　求你保護我的性命，搭救我，使我不致羞愧，因為我投靠你。",
        "約翰福音 14:19　因為我活著，你們也要活著。",
    ),
    "2026-10-07": (
        "阿摩司書 5:14　你們要尋求善，不要尋求惡，就必存活。",
        "帖撒羅尼迦前書 5:15　你們要謹慎，無論是誰都不可以惡報惡；或是彼此相待，或是待眾人，常要追求良善。",
    ),
    "2026-10-08": (
        "哈巴谷書 2:3　這默示有一定的日期，必然臨到，不再遲延；雖然遲延，還要等候。",
        "雅各書 5:7　看哪，農夫忍耐等候地裡寶貴的出產，直到得了秋雨春雨。",
    ),
    "2026-10-09": (
        "以賽亞書 50:9　主耶和華要幫助我，誰能定我有罪呢？",
        "羅馬書 8:34　有基督耶穌已經死了，而且從死裡復活，現今在神的右邊，也替我們祈求。",
    ),
    "2026-10-10": (
        "民數記 11:23　耶和華的膀臂豈是縮短了嗎？",
        "馬可福音 4:41　他們就大大懼怕，彼此說：這到底是誰，連風和海也聽從他了？",
    ),
    "2026-10-11": (
        "士師記 8:23　基甸對他們說：「我不治理你們，我的兒子也不治理你們，耶和華會治理你們。」",
        "約翰福音 20:28　多馬回答，對他說：「我的主！我的神！」",
    ),
    "2026-10-12": (
        "詩篇 143:5　我追想古時之日，思想你的一切作為，默念你手的工作。",
        "路加福音 1:50　他憐憫敬畏他的人，直到世世代代。",
    ),
    "2026-10-13": (
        "約書亞記 24:18　耶和華又把各民族和住此地的亞摩利人都從我們面前趕出去。所以，我們也必事奉耶和華，因為他是我們的上帝。",
        "路加福音 5:27-28　耶穌出去，看見一個稅吏，名叫利未，在稅關坐著，就對他說：「來跟從我！」他就撇下所有的，起來跟從耶穌。",
    ),
    "2026-10-14": (
        "詩篇 97:11　散布亮光是為義人，喜樂歸於心裡正直的人。",
        "路加福音 14:13-14　你擺設宴席，倒要請那貧窮的、殘疾的、瘸腿的、失明的，你就有福了！因為他們沒有甚麼可報答你。",
    ),
    "2026-10-15": (
        "耶利米哀歌 3:25　凡等候耶和華，心裡尋求他的，耶和華必施恩給他。",
        "啟示錄 3:20　看哪，我站在門外叩門，若有聽見我聲音而開門的，我要進到他那裡去；我與他，他與我一同坐席。",
    ),
}


def load_index() -> str:
    rows = []
    with open(HERE / "sources.csv", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            rows.append(f"{r['id']}: {r['keywords']}")
    return "\n".join(rows)


def load_outputs() -> dict[str, str]:
    out = {}
    with open(HERE / "pairings_2026.csv", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            out[r["date"]] = json.dumps(
                {
                    "third_text_id": r["third_text_id"],
                    "match_keyword": r["match_keyword"],
                    "note": r["note"],
                },
                ensure_ascii=False,
            )
    return out


def build_user(date: str, index: str) -> str:
    ot, nt = VERSES[date]
    return (
        f"日期：{date}\n舊約箴言：{ot}\n新約經文：{nt}\n\n"
        f"來源庫關鍵詞索引：\n{index}\n\n"
        "請挑出最合適的一筆並輸出 JSON。"
    )


# Illustrative public API prices (USD / 1M tokens); adjust to current rates.
PRICES = {
    "Claude Sonnet (3 / 15)": (3.0, 15.0),
    "GPT-5 class (1.25 / 10)": (1.25, 10.0),
    "Claude Haiku (0.80 / 4)": (0.80, 4.0),
}


def main() -> None:
    index = load_index()
    outputs = load_outputs()
    sys_tok = ntok(SYSTEM)
    idx_tok = ntok(index)

    print(f"Tokenizer: {TOKENIZER}")
    print(f"System prompt: {sys_tok} tok | keyword index ({index.count(chr(10))+1} rows): {idx_tok} tok\n")

    per_in, per_out = [], []
    print(f"{'date':12} {'in':>6} {'out':>5}  chosen")
    for date in sorted(VERSES):
        user = build_user(date, index)
        tin = sys_tok + ntok(user)
        tout = ntok(outputs[date])
        per_in.append(tin)
        per_out.append(tout)
        chosen = json.loads(outputs[date])["third_text_id"]
        print(f"{date:12} {tin:6} {tout:5}  {chosen}")

    n = len(per_in)
    avg_in = sum(per_in) / n
    avg_out = sum(per_out) / n
    print(f"\n{n}-day totals: in={sum(per_in)}  out={sum(per_out)}  total={sum(per_in)+sum(per_out)}")
    print(f"per-day avg : in={avg_in:.0f}  out={avg_out:.0f}  total={avg_in+avg_out:.0f}")

    yr_in = avg_in * 365
    yr_out = avg_out * 365
    print(f"\nFull year (x365, db_select / selection only):")
    print(f"  input ~ {yr_in:,.0f} tok | output ~ {yr_out:,.0f} tok | total ~ {yr_in+yr_out:,.0f} tok")
    print("  cost (illustrative rates, USD):")
    for name, (pin, pout) in PRICES.items():
        cost = yr_in / 1e6 * pin + yr_out / 1e6 * pout
        print(f"    {name:26} ~ ${cost:.2f}/yr")

    # Contrast: if we instead COMPOSED an original prayer (~110 output tokens),
    # smaller input (no index), larger output.
    comp_in = sys_tok  # verses only, no index; approximate same order
    comp_in = (avg_in - idx_tok)
    comp_out = 120
    yc_in, yc_out = comp_in * 365, comp_out * 365
    print(f"\nContrast - original composition (no index, ~{comp_out} out tok/day):")
    print(f"  input ~ {yc_in:,.0f} tok | output ~ {yc_out:,.0f} tok | total ~ {yc_in+yc_out:,.0f} tok")


if __name__ == "__main__":
    main()
