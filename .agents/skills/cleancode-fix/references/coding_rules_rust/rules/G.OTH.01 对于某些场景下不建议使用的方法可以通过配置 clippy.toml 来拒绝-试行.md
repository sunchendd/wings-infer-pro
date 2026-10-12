# G.OTH.01 对于某些场景下不建议使用的方法可以通过配置 clippy.toml 来拒绝-试行

- **规则ID**：f9a1962c-9308-47dd-a157-40e0c508e340
- **更新时间**：2025-06-05 04:40:04

---

**【问题级别】**

提示

**【描述】**

有些场合可能需要拒绝使用一些容易出错的方法或函数，可以在 clippy.toml 中通过配置 disallowed_method 来满足这个需求。

**【正确示例】**

```
// Example code which does not raise clippy warning
let mut xs = Vec::new(); // Vec::new is _not_ disallowed in the

```
**【错误示例】**

```
// Example code where clippy issues a warning
let xs = vec![1, 2, 3, 4];
xs.leak(); // Vec::leak is disallowed in the config.
// The diagnostic contains the message "no leaking memory".
let _now = Instant::now(); // Instant::now is disallowed in the config.
let _box = Box::new(3); // Box::new is disallowed in the config.

```
**【修复建议】**
