[![make.fun](https://make.fun/badge/news-image-20261119.svg)](https://make.fun/bounty/news-image-20261119)
[![rank](https://make.fun/badge/news-image-20261119/Iqblhkim/news-image-20261119/rank.svg)](https://make.fun/bounty/news-image-20261119)
[![reward](https://make.fun/badge/news-image-20261119/Iqblhkim/news-image-20261119/reward.svg)](https://make.fun/bounty/news-image-20261119)

# News in One Image — 19 November 2026

One image summing up the world's news of Thursday 19 November 2026,
built for make.fun's "Sum up 19 November's world news in one image"
bounty ($250 in USDC).

The image is a newspaper-style front page: the first-ever Trump–Xi–Putin
trilateral in Shenzhen on the APEC sidelines, Israel's ground operation
in central Gaza, Anthropic's record $81.3bn IPO (shares at $83, trading
on Nasdaq), the Crimea bridge attacked again, Iran widening its strikes
to a US base in Kuwait and Bahrain again, GTA VI's global rollout, a
record $190.4m Van Gogh sale, the UN court's Myanmar genocide verdict,
and Voyager 1 reaching one light-day from Earth — 81 stories in all.

## Run

The program draws the image itself, with the Python standard library
only — no network, no third-party packages:

```
python3 main.py
```

It writes `/output/entry.png` — running it twice writes the same bytes.
The image is a 1024x1024 PNG under 1 MiB.
