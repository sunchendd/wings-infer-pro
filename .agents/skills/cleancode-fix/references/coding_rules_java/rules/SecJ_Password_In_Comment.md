# SecJ_Password_In_Comment

- **规则ID**：f9d05d2e-a176-4124-966b-8310488a7e8d
- **更新时间**：2026-04-07 04:00:03

---

**【问题级别】**

一般

**【描述】**

注释中不能出现密码相关的描述

**【正确示例】**

```
```java

// 【GOOD】不要在注释中硬编码密码

public class Example {

// Some comment about functionality

}

```

```
**【错误示例】**

```
```java



public class Example {

// 【不符合】以明文形式在注释中存储密码会危及系统安全

// Default password for database connection is "root"

}

```

```
**【修复建议】**

避免在注释中以明文形式存储密码或密码详细信息。应确保注释中不包含任何敏感信息，尤其是与密码相关的信息
