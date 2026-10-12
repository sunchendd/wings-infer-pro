# G.TYP.ENM.03 在使用类似 C 语言的枚举写法且使用repr(isize/usize) 布局时要注意 32位架构上截断的问题-试行

- **规则ID**：6377bd1c-5426-4c3f-b6d9-10a60a2c842e
- **更新时间**：2025-06-05 04:40:02

---

**【问题级别】**

严重

**【描述】**

在使用类似 C 语言的枚举写法且使用repr(isize/usize) 布局时，在32位架构上会截断变体值，但在64位上工作正常。



但是没有这种风险的时候，可以正常使用。

**【正确示例】**

```
#![allow(clippy::enum_clike_unportable_variant)]
#[repr(isize)]
pub enum ZBarColor {
    ZBarSpace = 0,
    ZBarBar   = 1,
}
// 或者，没有指定 repr(isize/usize)
#[allow(clippy::enum_clike_unportable_variant)]
pub(crate) enum PropertyType {
    ActionItemSchemaVersion = 0x0C003473,
    ActionItemStatus = 0x10003470,
    ActionItemType = 0x10003463,
    Author = 0x1C001D75,
}

```
**【错误示例】**

```
#[cfg(target_pointer_width = "64")]
#[repr(usize)]
enum NonPortable {
    X = 0x1_0000_0000,
    Y = 0,
}

```
**【修复建议】**
