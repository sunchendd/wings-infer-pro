# G.MOD.04 一个项目中应该避免使用不同的模块布局风格-试行

- **规则ID**：51c5a4dc-bb34-4220-8610-c40e47485945
- **更新时间**：2025-06-05 04:40:03

---

**【问题级别】**

提示

**【描述】**

Rust 支持两种模块布局，文件夹内使用 mod.rs 或者是使用跟文件夹同名的文件名，来组织模块。



但是项目里如果混合这两种模块布局，是比较让人困惑的，最好统一为同一种风格。



上面两种lint，选择其中一种用于检查是否存在不同的模块布局。

**【正确示例】**

```
// 使用 `self_named_module_files`，允许下面模块布局
src/
  stuff/
    stuff_files.rs
    mod.rs
  lib.rs
// 使用 `mod_module_files`，允许下面模块布局
src/
  stuff/
    stuff_files.rs
  stuff.rs
  lib.rs

```
**【错误示例】**

```
// 使用 `self_named_module_files`，不允许下面模块布局
src/
  stuff/
    stuff_files.rs
  stuff.rs
  lib.rs
// 使用 `mod_module_files`，不允许下面模块布局
src/
  stuff/
    stuff_files.rs
    mod.rs
  lib.rs

```
**【修复建议】**
