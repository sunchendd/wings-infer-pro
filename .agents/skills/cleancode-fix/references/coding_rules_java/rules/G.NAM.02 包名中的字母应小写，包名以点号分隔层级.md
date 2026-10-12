# G.NAM.02 包名中的字母应小写，包名以点号分隔层级

- **规则ID**：9aa80571-fcae-47ef-932d-f16c2095134c
- **更新时间**：2026-04-07 04:00:05

---

**【问题级别】**

提示

**【描述】**

包名仅能使用小写字母、数字、下划线，下划线只能在一些特殊情况使用，如包名以数字开头或是java中保留关键字时，如:int_.example、com.example._123name。一层包路径可以是多个单词的简单连接（不用下划线连接）。

**【正确示例】**

```
##### 场景1
- 修复示例
  ```java
    package com.huaweicloud.views; // 【GOOD】Cloud小写-->cloud
    package com.huawei.mobilecontrol.views; // 【GOOD】去除mobile_control“_”-->mobilecontrol
  ```


```
**【错误示例】**

```
##### 场景1
- 错误示例
  ```java
    package com.huaweiCloud.views;  // 【不符合】Cloud没有小写，不符合规范
    package com.huawei.mobile_control.views; // 【不符合】mobile_control出现下划线“_”,不符合规范
  ```


```
**【修复建议】**

包名修改为仅使用小写字母、数字、下划线组成。
