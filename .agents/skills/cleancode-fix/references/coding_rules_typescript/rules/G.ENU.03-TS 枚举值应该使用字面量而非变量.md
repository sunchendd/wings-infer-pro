# G.ENU.03-TS 枚举值应该使用字面量而非变量

- **规则ID**：34f4e08e-8019-402d-82b1-8c4b693346fc
- **更新时间**：2026-04-07 04:35:02

---

**【问题级别】**

一般

**【描述】**

枚举值一般具有确定性，如果在枚举值定义时使用变量，在运行时的变量取值具有不确定性，可能会导致问题。

**【正确示例】**

```
##### 场景1：枚举值
- 修复示例：枚举值使用字面量

```typescript
// 使用字面量赋值枚举成员属性值
enum Person {
    NUM = '1',
    NAME = 'Jony' ,
    AGE = 14,
    DESC = 'Cute Boy!', 
    DEGREE = null, 
    FILTER = /some_regex/ 
}
```

```
**【错误示例】**

```
##### 场景1：枚举值
- 错误示例：枚举值使用变量

```typescript
import data from 'Persons';
// 除了NUM，其他会报错：不允许在具有字符串值成员的枚举中使用计算值
enum Person {
    NUM = '1',
    NAME = data.first + data.last ,
    AGE = data.age,
    DESC = `${data.desc}!`, 
    DEGREE = new Set(1, 2, 3), 
    FILTER = data.regex
}
```

```
**【修复建议】**

枚举值应该使用字面量而非变量。
