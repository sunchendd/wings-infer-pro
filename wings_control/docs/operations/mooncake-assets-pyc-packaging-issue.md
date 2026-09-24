# Mooncake 脚本兜底资产被镜像加密步骤破坏(.py → .pyc)问题分析

> 2026-09-23 排障记录。现象:分布式 KV 开启后,engine 容器内 `start_mooncake_store.sh`
> 启动失败,`/shared-volume/mooncake/` 下只有 `mooncake_store.pyc`,没有
> `mooncake_store.py`。本文记录根因、影响范围、修复方案与验证方法。

## 现象

engine Pod(如 `serving-rn-40-0-*`)的 `/var/log/wings/mooncake_store_setup.log`
末尾出现:

```
python3: can't open file '/shared-volume/mooncake/mooncake_store.py': [Errno 2] No such file or directory
```

同时:

- pod 内 `ls /opt/wings-control/src/wings_accel/distributed_offload/mooncake`
  显示的是 `mooncake_store.pyc`,而仓库源码中是 `mooncake_store.py`;
- 容器内无任何 mooncake 进程存活;
- 直接执行 `python3 mooncake_store.pyc` 报
  `RuntimeError: Bad magic number in .pyc file`。

## 根因

### 1. 镜像构建的"代码加密"步骤无差别处理所有 .py

`build/wings-control/Dockerfile` 末尾执行 `build/compile_wings.sh`:

```bash
python -m compileall -b -f .          # /opt/wings-control 下所有 .py → 同目录 .pyc
find . -name "*.py" -exec rm -f {} +  # 删除所有 .py
```

`mooncake_store.py` 位于 `/opt/wings-control/src/wings_accel/distributed_offload/mooncake/`
下,被打成 `mooncake_store.pyc` 并删除 `.py`。仓库是源码(永远是 `.py`),镜像是
加密产物(只有 `.pyc`)——这就是"pod 里看到 .pyc、代码里是 .py"的直接原因。

### 2. mooncake_store.py 是跨容器运行时资产,不能被加密

其它 `.pyc` 模块都在 wings-control 容器内、由编译它们的同一个 Python 3.10
`import`,没有问题。`mooncake_store.py` 不同:

- 运行期 `script_builder._install_mooncake_script_assets()` 把整个 mooncake 资产
  目录拷到 `${SHARED_VOLUME_PATH}/mooncake/`;
- `start_mooncake_store.sh` 以 `python3 ${CUR_PATH}/mooncake_store.py` 方式在
  **engine 容器**(Python 3.12,与 wings-control 的 3.10 不同)执行它。

因此有两个独立的失败模式:

1. `.py` 被加密步骤删除 → `python3 ...mooncake_store.py` 文件不存在(实际命中的);
2. 即使改脚本去跑 `.pyc` → 3.10 编译的字节码在 3.12 下 `bad magic number`
   (已在 pod 内实测确认)。

仓库已有同类先例:`log_analyzer` 当年同样踩坑,解法是构建期在加密**之前**单独
`COPY` 到 `/opt/log_analyzer`(`Dockerfile` 内有注释说明),运行时再由
`wings_start.sh` 拷到共享卷。本问题是同一模式在新资产上的复发。

## 影响范围

| 资产 | 是否受影响 | 说明 |
| --- | --- | --- |
| `mooncake_store.py` | **是** | engine 容器内以 `python3 xxx.py` 执行;唯一被加密破坏的资产 |
| `start_mooncake_store.sh` / `start_mooncake_master.sh` / `creat_mooncake_json.sh` / `start_mooncake_store_ascend.sh` | 否 | shell 脚本,加密步骤只处理 `.py` |
| `env.yaml` | 否 | 非 `.py`;但为单一来源一并迁到新资产目录 |
| master 侧(`mooncake_master` 二进制) | 否 | 由 `start_mooncake_master.sh` 拉起镜像内二进制,不涉及 `.py` |
| wings-control 自身模块 `.pyc` | 否 | 同容器同 Python import |

## 修复方案(log_analyzer 同模式)

### 构建期:`build/wings-control/Dockerfile`

在 `compile_wings.sh` 加密步骤**之前**新增:

```dockerfile
COPY ./wings_control/src/wings_accel/distributed_offload/mooncake /opt/mooncake_assets
```

`/opt/mooncake_assets` 中的 `.py` 不经过加密,以源码形态随镜像交付。

### 运行期:`src/wings_ctl/rendering/script_builder.py`

新增 `_resolve_mooncake_assets_dir()`,两处读取点统一从资产目录取源:

- `_install_mooncake_script_assets()`:源目录改为
  `_resolve_mooncake_assets_dir()`,拷贝到共享卷的逻辑不变;
- `_render_mooncake_client_env()`:`env.yaml` 改从资产目录读取。

解析优先级:

1. `MOONCAKE_ASSETS_PATH` 环境变量(本地/测试用,可指回仓库源目录);
2. 镜像默认 `/opt/mooncake_assets`;
3. 仓库内 `src/wings_accel/distributed_offload/mooncake/`(仅本地/测试回退,
   回退时打 WARN)。

**fail-fast 守卫**:若解析出的目录只有 `mooncake_store.pyc` 没有
`mooncake_store.py`(说明镜像用旧 Dockerfile 构建、资产被加密吃掉),抛
`ValueError`,阻止 `.pyc` 被静默拷到共享卷、把故障推迟到引擎启动期。

### 修复后链路

```
构建期:  Dockerfile COPY mooncake/ → /opt/mooncake_assets      # .py 保留,不加密
运行期:  wings-control 生成 start_command.sh 时(分布式 KV 开启且需脚本兜底)
            _install_mooncake_script_assets()
            /opt/mooncake_assets/* → ${SHARED_VOLUME_PATH}/mooncake/   # 每 pod 一份
            + 渲染 client.env / master.env
执行期:  engine 容器 pre-serve 段:
            source client.env → bash creat_mooncake_json.sh
            → bash start_mooncake_store.sh &
            → python3 mooncake_store.py                           # ✅ 可执行
          mooncake-master 容器(IS_MOONCAKE_MASTER=true)只起 mooncake_master 后退出
```

## 验证

- 单测:`tests/unit/test_accel_seam.py`
  - `test_build_scripts_installs_mooncake_script_assets`:资产完整落盘,含
    `mooncake_store.py`;
  - `test_install_mooncake_script_assets_fails_fast_on_pyc_only_assets`:只有
    `.pyc` 的资产源必须 fail-fast,且不产生共享卷目录。
- 端到端(本地,tjl-ctrl):复刻 MaaS 参数跑 `python -m wings_ctl`,确认
  `${SHARED_VOLUME_PATH}/mooncake/mooncake_store.py` 以 `.py` 落盘,
  `start_command.sh` 含 install.py 段、`IS_MOONCAKE_MASTER` 分支与 pre-serve 段。
- 重建镜像后 pod 内检查点:
  1. `ls /opt/mooncake_assets/mooncake_store.py` 存在;
  2. `ls /shared-volume/mooncake/mooncake_store.py` 存在;
  3. `mooncake_store_setup.log` 无 `can't open file` / `Bad magic number`;
  4. engine 容器内存在 `python3 .../mooncake_store.py` 进程。

## 注意事项

- 旧镜像(未带 `/opt/mooncake_assets`)+ 新代码:解析回退到
  `/opt/wings-control/src/.../mooncake/`,该目录只有 `.pyc` → fail-fast 报
  "rebuild the wings-control image",属预期防线;
- 若后续往 mooncake 资产目录新增**任何** `.py`(供 engine 容器执行),同样受
  本机制保护(资产目录整体不加密),无需再改构建;
- 资产目录内不要放 wings-control 自身要 import 的模块——那里只有 engine 侧
  运行时资产;wings-control 侧逻辑继续放 `src/wings_accel/distributed_offload.py`。
