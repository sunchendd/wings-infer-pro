# License 使用指导

本目录承载 AIPerf License 交付的宿主机查询工具 `aiperf.py`（模块化入口，
命令注册于 `commands.py`）：`license show` 读取配置指定目录下的唯一证书与
宿主机 ESN 并打印，不验签、不依赖 docker。验签由 wings-control 容器在
启动时完成。License 挂载已直接内置 `example/docker-compose-{gpu,npu}/
docker-compose.yaml`，部署无需叠加任何 override 文件。

## 部署全流程

### 前置条件

| 项 | 要求 |
|---|---|
| wings-control 镜像 | `IMAGE_CONTROL` 指向 `-license` 后缀 tag，由 `build/build.sh --enable-license` 产出（AIPerf 交付只有带 License 的这一套）；正式版本镜像是 `fusionregistry:5000/wings-control:26.0.2-license`（含 License 门禁） |
| License 证书 | 按机器 ESN 签发的唯一 `*.xml`，放入宿主机 `/etc/aiperf/license/`（目录放且只放一份） |
| Docker Compose | V2（`docker compose`）或 V1（`docker-compose`）均可，命令示例见下 |

### 步骤

```bash
# 1. 导入镜像(以 x86_64 为例;arm 将 x86_64 换成 aarch64)
unzip AIPerf_SDK_example_<版本>_<arch>.zip -d aiperf-sdk
cd aiperf-sdk
docker load -i Wings_accel_<版本>_<arch>.tar
docker load -i Wings_control_<版本>_<arch>.tar   # 交付的 control 已是 -license tag

# 2. (可选)核对机器 ESN,向签发方申请对应证书
python3 license/aiperf.py license show --esn-only
#    或在证书就位后查看证书内容与 ESN:
python3 license/aiperf.py license show

# 3. 放置证书(宿主机,只放一份 XML)
sudo mkdir -p /etc/aiperf/license
sudo cp <签发的证书>.xml /etc/aiperf/license/

# 4. 修改 env
cd example/docker-compose-npu        # GPU 用 docker-compose-gpu
cp env.example env
vim env
#    必改:IMAGE_ACCEL / IMAGE_CONTROL(正式版本 fusionregistry:5000/wings-control:26.0.2-license) /
#         IMAGE_ENGINE / MODEL_NAME / MODEL_PATH / XPU_VISIBLE_DEVICES / 端口
#    注意:License 版 DEVICE_COUNT 必填(缺失/非正整数启动即被 2016 拦截)

# 5. 加载 env 并启动(License 挂载已内置 compose,无需叠加 override)
set -a; source env; set +a
docker compose -f docker-compose.yaml up -d

# 6. 观察启动(control 完成验签并生成启动脚本,engine 拉起推理)
docker compose -f docker-compose.yaml logs -f aiperf-control
docker compose -f docker-compose.yaml logs -f aiperf-engine
```

### 常见问题

**`unknown flag: --env-file`**：`--env-file` 在部分 Docker/Compose 版本与
位置组合下不被识别（它属于 compose 插件的顶层选项，不是 `up` 的选项，
旧版 V1 甚至不支持）。统一改用环境变量加载，语义等价且全版本兼容：

```bash
set -a; source env; set +a     # set -a 让 source 的变量自动 export 给 compose 插值
docker compose -f docker-compose.yaml up -d
```

注意每次开新 shell 都要重新 `source env`；`env` 文件本身不被 compose 读取，
插值来自导出的环境变量。

**机器上只有独立版 `docker-compose`（无 `docker compose` 插件）**：把文档
命令中的 `docker compose` 换成 `docker-compose` 即可，参数与行为一致；
`set -a; source env; set +a` 的加载方式在两种形态下都适用。

**启动即失败、日志含 `[AIPERF-LICENSE] code=...`**：按 code 对照处理
（完整表见 `wings_control/docs/features/aiperf-license-design.md` §6）：

| code | 含义 | 处理 |
|---|---|---|
| 2001 | 证书目录为空 | 确认 `/etc/aiperf/license/` 有唯一 XML |
| 2002 | 证书多于一份 | 目录只保留一份 |
| 2009 | ESN 不匹配 | 证书与机器不对应，用 `license show --esn-only` 核对后重签 |
| 2016 | `DEVICE_COUNT` 缺失或不是正整数 | env 里显式设置 `DEVICE_COUNT`（正整数，910C 单芯多卡按物理卡数，如 8 卡传 16） |
| 2017 | 超出授权卡数 | 降低 `DEVICE_COUNT` 或扩容证书 |
| 2011 | checker 缺失 | `IMAGE_CONTROL` 的 tag/镜像不对,换 `-license` 后缀 tag（正式版本 `fusionregistry:5000/wings-control:26.0.2-license`） |

**日志出现 `code=2005 status=expired`（服务未中断）**：这不是启动失败——证书已过
宽限期，按告警放行，不拦截启动与重拉，已运行服务的推理不受影响；把续期证书放入
`/etc/aiperf/license/` 后 `docker-compose down && up -d` 重拉即恢复
`status=valid`。过期期间仅停止模型升级等人工服务，卡数配额校验（2017）照常生效。

**改了 env 不生效**：compose 变量插值发生在 `up` 时。改完 env 需重新
`set -a; source env; set +a` 后再 `up -d` 重建容器。

## 查询工具使用

## 使用

```bash
python3 aiperf.py license show          # 证书路径 + 内容 + ESN
python3 aiperf.py license show --esn-only  # 仅 ESN(脚本友好)
```

## 配置

配置文件 `aiperf.json`，加载顺序（后者覆盖前者）：

1. 内置默认（`license_dir=/etc/aiperf/license`、`board_serial_path=/sys/class/dmi/id/board_serial`）
2. `/etc/aiperf/aiperf.json`（系统级）
3. `./aiperf.json`（本地）
4. `--config <path>`（显式指定，缺失即报错）

```json
{
  "license_dir": "/etc/aiperf/license",
  "board_serial_path": "/sys/class/dmi/id/board_serial"
}
```

未知字段进 `extra` 保留，不报错（向前兼容）。

## 退出码

| 码 | 含义 |
|---|---|
| 0 | 成功 |
| 1 | 用法错误（未知命令/参数） |
| 2 | license 查询失败（证书缺失/多份、ESN 非法） |
| 3 | 配置文件缺失或不可解析 |
| 4 | 未预期运行期错误 |

## 模块结构

| 文件 | 职责 |
|---|---|
| `aiperf.py` | 总入口：解析全局参数、查表分发、错误转退出码 |
| `commands.py` | 子命令注册表（命令集唯一事实来源） |
| `cmd_license.py` | `license` 子命令实现 |
| `license_info.py` | 查询结果数据结构 |
| `config.py` | `aiperf.json` 分层加载 |
| `errors.py` | 错误体系与退出码契约 |

## License 状态查询（状态接口）

门禁放行后，control 容器内的告警守护进程每 8 小时复验一次证书时间有效性，
把最近一次校验结果落盘共享卷，由 health 服务开放 HTTP 查询（接口只反映
最近一次巡检结果，不触发校验）：

```bash
curl http://127.0.0.1:19001/license_status                     # 控制节点 host 网络（HEALTH_PORT）
docker exec aiperf-engine-<suffix> cat /shared-volume/license_status.json
```

返回 JSON 包含 `status`、`code`（`valid` 无专属错误码，回落 2000）、
`checked_at`（UTC ISO-8601 秒级）、`alarm_interval_seconds`（28800）、
`license_id`、`valid_until`、`grace_until`、`authorized_device_count`；
空值(null)字段不输出（`hint` 为空串时仍输出，属已知行为）。接口与状态
文件同源同构，`checked_at` 对应同一轮巡检。

端口定制：License 状态查询不独立占端口，随 `HEALTH_PORT`（默认 19001）
走；在 env 中设置 `HEALTH_PORT=19002` 并重新拉起，`/license_status` 与
`/health` 同端口经路径区分路由、互不影响。字段口径与校验规则详见
`wings_control/docs/features/aiperf-license-design.md` §5、§6。

## 部署（compose）

example（`example/docker-compose-{gpu,npu}/docker-compose.yaml`）已直接内置
License 挂载：给 `aiperf-control` 挂载四个只读目录——证书目录
`/etc/aiperf/license`、SafeTime 状态目录、`docker.sock`（已用卡数自查）与
DMI（ESN 防伪）。部署与普通流程完全一致，无需叠加任何 override（完整流程
见上文「部署全流程」，此处为最小命令）：

```bash
cd example/docker-compose-npu   # 或 docker-compose-gpu
set -a; source env; set +a
docker compose -f docker-compose.yaml up -d
```

前提：`IMAGE_CONTROL` 使用 `-license` 后缀 tag 的 wings-control 镜像
（正式版本 `fusionregistry:5000/wings-control:26.0.2-license`）；若换用
历史无门禁镜像，License 校验直通放行，不会拦截启动。

## 打包边界

本目录随 `AIPerf_SDK_example.zip` 统一分发（见 `build/build.sh` 的
`package_ai_perf`）。AIPerf 示例交付只有带 License 的一套：`--ai_perf` 须与
`--enable-license` 组合使用，不存在不携带本目录的非 License 示例包；
wings-control 镜像侧仍保留无门禁构建（`build/build.sh` 默认），仅供内部
使用，不进入 AIPerf 交付。
