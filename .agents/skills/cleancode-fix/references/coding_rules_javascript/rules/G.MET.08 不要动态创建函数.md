# G.MET.08 不要动态创建函数

- **规则ID**：56992ac7-63f3-4120-bfce-c32ee0d35e47
- **更新时间**：2026-04-07 04:25:01

---

**【问题级别】**

一般

**【描述】**

采用函数声明、Function构造函数和函数表达式定义函数时，它们都是Function对象的实例，并将继承Function对象所有默认或自定义的方法和属性。以函数构造器创建函数的方式类似于函数eval(),可以接受任何字符串形式作为它的函数体，这就会有安全漏洞的风险。

**【正确示例】**

```
##### 场景1：创建函数
- 修复示例：使用函数声明或函数表达式的方式来创建函数

```javascript
// 函数声明
function add(a,b) {
  return a + b;
}
// 函数表达式
let add = function(a,b) {
  return a + b;
}
```

```
**【错误示例】**

```
##### 场景1：创建函数
- 错误示例：使用new Function构造函数

```javascript
let add = new Function('a','b','return a + b');
// Function构造函数也可以只有一个参数，该参数可以为任意的字符串:
let dd = new Function('alert("hello")');
```

```
**【修复建议】**

使用函数声明或函数表达式的方式来创建函数。
