# V100-LLM leaderboard

![leaderboard](leaderboard.png)

| # | Model | Kernel | Size (GB) | Gen tok/s | Prompt tok/s (short) | Coding | Reasoning | Instructions | Web search | Agent | Vision | Long context | Overall |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | Qwen3.8-27B HauhauCS Aggressive IQ3_XS | fastmtp | 13.1 | 42.2 | 387 | 88 | 95 | 50 | 100 | 100 | 88 | 100 | **88.6** |
| 2 | MiniCPM-V 4.7 35B-A3B Q3 mix (official mix_q3gud_im) | llamacpp | 15.5 | 56.2 | 467 | 88 | 100 | 50 | 88 | 100 | 88 | 100 | **87.5** |
| 3 | MiniCPM-V 4.7 35B-A3B IQ3_XS | llamacpp | 14.5 | 41.4 | 476 | 94 | 100 | 42 | 88 | 100 | 88 | 100 | **87.2** |
| 4 | MiniCPM-V 4.7 35B-A3B Uncensored Q4_K-IQ4_XS (AtomicChat) | llamacpp | 20.1 | 38.3 | 376 | 88 | 100 | 33 | 100 | 100 | 88 | 100 | **86.9** |
| 5 | Strata: Qwen3.8-Flash-Next 125B IQ2_XS | strata | 68.0 | 34.1 | 1163 | 88 | 100 | 50 | 88 | 100 | 75 | 100 | **85.7** |
| 6 | Qwen3.8-27B HauhauCS Aggressive Q2_K_P (long context) | llamacpp | 10.7 | 41.6 | 326 | 75 | 95 | 42 | 100 | 100 | 88 | 50 | **78.5** |
| 7 | Ternary-Bonsai-2-27B Uncensored Heretic | prism | 7.2 | 39.5 | 363 | 56 | 100 | 42 | 100 | 100 | 88 | 50 | **76.5** |
| 8 | Underdog Saluki 27B (Qwen3.8 2-bit, MTP) | llamacpp | 8.3 | 46.8 | 351 | 62 | 95 | 42 | 88 | 100 | 88 | 50 | **74.9** |
| 9 | PXA-Fusion4-35B-A3B PXQ2 | pxa | 11.2 | 70.0 | 2384 | 38 | 90 | 25 | 88 | 100 | 75 | 100 | **73.6** |
| 10 | Qwen3.8-27B PXQ3 | pxa | 12.4 | 19.8 | 573 | 75 | 95 | 42 | 100 | 100 | 88 | 0 | **71.3** |
| 11 | Ornith-1.5-35B-A3B PXQ2 | pxa | 11.2 | 64.1 | 2333 | 50 | 85 | 33 | 100 | 83 | 75 | 0 | **60.9** |
