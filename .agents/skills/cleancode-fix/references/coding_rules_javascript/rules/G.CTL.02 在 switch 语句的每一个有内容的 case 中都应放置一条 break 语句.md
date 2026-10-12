# G.CTL.02 在 switch 语句的每一个有内容的 case 中都应放置一条 break 语句

- **规则ID**：a04e4615-08e9-4d88-8e8b-bb7b81b36071
- **更新时间**：2026-04-07 04:25:01

---

**【问题级别】**

一般

**【描述】**

在 switch 语句的每一个有内容的 case 中都应放置一条 break 语句，遗漏break，可能导致程序误入下一个case分支，执行了预期之外的代码，导致异常。而且，不推荐做出有意不写break的设计。

**【正确示例】**

```
##### 场景1：break语句
- 修复示例：每一个有内容的 case 中都放置一条 break 语句

```javascript
const str = '-';
switch (str) {
  case '+':
    console.log('+');
    break;
  case '-':
    console.log('-'); // 加上break，计算结果与预期一致
    break;
  case '*':
    console.log('*');
    break;
  case '/':
    console.log('/');
    break;
  default:
    ...    		
}
// 打印 – 
```

```
**【错误示例】**

```
##### 场景1：break语句
- 错误示例：遗漏break，导致计算结果与预期不一致

```javascript
const str = '-';
switch (str) {
  case '+':
    console.log('+');
    break;
  case '-':
    console.log('-'); // 遗漏break，导致计算结果与预期不一致
  case '*':
    console.log('*');
    break;
  case '/':
    console.log('/');
    break;
  default:
    ...    		
}
// 打印 – 和 * 
```

```
**【修复建议】**

switch 语句的每一个有内容的 case 中都应放置一条 break 语句。
