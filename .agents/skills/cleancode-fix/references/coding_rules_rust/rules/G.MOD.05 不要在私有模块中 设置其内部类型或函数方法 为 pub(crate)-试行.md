# G.MOD.05 不要在私有模块中 设置其内部类型或函数方法 为 pub(crate)-试行

- **规则ID**：8071ca9d-4651-411d-8b65-dd69522bef24
- **更新时间**：2025-06-05 04:40:03

---

**【问题级别】**

提示

**【描述】**

如果在私有模块中设置 pub(crate) 可能会让使用者产生误解。建议用 pub 代替。

**【正确示例】**

```
mod internal {
    pub fn internal_fn() { }
}

```
**【错误示例】**

```
mod internal {
    pub(crate) fn internal_fn() { }
}

```
**【修复建议】**
