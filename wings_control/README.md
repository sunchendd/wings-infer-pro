# wings-control

**Trace-first 推理引擎启动配置解析器** —— 从分层 YAML 配置资产产出**可追溯、可复现**的推理引擎启动命令(vLLM / vLLM-Ascend / SGLang)。

给定「模型名 + 硬件信息 + 引擎版本」,wings-control 完成:定位配置资产 → 多层深合并(每个参数保留完整来源链)→ 策略层协调(数据并行 / 特性开关 / 多机注入)→ 渲染成引擎启动命令,并产出可审计、可手工复现的制品。

## 快速上手

```bash
pip install -e .

# dry-run 只打印 argv,不落盘
python -m wings_ctl --model-name Qwen3.5-0.8B --hardware-info hardware_info.json --dry-run

# 生成三件产物(start_command.sh / repro.sh / audit.json)到 output 目录
python -m wings_ctl --model-name Qwen3.5-0.8B --hardware-info hardware_info.json -o ./out

python -m wings_ctl --help
```

引擎版本由环境变量 `ENGINE_VERSION` 指定;引擎名由 `--engine`(或 `ENGINE` env,默认 `vllm`)。

## 输出产物

| 产物 | 用途 |
|------|------|
| `start_command.sh` | 引擎实际执行的启动脚本(system_setup 注释 + export env + 引擎命令) |
| `repro.sh` | 人工最小复现脚本(全展开,不依赖临时 shell 态) |
| `audit.json` | 结构化审计:最终命令 + **每个参数的来源链**(来自哪层/哪文件、被谁覆盖) |
| `wings_start.log` | 人读启动摘要(host 日志,`WINGS_START_LOG` 可覆盖路径) |

## 架构

单向流水线:`cli → resolve → validate → render → audit`(见 `pipeline.py`)。

```
src/wings_ctl/
├── cli.py            # CLI 入口:具名参数解析 / --dry-run / 引擎分流
├── pipeline.py       # 流水线编排:resolve → validate → render → audit
├── core/             # 数据模型(ResolvedConfig / TracedValue)+ trace-aware 深合并
├── loaders/          # 配置资产定位 + YAML 读取 + 模型/变体匹配
├── engines/          # 引擎版本解析 + adapter(engine_config → argv 查表渲染)
├── translators/      # 用户 CLI 参数 → 引擎 native 参数(param_mapping 查表)
├── strategy/         # 策略层:大策略(topology 判定)/ 小策略(DP 协调 / 特性覆盖 / 多机注入)
├── validators/       # 拉起前校验(supported_params warn-only)
├── rendering/        # 渲染 start_command.sh / repro.sh
├── audit/            # audit.json + wings_start.log 产出
├── hardware/         # 硬件信息解析
└── accel/            # wings-accel(智能加速)接入
```

> `proxy/` `rag_acc/` `common/` 是移植进来的 proxy 子系统,**不属于配置解析主流水线**。

## 设计原则(维护/评审须知)

- **Trace-first**:合并不返回裸 dict——每个最终参数都带来源链(final_value / final_layer / source_file / events),全程可追溯,落 `audit.json`。
- **不按引擎分支(no if-engine)**:引擎差异只走**查表 + 缺省直通**(`translators/param_mapping.py`、`engines/vllm_adapter.py` 命令规格表),配置解析主流水线内 `engine == "..."` 恒为 0。新增引擎 = 加一行表项 + 建配置子树,不改控制流。
- **warn-only 校验**:`supported_params` 校验只告警、**绝不删参、绝不阻塞启动**;清单缺失按 warn-skip 兜底。
- **静态并行模板**:TP/DP 作为静态模板从 model.yaml 读取;仅在用户显式 `--device-count` 时协调数据并行度(`DP = device_count // TP`,TP 永远静态读、不计算)。
- **逃生通道(设计预留,当前未落地)**:裸透传场景预留 `direct_vllm_serve`、mindie 等旧接口引擎预留在流水线入口整体旁路——均为设计方向,尚未实现。

## 配置资产定位

配置根目录(含 `engines/{engine}/.../models/*.yaml`、`supported_params.txt` 等)按优先级定位:

1. **显式参数** `--config-root`(所有 API 亦接受 `config_root: Path`)
2. **环境变量** `WINGS_CTL_CONFIG_ROOT`
3. **开发模式** `pip install -e .` 后从源码位置向上找含 `pyproject.toml` 的目录下的 `config/`

> 输出目录(三件产物)另按 `--output-dir` → `/shared-volume`(sidecar)→ 当前目录 定位。

## 测试

```bash
# 完整门禁:ruff lint + 红线守卫(无 if-engine) + pytest
bash scripts/check.sh

# 仅单测
PYTHONPATH=src python -m pytest -q
```

## 引擎与拓扑支持

| 引擎 | standalone(单机) | multi_node(分布式多机) |
|------|:---:|:---:|
| vLLM / vLLM-Ascend | ✅ | ✅ |
| SGLang | ✅ | 规划中 |

> PD 分离(prefill / decode)拓扑规划中,尚未落地。

代码本身以中文 docstring + 关键分支注释自解释;新增函数/测试强制写 docstring(功能 / 入参出参 / 异常 / 关键分支),风格对齐 `audit/emitter.py`、`pipeline.py`。
