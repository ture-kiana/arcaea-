# Arcaea / 韵律源点 b50 导出工具

从手机本地存档（`st3`）直接算出 b50 与潜力值的桌面小工具。**不联网、不上传、不需要账号密码**，只读取游戏数据。

支持国服《韵律源点》（`com.xd.arcaea.tapcn`）与国际服《Arcaea》（`moe.low.arc`）。

---

## 它解决什么问题

国服 2026 年 11 月上线后，第三方查分生态（BotArcAPI、各类 b50 图站）都只对接国际服好友码，国服玩家没有现成的 b50 查询入口；官方的 b50 卡片又锁在 Arcaea Online 订阅功能里，TapTap 账号登不进去。

这个工具绕开接口，直接从设备上的 SQLite 存档读数，因此对国服同样有效。

## 功能

- **一键读取**：自动检测设备 → 逐层尝试 `run-as` / `root` → 解析存档 → 算出 b50
- **内置教程**：华为/荣耀、小米/红米、OPPO/一加/realme、vivo/iQOO、三星、魅族、原生安卓、纯血鸿蒙、iPhone、手动导入，共 10 类设备
- **b50 卡片**：5×10 网格，含曲绘、等级标注（`9+` / `10+`）、通关标记、b10 的 ×2 权重标记
- **完整分析页**：PTT 历史曲线、P50 / LS0 / MAX 多排行、定数区间查询、图片导出
- **数据导出**：`all_scores.csv` / `ratings.csv`，格式与 [arcaea-trend-b30](https://github.com/Arctan01/arcaea-trend-b30) 兼容
- **兜底路径**：读不到存档时可以手动导入 `st3` 文件（有 root / LSPatch 模块 / 模拟器三种取法见教程）

## 计算口径（v7.0 起）

单曲潜力值：

```
分数 ≥ 10,000,000  →  定数 + 2
分数 ≥  9,800,000  →  定数 + 1 + (分数 - 9,800,000) / 200,000
分数 <  9,800,000  →  定数 + (分数 - 9,500,000) / 300,000   （下限 0）
```

再叠加 **通关奖励 +0.2**（PM / FR / TC 均计，Track Lost 不计）。

整体潜力值：

```
PTT = ( b50 总和 + b10 总和 ) ÷ 60
```

前 10 名双倍权重，`r10` 自 v7.0 起已取消。

## 使用

### 直接运行

下载 [Release](../../releases) 里的 `ArcaeaB50.exe`，双击即可。程序会在本地起一个服务并打开浏览器界面。

### 从源码运行

```bash
pip install pyinstaller            # 只打包时需要；运行本身零依赖
python app/main.py                 # 会自动打开浏览器
python app/main.py --no-browser --port 8080
```

### 打包

```bash
build.bat
```

产物在 `dist/ArcaeaB50.exe`（约 13 MB，单文件，无需安装）。

## 目录结构

```
app/
  main.py           # 本地 HTTP 服务 + 路由
  api.py            # adb 交互、st3 解析、b50 计算、曲绘导出
  ui.html           # 单页界面（含各品牌教程）
  data/
    songlist        # 曲目表（Arcaea 格式 JSON）
    constants.json  # 谱面定数
  viewer/           # 完整分析页（衍生自 arcaea-trend-b30）
scripts/
  fetch_assets.py   # 拉取曲目表 / 定数 / 分析页静态资源
  b50.py            # 命令行版：拉存档 → 算 b50 → 出图
  export_viewer.py  # st3 → 分析页所需的 CSV
  render_card.py    # PIL 版 b50 卡片渲染
release/            # 已打包好的 exe
docs/               # 使用说明、手机端导出教程
```

## 数据存放在哪

```
%LOCALAPPDATA%\ArcaeaB50\
  jackets\   曲绘缓存
  data\      all_scores.csv / ratings.csv
```

删除该目录即可清空缓存。

## 已知限制

- **LS（Loss Score）**：国服拿不到，导出 CSV 里固定写 0，界面建议关闭「显示 LS」
- **历史曲线是阶梯状**：存档只保留每个谱面的最佳成绩及其达成时间，不是逐局历史
- **定数为社区整理**，与游戏内可能存在极小误差；遇到未收录的新曲会明确提示
- 纯血鸿蒙 HarmonyOS NEXT 无 adb、iOS 无法读取沙箱，这两类需借用安卓设备或手动导入

## 致谢

- [arcaea-trend-b30](https://github.com/Arctan01/arcaea-trend-b30) — 完整分析页（PTT 历史曲线、多排行、图片导出）衍生自此项目
- [smartrte 的 Arcaea 查分工具](http://smartrte.github.io/) — 曲目表与定数数据来源

## 免责声明

非官方工具，与 lowiro / 心动网络无关。只读取本机存档，不修改游戏数据、不绕过付费内容。请勿用于任何违反游戏用户协议的场景。
