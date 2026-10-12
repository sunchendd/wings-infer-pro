# G.TYP.11 使用展开语法 … 或concat复制数组

- **规则ID**：7c2c7a5a-6177-4cf6-9b2b-ba86e4d5a1a1
- **更新时间**：2025-06-05 04:25:02

---

**【问题级别】**

提示

**【描述】**

展开语法可以通过减少赋值语句的使用，或者减少通过下标访问数组或对象的方式，使代码更加简洁优雅，可读性更佳。

**【正确示例】**

```
const itemsCopy = [...items];

```
**【错误示例】**

```
const len = items.length;
const itemsCopy = [];
// 复制数组
for (let i = 0; i < len; i++) {
  itemsCopy[i] = items[i];
}

```
**【修复建议】**

使用展开语法 ... 复制数组
