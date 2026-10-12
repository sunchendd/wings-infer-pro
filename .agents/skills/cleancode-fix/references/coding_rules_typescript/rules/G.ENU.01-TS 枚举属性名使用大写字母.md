# G.ENU.01-TS 枚举属性名使用大写字母

- **规则ID**：b43fcc03-7fe3-42f1-8007-e37ef52406de
- **更新时间**：2025-06-05 04:35:03

---

**【问题级别】**

提示

**【描述】**

建议统一风格，推荐枚举属性名使用大写字母，单词之间使用下划线。

**【正确示例】**

```
// 枚举属性名使用大写字母，单词之间使用下划线
enum Status {
  OPEN_TAB =  'Open',
  CLOSE_TAB = 'Close',
}
enum Color {
  RED = 'Red',
  GREEN = 'Green',
  BLUE = 'Blue',
}

```
**【错误示例】**

```
// 枚举属性名使用大驼峰
enum Status {
  OpenTab = 'Open',
  CloseTab = 'Close',
}
enum Color {
  Red = 'Red',
  Green = 'Green',
  Blue = 'Blue',
}

```
**【修复建议】**

枚举属性名使用大写字母
