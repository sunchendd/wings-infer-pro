# G.FMT.11 用空格突出关键字和重要信息

- **规则ID**：e74c6236-d359-4c30-ae35-760b5e1db7f5
- **更新时间**：2026-04-07 04:10:04

---

**【问题级别】**

一般

**【描述】**

被强制转换的变量与类型之间不要加空格。

**【正确示例】**

```
##### 场景1：被强制转换的变量与类型之间存在空格
- 修复示例1：

```c
uint16_t number = ...
uint32_t newNumber = (uint32_t)number; // 符合
```

```
**【错误示例】**

```
##### 场景1：被强制转换的变量与类型之间存在空格
- 错误示例：

```c
uint16_t number = ...
uint32_t newNumber = (uint32_t) number; // 不符合：'(uint32_t)'和number之间存在空格
```

```
**【修复建议】**

移除被强制转换的变量与类型之间多余的空格。



建议通过格式化工具自动修复。例如[WeCode CodeCheck](https://marketplace.rnd.huawei.com/detail?identifier=wecodeCleanCodeCheck)中的[`FixBot`一键格式化](https://wecode-ex.rnd.huawei.com/Docs/85)。
