# G.DCL.06 使用字面量风格的声明

- **规则ID**：e6bda36e-c99e-4fdd-b50c-4f09d4f88f52
- **更新时间**：2026-04-07 04:35:01

---

**【问题级别】**

一般

**【描述】**

java采用公共安全组件执行命令

**【正确示例】**

```
##### 场景1：文件头注释没有首先包含“版权说明”
- 修复示例：文件头注释首先包含“版权说明”，然后包含其他可选内容

```go
/*
 * Copyright (c) Huawei Technologies Co., Ltd. 2021-2021. All rights reserved.
 * ...
 */

/* 其它说明：... */
```
##### 场景2：版权说明中公司和注释时间顺序错误
- 修复示例：文件头注释首先包含“版权说明”，版权说明的内容及格式必须和规范规定的一致，然后包含其他可选内容

```go
/*
 * Copyright (c) Huawei Technologies Co., Ltd. 2021-2021. All rights reserved.
 * ...
 */
```

```
**【错误示例】**

```
##### 场景1：文件头注释没有首先包含“版权说明”
- 错误示例：

```go
/* 其它说明：... */
/*
 * Copyright (c) Huawei Technologies Co., Ltd. 2021-2021. All rights reserved.
 * ...
 */
```
##### 场景2：版权说明中公司和注释时间顺序错误
- 错误示例：

```go
/*
 * 2021-2021. Copyright (c) Huawei Technologies Co., Ltd. All rights reserved.
 * ...
 */
```

```
**【修复建议】**

参考WIKI，使用CBB组件提供的公共方法执行命令/脚本。
