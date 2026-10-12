# G.COL.03 声明一个泛型类通过限定符限制可用的泛型类型

- **规则ID**：f8b5a8a7-686b-4792-a895-d381246211e9
- **更新时间**：2025-06-05 04:00:06

---

**【问题级别】**

一般

**【描述】**

Java的泛型可按PECS(Producer Extends，Consumer Super)原则来设计上界和下界类型。声明一个带

泛型的类或接口的时候，建议通过extends关键字限制可以用的泛型类型，避免接口使用者乱用。

**【正确示例】**

```
class GenericRight<S extends List, T extends Map> {
}

```
**【错误示例】**

```
class GenericWrong<T, S extends Collection> {
}

```
**【修复建议】**

泛型参数配合extends使用
