# rime-german-gloss

一个跨平台 Rime 德语释义扩展：通过 librime-lua 的 `lua_filter`，在候选词注释（comment）中追加离线中德词典的德语释义。适用于 Windows（Weasel）与 Linux（fcitx5-rime / ibus-rime）。

```
xuexiao →  1. 学校  die Schule
```

## 行为定义

- 对每个候选按 `cand.text` **整词匹配**查询本地 TSV 词典；不做分词、不做子串匹配。
- 简繁通用：先按原文精确匹配；未命中时，用 OpenCC `t2s.json` 将候选文本转为简体后再查。词典键也做同样转换，因此词典用简体或繁体书写均可，一份词典同时服务简体与繁体输出（详见“简繁体与仓颉”）。
- 命中且原注释为空：`comment = " " .. gloss`。
- 命中且原注释非空（如 simplifier 的 `〔繁〕`、编码提示等）：保留原注释，追加为 `原注释 .. " " .. gloss`。
- 未命中：候选原样输出；候选顺序与数量不变。
- 过滤器只读取 `cand.text`，与输入编码无关，因此全拼（如 `luna_pinyin`）、小鹤双拼（如 `double_pinyin_flypy`）及其他方案均可使用，不绑定具体 schema。
- 纯离线：仅读取本地 TSV，不联网。

实现细节：librime-lua 中对 `Shadow` / `Uniquified` 类型候选（例如经 simplifier、uniquifier 处理后的候选）设置 `cand.comment` 是静默无效操作（见 librime-lua `src/types.cc` 的 `set_comment`）。本过滤器在赋值后回读校验，若未生效则以 `ShadowCandidate(cand, cand.type, cand.text, comment)` 包装输出。

## 文件结构

```
lua/german_gloss.lua        过滤器模块（安装到 <用户目录>/lua/）
german_gloss/zh_de.tsv      最小测试词典（安装到 <用户目录>/german_gloss/）
install-windows.ps1         Windows / Weasel 安装脚本
install-linux.sh            Linux / fcitx5-rime / ibus-rime 安装脚本
tests/test_german_gloss.lua 离线单元测试（mock librime-lua 对象）
```

不修改 librime、Weasel、fcitx5-rime 或 ibus-rime 的任何核心代码，也不需要修改 `rime.lua`。

## 前提条件

前端需内置 librime-lua，且支持 `lua_filter@*模块名` 形式（自动 `require` 用户目录 `lua/` 下的模块）。

- Windows：Weasel 安装包自带 librime-lua。
- Linux：发行版的 librime 包可能未启用 lua 插件，需要另行安装（例如 Debian/Ubuntu 的 `librime-plugin-lua`；其他发行版以其实际包名为准）。

若所用 librime-lua 版本过旧、不支持 `*` 语法，见下文“旧版 librime-lua 兼容写法”。

## 安装

### Windows（Weasel）

```powershell
powershell -ExecutionPolicy Bypass -File .\install-windows.ps1 -Schema luna_pinyin,double_pinyin_flypy -Deploy
```

用户目录检测顺序：

1. `-RimeUserDir <路径>` 参数；
2. 注册表 `HKCU\Software\Rime\Weasel` 的 `RimeUserDir` 值（在 Weasel 中自定义用户目录时写入）；
3. 默认 `%APPDATA%\Rime`。

`-Deploy` 通过注册表 `HKLM\SOFTWARE\Rime\Weasel`（或 `WOW6432Node`）的 `WeaselRoot` 定位 `WeaselDeployer.exe` 并执行 `/deploy`。

### Linux（fcitx5-rime / ibus-rime）

```sh
./install-linux.sh --schema luna_pinyin --schema double_pinyin_flypy
```

仓颉五代用户：`./install-linux.sh --schema cangjie5`（Windows：`-Schema cangjie5`）。

未指定 `--dir` 时，安装到以下**所有已存在**的目录：

| 前端 | 用户目录 |
|---|---|
| fcitx5-rime | `${XDG_DATA_HOME:-~/.local/share}/fcitx5/rime` |
| fcitx5-rime（Flatpak） | `~/.var/app/org.fcitx.Fcitx5/data/fcitx5/rime` |
| ibus-rime | `${XDG_CONFIG_HOME:-~/.config}/ibus/rime` |
| fcitx-rime（fcitx4） | `${XDG_CONFIG_HOME:-~/.config}/fcitx/rime` |

目录不存在时，先部署一次 Rime，或用 `--dir DIR` 显式指定。

### 安装脚本的共同行为

- `lua/german_gloss.lua` 总是覆盖安装。
- `german_gloss/zh_de.tsv` 若已存在且内容不同（视为用户已修改），保留原文件，新版本写为 `zh_de.tsv.new`；`--force` / `-Force` 强制覆盖。
- 对每个 `--schema` / `-Schema` 指定的方案：
  - `<schema>.custom.yaml` 不存在 → 创建并写入启用补丁；
  - 已存在且含 `german_gloss` → 不改动；
  - 已存在但不含 → **不改动**，打印需手动添加的补丁行（避免破坏用户已有 YAML）。
- 未指定方案时，只安装文件，不启用过滤器。

## 启用 filter

在用户目录的 `<schema_id>.custom.yaml` 中加入（schema_id 例如 `luna_pinyin`、`double_pinyin_flypy`、`rime_ice` 等，按实际使用的方案填写）：

```yaml
patch:
  engine/filters/@next: lua_filter@*german_gloss
```

`@next` 将过滤器追加到该方案 `engine/filters` 列表末尾，因此在 simplifier、uniquifier 之后运行，能看到并保留它们产生的注释。若文件已有 `patch:`，只需把该行加入现有 `patch:` 下。

可选：指定其他词典路径（相对用户目录，找不到时再查共享目录；也可写绝对路径）：

```yaml
patch:
  engine/filters/@next: lua_filter@*german_gloss
  german_gloss/dictionary: german_gloss/my_zh_de.tsv
```

可选：简繁转换配置（默认 `t2s.json`；设为 `none` 关闭简繁通用匹配，恢复纯精确匹配）：

```yaml
patch:
  german_gloss/opencc_config: none
```

配置键前缀为过滤器的 name space：`lua_filter@*german_gloss` 对应 `german_gloss`；若写成 `lua_filter@*german_gloss@de`，则对应 `de/dictionary`。

### 旧版 librime-lua 兼容写法

若前端的 librime-lua 不支持 `*` 自动加载，在用户目录 `rime.lua` 中加入：

```lua
german_gloss = require("german_gloss")
```

并将补丁改为 `engine/filters/@next: lua_filter@german_gloss`（无 `*`）。

## 简繁体与仓颉

以 rime-cangjie 的 `cangjie5` 方案为例（其码表为繁体；`engine/filters` 为 `simplifier`、`uniquifier`、`single_char_filter`；`simplifier/tips: all`）。本过滤器以 `@next` 追加在这些 filter 之后，因此看到的是简化转换之后的文本：

| 方案状态 | 候选文本 | 匹配路径 | 结果注释（示意） |
|---|---|---|---|
| 漢字（繁体输出） | `學校` | 精确未命中 → `t2s` 得 `学校` → 命中 | `<原编码提示> die Schule` |
| 汉字（简化输出） | `学校` | 精确命中 | `〔學校〕 die Schule` |

设计取舍：统一归一到**简体**而非繁体，因为繁→简基本是多对一映射，结果确定；简→繁是一对多（如 发→發/髮），反向归一会产生歧义。

条件与限制：

- 需要 librime-lua 提供 `Opencc` 接口，且能在 `<用户目录>/opencc/` 或 `<共享目录>/opencc/` 找到 `t2s.json`。这与 librime simplifier 的查找位置相同，因此若方案的简繁切换可用，该文件通常已存在。任一条件不满足时，过滤器记录警告并退化为纯精确匹配，不影响输入。
- `t2s` 是字形转换，不处理地区词汇差异（如台湾「軟體」→ `软体`，而非「软件」）。如需要，可改用 OpenCC 的 `tw2sp.json` 等配置，前提是该文件存在于上述目录。
- 仓颉以单字输入为主；多字词条只有在方案以词组形式给出候选（如 `cangjie5` 的预设词汇或用户造词）时才会命中。单字释义需在词典中单独添加。

## 重新部署

修改 `*.custom.yaml`、Lua 文件或词典后，需重新部署（词典在过滤器初始化时载入）：

- **Weasel**：托盘图标右键 →「重新部署」；或运行 `WeaselDeployer.exe /deploy`（位于 Weasel 安装目录）。
- **fcitx5-rime**：托盘菜单 → Rime →「重新部署」（Deploy）。
- **ibus-rime**：ibus 输入法菜单 →「部署」（Deploy）；或 `ibus restart`。

验证：输入 `xuexiao`（全拼）或 `xtxn`（小鹤双拼），候选「学校」后应显示 `die Schule`。

## 词典格式

UTF-8 文本，每行 `中文<TAB>德语释义`：

```
学校	die Schule
工作	die Arbeit
研究	die Forschung
电脑	der Computer
```

- 以 `#` 开头的行与空行忽略；无 TAB 的行忽略；键与值两端空白被去除。
- 允许 UTF-8 BOM 与 CRLF 换行（Windows 编辑器保存的文件可直接使用）。
- 同一键出现多次时，按文件顺序以 `; ` 连接（完全重复的释义去重），例如 `die Schule; die Hochschule`。

## 测试

需要本地 Lua 解释器（已在 Lua 5.1 与 5.4 下验证）：

```sh
lua tests/test_german_gloss.lua
```

测试以 mock 对象模拟 librime-lua 的 `Candidate`、`ShadowCandidate`、`Opencc`、`rime_api`、`yield`，覆盖：简繁归一（繁体候选、繁体词典键、精确优先、关闭与缺失配置）、四个词条载入、空注释/已有注释/Shadow 候选/Sentence 候选/未命中、BOM/CRLF/重复键解析、自定义词典路径与 name space、词典缺失时的直通行为。该测试不等价于在真实 Weasel / fcitx5-rime / ibus-rime 中的端到端验证。

## 已知限制

- 仅匹配整个候选文本（含简繁归一）；句子候选（如「学校工作」）不会被拆分查询。
- Windows 下用户目录路径含非 ASCII 字符时，Lua `io.open` 依赖 librime 返回的本地编码路径；未在此类环境中验证。
- 词典在每次过滤器初始化（部署、切换方案、新建会话）时完整载入内存；大词典会相应增加初始化时间与内存占用。
