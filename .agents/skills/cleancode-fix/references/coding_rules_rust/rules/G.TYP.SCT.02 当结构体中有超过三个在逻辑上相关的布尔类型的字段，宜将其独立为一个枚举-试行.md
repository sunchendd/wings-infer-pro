# G.TYP.SCT.02 当结构体中有超过三个在逻辑上相关的布尔类型的字段，宜将其独立为一个枚举-试行

- **规则ID**：3bfbda9c-5dc8-469e-9685-8fc20132c908
- **更新时间**：2025-06-05 04:40:02

---

**【问题级别】**

提示

**【描述】**

这样有助于提升 代码可读性和 API 。

**【正确示例】**

```
enum S {
    Pending,
    Processing,
    Finished,
}

```
**【错误示例】**

```
struct S {
    is_pending: bool,
    is_processing: bool,
    is_finished: bool,
}

```
**【修复建议】**
