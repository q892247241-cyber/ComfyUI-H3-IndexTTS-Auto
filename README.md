# ComfyUI-H3-IndexTTS-Auto

MiniMax H3 提示词 → IndexTTS 2.5 对白/情绪脚本的 **ComfyUI 自定义节点包**。

针对 H3 + IndexTTS 工作流里显示为红色 `UNKNOWN` 的 **6 个节点**：它们实际上只对应 **2 种节点类型**。安装本插件后，ComfyUI 可以识别并执行这些节点（前提是托管平台允许安装 Python 自定义节点）。**不需要在这里安装 H3 或 IndexTTS 模型，也不需要重复造 6 个插件。**

## 支持的两个节点

| `class_type`（与原 JSON 保持一致） | 显示名称 | 输入 → 输出 |
| --- | --- | --- |
| `H3DialogueExtractToIndexTTS` | H3 → IndexTTS 自动提取台词/情绪 | H3 提示词 STRING → IndexTTS batch 脚本文本 STRING、提取报告 JSON STRING |
| `H3DurationFromTTS` | H3 时长跟随 IndexTTS 原声音频 | ComfyUI AUDIO → H3 请求时长 FLOAT、音频报告 JSON STRING |

**安装后，工作流中的 3 个台词解析节点和 3 个时长计算节点都由这两种类型复用。** 不会改动 H3 模型本身，也不会自动安装其它 TTS/口型插件。

## 安装到有权限的 ComfyUI 环境

在可运行 ComfyUI 的机器上：

```bash
cd ComfyUI/custom_nodes
# 把下面的 URL 改成你发布后的实际 GitHub 仓库地址
git clone https://github.com/YOUR_USERNAME/ComfyUI-H3-IndexTTS-Auto.git
# 不需要额外 pip 依赖（使用 Python 标准库和 ComfyUI 的 AUDIO 格式）
```

重启 ComfyUI 服务，刷新网页，确认节点搜索中出现：

- `H3 → IndexTTS 自动提取台词/情绪`
- `H3 时长跟随 IndexTTS 原声音频`

**RunningHub 用户注意**：GitHub 仓库发布成功 ≠ RunningHub 云端已安装。只有 RunningHub 的相应运行环境允许**从 GitHub 安装自定义 Python 节点**，并能重新加载插件时，上述步骤才适用。若只是同步 JSON 或同步 GitHub 文件，不会使红色节点恢复。若云端不开放安装，需要请求平台上架/支持，或在本地运行预处理后提交不含这些节点的工作流。

## 上传到 GitHub（你自己发布）

1. 在 GitHub 新建仓库，建议名称 `ComfyUI-H3-IndexTTS-Auto`。
2. **先解压交付 ZIP**，将其中仓库文件（包括根目录 `__init__.py`）上传到新仓库的**根目录**。不要仅上传 ZIP 压缩包。
3. 仓库至少应看到根目录的 `__init__.py`、`h3_dialogue_parser.py`、`README.md`。
4. 把仓库链接交给支持 GitHub 插件安装的 ComfyUI/RunningHub 环境安装，然后重启/重载后再导入原工作流。

预期仓库结构：

```text
ComfyUI-H3-IndexTTS-Auto/
├── __init__.py                 # NODE_CLASS_MAPPINGS，注册两类节点
├── h3_dialogue_parser.py       # 规则解析实现
├── README.md
├── LICENSE
├── .gitignore
├── examples/
│   └── prompt_example.txt
├── tests/
│   └── test_nodes.py
└── .github/
    └── workflows/
        └── test.yml
```

## 工作流中的用法

- 把 H3 提示词同时连接到 `H3DialogueExtractToIndexTTS.h3_prompt` 和原 H3 视频节点的 Prompt。
- 台词节点输出的 `IndexTTS批量脚本文本` 连接到 `T8_IndexTTS25_DialogueScript.script`。
- TTS 生成的 AUDIO 连接到 `H3DurationFromTTS.audio`，其 `H3视频请求秒数` FLOAT 输出再接回原先工作流的“时长→帧数”逻辑。
- 最终视频如果要保留 **IndexTTS 原声**，`VHS_VideoCombine.audio` 应接 TTS 的原音轨而不是 H3 解码音频。
- 三角色 A/B/C 仍需独立上传参考音色（须有合法授权），并在 IndexTTS 的角色音色库中设置对应名称。

> 原工作流的连接与端口已有对应关系；**本仓库只提供缺失节点的后端代码**，不修改你原来的 JSON。

### H3 台词写法

```text
【镜头1】角色A用焦急质问的语气说：「你为什么现在才告诉我？」
```

或者带 H3 `<d>` 标签：

```text
[Shot 1] <Subject 1> (S1) angrily commands:
<d>[Chinese] 炎魔，还不乖乖束手就擒！</d>
```

输出为 IndexTTS T8 `batch` 格式：

```json
[
  {
    "role": "角色A",
    "text": "你为什么现在才告诉我？",
    "language": "ZH",
    "duration_factor": 1.0,
    "emotion": {"mode": "text", "text": "焦急质问", "strength": 0.82}
  }
]
```

### 人物名字别名

若 H3 文本使用实际人物名字，在节点可选 `role_aliases_json` 填：

```json
{"七七": "角色A", "林父": "角色B", "旁白": "角色C"}
```

这是在解析阶段把人物名映射到音色库的角色 ID。默认支持 `角色A/B/C`、`S1/S2/S3`、`<Subject 1/2/3>`。

### 重要参数

- `default_role`：镜头未写明确发言人时，默认角色 A/B/C。
- `strict=true`：没有发现显式对白时直接报错，避免乱配音。
- `allow_multi_role=false`：同镜头出现多个说话者则报错，减少口型错人风险。
- `min_seconds=4`：视频最短请求秒数。
- `tail_padding_seconds=0.4`：尾部自然停顿缓冲。
- `max_audio_seconds=15`：最大允许参考音频时长，超出报错而不是静默截断。

时长节点输出是 **秒数 FLOAT**，不是帧数；需经过原工作流的帧数计算节点，才能输入 H3 的 `length`。

## 功能边界

- 台词与情绪是基于规则和显式标记提取，**不是 LLM 自动理解整段剧情**。只识别显式对白；复杂的多人连续台词可能需要改写提示词或拆镜头。
- 本插件 **只做解析与时长计算**，不负责生成语音、视频、口型修改；这些依赖你现有的 H3、T8 IndexTTS 2.5、（如需）LatentSync 等插件和模型。
- TTS 音频喂给 H3 作为参考并不能保证嘴形逐音素对齐。即使做了原声替换也不能据此承诺精准唇形。
- 输出时长取 `max(min_seconds, TTS时长+缓冲)`，**没有把 H3 的实际生成帧数误写成时长节点输出**。
- 不会扫描、发送或上传你的音频、提示词。本插件无网络请求、无外部依赖、无模型下载功能。

## 本地验证

```bash
python -m unittest discover -s tests -v
```

测试包括：节点注册名与接口、角色台词提取、情绪提取、别名、无对白及多人对白错误处理、音频时长计算。**单元测试通过不等于已在 RunningHub 上实测成功**。

## 授权

MIT License，详见 `LICENSE`。
