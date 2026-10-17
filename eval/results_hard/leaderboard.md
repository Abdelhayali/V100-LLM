# V100-LLM leaderboard

![leaderboard](leaderboard.png)

| # | Model | Kernel | Size (GB) | Context | Gen tok/s | Fastest preset (tok/s @ context) | Prompt tok/s (short) | Coding | Reasoning | Instructions | Web search | Agent | Vision | Long context | Overall |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | Qwen3.8-27B HauhauCS Aggressive IQ3_XS | fastmtp | 13.1 | 24k | 42.2 | – | 387 | 88 | 95 | 50 | 100 | 100 | 88 | 100 | **88.6** |
| 2 | MiniCPM-V 4.7 35B-A3B Q3 mix (official mix_q3gud_im) | llamacpp | 15.5 | 262k | 56.2 | **93.4 @ 128k** | 467 | 88 | 100 | 50 | 88 | 100 | 88 | 100 | **87.5** |
| 3 | MiniCPM-V 4.7 35B-A3B IQ3_XS | llamacpp | 14.5 | 262k | 41.4 | – | 476 | 94 | 100 | 42 | 88 | 100 | 88 | 100 | **87.2** |
| 4 | MiniCPM-V 4.7 35B-A3B Uncensored Q4_K-IQ4_XS (AtomicChat) | llamacpp | 20.1 | 262k | 38.3 | – | 376 | 88 | 100 | 33 | 100 | 100 | 88 | 100 | **86.9** |
| 5 | MiniCPM-V 4.7 35B-A3B CRACK Q4_K_M (dealignai) | llamacpp | 22.6 | 262k | 40.5 | – | 340 | 88 | 95 | 33 | 100 | 100 | 88 | 100 | **86.2** |
| 6 | Strata: Qwen3.8-Flash-Next 125B Q2_0 | strata | 66.4 | 262k | 34.8 | – | 1207 | 94 | 90 | 42 | 88 | 100 | 88 | 100 | **85.8** |
| 7 | Strata: Qwen3.8-Flash-Next 125B IQ2_XS | strata | 68.0 | 262k | 34.1 | – | 1163 | 88 | 100 | 50 | 88 | 100 | 75 | 100 | **85.7** |
| 8 | Strata: Qwen3.8-Flash-Next 125B Coder IQ1_M | strata | 58.4 | 262k | 29.7 | – | 1247 | 94 | 100 | 42 | 88 | 100 | 75 | 100 | **85.4** |
| 9 | NVIDIA Nemotron-3.5-Bolt-74B-A9B (2-bit) | llamacpp | 22.0 | 262k | 16.7 | – | 277 | 75 | 85 | 58 | 100 | 100 | 88 | 50 | **79.4** |
| 10 | Qwen3.8-27B HauhauCS Aggressive Q2_K_P (long context) | llamacpp | 10.7 | 160k | 41.6 | – | 326 | 75 | 95 | 42 | 100 | 100 | 88 | 50 | **78.5** |
| 11 | Ternary-Bonsai-2-27B Uncensored Heretic | prism | 7.2 | 262k | 39.5 | – | 363 | 56 | 100 | 42 | 100 | 100 | 88 | 50 | **76.5** |
| 12 | Underdog Saluki 27B (Qwen3.8 2-bit, MTP) | llamacpp | 8.3 | 262k | 46.8 | – | 351 | 62 | 95 | 42 | 88 | 100 | 88 | 50 | **74.9** |
| 13 | PXA-Fusion4-35B-A3B PXQ2 | pxa | 11.2 | 16k | 70.0 | – | 2384 | 38 | 90 | 25 | 88 | 100 | 75 | 100 | **73.6** |
| 14 | Qwen3.8-27B PXQ3 | pxa | 12.4 | 8k | 19.8 | – | 573 | 75 | 95 | 42 | 100 | 100 | 88 | 0 | **71.3** |
| 15 | Ornith-1.5-35B-A3B PXQ2 | pxa | 11.2 | 16k | 64.1 | – | 2333 | 50 | 85 | 33 | 100 | 83 | 75 | 0 | **60.9** |
