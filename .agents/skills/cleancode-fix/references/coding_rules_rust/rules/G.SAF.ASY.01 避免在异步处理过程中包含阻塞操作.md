# G.SAF.ASY.01 避免在异步处理过程中包含阻塞操作

- **规则ID**：42f711c2-cf98-4cc0-a48b-c64912902dce
- **更新时间**：2026-04-07 04:40:01

---

**【问题级别】**

提示

**【描述】**

避免在异步处理过程中包含阻塞操作

**【正确示例】**

```
```
use std::time::Duration;
pub async fn foo() {
    tokio::time::sleep(Duration::from_secs(5));
}
```

```
**【错误示例】**

```
```
use std::time::Duration;
pub async fn foo() {
    std::thread::sleep(Duration::from_secs(5));
}
```

```
**【修复建议】**

避免在异步处理过程中包含阻塞操作
