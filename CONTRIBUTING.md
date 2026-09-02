# 贡献代码

本仓库中的重构版 wings-control 主流程位于 `wings_control/src/wings_ctl/`。

修改代码前，先阅读[文档入口](wings_control/docs/README.md)，再阅读与本次改动相关的接口、能力、运维或策略文档。

## 提交前

执行统一验证入口：

~~~bash
cd wings_control
bash scripts/check.sh
~~~

命令未以 `check OK` 结束时，不要提交或合并。该脚本是本地开发和 CI 的基础检查，不能代替真机、性能、稳定性、升级或回退验证。

仔细检查最终改动：

~~~bash
git diff --stat
git diff
git status --short --branch
~~~

改动应保持聚焦。除非已获明确批准并更新文档，否则必须保持公共 CLI、环境变量、YAML、trace、audit、argv、脚本、日志、错误、退出码和输出文件的兼容性。新增行为需要测试；不要只为掩盖回归而更新 golden 文件。

## 提交信息

提交信息使用以下项目格式：

~~~text
[xfusion] <short summary>

Offering: <version or scope>
CVE:
Reference:
Type: <requirement | bugfix | refactor | documentation>
DTS/US: <id or N/A>
reason: <reason and impact>
Signed-off-by: <name> <email>
~~~

完整的开发、验证、安全评审、责任边界和文档要求见[开发、验证与提交要求](wings_control/docs/development/development-and-contribution.md)。
