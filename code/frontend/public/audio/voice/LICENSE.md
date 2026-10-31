# 牌面报牌人声 · 素材来源与授权风险登记（v1.1 / I11 / S-1）

本目录下 **34 个 mp3** 是「牌面人声报牌」用的女声素材（出牌后叠加在落牌底噪之上播报该张牌）。
规格见 [08-音效设计.md §6.2](../../../../../plan/08-音效设计.md)；实现路径见 §4.5。

## 来源

| 项 | 内容 |
| --- | --- |
| 来源仓库 | `1RGameSol/Mahjong-1` |
| 检索地址 | <https://github.com/1RGameSol/Mahjong-1> |
| 源路径 | `Assets/Resources/Sound/g_*.ogg` |
| 原始素材（本项目留档） | `plan/majiang_sound/women/`（40 个 `.ogg`）—— **本机留档，不入库**（根 `.gitignore` 已忽略 `plan/majiang_sound/`） |
| 转码素材（本项目留档） | `plan/majiang_sound/women_mp3/`（同名 40 个 `.mp3`，ffmpeg 转码产物）—— **本机留档，不入库** |
| 本项目取用 | **仅 34 个牌面音**：`1wan`…`9wan`、`1tong`…`9tong`、`1tiao`…`9tiao`、`dongfeng`、`nanfeng`、`xifeng`、`beifeng`、`zhong`、`fa`、`bai` |
| **未取用** | 6 个叫牌音 `hu` / `pong` / `chow` / `kong_exposed` / `kong_hidden` / `kong_added` —— **一律不复制进本目录**，游戏里的叫牌音继续沿用 `public/audio/sfx/` 的自制合成音 |

## 授权状态（风险登记）

- 源仓库**未提供 LICENSE 文件**，其授权状态未知；在无明确开源许可的情况下，法律默认「**保留所有权利（all rights reserved）**」，因此**权利归属不明**。
- **用户已于 2026-10-31 明确知悉并接受该风险，且要求直接发布**（风险处置见 [08-音效设计.md §6.3](../../../../../plan/08-音效设计.md)）。
- 该风险在**两处留痕**：本文件与 `plan/08-音效设计.md` §6.3；两者必须同时保留，不得省略。

## 后续替换约定

1. 替换素材时**保持文件名不变**即可不改任何代码（`src/audio/voiceMap.ts` 的映射表只认基名）。
2. 若需强制刷新浏览器缓存，改文件名并在 `voiceMap.ts` 里加 `?v=` —— **不要依赖用户强制刷新**（nginx 对 `*/audio/voice/` 设 30 天 `max-age=2592000` 强缓存）。
3. 替换为自制或 CC0 录音后，请删除本文件中的「风险登记」段，并把「来源 / 授权」改记为新的来源与许可。

## 规格与实测

- 格式：MP3（MPEG-1 Layer III），单声道，44.1 kHz，112 kbps（与 `plan/majiang_sound/women_mp3` 的转码口径一致：`ffmpeg -i <src>.ogg -ac 1 -ar 44100 -b:a 112k <dst>.mp3`）。
- 时长：0.57–0.76 s（不裁剪、不变速）。
- 体积：**目录合计 301,379 B（约 294.3 KB，≤ 400 KB）**；单文件 6,261–11,015 B（最大 11,015 B）。
- 目录内文件清单：34 个 mp3 + 本 `LICENSE.md`。
