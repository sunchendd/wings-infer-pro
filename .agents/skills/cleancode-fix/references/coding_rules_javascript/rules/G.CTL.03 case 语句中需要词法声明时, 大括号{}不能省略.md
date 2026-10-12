# G.CTL.03 case 语句中需要词法声明时, 大括号{}不能省略

- **规则ID**：20a8c4a5-6567-4286-975b-66dd55b89e95
- **更新时间**：2026-04-07 04:25:01

---

**【问题级别】**

一般

**【描述】**

词法声明在整个 switch 语句块中是可见的，但是它只有在运行到它定义的 case 语句时，才会进行初始化操作。为了保证词法声明语句只在当前 case 语句中有效，应该将语句包裹在块中。

**【正确示例】**

```
##### 场景1：case 语句词法声明时大括号{}
- 修复示例：case 语句中词法声明时, 大括号{}不省略。

```javascript
// switch语句之外的声明是有效的
const num = 0;
switch (foo) {
  // 下面的case子句使用括号包装成块
  case 1: {
    let age = 1;
    break;
  }
  case 2: {
    const bar = 2;
    break;
  }
  default: {
    class ClassA {}
  }
}
```

```
**【错误示例】**

```
##### 场景1：case 语句词法声明时大括号{}
- 错误示例：case 语句中词法声明时, 大括号{}省略

```javascript
switch (foo) {
  case 1:
    let age = 1;
    break;
  case 2:
    const bar = 2;
    break;
  default:
    class ClassA {}
}
```

```
**【修复建议】**

case 语句中需要词法声明时, 大括号{}不能省略。
