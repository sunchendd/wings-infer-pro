# G.EXP.04 在混合使用不同的操作符时，采用括号明确运算的优先级

- **规则ID**：e37a72e1-8109-449b-9e3c-c5679a8a4085
- **更新时间**：2026-04-07 04:25:01

---

**【问题级别】**

提示

**【描述】**

在混合使用不同的操作符中，使用括号说明优先级，以方便阅读和理解。即使代码优先级正确，也应该考虑到后续阅读或者修改这段代码的其他人员的方便，最好加上括号。

**【正确示例】**

```
##### 场景1：操作符
- 修复示例：采用括号明确运算的优先级。
```javascript
const foo = bar || num || char;
const foo = bar && num && char;
const foo = (bar && num < 0) || char > 0 || dog + 1 === 0;
const foo = bar && (num < 0 || char > 0 || dog + 1 === 0);
const foo = bar + (num * char);
const foo = (bar + num) * char;

```
##### 场景2：混合使用自增、自减运算
- 修复示例：
```javascript
let num = x++;
console.log(x + num);
```

```
**【错误示例】**

```
##### 场景1：操作符
- 错误示例：没有采用括号来明确运算的优先级，可读性不好。

```javascript
const foo = age && bar < 0 || char > 0 || dog + 1 === 0;
const foo = age + bar * char;

```
##### 场景2：混合使用自增、自减运算
- 错误示例：在表达式中与其他运算混合使用自增、自减运算，因为自增自减是存在副作用，这会带来意外的结果。

```javascript
console.log(x + x++);
```

```
**【修复建议】**

在混合使用不同的操作符时，采用括号明确运算的优先级。
