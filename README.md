# wings-infer-pro

本仓库包含 Wings 推理镜像和启动控制组件。`wings_control/` 根据模型配置和运行输入生成可追溯的推理引擎启动脚本；`build/` 用于构建发布镜像。

## 目录

| 目录 | 用途 |
| --- | --- |
| [`wings_control/`](wings_control/) | wings-control 主代码和开发文档。使用方法、输出文件和开发入口见其 README。 |
| [`build/`](build/) | 镜像构建脚本、Dockerfile 和依赖定义。 |

## 构建

```bash
bash build/build.sh 26.0.0
```

## 验证

```bash
cd wings_control
bash scripts/check.sh
```

详细使用、接口和维护文档见 [`wings_control/README.md`](wings_control/README.md)。
