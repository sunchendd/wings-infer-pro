# G.CTL.04 含else if分支的条件判断应在最后加一个else分支

- **规则ID**：e58c7164-06b4-44eb-a3cf-5c0e0ef2c680
- **更新时间**：2025-06-05 04:25:01

---

**【问题级别】**

提示

**【描述】**

多个else if条件组合的判断逻辑，往往会出现开发人员忽略的分支，需要设置else默认操作(类似中switch-case语句要有default分支) 。

**【正确示例】**

```
if (employee.age > 65) {
  ...
} else if (employee.age < 65) {
  ...
} else if (employee.age === 65) {
  ...
} else {
  ...
}

```
**【错误示例】**

```
if (employee.age > 65) {
  ...
} else if (employee.age < 65) {
  ...
} else if (employee.age === 65) {
  ...
}

```
**【修复建议】**

if-else if（有多个 else if）类型的条件判断，最后应包含一个 else分支
