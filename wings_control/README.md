# wings-control

wings-control 根据模型配置、硬件信息和 MaaS/CLI 输入生成推理引擎启动脚本。每个最终参数都会记录来源，可通过 `audit.json` 查明“这个值为什么生效”。

## 快速开始

```bash
pip install -e .
pip install -e '.[dev]'

# 仅推演本次启动使用的环境变量和引擎命令，不写文件
python -m wings_ctl --model-name Qwen3.5-0.8B --hardware-info hardware_info.json --dry-run

# 生成启动脚本、复现脚本和审计文件
python -m wings_ctl --model-name Qwen3.5-0.8B --hardware-info hardware_info.json --output-dir ./out

python -m wings_ctl --help
```

引擎版本来自 `ENGINE_VERSION`。引擎名通过 `--engine` 或 `ENGINE` 指定，默认是 `vllm`。

开发和测试需要安装 `pip install -e '.[dev]'` 中的开发依赖，其中包括 pytest 和 Ruff。缺少它们时，`bash scripts/check.sh` 会失败。

## 输出

| 文件 | 用途 |
| --- | --- |
| `start_command.sh` | engine 容器实际执行的启动脚本。 |
| `repro.sh` | 用于审查和复现启动参数的脚本；执行前先查看内容。 |
| `audit.json` | 最终参数、来源配置和覆盖过程的结构化记录。 |
| `wings_start.log` | 面向人的单次启动摘要。 |

文件位置、日志差异、dry-run 行为和副作用见 [配置、产物与日志](docs/contracts/configuration-artifacts-and-logs.md)。

## 文档

[docs/README.md](docs/README.md) 是开发、MaaS 对接和运维文档入口。支持范围以 [支持边界](docs/capabilities/support-boundaries.md) 为准。

## 开发验证

```bash
bash scripts/check.sh
```

修改接口、产物或运行行为前，阅读 [开发与提交要求](docs/development/development-and-contribution.md)。
