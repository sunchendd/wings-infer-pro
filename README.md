# wings-infer-pro

Wings 推理平台 —— 把分层配置资产**可追溯、可复现**地解析成推理引擎(vLLM / vLLM-Ascend / SGLang)启动命令,并构建为可发布镜像。

## 仓库结构

| 目录 | 内容 |
|------|------|
| `wings_control/` | **主体代码** —— trace-first 配置解析框架(`src/wings_ctl`)+ SmartAccel 智能加速引擎(`src/wings_accel`)。用法 / 架构 / 设计原则详见 [`wings_control/README.md`](wings_control/README.md) |
| `build/` | 镜像构建脚手架 —— `build.sh` 依次构建 wings-accel + wings-control 子镜像,打包为可发布 zip;各子镜像的 Dockerfile / requirements 在此 |

## 快速开始

```bash
cd wings_control
pip install -e .

# dry-run 只打印引擎启动 argv,不落盘
python -m wings_ctl --model-name Qwen3.5-0.8B --hardware-info hardware_info.json --dry-run
```

给定「模型名 + 硬件信息 + 引擎版本」,产出 `start_command.sh` / `repro.sh` / `audit.json`(每个参数带完整来源链)。完整用法见 [`wings_control/README.md`](wings_control/README.md)。

## 构建镜像

```bash
# 构建 wings 推理镜像(wings-accel + wings-control → 可发布 zip;版本号可选)
bash build/build.sh 26.0.0
```

## 测试

```bash
cd wings_control && bash scripts/check.sh   # ruff lint + 红线守卫(无 if-engine) + pytest
```
