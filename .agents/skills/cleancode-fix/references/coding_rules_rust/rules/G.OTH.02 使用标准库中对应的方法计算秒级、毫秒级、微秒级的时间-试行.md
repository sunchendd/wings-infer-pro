# G.OTH.02 使用标准库中对应的方法计算秒级、毫秒级、微秒级的时间-试行

- **规则ID**：a6ff655c-971a-4610-bc02-cdde83f4b2cc
- **更新时间**：2025-06-05 04:40:04

---

**【问题级别】**

一般

**【描述】**



**【正确示例】**

```
# use std::time::Duration;
let dur = Duration::new(5, 0);
// Good
let _micros = dur.subsec_micros(); // 得到微秒
let _millis = dur.subsec_millis(); // 得到毫秒

```
**【错误示例】**

```
# use std::time::Duration;
let dur = Duration::new(5, 0);
// Bad
let _micros = dur.subsec_nanos() / 1_000;      // 用纳秒 计算
let _millis = dur.subsec_nanos() / 1_000_000;  // 用纳秒 计算

```
**【修复建议】**
